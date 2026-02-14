from django.db import models
from django.utils import timezone

from core.models.case_models import Case


class ServiceTicket(models.Model):
    STATUS = [
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("CLOSED", "Closed"),
    ]

    ticket_pk = models.BigAutoField(primary_key=True)
    ticket_id = models.CharField(max_length=128, unique=True, db_index=True)

    case = models.ForeignKey(Case, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets")
    account_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)

    category = models.CharField(max_length=64)
    priority = models.CharField(max_length=16, default="HIGH")
    description = models.TextField()

    status = models.CharField(max_length=32, choices=STATUS, default="OPEN")

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    def __str__(self):
        return f"{self.ticket_id} ({self.status})"
