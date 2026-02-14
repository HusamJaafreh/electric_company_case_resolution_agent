# core/flows/case_resolution/flow.py
import logging
import re
from typing import Optional

from django.conf import settings
from django.utils import timezone

from core.models import Case, CaseMessage, AgentRun, AgentAction, CaseEvent
from core.flows.case_resolution.schema import CaseResolutionState
from core.crews.case_resolution.crew import run_case_resolution_ai

logger = logging.getLogger(__name__)


def _is_arabic(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06FF" for ch in (text or ""))


def _extract_account_id(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.strip()

    m = re.search(r"\bACC[\-_]?\s*([A-Z0-9]{3,})\b", t, flags=re.IGNORECASE)
    if m:
        return f"ACC_{m.group(1).upper()}"

    m = re.search(r"\b\d{6,}\b", t)
    if m:
        return m.group(0)

    return None


class CaseResolutionFlow:
    def __init__(self):
        self.state = CaseResolutionState()

    def kickoff_new_case(
        self,
        incoming_text: str,
        phone: Optional[str] = None,
        account_id: Optional[str] = None,
        channel: str = "WHATSAPP",
    ):
        self.state.incoming_text = incoming_text
        self.state.phone = phone
        self.state.account_id = account_id

        subject = (incoming_text or "")[:200]
        case = Case.objects.create(
            phone=phone or None,
            account_id=account_id or None,
            customer_id=None,
            case_type="OTHER",
            channel=channel,
            subject=subject,
            last_customer_message_at=timezone.now(),
        )

        CaseMessage.objects.create(
            case=case,
            sender_type="CUSTOMER",
            message_text=incoming_text,
            message_lang="AR" if _is_arabic(incoming_text) else "EN",
        )
        CaseEvent.objects.create(
            case=case,
            event_type="CASE_CREATED",
            event_data={"phone": phone, "text": incoming_text},
        )

        return self._process_case(case=case, incoming_text=incoming_text, phone=phone)

    def kickoff_existing_case(self, case: Case, incoming_text: str, phone: Optional[str] = None):
        self.state.incoming_text = incoming_text
        self.state.phone = phone
        self.state.account_id = case.account_id

        # If user sent account_id in the message, store it (important for seamless demo)
        extracted = _extract_account_id(incoming_text)
        if extracted and not case.account_id:
            case.account_id = extracted

        if phone and not case.phone:
            case.phone = phone

        case.last_customer_message_at = timezone.now()
        case.save(update_fields=["account_id", "phone", "last_customer_message_at", "updated_at"])

        return self._process_case(case=case, incoming_text=incoming_text, phone=phone)

    def _process_case(self, case: Case, incoming_text: str, phone: Optional[str]):
        self.state.case_id = str(case.case_id)

        # ---- Build CrewAI input ----
        recent_messages = list(
            case.messages.order_by("-created_at")
            .values("sender_type", "message_text", "created_at")[:10]
        )
        recent_messages.reverse()
        for m in recent_messages:
            if m.get("created_at"):
                m["created_at"] = m["created_at"].isoformat()
        payload = {
            "incoming_text": incoming_text,
            "phone": phone,
            "case": {
                "case_id": str(case.case_id),
                "status": case.status,
                "account_id": case.account_id,
                "customer_id": case.customer_id,
                "channel": case.channel,
                "case_type": case.case_type,
                "subject": case.subject,
            },
            "recent_messages": recent_messages,
            # Let CrewAI use tools; no rule-based evidence gathering here.
            "evidence": {},
        }

        # ---- Build conversation history from previous messages (excluding current incoming message) ----
        # Exclude the current incoming message and only pair customer-agent exchanges
        all_messages = list(
            case.messages.order_by("created_at")
            .values("sender_type", "message_text")
        )
        
        conversation_history = []
        i = 0
        while i < len(all_messages):
            msg = all_messages[i]
            if msg["sender_type"] == "CUSTOMER":
                user_msg = msg["message_text"]
                # Look for the next agent reply
                agent_reply = ""
                if i + 1 < len(all_messages) and all_messages[i + 1]["sender_type"] == "AGENT":
                    agent_reply = all_messages[i + 1]["message_text"]
                    i += 2  # Skip both customer and agent messages
                else:
                    i += 1
                
                if user_msg and agent_reply:  # Only add complete exchanges
                    conversation_history.append({
                        "user_message": user_msg,
                        "agent_reply": agent_reply
                    })
            else:
                i += 1

        # ---- Create AgentRun record BEFORE call (demo transparency) ----
        run = AgentRun.objects.create(
            case=case,
            model_name=getattr(settings, "AGENT_MODEL", "crewai-case-resolution"),
            run_status="STARTED",
        )

        try:
            result = run_case_resolution_ai(payload, conversation_history=conversation_history)

            decision = result.get("decision")
            reply = result.get("reply_text") or ""
            actions = result.get("actions") or []
            confidence = float(result.get("confidence") or 0.7)
            summary = result.get("summary_for_human") or f"Decision: {decision}"

            # Save raw agent output as an action for debugging
            AgentAction.objects.create(
                run=run,
                action_type="API_CALL",
                action_target="CREWAI_OUTPUT",
                request_payload={"input_payload": payload},
                response_payload=result,
                success=True,
            )

            # Save any declared actions (even if tools already executed them)
            for a in actions:
                AgentAction.objects.create(
                    run=run,
                    action_type=str(a.get("type") or "ACTION"),
                    action_target=str(a.get("target") or ""),
                    request_payload=a.get("request_payload") or {},
                    response_payload={},
                    success=True,
                )

            # Update case status based on decision
            if decision == "EXPLAIN":
                case.status = "RESOLVED"
                case.resolution_summary = reply
                case.resolved_at = timezone.now()
            elif decision == "REQUEST_MORE_INFO":
                case.status = "WAITING_CUSTOMER"
                case.resolution_summary = "Requested more info"
            elif decision == "CREATE_TICKET":
                case.status = "IN_REVIEW"
                case.resolution_summary = "Ticket created / inspection requested"
            elif decision == "ESCALATE":
                case.status = "ESCALATED"
                case.resolution_summary = "Escalated to specialist team"

            case.last_agent_message_at = timezone.now()
            case.save(update_fields=["status", "resolution_summary", "resolved_at", "last_agent_message_at", "updated_at"])

            # RTL wrap if Arabic
            if _is_arabic(reply):
                reply_to_send = f'<div dir="rtl" style="text-align:right; font-family: Arial, Tahoma;">{reply}</div>'
            else:
                reply_to_send = reply

            # Persist agent reply message
            CaseMessage.objects.create(
                case=case,
                sender_type="AGENT",
                message_text=reply_to_send,
                message_lang="AR" if _is_arabic(reply) else "EN",
            )

            # Finalize run
            run.final_decision = decision
            run.run_status = "SUCCESS"
            run.finished_at = timezone.now()
            run.agent_summary = summary
            run.confidence = confidence
            run.save(update_fields=["final_decision", "run_status", "finished_at", "agent_summary", "confidence"])

            # Event
            CaseEvent.objects.create(
                case=case,
                event_type="AGENT_RUN",
                event_data={"decision": decision, "confidence": confidence},
            )

            return {
                "decision": decision,
                "reply_text": reply_to_send,
                "actions": actions,
                "evidence": {},  # CrewAI tools may have fetched info internally
                "confidence": confidence,
                "summary_for_human": summary,
                "case_id": str(case.case_id),
            }

        except Exception as e:
            logger.error("CrewAI run failed: %s", e, exc_info=True)

            AgentAction.objects.create(
                run=run,
                action_type="API_CALL",
                action_target="CREWAI_ERROR",
                request_payload={"input_payload": payload},
                response_payload={"error": str(e)},
                success=False,
                error_message=str(e),
            )

            run.run_status = "FAILED"
            run.finished_at = timezone.now()
            run.agent_summary = f"Failed: {e}"
            run.confidence = 0.0
            run.save(update_fields=["run_status", "finished_at", "agent_summary", "confidence"])

            # Fail-safe reply for demo
            fallback = "Sorry—there was a system issue while processing your request. Please share your account number and we’ll investigate."
            CaseMessage.objects.create(
                case=case,
                sender_type="AGENT",
                message_text=fallback,
                message_lang="EN",
            )
            case.last_agent_message_at = timezone.now()
            case.save(update_fields=["last_agent_message_at", "updated_at"])

            return {
                "decision": "REQUEST_MORE_INFO",
                "reply_text": fallback,
                "actions": [{"type": "ERROR"}],
                "evidence": {},
                "confidence": 0.0,
                "summary_for_human": f"Error: {e}",
                "case_id": str(case.case_id),
            }
