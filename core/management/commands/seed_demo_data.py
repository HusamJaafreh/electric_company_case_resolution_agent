# core/management/commands/seed_demo_data.py
import random
from datetime import timedelta, date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (
    Case,
    CaseMessage,
    AgentRun,
    AgentAction,
    CaseEvent,
    WhatsAppMessage,
    ServiceTicket,
)
from core.models.utility_models import (
    UtilityAccount,
    UtilityBill,
    UtilityPayment,
    UtilityMeterReading,
    UtilityTariff,
    UtilityOutage,
)


def _arabic_or_english(i: int) -> str:
    # Mix languages for realism
    if i % 3 == 0:
        return "AR"
    return "EN"


def _maybe_arabic_text(kind: str, i: int) -> str:
    if _arabic_or_english(i) == "AR":
        if kind == "high_bill":
            return "فاتورتي عالية جدًا، ممكن تساعدوني؟"
        if kind == "meter_issue":
            return "قراءة العداد فيها مشكلة وأظن أنها رجعت للخلف."
        if kind == "outage":
            return "في انقطاع كهرباء بالمنطقة من أمس."
        if kind == "payment":
            return "دفعت الفاتورة لكن النظام ما حدث."
        return "ممكن توضيح السبب؟"
    else:
        if kind == "high_bill":
            return "My bill is very high this month, please help."
        if kind == "meter_issue":
            return "I think the meter reading went backwards / is incorrect."
        if kind == "outage":
            return "There is a power outage in my area since yesterday."
        if kind == "payment":
            return "I paid but it still shows unpaid."
        return "Can you explain this charge?"


def _mk_phone(i: int) -> str:
    # Jordan-style demo numbers (not real)
    return f"96279{random.randint(1000000, 9999999)}"


def _mk_account(i: int) -> str:
    return f"ACC_{10000 + i}"


def _dt_days_ago(days: int):
    return timezone.now() - timedelta(days=days)


def _date_days_ago(days: int) -> date:
    return (timezone.now() - timedelta(days=days)).date()


class Command(BaseCommand):
    help = "Clears and repopulates DB with demo data for the case resolution system."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic data.")
        parser.add_argument(
            "--accounts",
            type=int,
            default=8,
            help="How many utility accounts to create (default 8).",
        )
        parser.add_argument(
            "--cases",
            type=int,
            default=14,
            help="How many cases to create (default 14).",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        seed = opts["seed"]
        n_accounts = opts["accounts"]
        n_cases = opts["cases"]
        random.seed(seed)

        self.stdout.write(self.style.WARNING("⚠️ This will DELETE existing demo-related data in core tables."))

        # -------------------------
        # 1) CLEAR (delete in FK-safe order)
        # -------------------------
        AgentAction.objects.all().delete()
        AgentRun.objects.all().delete()
        CaseMessage.objects.all().delete()
        CaseEvent.objects.all().delete()
        ServiceTicket.objects.all().delete()
        Case.objects.all().delete()

        WhatsAppMessage.objects.all().delete()

        UtilityBill.objects.all().delete()
        UtilityPayment.objects.all().delete()
        UtilityMeterReading.objects.all().delete()
        UtilityOutage.objects.all().delete()
        UtilityAccount.objects.all().delete()
        UtilityTariff.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("✅ Cleared core demo tables."))

        # -------------------------
        # 2) CREATE UTILITY MASTER DATA (tariffs)
        # -------------------------
        tariffs = []
        for t in range(3):
            tariff = UtilityTariff.objects.create(
                tariff_id=f"TAR_{t+1}",
                name=f"Residential Tier {t+1}",
                rate=round(0.10 + (t * 0.05), 6),
            )
            tariffs.append(tariff)

        # -------------------------
        # 3) CREATE ACCOUNTS + BILLS + PAYMENTS + READINGS + OUTAGES
        # -------------------------
        accounts = []
        for i in range(n_accounts):
            acc_id = _mk_account(i + 1)
            phone = _mk_phone(i + 1)

            acc = UtilityAccount.objects.create(
                account_id=acc_id,
                customer_id=f"CUST_{2000 + i}",
                meter_id=f"MTR_{3000 + i}",
                address=f"Amman - District {i+1} - Street {10+i}",
                tariff_id=random.choice(tariffs).tariff_id,
            )
            accounts.append((acc, phone))

            # Bills (last 6 periods, spaced 30 days)
            base_kwh = random.randint(80, 200)
            for m in range(6):
                bill_date = _date_days_ago(30 * (m + 1))
                kwh = base_kwh + random.randint(-20, 30)
                amount = round(float(kwh) * float(random.choice(tariffs).rate) * 10, 2)

                UtilityBill.objects.create(
                    account=acc,
                    bill_date=bill_date,
                    kwh=kwh,
                    amount=amount,
                    is_estimated=False,
                )

            # Payments (some accounts have partial / missing payments)
            for p in range(random.randint(2, 5)):
                UtilityPayment.objects.create(
                    account=acc,
                    payment_date=_date_days_ago(random.randint(5, 150)),
                    amount=round(random.uniform(20, 120), 2),
                )

            # Meter readings (5 recent)
            current = random.randint(1000, 5000)
            for r in range(5):
                UtilityMeterReading.objects.create(
                    meter_id=acc.meter_id,
                    reading_date=_date_days_ago(r * 7),
                    value=current - (r * random.randint(10, 30)),
                )

            # Outages (some addresses have outages)
            if i % 3 == 0:
                for o in range(random.randint(1, 3)):
                    UtilityOutage.objects.create(
                        address=acc.address,
                        outage_date=_dt_days_ago(random.randint(1, 20)),
                        status=random.choice(["REPORTED", "RESOLVED"]),
                        details="Transformer maintenance / network issue (demo).",
                    )

        # -------------------------
        # 4) FORCE SPECIAL SCENARIOS TO TRIGGER ALL DECISIONS
        # -------------------------

        # A) EXPLAIN scenario: consumption spike (recent bill > 2x avg prev)
        spike_acc, spike_phone = accounts[0]
        bills = list(spike_acc.bills.order_by("-bill_date")[:4])
        if len(bills) >= 4:
            # Make the most recent bill huge
            b0 = bills[0]
            b0.kwh = 450
            b0.amount = 4500  # also "high", but we want EXPLAIN (so keep <2000 if using your rule)
            # If your rule escalates >2000 amount, keep it below:
            b0.amount = 1500
            b0.is_estimated = False
            b0.save(update_fields=["kwh", "amount", "is_estimated"])

        # B) REQUEST_MORE_INFO scenario: estimated bill
        est_acc, est_phone = accounts[1]
        b = est_acc.bills.order_by("-bill_date").first()
        if b:
            b.is_estimated = True
            b.amount = 300
            b.save(update_fields=["is_estimated", "amount"])

        # C) CREATE_TICKET scenario: meter rollback (latest reading < previous)
        rollback_acc, rollback_phone = accounts[2]
        readings = list(UtilityMeterReading.objects.filter(meter_id=rollback_acc.meter_id).order_by("-reading_date")[:2])
        if len(readings) == 2:
            latest, prev = readings[0], readings[1]
            # Force rollback
            latest.value = max(0, prev.value - 50)
            latest.save(update_fields=["value"])

        # D) ESCALATE scenario: bill amount > 2000
        esc_acc, esc_phone = accounts[3]
        eb = esc_acc.bills.order_by("-bill_date").first()
        if eb:
            eb.amount = 2500
            eb.kwh = 600
            eb.is_estimated = False
            eb.save(update_fields=["amount", "kwh", "is_estimated"])

        # -------------------------
        # 5) CREATE CASES + THREADS (WEB + WHATSAPP)
        # -------------------------
        def create_case_thread(
            *,
            channel: str,
            phone: str | None,
            account_id: str | None,
            initial_text: str,
            status: str = "NEW",
            add_followup: bool = True,
        ) -> Case:
            case = Case.objects.create(
                phone=phone,
                account_id=account_id,
                channel=channel,
                case_type="OTHER",
                status=status,
                subject=(initial_text or "")[:200],
                last_customer_message_at=timezone.now(),
            )

            CaseMessage.objects.create(
                case=case,
                sender_type="CUSTOMER",
                message_text=initial_text,
                message_lang="AR" if any("\u0600" <= ch <= "\u06FF" for ch in (initial_text or "")) else "EN",
            )

            CaseEvent.objects.create(case=case, event_type="CASE_CREATED", event_data={"phone": phone, "text": initial_text})

            if add_followup:
                follow = "Thanks. Please check and update me." if "?" not in initial_text else "Any updates?"
                CaseMessage.objects.create(
                    case=case,
                    sender_type="CUSTOMER",
                    message_text=follow,
                    message_lang="EN",
                )
                case.last_customer_message_at = timezone.now()
                case.save(update_fields=["last_customer_message_at", "updated_at"])

            return case

        # Create targeted cases matching decision triggers
        demo_cases = []

        # EXPLAIN (spike)
        demo_cases.append(
            create_case_thread(
                channel="WHATSAPP",
                phone=spike_phone,
                account_id=spike_acc.account_id,
                initial_text=_maybe_arabic_text("high_bill", 1),
                status="IN_REVIEW",
            )
        )

        # REQUEST_MORE_INFO (estimated bill)
        demo_cases.append(
            create_case_thread(
                channel="WHATSAPP",
                phone=est_phone,
                account_id=est_acc.account_id,
                initial_text="Why is my bill estimated? I want the exact reading.",
                status="IN_REVIEW",
            )
        )

        # CREATE_TICKET (rollback)
        demo_cases.append(
            create_case_thread(
                channel="WHATSAPP",
                phone=rollback_phone,
                account_id=rollback_acc.account_id,
                initial_text=_maybe_arabic_text("meter_issue", 3),
                status="IN_REVIEW",
            )
        )

        # ESCALATE (very high amount)
        demo_cases.append(
            create_case_thread(
                channel="WEB",
                phone=None,
                account_id=esc_acc.account_id,
                initial_text="My bill is extremely high (over 2500). This is unacceptable.",
                status="IN_REVIEW",
            )
        )

        # Missing account => REQUEST_MORE_INFO
        demo_cases.append(
            create_case_thread(
                channel="WHATSAPP",
                phone=_mk_phone(999),
                account_id=None,
                initial_text="My bill is high but I don't have the account number.",
                status="NEW",
                add_followup=False,
            )
        )

        # Outage report case
        out_acc, out_phone = accounts[0]
        demo_cases.append(
            create_case_thread(
                channel="WHATSAPP",
                phone=out_phone,
                account_id=out_acc.account_id,
                initial_text=_maybe_arabic_text("outage", 6),
                status="IN_REVIEW",
            )
        )

        # Payment issue case
        pay_acc, pay_phone = accounts[4] if len(accounts) > 4 else accounts[-1]
        demo_cases.append(
            create_case_thread(
                channel="WEB",
                phone=None,
                account_id=pay_acc.account_id,
                initial_text=_maybe_arabic_text("payment", 7),
                status="IN_REVIEW",
            )
        )

        # More random cases to fill dashboard (variety)
        kinds = ["high_bill", "meter_issue", "outage", "payment", "other"]
        for i in range(max(0, n_cases - len(demo_cases))):
            acc, ph = random.choice(accounts)
            kind = random.choice(kinds)
            channel = random.choice(["WEB", "WHATSAPP"])
            text = _maybe_arabic_text(kind, i + 10)

            # Some cases have no account id (to test request info)
            acc_id = acc.account_id if random.random() > 0.2 else None
            phone = ph if channel == "WHATSAPP" else None

            st = random.choice(["NEW", "IN_REVIEW", "WAITING_CUSTOMER", "ESCALATED"])
            c = create_case_thread(channel=channel, phone=phone, account_id=acc_id, initial_text=text, status=st, add_followup=True)
            demo_cases.append(c)

        # -------------------------
        # 6) Create a couple of demo tickets linked to cases (so admin looks real)
        # -------------------------
        for idx, c in enumerate(demo_cases[:3]):
            ServiceTicket.objects.create(
                ticket_id=f"TCK-DEMO-{idx+1}",
                case=c,
                account_id=c.account_id,
                category="inspection",
                priority="HIGH",
                description="Demo ticket created during seeding.",
                status=random.choice(["OPEN", "IN_PROGRESS"]),
            )

        self.stdout.write(self.style.SUCCESS(f"✅ Seeded: {len(tariffs)} tariffs, {n_accounts} accounts, {len(demo_cases)} cases, tickets + utility data."))
        self.stdout.write(self.style.SUCCESS("Run WhatsApp demo: send a message from one of the seeded WHATSAPP phones (shown in DB) or just start a new phone thread."))
