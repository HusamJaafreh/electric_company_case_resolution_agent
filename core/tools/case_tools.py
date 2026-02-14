# core/tools/case_tools.py
import logging
import uuid
from django.utils import timezone
from django.db import IntegrityError, transaction
from core.models.utility_models import (
    UtilityAccount,
    UtilityBill,
    UtilityPayment,
    UtilityMeterReading,
    UtilityTariff,
    UtilityOutage,
)
from core.models.ticket_models import ServiceTicket

logger = logging.getLogger(__name__)



def get_account_snapshot(account_id: str) -> dict:
    def run():
        row = (
            UtilityAccount.objects.filter(account_id=account_id)
            .values("account_id", "customer_id", "meter_id", "address", "tariff_id")
            .first()
        )
        return {"account": row}

    return _safe_query(run, {"account": None}, "account_snapshot")

def _safe_query(fn, default, label: str):
    try:
        return fn()
    except Exception as e:
        logger.warning("%s unavailable: %s", label, e)
        return default


def find_customer_by_phone(phone: str) -> dict:
    # Still stub for now (fine for demo)
    return {"customer": None}


def get_account_snapshot(account_id: str) -> dict:
    def run():
        row = (
            UtilityAccount.objects.filter(account_id=account_id)
            .values("account_id", "customer_id", "meter_id", "address", "tariff_id")
            .first()
        )
        return {"account": row}

    return _safe_query(run, {"account": None}, "account")


def get_billing_history(account_id: str, months: int = 6) -> dict:
    def run():
        rows = list(
            UtilityBill.objects.filter(account_id=account_id)  # FK column name works
            .order_by("-bill_date")[:24]
            .values("bill_id", "account_id", "bill_date", "amount", "kwh", "is_estimated")
        )
        return {"billing": rows}

    return _safe_query(run, {"billing": []}, "billing")


def get_payment_history(account_id: str, months: int = 6) -> dict:
    def run():
        rows = list(
            UtilityPayment.objects.filter(account_id=account_id)  # FK column name works
            .order_by("-payment_date")[:50]
            .values("payment_id", "account_id", "payment_date", "amount")
        )
        return {"payments": rows}

    return _safe_query(run, {"payments": []}, "payments")


def get_meter_readings(meter_id: str, n: int = 5) -> dict:
    def run():
        rows = list(
            UtilityMeterReading.objects.filter(meter_id=meter_id)
            .order_by("-reading_date")[:n]
            .values("reading_id", "meter_id", "reading_date", "value")
        )
        return {"readings": rows}

    return _safe_query(run, {"readings": []}, "meter_readings")


def get_tariff(tariff_id: str) -> dict:
    def run():
        row = (
            UtilityTariff.objects.filter(tariff_id=tariff_id)
            .values("tariff_id", "name", "rate")
            .first()
        )
        return {"tariff": row}

    return _safe_query(run, {"tariff": None}, "tariff")


def get_recent_outages(address: str, days: int = 30) -> dict:
    def run():
        rows = list(
            UtilityOutage.objects.filter(address=address)
            .order_by("-outage_date")[:20]
            .values("outage_id", "address", "outage_date", "status", "details")
        )
        return {"outages": rows}

    return _safe_query(run, {"outages": []}, "outages")


def _make_ticket_id(account_id: str) -> str:
    """
    Unique ticket id:
    - includes microseconds
    - includes a short random suffix
    """
    ts = timezone.now().strftime("%Y%m%d%H%M%S%f")  # microseconds
    safe = (account_id or "UNKNOWN").replace(" ", "_")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"TCK-{safe}-{ts}-{suffix}"


def create_service_ticket(
    account_id: str,
    category: str,
    description: str,
    priority: str = "HIGH",
    case_id: str | None = None,
) -> dict:
    """
    Persist ticket in DB. Retries if extremely unlucky collision occurs.
    """
    try:
        for _ in range(3):
            ticket_id = _make_ticket_id(account_id)
            try:
                with transaction.atomic():
                    ticket = ServiceTicket.objects.create(
                        ticket_id=ticket_id,
                        account_id=account_id or None,
                        category=category,
                        priority=priority,
                        description=description,
                        case_id=case_id if case_id else None,
                    )
                return {
                    "success": True,
                    "ticket_id": ticket.ticket_id,
                    "priority": ticket.priority,
                    "category": ticket.category,
                    "status": ticket.status,
                }
            except IntegrityError:
                # retry with a new id
                continue

        return {"success": False, "error": "Could not generate unique ticket_id after retries"}

    except Exception as e:
        logger.error("create_service_ticket failed: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}