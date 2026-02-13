#core/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from core.models import Case, CaseMessage, AgentRun, AgentAction, CaseEvent, WhatsAppMessage


# -----------------------
# Inlines (shown inside Case)
# -----------------------

class CaseMessageInline(admin.TabularInline):
    model = CaseMessage
    extra = 0
    fields = ("created_at", "sender_type", "sender_id", "message_lang", "short_message")
    readonly_fields = ("created_at", "short_message")
    ordering = ("-created_at",)

    @admin.display(description="Message")
    def short_message(self, obj):
        txt = (obj.message_text or "").strip()
        return (txt[:120] + "…") if len(txt) > 120 else txt


class AgentRunInline(admin.TabularInline):
    model = AgentRun
    extra = 0
    fields = ("run_id", "run_status", "final_decision", "confidence", "started_at", "finished_at")
    readonly_fields = ("run_id", "started_at", "finished_at")
    ordering = ("-started_at",)


class CaseEventInline(admin.TabularInline):
    model = CaseEvent
    extra = 0
    fields = ("created_at", "event_type", "short_event_data")
    readonly_fields = ("created_at", "short_event_data")
    ordering = ("-created_at",)

    @admin.display(description="Event data")
    def short_event_data(self, obj):
        data = obj.event_data
        if not data:
            return "-"
        s = str(data)
        return (s[:120] + "…") if len(s) > 120 else s


# -----------------------
# Case
# -----------------------

@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = (
        "case_id",
        "case_type",
        "status",
        "priority",
        "channel",
        "subject_short",
        "customer_id",
        "account_id",
        "assigned_team",
        "assigned_user_id",
        "created_at",
        "updated_at",
        "resolved_at",
    )
    list_filter = ("case_type", "status", "priority", "channel", "created_at", "updated_at", "resolved_at")
    search_fields = (
        "case_id",
        "customer_id",
        "account_id",
        "subject",
        "resolution_code",
        "assigned_team",
        "assigned_user_id",
    )
    ordering = ("-updated_at", "-created_at")
    date_hierarchy = "created_at"
    list_per_page = 50

    readonly_fields = ("case_id", "created_at", "updated_at")

    fieldsets = (
        ("Case", {"fields": ("case_id", "case_type", "status", "priority", "channel", "subject")}),
        ("Customer", {"fields": ("customer_id", "account_id")}),
        ("Assignment", {"fields": ("assigned_team", "assigned_user_id")}),
        ("Resolution", {"fields": ("resolution_code", "resolution_summary", "resolved_at")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    inlines = [CaseMessageInline, AgentRunInline, CaseEventInline]

    @admin.display(description="Subject")
    def subject_short(self, obj):
        s = (obj.subject or "").strip()
        return (s[:60] + "…") if len(s) > 60 else (s or "-")


# -----------------------
# CaseMessage
# -----------------------

@admin.register(CaseMessage)
class CaseMessageAdmin(admin.ModelAdmin):
    list_display = ("message_id", "case", "sender_type", "sender_id", "message_lang", "short_message", "created_at")
    list_filter = ("sender_type", "message_lang", "created_at")
    search_fields = ("case__case_id", "sender_id", "message_text")
    ordering = ("-created_at",)
    autocomplete_fields = ("case",)
    list_select_related = ("case",)
    date_hierarchy = "created_at"

    readonly_fields = ("message_id", "created_at")

    @admin.display(description="Message")
    def short_message(self, obj):
        txt = (obj.message_text or "").strip()
        return (txt[:120] + "…") if len(txt) > 120 else txt


# -----------------------
# AgentRun
# -----------------------

@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = (
        "run_id",
        "case",
        "run_status",
        "final_decision",
        "confidence",
        "model_name",
        "duration",
        "started_at",
        "finished_at",
    )
    list_filter = ("run_status", "final_decision", "model_name", "started_at")
    search_fields = ("run_id", "case__case_id", "model_name", "agent_summary")
    ordering = ("-started_at",)
    autocomplete_fields = ("case",)
    list_select_related = ("case",)
    date_hierarchy = "started_at"

    readonly_fields = ("run_id", "started_at")

    @admin.display(description="Duration")
    def duration(self, obj):
        if obj.finished_at and obj.started_at:
            seconds = (obj.finished_at - obj.started_at).total_seconds()
            if seconds < 60:
                return f"{int(seconds)}s"
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        return "-"


# -----------------------
# AgentAction
# -----------------------

@admin.register(AgentAction)
class AgentActionAdmin(admin.ModelAdmin):
    list_display = (
        "action_id",
        "run",
        "action_type",
        "action_target",
        "success",
        "has_error",
        "created_at",
        "short_request",
        "short_response",
    )
    list_filter = ("action_type", "success", "created_at")
    search_fields = ("action_id", "run__run_id", "action_target", "error_message")
    ordering = ("-created_at",)
    autocomplete_fields = ("run",)
    list_select_related = ("run", "run__case")
    date_hierarchy = "created_at"

    readonly_fields = ("action_id", "created_at")

    @admin.display(description="Error?")
    def has_error(self, obj):
        return bool(obj.error_message)

    @admin.display(description="Req")
    def short_request(self, obj):
        if not obj.request_payload:
            return "-"
        s = str(obj.request_payload)
        return (s[:90] + "…") if len(s) > 90 else s

    @admin.display(description="Resp")
    def short_response(self, obj):
        if not obj.response_payload:
            return "-"
        s = str(obj.response_payload)
        return (s[:90] + "…") if len(s) > 90 else s


# -----------------------
# CaseEvent
# -----------------------

@admin.register(CaseEvent)
class CaseEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "case", "event_type", "created_at", "short_event_data")
    list_filter = ("event_type", "created_at")
    search_fields = ("event_id", "case__case_id", "event_type")
    ordering = ("-created_at",)
    autocomplete_fields = ("case",)
    list_select_related = ("case",)
    date_hierarchy = "created_at"

    readonly_fields = ("event_id", "created_at")

    @admin.display(description="Event data")
    def short_event_data(self, obj):
        if not obj.event_data:
            return "-"
        s = str(obj.event_data)
        return (s[:120] + "…") if len(s) > 120 else s


# -----------------------
# WhatsAppMessage
# -----------------------

@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ("message_id", "from_phone", "created_at", "payload_preview")
    list_filter = ("created_at",)
    search_fields = ("message_id", "from_phone")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    readonly_fields = ("message_id", "created_at")

    @admin.display(description="Payload")
    def payload_preview(self, obj):
        if not obj.payload:
            return "-"
        s = str(obj.payload)
        return (s[:160] + "…") if len(s) > 160 else s
