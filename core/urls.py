#core/urls.py
from django.urls import path
from core import views

urlpatterns = [
    # WhatsApp
    path("whatsapp/test/", views.whatsapp_test),
    path("whatsapp/inbound/", views.whatsapp_inbound),

    # Cases
    path("cases/", views.create_case),
    path("cases/<uuid:case_id>/messages/", views.add_message),
    path("cases/<uuid:case_id>/run/", views.run_case_agent),
    path("cases/<uuid:case_id>/", views.get_case),
    path("cases/<uuid:case_id>/messages/list/", views.get_case_messages),

    # Content
    path("content/generate/", views.generate_content),
]
