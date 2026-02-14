# core/crews/case_resolution/tools.py
from crewai.tools import tool
from core.tools import case_tools

@tool("Get account snapshot")
def get_account_snapshot(account_id: str) -> dict:
    """Fetch account snapshot (meter_id, address, tariff_id)."""
    return case_tools.get_account_snapshot(account_id)

@tool("Get billing history")
def get_billing_history(account_id: str, months: int = 6) -> dict:
    """Fetch billing history for an account."""
    return case_tools.get_billing_history(account_id, months=months)

@tool("Get payment history")
def get_payment_history(account_id: str, months: int = 6) -> dict:
    """Fetch payment history for an account."""
    return case_tools.get_payment_history(account_id, months=months)

@tool("Get meter readings")
def get_meter_readings(meter_id: str, n: int = 5) -> dict:
    """Fetch latest meter readings for a meter."""
    return case_tools.get_meter_readings(meter_id, n=n)

@tool("Get tariff")
def get_tariff(tariff_id: str) -> dict:
    """Fetch tariff info."""
    return case_tools.get_tariff(tariff_id)

@tool("Get recent outages")
def get_recent_outages(address: str, days: int = 30) -> dict:
    """Fetch recent outages by address."""
    return case_tools.get_recent_outages(address, days=days)

@tool("Create service ticket")
def create_service_ticket(account_id: str, category: str, description: str, priority: str = "HIGH") -> dict:
    """Create a service ticket."""
    return case_tools.create_service_ticket(account_id, category, description, priority=priority)
