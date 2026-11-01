# Utility Case-Resolution AI Agent

An AI customer-support agent for an electricity company. Customers write in over **WhatsApp** or **web chat**. The agent looks up their account, bills, payments, meter readings, tariffs and local outages, then decides the next step: **explain** the bill, **request more info**, **open a service ticket**, or **escalate** to a human. Every decision, tool call and message is logged for audit.

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/Django_REST-A30000?logo=django&logoColor=white)
![CrewAI](https://img.shields.io/badge/CrewAI-agents-FF5A50)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)

## How it works

```
 WhatsApp (Gupshup) ─┐
                     ├─► Case + CaseMessage ─► CaseResolutionFlow ─► CrewAI agent ──► tools
 Web chat widget  ───┘                                │                 │
                                                      │                 ├─ get_account_snapshot
                                                      │                 ├─ get_billing_history / get_payment_history
                                                      │                 ├─ get_meter_readings / get_tariff
                                                      │                 ├─ get_recent_outages
                                                      │                 └─ create_service_ticket
                                                      ▼
                         Strict JSON decision {decision, reply_text, actions, confidence, summary_for_human}
                                                      ▼
                         Reply to customer · AgentRun / AgentAction / CaseEvent audit trail · ServiceTicket
```

### Key design points

- **Structured, validated LLM output:** the agent must return a fixed JSON schema. Non-compliant output is normalised, never trusted blindly.
- **Tool-grounded answers:** the agent is instructed to support every explanation with account, billing and meter data fetched through tools. If a critical lookup fails, it asks for more information instead of guessing.
- **Safety-first escalation:** unusually large bills, distressed customers and regulatory matters are routed to a human.
- **Conversation memory:** account IDs are extracted from chat history (regex plus context), so customers aren't asked twice.
- **Bilingual:** detects Arabic vs. English messages.
- **Full audit trail:** `AgentRun`, `AgentAction` and `CaseEvent` models record every run, tool call and state change.

## API

Interactive Swagger docs are served at `/api/docs/`.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/cases/` | Open a new case |
| GET  | `/api/cases/{id}/` | Case details |
| POST | `/api/cases/{id}/messages/` | Add a customer message |
| GET  | `/api/cases/{id}/messages/list/` | Conversation history |
| POST | `/api/cases/{id}/run/` | Run the agent on a case |
| POST | `/api/whatsapp/inbound/` | Gupshup WhatsApp webhook |
| POST | `/api/webchat/start/`, `/api/webchat/send/` | Web chat widget |
| POST | `/api/content/generate/` | Content-generation flow |

## Getting started

Prerequisites: Python 3.10+, PostgreSQL, and an LLM API key (e.g. OpenAI).

```bash
python -m venv .venv
.venv\Scripts\activate                 # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env                 # cp on macOS/Linux, then fill in DB + API keys
python manage.py migrate
python manage.py seed_demo_data        # demo accounts, bills, meter readings, outages
python manage.py runserver
```

Then open <http://127.0.0.1:8000/> for the demo site, or <http://127.0.0.1:8000/api/docs/> for the API.

Run the agent over every seeded demo case:

```bash
python manage.py demo_run_all_cases --only-open
```

## Project structure

```
config/                         Django settings & URLs
core/
├── crews/case_resolution/      CrewAI agent, system prompt, tool bindings
├── flows/case_resolution/      orchestration: state, history, account extraction, persistence
├── flows/content_generation/   content-generation flow
├── models/                     Case, Message, AgentRun/Action, Ticket, Utility* data, WhatsApp
├── tools/                      data-access tools + Gupshup WhatsApp client
├── management/commands/        seed_demo_data, demo_run_all_cases
└── views.py, webchat_views.py  REST endpoints
templates/site/                 demo landing page with web chat
```

## License

[MIT](LICENSE)
