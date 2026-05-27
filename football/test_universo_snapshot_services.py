import json
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from football import universo_snapshot_services


class UniversoSnapshotServicesTests(SimpleTestCase):
    def test_load_universo_snapshot_returns_dict_payload(self):
        path = Path('/tmp/universo-snapshot-test.json')
        path.write_text(json.dumps({'standings': []}), encoding='utf-8')
        try:
            with patch.object(universo_snapshot_services, 'UNIVERSO_SNAPSHOT_PATH', path):
                if hasattr(universo_snapshot_services.load_universo_snapshot, '_memo'):
                    delattr(universo_snapshot_services.load_universo_snapshot, '_memo')
                payload = universo_snapshot_services.load_universo_snapshot()
        finally:
            try:
                path.unlink()
            except OSError:
                pass

        self.assertEqual(payload, {'standings': []})

    def test_load_universo_snapshot_returns_none_for_missing_file(self):
        with patch.object(universo_snapshot_services, 'UNIVERSO_SNAPSHOT_PATH', Path('/tmp/missing-universo-snapshot.json')):
            if hasattr(universo_snapshot_services.load_universo_snapshot, '_memo'):
                delattr(universo_snapshot_services.load_universo_snapshot, '_memo')
            self.assertIsNone(universo_snapshot_services.load_universo_snapshot())
