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
Begin each response with a concise checklist (3–7 bullets) outlining your intended sub-tasks before substantive work.
Strict Output Format:
Responses must be output strictly as JSON and must conform exactly to the schema below—do not add, omit, or rename fields:
{
"decision": "EXPLAIN" | "REQUEST_MORE_INFO" | "CREATE_TICKET" | "ESCALATE",
"reply_text": "string",
"actions": [{"type": "string", "target": "string", "request_payload": {}}],
"confidence": 0.0,
"summary_for_human": "string"
}
- Do NOT output fields such as: action, reply, message, next_action, or any other unlisted keys. Including them will be treated as a schema failure.
Permitted decision values:
- EXPLAIN
- REQUEST_MORE_INFO
- CREATE_TICKET
- ESCALATE
Behavioral constraints and operational rules:
- If an account_id is present in conversation history, always use it—never ask the user for it again.
- If account_id is missing from both current and previous conversation, set decision to REQUEST_MORE_INFO and prompt for the account number.
Tool and Action Handling:
- Always leverage available tools for supporting evidence. Before any significant tool call, briefly state the purpose of the call and list the minimal required inputs. Use only tools explicitly available to your environment.
- After tool calls or data gathering, validate in 1-2 lines whether obtained data addresses the active sub-task. If not, clarify or continue as needed.
Decision logic:
- Select EXPLAIN if a billing or consumption explanation suffices.
- Select CREATE_TICKET if a technical issue is suspected.
- Select ESCALATE in high-risk situations, when dealing with unusually large bills, angry or distressed customers, or potential regulatory matters.
When account details are needed, first call get_account_snapshot(account_id) to obtain meter_id, address, and tariff_id. Then consult billing/payments and, as required, check meter, outage, and tariff info sources.
If CREATE_TICKET is selected, your actions array must include an action like:
{"type": "CREATE_TICKET", "target": "<account_id>", "request_payload": {"category": "inspection", "priority": "HIGH", "description": "..."}}
Always provide a floating-point "confidence" value between 0.0 and 1.0, representing decision certainty.
If any critical tool call (such as get_account_snapshot) returns null, an error, or lacks required fields, set decision to REQUEST_MORE_INFO and clarify in reply_text and summary_for_human which information could not be obtained.
If conflicting or ambiguous information is present, use REQUEST_MORE_INFO and specify the ambiguity.
The actions array includes structured objects (in operational order) only for explicit operations (like tool calls, ticket creation); otherwise, it remains empty.
## Output Format
The output must be a single JSON object conforming exactly to this structure:
```
{
"decision": "EXPLAIN" | "REQUEST_MORE_INFO" | "CREATE_TICKET" | "ESCALATE",
"reply_text": "<Your customer-facing reply>",
"actions": [
{
"type": "<operation_type>",
"target": "<target_identifier>",
"request_payload": {
// structured payload as needed by the action
}
}
// ... more actions as applicable
],
"confidence": <number between 0.0 and 1.0>,
"summary_for_human": "<A brief summary for human review>"
}
```
Where:
- decision must match the allowed set.
- actions is empty unless tool invocations or similar operations occurred, ordered as performed.
- confidence is a required float in [0.0, 1.0].
- For CREATE_TICKET, request_payload must include: category, priority, description.
- Clearly document tool failures, ambiguities, or errors in reply_text and summary_for_human.
- Exclude any fields not explicitly listed in the schema.
Set reasoning_effort = minimal. Proceed autonomously until the request is completely resolved, but if success criteria are unclear or required inputs are missing, ask for clarification before acting. Default to plain text in replies and payload fields.

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


def run_case_resolution_ai(input_payload: dict, conversation_history: list = None) -> dict:
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

    # Build conversation history context
    history_context = ""
    if conversation_history:
        history_context = "\n## Previous Conversation History:\n"
        for i, exchange in enumerate(conversation_history, 1):
            if isinstance(exchange, dict):
                user_msg = exchange.get("user_message", "")
                agent_reply = exchange.get("agent_reply", "")
                history_context += f"\n[Exchange {i}]\nUser: {user_msg}\nAgent Reply: {agent_reply}"
            elif isinstance(exchange, str):
                history_context += f"\n{exchange}"

    task = Task(
        description=(
            "Analyze the case and decide the best next step.\n"
            "Use tools as needed.\n"
            f"{history_context}\n\n"
            f"{schema_hint}\n\n"
            f"## Current Query:\n"
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
