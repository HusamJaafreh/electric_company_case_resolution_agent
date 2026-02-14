#core/models/whatsapp_message.py
from django.db import models

class WhatsAppMessage(models.Model):
    message_id = models.BigAutoField(primary_key=True)
    provider_message_id = models.CharField(max_length=128, null=True, blank=True, unique=True)
    from_phone = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
