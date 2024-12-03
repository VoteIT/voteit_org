from __future__ import annotations


from django.core.management import BaseCommand
from django.db import transaction

from voteit.organisation.models import Organisation
from voteit_org.models import MembershipType


class Command(BaseCommand):
    help = "Create memberships"

    def add_arguments(self, parser):
        parser.add_argument("year", help="Year, as YYYY")
        parser.add_argument(
            "--mem",
            help="Membership type, specified as primary key or title",
            required=True,
        )
        parser.add_argument(
            "--commit", help="Save result", default=False, action="store_true"
        )

    def handle(self, *args, **options):
        year = options["year"]
        int(year)  # Just to make sure
        assert len(year) == 4
        try:
            membership = MembershipType.objects.get(pk=int(options["mem"]))
        except ValueError:
            membership = MembershipType.objects.filter(
                title__iexact=options["mem"]
            ).first()
        if not membership:
            exit("Membership not found")
        self.stdout.write(f"Skapar medlemskap '{membership}' för året {year}")
        orgs_qs = Organisation.objects.filter(active=True)
        if exclude_count := orgs_qs.filter(memberships__year=year).count():
            self.stdout.write(f"Skippar {exclude_count} som redan var skapade")
        orgs_qs = orgs_qs.exclude(memberships__year=year)
        if create_count := orgs_qs.count():
            with transaction.atomic(durable=True):
                self.stdout.write(
                    self.style.SUCCESS(f"{create_count} kommer skapas...")
                )
                for org in orgs_qs:
                    org.memberships.create(year=year, membership_type=membership)
                if options.get("commit"):
                    self.stdout.write(self.style.SUCCESS("All done, saving"))
                else:
                    self.stdout.write(
                        self.style.WARNING("DRY-RUN: Specify --commit to save")
                    )
                    transaction.set_rollback(True)
        else:
            self.stdout.write(
                self.style.WARNING(f"Inga organisationer behövde uppdateras för året")
            )
