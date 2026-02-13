#core/case_resolution/flow.py
import logging
from typing import Optional
from django.utils import timezone
from django.conf import settings

from core.models import Case, CaseMessage, AgentRun, AgentAction, CaseEvent
from core.tools import case_tools
from .schema import CaseResolutionState

logger = logging.getLogger(__name__)

def _is_arabic(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06FF" for ch in (text or ""))

class CaseResolutionFlow:
    def __init__(self):
        self.state = CaseResolutionState()

    def kickoff(self, incoming_text: str, phone: Optional[str] = None, account_id: Optional[str] = None, channel: str = "WHATSAPP"):
        self.state.incoming_text = incoming_text
        self.state.phone = phone
        self.state.account_id = account_id

        # 1) Create a case
        subject = (incoming_text or "")[:200]
        case = Case.objects.create(
            account_id=account_id or None,
            customer_id=None,
            case_type="OTHER",
            channel=channel,
            subject=subject,
        )
        self.state.case_id = str(case.case_id)

        # 2) Save customer message + event
        CaseMessage.objects.create(
            case=case,
            sender_type="CUSTOMER",
            message_text=incoming_text,
            message_lang="AR" if _is_arabic(incoming_text) else "EN",
        )
        CaseEvent.objects.create(case=case, event_type="CASE_CREATED", event_data={"phone": phone, "text": incoming_text})

        # 3) Attempt lookup by phone if account missing
        if not account_id and phone:
            c = case_tools.find_customer_by_phone(phone)
            if c.get("customer"):
                case.customer_id = str(c["customer"].get("customer_id") or c["customer"].get("id"))
                case.account_id = c["customer"].get("account_id") or None
                case.save()

        # 4) Gather evidence safely (won't crash if bills table missing)
        evidence = {}
        acct = case.account_id or account_id

        if acct:
            evidence["billing"] = case_tools.get_billing_history(acct, months=6)
            evidence["payments"] = case_tools.get_payment_history(acct, months=6)

            # best-effort account row
            try:
                acc_row = case_tools._fetchone(
                    f"SELECT meter_id, address, tariff_id FROM {case_tools._table('accounts')} WHERE account_id = %s LIMIT 1",
                    [acct],
                )
            except Exception as e:
                logger.warning("accounts lookup unavailable: %s", e)
                acc_row = None

            if acc_row:
                evidence["account"] = acc_row
                meter_id = acc_row.get("meter_id")
                if meter_id:
                    evidence["meter"] = case_tools.get_meter_readings(meter_id, n=5)
                tariff_id = acc_row.get("tariff_id")
                if tariff_id:
                    evidence["tariff"] = case_tools.get_tariff(tariff_id)
                address = acc_row.get("address")
                if address:
                    evidence["outages"] = case_tools.get_recent_outages(address, days=30)
        else:
            evidence["note"] = "No account_id available; attempted phone lookup"

        self.state.evidence = evidence

        # 5) Decision rules
        decision = "REQUEST_MORE_INFO"
        billing_rows = (evidence.get("billing") or {}).get("billing", [])

        # Estimated bill => ask for info
        if any(b.get("is_estimated") for b in billing_rows):
            decision = "REQUEST_MORE_INFO"

        # Consumption spike => explain
        if len(billing_rows) >= 2:
            try:
                recent = float(billing_rows[0].get("kwh") or 0)
                prevs = [float(b.get("kwh") or 0) for b in billing_rows[1:4]]
                avg_prev = sum(prevs) / (len(prevs) or 1)
                if recent > avg_prev * 2.0 and recent > 50:
                    decision = "EXPLAIN"
            except Exception:
                pass

        # Meter rollback => ticket
        meter_rows = (evidence.get("meter") or {}).get("readings", [])
        if len(meter_rows) >= 2:
            try:
                latest = float(meter_rows[0].get("value") or 0)
                prev = float(meter_rows[1].get("value") or 0)
                if latest < prev:
                    decision = "CREATE_TICKET"
            except Exception:
                pass

        # Very high bill => escalate
        if billing_rows:
            try:
                if float(billing_rows[0].get("amount") or 0) > 2000:
                    decision = "ESCALATE"
            except Exception:
                pass

        self.state.decision = decision

        # 6) Agent run record
        run = AgentRun.objects.create(case=case, model_name=getattr(settings, "AGENT_MODEL", "case-resolution-v1"))

        actions = []
        reply = None

        if decision == "CREATE_TICKET":
            ticket = case_tools.create_service_ticket(acct or "unknown", "inspection", incoming_text, priority="HIGH")
            AgentAction.objects.create(
                run=run,
                action_type="CREATE_TICKET",
                action_target=str(acct),
                request_payload={"reason": incoming_text},
                response_payload=ticket,
                success=bool(ticket.get("success", False)),
            )
            CaseEvent.objects.create(case=case, event_type="TICKET_CREATED", event_data=ticket)
            case.status = "IN_REVIEW"
            case.resolution_summary = "Inspection ticket created"
            case.save()
            actions.append({"type": "CREATE_TICKET", "ticket": ticket})
            reply = "We created an inspection ticket and our team will follow up shortly."

        elif decision == "EXPLAIN":
            try:
                recent_kwh = billing_rows[0].get("kwh")
                prev_kwh = billing_rows[1].get("kwh") if len(billing_rows) > 1 else None
                reply = f"We reviewed your bill. Your consumption changed from {prev_kwh} kWh to {recent_kwh} kWh. This explains the amount change."
            except Exception:
                reply = "We reviewed your account and found increased consumption compared to previous periods."

            AgentAction.objects.create(run=run, action_type="API_CALL", action_target="explain", response_payload={"reply": reply}, success=True)
            case.status = "RESOLVED"
            case.resolution_summary = reply
            case.save()
            actions.append({"type": "EXPLAIN"})

        elif decision == "REQUEST_MORE_INFO":
            reply = "Please provide your account number and a photo of the meter reading so we can investigate further."
            AgentAction.objects.create(run=run, action_type="API_CALL", action_target="request_info", response_payload={"reply": reply}, success=True)
            case.status = "WAITING_CUSTOMER"
            case.resolution_summary = "Requested more info from customer"
            case.save()
            actions.append({"type": "REQUEST_MORE_INFO"})

        elif decision == "ESCALATE":
            reply = "Your case has been escalated to the specialist team. A human will contact you shortly."
            AgentAction.objects.create(run=run, action_type="API_CALL", action_target="escalate", response_payload={"reply": reply}, success=True)
            case.status = "ESCALATED"
            case.resolution_summary = "Escalated to specialist"
            case.save()
            actions.append({"type": "ESCALATE"})

        if not reply:
            reply = "Thank you. We created a case and will follow up shortly."

        if _is_arabic(reply):
            reply = f'<div dir="rtl" style="text-align:right; font-family: Arial, Tahoma;">{reply}</div>'

        self.state.reply_text = reply

        # persist agent reply
        CaseMessage.objects.create(
            case=case,
            sender_type="AGENT",
            message_text=reply,
            message_lang="AR" if _is_arabic(reply) else "EN",
        )

        # finalize run
        run.final_decision = decision
        run.run_status = "SUCCESS"
        run.finished_at = timezone.now()
        run.agent_summary = f"Decision: {decision}"
        run.confidence = 0.8
        run.save()

        CaseEvent.objects.create(case=case, event_type="AGENT_RUN", event_data={"decision": decision, "evidence_keys": list(evidence.keys())})

        return {
            "decision": decision,
            "reply_text": reply,
            "actions": actions,
            "evidence": evidence,
            "confidence": run.confidence,
            "summary_for_human": run.agent_summary,
            "case_id": str(case.case_id),
        }
