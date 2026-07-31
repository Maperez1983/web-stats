"""La chapa con escudo es el formato aprobado: este test la protege.

Duplica en `manage.py test` el candado que `build.sh` ejecuta antes de desplegar,
para que una regresion salte tambien en local y no solo al desplegar.

Si este test falla, el fallo esta en el editor 2D, NO en el test.
Relajarlo requiere peticion expresa del propietario.
"""
import importlib.util
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts" / "check_chapa_contract.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_chapa_contract", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ChapaContractTests(SimpleTestCase):
    def test_el_candado_de_la_chapa_existe(self):
        self.assertTrue(CHECKER.exists(), "scripts/check_chapa_contract.py no puede desaparecer")

    def test_la_chapa_conserva_su_contrato(self):
        problems = []
        _load_checker().check(problems)
        self.assertEqual(
            problems,
            [],
            "Contrato de la chapa roto:\n  - " + "\n  - ".join(problems),
        )
