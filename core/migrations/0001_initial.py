# Generated manually for the provided models
from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Case",
            fields=[
                ("case_id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("customer_id", models.CharField(max_length=128, null=True, blank=True)),
                ("account_id", models.CharField(max_length=128, null=True, blank=True)),
                ("case_type", models.CharField(max_length=32, default="OTHER")),
                ("priority", models.CharField(max_length=16, default="MEDIUM")),
                ("status", models.CharField(max_length=32, default="NEW")),
                ("channel", models.CharField(max_length=32, default="WHATSAPP")),
                ("subject", models.CharField(max_length=255, blank=True)),
                ("resolution_code", models.CharField(max_length=64, null=True, blank=True)),
                ("resolution_summary", models.TextField(null=True, blank=True)),
                ("assigned_team", models.CharField(max_length=128, null=True, blank=True)),
                ("assigned_user_id", models.CharField(max_length=128, null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("resolved_at", models.DateTimeField(null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="WhatsAppMessage",
            fields=[
                ("message_id", models.BigAutoField(primary_key=True, serialize=False)),
                ("from_phone", models.CharField(max_length=64)),
                ("payload", models.JSONField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="AgentRun",
            fields=[
                ("run_id", models.BigAutoField(primary_key=True, serialize=False)),
                ("model_name", models.CharField(max_length=255, null=True, blank=True)),
                ("run_status", models.CharField(max_length=32, default="STARTED")),
                ("final_decision", models.CharField(max_length=32, null=True, blank=True)),
                ("confidence", models.FloatField(null=True, blank=True)),
                ("agent_summary", models.TextField(null=True, blank=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(null=True, blank=True)),
                ("case", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="runs", to="core.case")),
            ],
        ),
        migrations.CreateModel(
            name="CaseMessage",
            fields=[
                ("message_id", models.BigAutoField(primary_key=True, serialize=False)),
                ("sender_type", models.CharField(max_length=16, default="CUSTOMER")),
                ("sender_id", models.CharField(max_length=128, null=True, blank=True)),
                ("message_text", models.TextField()),
                ("message_lang", models.CharField(max_length=8, default="EN")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("case", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="core.case")),
            ],
        ),
        migrations.CreateModel(
            name="AgentAction",
            fields=[
                ("action_id", models.BigAutoField(primary_key=True, serialize=False)),
                ("action_type", models.CharField(max_length=64)),
                ("action_target", models.CharField(max_length=255, null=True, blank=True)),
                ("request_payload", models.JSONField(null=True, blank=True)),
                ("response_payload", models.JSONField(null=True, blank=True)),
                ("success", models.BooleanField(default=True)),
                ("error_message", models.TextField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="actions", to="core.agentrun")),
            ],
        ),
        migrations.CreateModel(
            name="CaseEvent",
            fields=[
                ("event_id", models.BigAutoField(primary_key=True, serialize=False)),
                ("event_type", models.CharField(max_length=64)),
                ("event_data", models.JSONField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("case", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="core.case")),
            ],
        ),
    ]
