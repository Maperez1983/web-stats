from django.test import TestCase
from django.urls import reverse
from datetime import date
from football.models import Player, PlayerInjuryRecord, Team


class InjuryDetailLinkTests(TestCase):
    """
    Cada lesión enlaza con su ficha.

    La plantilla de la ficha pedía `item.detail_url` desde hace tiempo y la vista nunca lo
    daba: la fila se pintaba sin enlace y la página de detalle era inalcanzable desde ahí.
    """

    def test_record_knows_its_detail_url(self):
        team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        player = Player.objects.create(team=team, name="Acosta", is_active=True)
        record = PlayerInjuryRecord.objects.create(
            player=player, injury="Rotura fibrilar", injury_date=date(2026, 7, 28)
        )
        self.assertEqual(
            record.detail_url, reverse("player-injury-detail", args=[player.id, record.id])
        )
