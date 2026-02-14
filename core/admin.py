# core/admin.py
from django.contrib import admin
from django.utils.html import format_html

#from core.models import Case, CaseMessage, AgentRun, AgentAction, CaseEvent, WhatsAppMessage
from core.models.case_models import Case, CaseMessage, AgentRun, AgentAction, CaseEvent
from core.models.whatsapp_message import WhatsAppMessage
from core.models.utility_models import (
    UtilityAccount,
    UtilityBill,
    UtilityPayment,
    UtilityMeterReading,
    UtilityTariff,
    UtilityOutage,
)
from core.models.ticket_models import ServiceTicket

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
# Utility Inlines (shown inside UtilityAccount)
# -----------------------

class UtilityBillInline(admin.TabularInline):
    model = UtilityBill
    extra = 0
    fields = ("bill_date", "amount", "kwh", "is_estimated", "created_at")
    readonly_fields = ("created_at",)
    ordering = ("-bill_date",)


class UtilityPaymentInline(admin.TabularInline):
    model = UtilityPayment
    extra = 0
    fields = ("payment_date", "amount", "created_at")
    readonly_fields = ("created_at",)
    ordering = ("-payment_date",)


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

    readonly_fields = ("case_id", "created_at", "updated_at", "utility_snapshot")

    fieldsets = (
        ("Case", {"fields": ("case_id", "case_type", "status", "priority", "channel", "subject")}),
        ("Customer", {"fields": ("customer_id", "account_id")}),
        ("Utility Snapshot", {"fields": ("utility_snapshot",)}),
        ("Assignment", {"fields": ("assigned_team", "assigned_user_id")}),
        ("Resolution", {"fields": ("resolution_code", "resolution_summary", "resolved_at")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    inlines = [CaseMessageInline, AgentRunInline, CaseEventInline]

    @admin.display(description="Subject")
    def subject_short(self, obj):
        s = (obj.subject or "").strip()
        return (s[:60] + "…") if len(s) > 60 else (s or "-")

    @admin.display(description="Utility data")
    def utility_snapshot(self, obj: Case):
        acct_id = (obj.account_id or "").strip()
        if not acct_id:
            return format_html("<i>No account_id on this case.</i>")

        acc = UtilityAccount.objects.filter(account_id=acct_id).first()
        if not acc:
            return format_html("<b>Account:</b> {} <br><i>No UtilityAccount row found.</i>", acct_id)

        bills = list(acc.bills.order_by("-bill_date")[:5])
        pays = list(acc.payments.order_by("-payment_date")[:5])

        readings = []
        if acc.meter_id:
            readings = list(
                UtilityMeterReading.objects.filter(meter_id=acc.meter_id).order_by("-reading_date")[:5]
            )

        tariff = None
        if acc.tariff_id:
            tariff = UtilityTariff.objects.filter(tariff_id=acc.tariff_id).first()

        outages = []
        if acc.address:
            outages = list(UtilityOutage.objects.filter(address=acc.address).order_by("-outage_date")[:5])

        html = []
        html.append(f"<b>Account:</b> {acc.account_id}")
        html.append(f"<br><b>Customer:</b> {acc.customer_id or '-'}")
        html.append(f"<br><b>Meter:</b> {acc.meter_id or '-'}")
        html.append(f"<br><b>Tariff:</b> {acc.tariff_id or '-'}")
        html.append(f"<br><b>Address:</b> {(acc.address or '-')}")
        if tariff:
            html.append(f"<br><b>Tariff Name:</b> {tariff.name} | <b>Rate:</b> {tariff.rate}")

        # Bills
        html.append("<hr><b>Recent Bills</b><br>")
        if bills:
            for b in bills:
                html.append(f"{b.bill_date} | amount={b.amount} | kwh={b.kwh} | estimated={b.is_estimated}<br>")
        else:
            html.append("<i>None</i><br>")

        # Payments
        html.append("<hr><b>Recent Payments</b><br>")
        if pays:
            for p in pays:
                html.append(f"{p.payment_date} | amount={p.amount}<br>")
        else:
            html.append("<i>None</i><br>")

        # Meter readings
        html.append("<hr><b>Recent Meter Readings</b><br>")
        if readings:
            for r in readings:
                html.append(f"{r.reading_date} | value={r.value}<br>")
        else:
            html.append("<i>None</i><br>")

        # Outages
        html.append("<hr><b>Recent Outages</b><br>")
        if outages:
            for o in outages:
                html.append(f"{o.outage_date} | status={o.status}<br>")
        else:
            html.append("<i>None</i><br>")

        return format_html("".join(html))


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


# -----------------------
# UtilityAccount
# -----------------------

@admin.register(UtilityAccount)
class UtilityAccountAdmin(admin.ModelAdmin):
    list_display = ("account_id", "customer_id", "meter_id", "tariff_id", "address_short", "created_at")
    list_filter = ("created_at",)
    search_fields = ("account_id", "customer_id", "meter_id", "tariff_id", "address")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Account", {"fields": ("account_id", "customer_id")}),
        ("Utility Info", {"fields": ("meter_id", "tariff_id", "address")}),
        ("Timestamps", {"fields": ("created_at",)}),
    )

    inlines = [UtilityBillInline, UtilityPaymentInline]

    @admin.display(description="Address")
    def address_short(self, obj):
        s = (obj.address or "").strip()
        return (s[:60] + "…") if len(s) > 60 else (s or "-")


# -----------------------
# UtilityBill
# -----------------------

@admin.register(UtilityBill)
class UtilityBillAdmin(admin.ModelAdmin):
    list_display = ("bill_id", "account", "bill_date", "amount", "kwh", "is_estimated", "created_at")
    list_filter = ("is_estimated", "bill_date", "created_at")
    search_fields = ("bill_id", "account__account_id")
    ordering = ("-bill_date", "-created_at")
    date_hierarchy = "bill_date"
    autocomplete_fields = ("account",)
    list_select_related = ("account",)
    readonly_fields = ("bill_id", "created_at")


# -----------------------
# UtilityPayment
# -----------------------

@admin.register(UtilityPayment)
class UtilityPaymentAdmin(admin.ModelAdmin):
    list_display = ("payment_id", "account", "payment_date", "amount", "created_at")
    list_filter = ("payment_date", "created_at")
    search_fields = ("payment_id", "account__account_id")
    ordering = ("-payment_date", "-created_at")
    date_hierarchy = "payment_date"
    autocomplete_fields = ("account",)
    list_select_related = ("account",)
    readonly_fields = ("payment_id", "created_at")


# -----------------------
# UtilityMeterReading
# -----------------------

@admin.register(UtilityMeterReading)
class UtilityMeterReadingAdmin(admin.ModelAdmin):
    list_display = ("reading_id", "meter_id", "reading_date", "value", "created_at")
    list_filter = ("reading_date", "created_at")
    search_fields = ("reading_id", "meter_id")
    ordering = ("-reading_date", "-created_at")
    date_hierarchy = "reading_date"
    readonly_fields = ("reading_id", "created_at")


# -----------------------
# UtilityTariff
# -----------------------

@admin.register(UtilityTariff)
class UtilityTariffAdmin(admin.ModelAdmin):
    list_display = ("tariff_id", "name", "rate", "created_at")
    list_filter = ("created_at",)
    search_fields = ("tariff_id", "name")
    ordering = ("name",)
    readonly_fields = ("created_at",)


# -----------------------
# UtilityOutage
# -----------------------

@admin.register(UtilityOutage)
class UtilityOutageAdmin(admin.ModelAdmin):
    list_display = ("outage_id", "address_short", "outage_date", "status", "created_at")
    list_filter = ("status", "outage_date", "created_at")
    search_fields = ("outage_id", "address", "details")
    ordering = ("-outage_date", "-created_at")
    date_hierarchy = "outage_date"
    readonly_fields = ("outage_id", "created_at")

    @admin.display(description="Address")
    def address_short(self, obj):
        s = (obj.address or "").strip()
        return (s[:60] + "…") if len(s) > 60 else (s or "-")

@admin.register(ServiceTicket)
class ServiceTicketAdmin(admin.ModelAdmin):
    list_display = ("ticket_id", "status", "priority", "category", "account_id", "case", "created_at")
    list_filter = ("status", "priority", "category", "created_at")
    search_fields = ("ticket_id", "account_id", "description", "case__case_id")
    ordering = ("-created_at",)
    autocomplete_fields = ("case",)
    readonly_fields = ("ticket_pk", "created_at")
