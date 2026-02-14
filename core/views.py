# core/views.py
import json
import logging
from threading import Lock

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from core.tools.whatsapp_gupshup import send_whatsapp_messages
from core.flows.case_resolution.flow import CaseResolutionFlow
from core.flows.content_generation.flow import ContentGenerationFlow

from core.models.case_models import Case, CaseMessage
from core.models.whatsapp_message import WhatsAppMessage


from core.serializers import (
    CreateCaseRequestSerializer,
    CreateCaseResponseSerializer,
    AddMessageRequestSerializer,
    AddMessageResponseSerializer,
    RunCaseAgentResponseSerializer,
    GenerateContentRequestSerializer,
    GenerateContentResponseSerializer,
    GetCaseResponseSerializer,
    GetCaseMessagesResponseSerializer,
)

from datetime import timedelta

logger = logging.getLogger(__name__)

processing_phones: set = set()
processing_lock = Lock()


@csrf_exempt
@require_POST
def whatsapp_test(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponse(
            json.dumps({"status": "error", "message": "invalid_json"}),
            content_type="application/json",
            status=400,
        )

    from_wa = payload.get("phone", "")
    test_message = payload.get("message", "Test message from WhatsApp")

    if not from_wa:
        return HttpResponse(
            json.dumps({"status": "error", "message": "phone required"}),
            content_type="application/json",
            status=400,
        )

    try:
        send_whatsapp_messages(from_wa, [{"text": f"✅ Test Reply:\n\n{test_message}", "image": None}])
        return HttpResponse(json.dumps({"status": "ok", "message": "Test sent"}), content_type="application/json")
    except Exception as e:
        logger.error("Test send failed: %s", e, exc_info=True)
        return HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            content_type="application/json",
            status=500,
        )


@csrf_exempt
@require_POST
def whatsapp_inbound(request):
    logger.warning("Webhook received! Raw body: %s", request.body[:500])

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error("Failed to parse webhook: %s", e)
        return HttpResponse(json.dumps({"status": "error"}), content_type="application/json", status=400)

    if payload.get("type") != "message":
        return HttpResponse(json.dumps({"status": "ok"}), content_type="application/json")

    message_payload = payload.get("payload", {})
    sender_info = message_payload.get("sender", {})
    from_wa = (sender_info.get("phone") or "").strip()

    nested_payload = message_payload.get("payload", {})
    body = (nested_payload.get("text") or "").strip()

    # ✅ Best-effort provider message id (for dedup)
    provider_message_id = (
        message_payload.get("id")
        or nested_payload.get("id")
        or payload.get("id")
        or nested_payload.get("messageId")
        or message_payload.get("messageId")
    )
    provider_message_id = str(provider_message_id).strip() if provider_message_id else None

    logger.warning("Inbound WhatsApp: from=%s msg_id=%s body=%r", from_wa, provider_message_id, body)

    if not from_wa or not body:
        return HttpResponse(json.dumps({"status": "ok", "message": "ignored_empty"}), content_type="application/json")

    # ✅ Dedup: if already stored, ignore
    try:
        if provider_message_id:
            obj, created = WhatsAppMessage.objects.get_or_create(
                provider_message_id=provider_message_id,
                defaults={"from_phone": from_wa, "payload": payload},
            )
            if not created:
                return HttpResponse(json.dumps({"status": "ok", "message": "duplicate_ignored"}), content_type="application/json")
        else:
            WhatsAppMessage.objects.create(from_phone=from_wa, payload=payload)
    except Exception as e:
        logger.warning("Failed to persist WhatsAppMessage: %s", e)

    try:
        with processing_lock:
            if from_wa in processing_phones:
                return HttpResponse(json.dumps({"status": "ok", "message": "already_processing"}), content_type="application/json")
            processing_phones.add(from_wa)

        try:
            cutoff = timezone.now() - timedelta(hours=24)

            # ✅ NEW: stable open case lookup using Case.phone + timestamps (fast, indexed)
            open_case = (
                Case.objects
                .filter(channel="WHATSAPP")
                .filter(phone=from_wa)
                .filter(status__in=["NEW", "WAITING_CUSTOMER", "IN_REVIEW", "ESCALATED"])
                .filter(updated_at__gte=cutoff)
                .order_by("-updated_at")
                .first()
            )

            flow = CaseResolutionFlow()

            if open_case:
                # Attach message to existing case
                CaseMessage.objects.create(
                    case=open_case,
                    sender_type="CUSTOMER",
                    message_text=body,
                    message_lang="AR" if any("\u0600" <= ch <= "\u06FF" for ch in (body or "")) else "EN",
                )
                open_case.last_customer_message_at = timezone.now()
                open_case.save(update_fields=["last_customer_message_at", "updated_at"])

                results = flow.kickoff_existing_case(case=open_case, incoming_text=body, phone=from_wa)
            else:
                results = flow.kickoff_new_case(
                    incoming_text=body,
                    phone=from_wa,
                    account_id=None,
                    channel="WHATSAPP",
                )

        finally:
            with processing_lock:
                processing_phones.discard(from_wa)

        if results and results.get("reply_text"):
            send_whatsapp_messages(from_wa, [{"text": results["reply_text"], "image": None}])

        return HttpResponse(json.dumps({"status": "ok", "case": results.get("case_id")}), content_type="application/json")

    except Exception as e:
        logger.error("Error processing webhook: %s", e, exc_info=True)
        return HttpResponse(json.dumps({"status": "error", "message": str(e)}), content_type="application/json", status=500)




@extend_schema(
    operation_id="create_case",
    tags=["Cases"],
    summary="Create a new support case",
    request=CreateCaseRequestSerializer,
    responses={201: CreateCaseResponseSerializer},
    examples=[
        OpenApiExample(
            "Basic request",
            value={"phone": "962790477161", "account_id": "ACC_001", "message": "My bill is high", "channel": "WEB"},
            request_only=True,
        )
    ],
)
@api_view(["POST"])
def create_case(request):
    ser = CreateCaseRequestSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"success": False, "error": ser.errors}, status=status.HTTP_400_BAD_REQUEST)

    phone = (ser.validated_data.get("phone") or "").strip() or None
    account_id = ser.validated_data.get("account_id") or None
    message = ser.validated_data["message"]
    channel = ser.validated_data.get("channel", "WEB")

    case = Case.objects.create(
        phone=phone,
        account_id=account_id,
        channel=channel,
        subject=message[:255],
        last_customer_message_at=timezone.now(),
    )

    CaseMessage.objects.create(
        case=case,
        sender_type="CUSTOMER",
        message_text=message,
        message_lang="AR" if any("\u0600" <= ch <= "\u06FF" for ch in (message or "")) else "EN",
    )

    return Response({"success": True, "case_id": str(case.case_id)}, status=status.HTTP_201_CREATED)

@extend_schema(
    operation_id="add_case_message",
    tags=["Cases"],
    summary="Add a message to a case",
    request=AddMessageRequestSerializer,
    parameters=[OpenApiParameter(name="case_id", location=OpenApiParameter.PATH, required=True, type=OpenApiTypes.UUID)],
    responses={201: AddMessageResponseSerializer},
)
@api_view(["POST"])
def add_message(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)

    ser = AddMessageRequestSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"success": False, "error": ser.errors}, status=status.HTTP_400_BAD_REQUEST)

    message = ser.validated_data["message"]
    sender_type = ser.validated_data.get("sender_type", "CUSTOMER")

    msg = CaseMessage.objects.create(
        case=case,
        sender_type=sender_type,
        message_text=message,
        message_lang="AR" if any("\u0600" <= ch <= "\u06FF" for ch in (message or "")) else "EN",
    )

    return Response({"success": True, "message_id": msg.message_id}, status=status.HTTP_201_CREATED)


@extend_schema(
    operation_id="run_case_agent",
    tags=["Cases"],
    summary="Execute case resolution AI agent",
    request=None,
    responses={200: RunCaseAgentResponseSerializer},
)
@api_view(["POST"])
def run_case_agent(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)
    latest = case.messages.filter(sender_type="CUSTOMER").order_by("-created_at").first()
    if not latest:
        return Response({"success": False, "error": "no customer messages"}, status=status.HTTP_400_BAD_REQUEST)

    flow = CaseResolutionFlow()

    # ✅ Run agent on the existing case (no new case created)
    res = flow.kickoff_existing_case(case=case, incoming_text=latest.message_text, phone=None)

    return Response({"success": True, "result": res}, status=status.HTTP_200_OK)


@extend_schema(
    operation_id="get_case",
    tags=["Cases"],
    summary="Get case details",
    responses={200: GetCaseResponseSerializer},
)
@api_view(["GET"])
def get_case(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)
    msgs = list(
        case.messages.order_by("created_at").values("message_id", "sender_type", "message_text", "created_at")
    )
    runs = list(
        case.runs.order_by("-started_at").values("run_id", "final_decision", "run_status", "started_at", "finished_at")
    )
    return Response(
        {"case": {"case_id": str(case.case_id), "status": case.status, "subject": case.subject}, "messages": msgs, "runs": runs}
    )


@extend_schema(
    operation_id="get_case_messages",
    tags=["Cases"],
    summary="Get all messages for a case",
    responses={200: GetCaseMessagesResponseSerializer},
)
@api_view(["GET"])
def get_case_messages(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)
    msgs = list(
        case.messages.order_by("created_at").values("message_id", "sender_type", "message_text", "created_at")
    )
    return Response({"messages": msgs})


@extend_schema(
    operation_id="generate_content",
    tags=["Content"],
    summary="Generate content",
    request=GenerateContentRequestSerializer,
    responses={200: GenerateContentResponseSerializer},
)
@api_view(["POST"])
def generate_content(request):
    ser = GenerateContentRequestSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"success": False, "error": ser.errors}, status=status.HTTP_400_BAD_REQUEST)

    flow = ContentGenerationFlow()
    result = flow.kickoff(user_query=ser.validated_data["user_query"])

    return Response(
        {"success": True, "data": result, "message": "Content generated successfully"},
        status=status.HTTP_200_OK,
    )
