# core/crews/case_resolution/crew.py
import json
import re
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from crewai import Agent, Task, Crew
from django.conf import settings

from .tools import (
    get_account_snapshot,
    get_billing_history,
    get_payment_history,
    get_meter_readings,
    get_tariff,
    get_recent_outages,
    create_service_ticket,
)

SYSTEM_RULES = """
You are a utility customer support case-resolution AI.

CRITICAL OUTPUT RULE:
- Output MUST be STRICT JSON ONLY.
- Output MUST match THIS schema EXACTLY (same keys):
{
  "decision": "EXPLAIN|REQUEST_MORE_INFO|CREATE_TICKET|ESCALATE",
  "reply_text": "string",
  "actions": [{"type": "string", "target": "string", "request_payload": {}}],
  "confidence": 0.0,
  "summary_for_human": "string"
}

You MUST NOT output keys like: action, reply, message, next_action, etc.
If you do, it will be considered a failure.

Allowed decisions:
- EXPLAIN
- REQUEST_MORE_INFO
- CREATE_TICKET
- ESCALATE

Rules:
- If account_id is missing and you can't proceed, choose REQUEST_MORE_INFO and ask for account number.
- Use tools to gather evidence.
- If billing/consumption explanation is enough, choose EXPLAIN.
- If technical issue suspected, choose CREATE_TICKET.
- If high-risk / very high amount / angry customer / regulatory risk, choose ESCALATE.

Tool guidance:
1) First call get_account_snapshot(account_id) to get meter_id/address/tariff_id when needed.
2) Then call billing/payments and optionally meter/outages/tariff.

If you choose CREATE_TICKET, include an action like:
{"type":"CREATE_TICKET","target":"<account_id>","request_payload":{"category":"inspection","priority":"HIGH","description":"..."}}
"""

_ALLOWED = {"EXPLAIN", "REQUEST_MORE_INFO", "CREATE_TICKET", "ESCALATE"}


def _json_default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, UUID):
        return str(o)
    return str(o)


def _safe_json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=_json_default)


def _extract_json(text: str) -> dict:
    if isinstance(text, dict):
        return text
    s = str(text).strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not m:
        raise ValueError(f"Agent did not return JSON. Raw: {s[:400]}")
    return json.loads(m.group(0))


def _normalize_result(raw: dict) -> dict:
    """
    Fix common non-compliant outputs into the required schema.
    """
    if not isinstance(raw, dict):
        return {}

    # If correct schema already
    if "decision" in raw and "reply_text" in raw:
        return raw

    # Common wrong shapes:
    # {"action":"REPLY","reply":"..."}
    # {"next_action":"REPLY","message":"..."}
    reply = raw.get("reply") or raw.get("message") or raw.get("reply_text") or ""
    decision = raw.get("decision")

    # If decision missing, infer from wording minimally (demo-safe)
    if not decision:
        low = (reply or "").lower()
        if "escalat" in low or "specialist" in low:
            decision = "ESCALATE"
        elif "ticket" in low or "inspection" in low:
            decision = "CREATE_TICKET"
        elif "account" in low and ("provide" in low or "send" in low):
            decision = "REQUEST_MORE_INFO"
        else:
            # default safe
            decision = "REQUEST_MORE_INFO"

    # Build normalized schema
    return {
        "decision": str(decision).upper().strip(),
        "reply_text": str(reply).strip() or "Thanks. Please provide your account number so we can investigate.",
        "actions": raw.get("actions") or [],
        "confidence": float(raw.get("confidence") or 0.7),
        "summary_for_human": raw.get("summary_for_human") or "Normalized non-compliant agent output",
    }


def build_case_resolution_agent():
    model_name = getattr(settings, "AGENT_MODEL", None)

    return Agent(
        role="Case Resolution Agent",
        goal="Resolve utility support cases by deciding the best next step and drafting a helpful reply.",
        backstory="You handle billing disputes, outages, meter issues, and payment issues.",
        allow_delegation=False,
        verbose=False,
        llm=model_name,
        tools=[
            get_account_snapshot,
            get_billing_history,
            get_payment_history,
            get_meter_readings,
            get_tariff,
            get_recent_outages,
            create_service_ticket,
        ],
        system_template=SYSTEM_RULES,
    )


def run_case_resolution_ai(input_payload: dict) -> dict:
    agent = build_case_resolution_agent()

    schema_hint = (
        'Return ONLY this JSON schema:\n'
        '{'
        '"decision":"EXPLAIN|REQUEST_MORE_INFO|CREATE_TICKET|ESCALATE",'
        '"reply_text":"...",'
        '"actions":[{"type":"...","target":"...","request_payload":{}}],'
        '"confidence":0.0,'
        '"summary_for_human":"..."'
        '}'
    )

    task = Task(
        description=(
            "Analyze the case and decide the best next step.\n"
            "Use tools as needed.\n\n"
            f"{schema_hint}\n\n"
            f"INPUT_JSON:\n{_safe_json_dumps(input_payload)}\n"
        ),
        expected_output=schema_hint,
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task], verbose=False)
    raw = crew.kickoff()
    if hasattr(raw, "raw"):
        raw = raw.raw

    parsed = _extract_json(raw)
    result = _normalize_result(parsed)

    decision = (result.get("decision") or "").upper().strip()
    if decision not in _ALLOWED:
        # last-resort fallback (never crash the demo)
        decision = "REQUEST_MORE_INFO"
        result["decision"] = decision
        if not result.get("reply_text"):
            result["reply_text"] = "Please provide your account number so we can investigate your case properly."
        result["summary_for_human"] = f"Fallback: invalid decision from agent. Raw={parsed}"

    # Ensure required keys exist
    result["actions"] = result.get("actions") or []
    result["confidence"] = float(result.get("confidence") or 0.7)
    result["summary_for_human"] = result.get("summary_for_human") or f"Decision: {decision}"
    result["reply_text"] = result.get("reply_text") or "Thanks. We are reviewing your case and will follow up shortly."
    return result
