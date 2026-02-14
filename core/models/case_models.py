import uuid
from django.db import models
from django.utils import timezone


class Case(models.Model):
    CASE_TYPES = [
        ("BILL_DISPUTE", "Bill Dispute"),
        ("OUTAGE_REPORT", "Outage Report"),
        ("METER_READING_ISSUE", "Meter Reading Issue"),
        ("PAYMENT_ISSUE", "Payment Issue"),
        ("TARIFF_QUESTION", "Tariff Question"),
        ("OTHER", "Other"),
    ]

    STATUS = [
        ("NEW", "New"),
        ("IN_REVIEW", "In Review"),
        ("WAITING_CUSTOMER", "Waiting Customer"),
        ("ESCALATED", "Escalated"),
        ("RESOLVED", "Resolved"),
        ("CLOSED", "Closed"),
    ]

    PRIORITY = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("CRITICAL", "Critical"),
    ]

    case_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # demo-critical
    phone = models.CharField(max_length=32, null=True, blank=True, db_index=True)

    customer_id = models.CharField(max_length=128, null=True, blank=True)
    account_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)

    case_type = models.CharField(max_length=32, choices=CASE_TYPES, default="OTHER")
    priority = models.CharField(max_length=16, choices=PRIORITY, default="MEDIUM")
    status = models.CharField(max_length=32, choices=STATUS, default="NEW")
    channel = models.CharField(max_length=32, default="WHATSAPP")
    subject = models.CharField(max_length=255, blank=True)

    resolution_code = models.CharField(max_length=64, null=True, blank=True)
    resolution_summary = models.TextField(null=True, blank=True)

    assigned_team = models.CharField(max_length=128, null=True, blank=True)
    assigned_user_id = models.CharField(max_length=128, null=True, blank=True)

    last_customer_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_agent_message_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def mark_resolved(self, summary: str = ""):
        self.status = "RESOLVED"
        if summary:
            self.resolution_summary = summary
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolution_summary", "resolved_at", "updated_at"])

    def __str__(self):
        return f"Case {self.case_id} ({self.case_type})"


class CaseMessage(models.Model):
    SENDER = [
        ("CUSTOMER", "Customer"),
        ("AGENT", "Agent"),
        ("HUMAN", "Human"),
    ]

    LANG = [("AR", "Arabic"), ("EN", "English"), ("MIX", "Mixed")]

    message_id = models.BigAutoField(primary_key=True)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="messages")
    sender_type = models.CharField(max_length=16, choices=SENDER, default="CUSTOMER")
    sender_id = models.CharField(max_length=128, null=True, blank=True)
    message_text = models.TextField()
    message_lang = models.CharField(max_length=8, choices=LANG, default="EN")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class AgentRun(models.Model):
    RUN_STATUS = [("STARTED", "Started"), ("SUCCESS", "Success"), ("FAILED", "Failed")]
    DECISIONS = [
        ("EXPLAIN", "Explain"),
        ("REQUEST_MORE_INFO", "Request More Info"),
        ("CREATE_TICKET", "Create Ticket"),
        ("ESCALATE", "Escalate"),
    ]

    run_id = models.BigAutoField(primary_key=True)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="runs")
    model_name = models.CharField(max_length=255, null=True, blank=True)
    run_status = models.CharField(max_length=32, choices=RUN_STATUS, default="STARTED")
    final_decision = models.CharField(max_length=32, choices=DECISIONS, null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    agent_summary = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)


class AgentAction(models.Model):
    ACTION_TYPES = [
        ("DB_QUERY", "DB Query"),
        ("API_CALL", "API Call"),
        ("CREATE_TICKET", "Create Ticket"),
        ("SEND_SMS", "Send SMS"),
        ("GENERATE_DOC", "Generate Doc"),
    ]

    action_id = models.BigAutoField(primary_key=True)
    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name="actions")
    action_type = models.CharField(max_length=64, choices=ACTION_TYPES)
    action_target = models.CharField(max_length=255, null=True, blank=True)
    request_payload = models.JSONField(null=True, blank=True)
    response_payload = models.JSONField(null=True, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class CaseEvent(models.Model):
    EVENT_TYPES = [
        ("CASE_CREATED", "Case Created"),
        ("AGENT_RUN", "Agent Run"),
        ("TICKET_CREATED", "Ticket Created"),
        ("ESCALATED", "Escalated"),
        ("RESOLVED", "Resolved"),
    ]

    event_id = models.BigAutoField(primary_key=True)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=64, choices=EVENT_TYPES)
    event_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
