# core/urls.py
from django.urls import path
from core import views

urlpatterns = [

    # =========================
    # WhatsApp
    # =========================
    path(
        "whatsapp/test/",
        views.whatsapp_test,
        name="whatsapp-test",
    ),
    path(
        "whatsapp/inbound/",
        views.whatsapp_inbound,
        name="whatsapp-inbound",
    ),

    # =========================
    # Cases
    # =========================
    path(
        "cases/",
        views.create_case,
        name="create-case",
    ),
    path(
        "cases/<uuid:case_id>/",
        views.get_case,
        name="get-case",
    ),
    path(
        "cases/<uuid:case_id>/messages/",
        views.add_message,
        name="add-case-message",
    ),
    path(
        "cases/<uuid:case_id>/messages/list/",
        views.get_case_messages,
        name="get-case-messages",
    ),
    path(
        "cases/<uuid:case_id>/run/",
        views.run_case_agent,
        name="run-case-agent",
    ),

    # =========================
    # Content
    # =========================
    path(
        "content/generate/",
        views.generate_content,
        name="generate-content",
    ),
]
