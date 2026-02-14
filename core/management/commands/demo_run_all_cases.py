# core/management/commands/demo_run_all_cases.py
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.flows.case_resolution.flow import CaseResolutionFlow
from core.models import Case, AgentRun


class Command(BaseCommand):
    help = "Run CaseResolutionFlow for existing cases to populate AgentRuns/Actions/Agent messages for demo."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Max number of cases to run (0 = no limit).")
        parser.add_argument("--force", action="store_true", help="Run even if a case already has a SUCCESS AgentRun.")
        parser.add_argument(
            "--only-open",
            action="store_true",
            help="Only run for open-ish statuses: NEW/IN_REVIEW/WAITING_CUSTOMER/ESCALATED.",
        )
        parser.add_argument(
            "--show-messages",
            action="store_true",
            help="Print customer/agent messages before and after running the agent.",
        )
        parser.add_argument(
            "--last-n",
            type=int,
            default=6,
            help="How many most recent messages to show per case when --show-messages is used.",
        )

    def handle(self, *args, **opts):
        # Disable CrewAI prompts/telemetry for demo
        os.environ["CREWAI_DISABLE_TELEMETRY"] = "1"
        os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "1"

        limit = opts["limit"]
        force = opts["force"]
        only_open = opts["only_open"]
        show_messages = opts["show_messages"]
        last_n = opts["last_n"]

        qs = Case.objects.all().order_by("-updated_at")
        if only_open:
            qs = qs.filter(status__in=["NEW", "IN_REVIEW", "WAITING_CUSTOMER", "ESCALATED"])
        if limit and limit > 0:
            qs = qs[:limit]

        total = qs.count() if hasattr(qs, "count") else len(qs)
        self.stdout.write(self.style.WARNING(f"Running demo agent on {total} case(s)..."))

        ok = 0
        skipped = 0
        failed = 0

        for case in qs:
            try:
                if not force and AgentRun.objects.filter(case=case, run_status="SUCCESS").exists():
                    skipped += 1
                    continue

                latest = case.messages.filter(sender_type="CUSTOMER").order_by("-created_at").first()
                if not latest:
                    skipped += 1
                    continue

                if show_messages:
                    self.stdout.write("\n" + "=" * 110)
                    self.stdout.write(
                        f"CASE {case.case_id} | channel={case.channel} | status={case.status} | account={case.account_id or '-'}"
                    )
                    self.stdout.write("-" * 110)
                    msgs = list(case.messages.order_by("-created_at")[:last_n])
                    msgs.reverse()
                    for m in msgs:
                        ts = m.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        who = m.sender_type
                        txt = (m.message_text or "").replace("\n", " ")
                        if len(txt) > 220:
                            txt = txt[:220] + "…"
                        self.stdout.write(f"[{ts}] {who}: {txt}")
                    self.stdout.write("-" * 110)

                phone = case.phone if case.channel == "WHATSAPP" else None

                with transaction.atomic():
                    flow = CaseResolutionFlow()
                    res = flow.kickoff_existing_case(case=case, incoming_text=latest.message_text, phone=phone)

                    case.updated_at = timezone.now()
                    case.save(update_fields=["updated_at"])

                ok += 1
                self.stdout.write(self.style.SUCCESS(f"✅ {case.case_id} -> {res.get('decision')}"))

                if show_messages:
                    # Show the new agent reply (last message)
                    last_msg = case.messages.order_by("-created_at").first()
                    if last_msg:
                        ts = last_msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        txt = (last_msg.message_text or "").replace("\n", " ")
                        if len(txt) > 220:
                            txt = txt[:220] + "…"
                        self.stdout.write(f"[{ts}] {last_msg.sender_type}: {txt}")
                    self.stdout.write("=" * 110)

            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f"❌ {case.case_id} failed: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Done. ok={ok} skipped={skipped} failed={failed}"))
        self.stdout.write("Tip: use --force to re-run and generate more AgentRuns for the same cases.")
