from django.contrib.auth.models import AnonymousUser
from django.core.management.base import BaseCommand
from django.test import RequestFactory

from football import views
from football.models import PlayerMatchReportArchive, PlayerStatistic


class Command(BaseCommand):
    help = "Genera o recupera las versiones PDF pendientes de informes individuales de partido."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--match-id", type=int, default=0)
        parser.add_argument("--retry-errors", action="store_true")

    def handle(self, *args, **options):
        limit = max(1, min(100, int(options.get("limit") or 10)))
        match_id = int(options.get("match_id") or 0)
        statuses = [PlayerMatchReportArchive.STATUS_PENDING]
        if options.get("retry_errors"):
            statuses.append(PlayerMatchReportArchive.STATUS_ERROR)

        rating_qs = PlayerStatistic.objects.filter(
            match__isnull=False,
            match__is_closed=True,
            name="rating",
            context="auto-rating",
        )
        if match_id:
            rating_qs = rating_qs.filter(match_id=match_id)
        for rating in rating_qs.select_related("player", "match").iterator(chunk_size=250):
            PlayerMatchReportArchive.objects.get_or_create(
                player=rating.player,
                match=rating.match,
                version=1,
                defaults={
                    "status": PlayerMatchReportArchive.STATUS_PENDING,
                    "rating": rating.value,
                    "reason": "historical_backfill",
                    "snapshot": {"historical_backfill": True},
                },
            )

        qs = PlayerMatchReportArchive.objects.filter(status__in=statuses).select_related(
            "player__team", "match__home_team", "match__away_team"
        )
        if match_id:
            qs = qs.filter(match_id=match_id)
        archives = list(qs.order_by("generated_at", "id")[:limit])
        request = RequestFactory().get("/", HTTP_HOST="app.segundajugada.es", secure=True)
        request.user = AnonymousUser()
        ready = 0
        failed = 0
        for archive in archives:
            try:
                snapshot = archive.snapshot or {}
                if not snapshot or snapshot.get("historical_backfill"):
                    archive = views._create_player_report_archive(
                        request,
                        primary_team=archive.player.team,
                        player=archive.player,
                        match=archive.match,
                        reason=archive.reason or "historical_backfill",
                        force_new_version=False,
                        render_pdf=False,
                    )
                if views._render_player_report_archive_pdf(request, archive):
                    ready += 1
                else:
                    failed += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(f"Informe {archive.id}: {exc.__class__.__name__}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Procesados={len(archives)} · listos={ready} · fallidos={failed}"))
