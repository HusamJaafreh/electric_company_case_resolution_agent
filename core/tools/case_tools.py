#core/tools/case_tools.py
import logging
from django.db import connection
from django.conf import settings

logger = logging.getLogger(__name__)

def _table(key: str) -> str:
    # key in {"bills","payments","accounts","meter_readings","tariffs","outages"}
    return settings.TABLE_MAPPINGS.get(key, key)

def _fetchall(sql: str, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        cols = [c[0] for c in cur.description] if cur.description else []
        return [dict(zip(cols, row)) for row in cur.fetchall()]

def _fetchone(sql: str, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description] if cur.description else []
        return dict(zip(cols, row))

def _safe_query(fn, default, label: str):
    try:
        return fn()
    except Exception as e:
        # IMPORTANT: do not crash the agent if utility tables are missing
        logger.warning("%s unavailable: %s", label, e)
        return default

def find_customer_by_phone(phone: str) -> dict:
    # Stub: replace with real lookup
    return {"customer": None}

def get_billing_history(account_id: str, months: int = 6) -> dict:
    def run():
        sql = f"""
        SELECT *
        FROM {_table('bills')}
        WHERE account_id = %s
        ORDER BY bill_date DESC
        LIMIT 24
        """
        rows = _fetchall(sql, [account_id])
        return {"billing": rows}

    return _safe_query(run, {"billing": []}, "billing")

def get_payment_history(account_id: str, months: int = 6) -> dict:
    def run():
        sql = f"""
        SELECT *
        FROM {_table('payments')}
        WHERE account_id = %s
        ORDER BY payment_date DESC
        LIMIT 50
        """
        rows = _fetchall(sql, [account_id])
        return {"payments": rows}

    return _safe_query(run, {"payments": []}, "payments")

def get_meter_readings(meter_id: str, n: int = 5) -> dict:
    def run():
        sql = f"""
        SELECT *
        FROM {_table('meter_readings')}
        WHERE meter_id = %s
        ORDER BY reading_date DESC
        LIMIT %s
        """
        rows = _fetchall(sql, [meter_id, n])
        return {"readings": rows}

    return _safe_query(run, {"readings": []}, "meter_readings")

def get_tariff(tariff_id: str) -> dict:
    def run():
        sql = f"SELECT * FROM {_table('tariffs')} WHERE tariff_id = %s LIMIT 1"
        row = _fetchone(sql, [tariff_id])
        return {"tariff": row}

    return _safe_query(run, {"tariff": None}, "tariff")

def get_recent_outages(address: str, days: int = 30) -> dict:
    def run():
        sql = f"""
        SELECT *
        FROM {_table('outages')}
        WHERE address = %s
        ORDER BY outage_date DESC
        LIMIT 20
        """
        rows = _fetchall(sql, [address])
        return {"outages": rows}

    return _safe_query(run, {"outages": []}, "outages")

def create_service_ticket(account_id: str, category: str, description: str, priority: str = "HIGH") -> dict:
    # Stub: replace with real ticketing integration
    return {"success": True, "ticket_id": f"TCK-{account_id}-001", "priority": priority, "category": category}
