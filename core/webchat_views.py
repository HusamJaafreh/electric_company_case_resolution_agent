# core/webchat_views.py

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from core.flows.case_resolution.flow import CaseResolutionFlow
from core.models.case_models import Case, CaseMessage


def _lang(text: str) -> str:
    return "AR" if any("\u0600" <= ch <= "\u06FF" for ch in (text or "")) else "EN"


# ✅ Important:
# - csrf_exempt disables Django CSRF middleware
# - authentication_classes([]) disables DRF SessionAuthentication CSRF enforcement
# - AllowAny lets public users call it
@csrf_exempt
@api_view(["POST"])
@authentication_classes([])          # ✅ disable SessionAuthentication (which forces CSRF)
@permission_classes([AllowAny])      # ✅ public endpoint
def webchat_start(request):
    message = (request.data.get("message") or "").strip()
    phone = (request.data.get("phone") or "").strip() or None
    account_id = (request.data.get("account_id") or "").strip() or None

    if not message:
        return Response({"success": False, "error": "message required"}, status=status.HTTP_400_BAD_REQUEST)

    case = Case.objects.create(
        phone=phone,
        account_id=account_id,
        channel="WEB",
        subject=message[:255],
        last_customer_message_at=timezone.now(),
    )

    CaseMessage.objects.create(
        case=case,
        sender_type="CUSTOMER",
        message_text=message,
        message_lang=_lang(message),
    )

    flow = CaseResolutionFlow()
    res = flow.kickoff_existing_case(case=case, incoming_text=message, phone=phone)

    reply_text = (res or {}).get("reply_text") or ""

    if reply_text:
        CaseMessage.objects.create(
            case=case,
            sender_type="AGENT",
            message_text=reply_text,
            message_lang=_lang(reply_text),
        )

    return Response(
        {"success": True, "case_id": str(case.case_id), "reply_text": reply_text},
        status=status.HTTP_200_OK,
    )


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])          # ✅ disable SessionAuthentication (which forces CSRF)
@permission_classes([AllowAny])      # ✅ public endpoint
def webchat_send(request):
    case_id = (request.data.get("case_id") or "").strip()
    message = (request.data.get("message") or "").strip()

    if not case_id or not message:
        return Response(
            {"success": False, "error": "case_id and message required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    case = get_object_or_404(Case, case_id=case_id)

    CaseMessage.objects.create(
        case=case,
        sender_type="CUSTOMER",
        message_text=message,
        message_lang=_lang(message),
    )

    case.last_customer_message_at = timezone.now()
    case.save(update_fields=["last_customer_message_at", "updated_at"])

    flow = CaseResolutionFlow()
    res = flow.kickoff_existing_case(case=case, incoming_text=message, phone=case.phone)

    reply_text = (res or {}).get("reply_text") or ""

    if reply_text:
        CaseMessage.objects.create(
            case=case,
            sender_type="AGENT",
            message_text=reply_text,
            message_lang=_lang(reply_text),
        )

    return Response(
        {"success": True, "reply_text": reply_text, "result": res},
        status=status.HTTP_200_OK,
    )
