#core/models/whatsapp_message.py
from django.db import models

class WhatsAppMessage(models.Model):
    message_id = models.BigAutoField(primary_key=True)
    from_phone = models.CharField(max_length=64)
    payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
