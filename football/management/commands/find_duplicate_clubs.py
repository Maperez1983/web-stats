"""
Reporta clubes que podrían ser el MISMO club real (candidatos a fusionar).

Por construcción no debería haber dos clubes con el mismo name_key; este comando busca
el caso residual: el mismo club escrito diferente (variantes/erratas/equipos 'B') cuyo
nombre no normaliza igual. No fusiona nada: solo informa para que decidas.

Uso:  python manage.py find_duplicate_clubs
"""

from django.core.management.base import BaseCommand

from football.models import Club


class Command(BaseCommand):
    help = "Lista clubes candidatos a ser duplicados (mismo club real escrito distinto)."

    def handle(self, *args, **options):
        clubs = list(
            Club.objects.all().prefetch_related("teams__group").order_by("name_key", "id")
        )
        total = len(clubs)
        self.stdout.write(f"Clubes totales: {total}")

        # 1) name_key EXACTO repetido (no debería ocurrir; si ocurre, fusionar).
        by_key = {}
        for club in clubs:
            by_key.setdefault(club.name_key, []).append(club)
        exact = {k: v for k, v in by_key.items() if k and len(v) > 1}
        if exact:
            self.stdout.write(self.style.WARNING("\n== Duplicados EXACTOS (mismo name_key) — fusionar =="))
            for key, group in exact.items():
                self.stdout.write(f"  [{key}] -> " + " | ".join(f"#{c.id} {c.name} ({c.teams.count()} eq.)" for c in group))
        else:
            self.stdout.write(self.style.SUCCESS("\nSin duplicados exactos por name_key. ✔"))

        # 2) Candidatos por CONTENCIÓN de name_key (uno contenido en el otro, len >= 4):
        #    típico de 'cdrincon' vs 'cdrinconb' (equipo B) o 'rincon' vs 'cdrincon'.
        keys = sorted({c.name_key for c in clubs if c.name_key and len(c.name_key) >= 4})
        candidates = []
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                if a != b and (a in b or b in a):
                    candidates.append((a, b))
        if candidates:
            self.stdout.write(self.style.WARNING("\n== Posibles duplicados (nombres parecidos) — revisar manualmente =="))
            for a, b in candidates:
                ca = by_key.get(a, [])
                cb = by_key.get(b, [])
                names_a = ", ".join(f"#{c.id} {c.name}" for c in ca)
                names_b = ", ".join(f"#{c.id} {c.name}" for c in cb)
                self.stdout.write(f"  {a} ~ {b}\n      A: {names_a}\n      B: {names_b}")
        else:
            self.stdout.write(self.style.SUCCESS("\nSin candidatos por nombre parecido. ✔"))

        self.stdout.write("\n(No se ha fusionado nada; este comando solo informa.)")
