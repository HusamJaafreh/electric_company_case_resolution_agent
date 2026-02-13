#core/tools/whatsapp_gupshup.py
from __future__ import annotations
import json
import logging
from typing import List

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

def get_gupshup_headers():
    api_key = settings.GUPSHUP_API_KEY
    if not api_key:
        raise ValueError("GUPSHUP_API_KEY must be set in .env")
    return {
        "apikey": api_key,
        "Content-Type": "application/x-www-form-urlencoded",
        "Cache-Control": "no-cache",
    }

def send_whatsapp_messages(to: str, messages: List[dict]) -> List[str]:
    from_number = settings.GUPSHUP_PHONE_NUMBER
    if not from_number:
        raise ValueError("GUPSHUP_PHONE_NUMBER must be set in .env")

    if to.startswith("whatsapp:"):
        to = to.replace("whatsapp:", "")

    message_ids = []
    headers = get_gupshup_headers()
    url = "https://api.gupshup.io/wa/api/v1/msg"
    app_name = getattr(settings, "GUPSHUP_APP_NAME", "nexsusWhatsapp")

    for msg in messages:
        body = msg.get("text") or ""
        media = msg.get("image")

        if media:
            if isinstance(media, dict):
                img_url = media.get("url") or media.get("originalUrl") or media.get("previewUrl")
                filename = media.get("filename") or (img_url.split("/")[-1] if img_url else "image.jpg")
                caption = media.get("caption") or body
            else:
                img_url = str(media)
                filename = img_url.split("/")[-1] if img_url else "image.jpg"
                caption = body

            msg_obj = {
                "type": "image",
                "caption": caption,
                "previewUrl": img_url,
                "originalUrl": img_url,
                "filename": filename,
                "url": img_url,
            }
        else:
            msg_obj = {"type": "text", "text": body}

        data = {
            "channel": "whatsapp",
            "source": from_number,
            "destination": to,
            "message": json.dumps(msg_obj),
            "src.name": app_name,
        }

        resp = requests.post(url, data=data, headers=headers, timeout=15)
        if resp.status_code not in (200, 201, 202):
            logger.error("Gupshup send failed: %s %s", resp.status_code, resp.text)
            resp.raise_for_status()

        out = resp.json()
        msg_id = out.get("messageId") or out.get("id") or "unknown"
        message_ids.append(msg_id)
        logger.info("Gupshup WhatsApp sent: messageId=%s to=%s", msg_id, to)

    return message_ids
