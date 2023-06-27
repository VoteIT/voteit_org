from __future__ import annotations

from datetime import date
from functools import reduce

from django.core.management import BaseCommand
from django.db import models
from django.utils import timezone
from envelope.models import Connection

from voteit.organisation.models import Organisation


class Command(BaseCommand):
    help = "Generate organisation statistics"

    def add_arguments(self, parser):
        # parser.add_argument("-o", help="Output file")
        parser.add_argument("-y", help="Year", default=int(timezone.now().date().year))
        parser.add_argument(
            "--pmin",
            help="Filtrera bort möten med färre deltagare än det här",
            default=20,
            type=int,
        )
        parser.add_argument(
            "--plarge",
            help="Anse möten med fler deltagare än detta som stora",
            default=500,
            type=int,
        )

    def handle(self, *args, **options):
        columns = [
            "Namn",
            "Möten",
            "Stora möten",
            "Bortfiltrerade möten",
            "Antal användare under året",
            "Uppkopplingar",
            "Effektiv använgningstid",
        ]
        year = int(options["y"])
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        output = [columns]
        for org in Organisation.objects.all():
            row = [org.title]
            meeting_qs = org.meetings.filter(
                created__gte=year_start, created__lte=year_end
            ).annotate(participants_count=models.Count(models.F("participants")))
            # Möten
            row.append(
                meeting_qs.filter(participants_count__gte=options["pmin"]).count()
            )
            # Stora möten
            row.append(
                meeting_qs.filter(participants_count__gte=options["plarge"]).count()
            )
            # Bortfiltrerade möten
            row.append(
                meeting_qs.filter(participants_count__lt=options["pmin"]).count()
            )
            # Antal användare under året
            row.append(
                org.users.filter(
                    connections__online_at__gte=year_start,
                    connections__online_at__lte=year_end,
                ).count()
            )
            # Uppkopplingar och Effektiv använgningstid
            ts_sum = []
            for online_ts, offline_ts in (
                Connection.objects.filter(user__in=org.users.all())
                .filter(online_at__gte=year_start, online_at__lte=year_end)
                .exclude(offline_at__isnull=True)
                .values_list("online_at", "offline_at")
            ):
                ts_sum.append(offline_ts - online_ts)
            row.append(len(ts_sum))
            if ts_sum:
                ts_total = reduce(lambda x, y: x + y, ts_sum)
                row.append(f"{ts_total.days} d, {divmod(ts_total.seconds, 3600)[0]} h")
            else:
                row.append(0)
            output.append(row)
        for row in output:
            self.stdout.write("\t".join(str(x) for x in row))
