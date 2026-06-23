from unittest import mock

from django.test import SimpleTestCase

from football.render_api import inspect_render_service, list_render_services


class RenderApiTests(SimpleTestCase):
    def test_list_render_services_parses_service_rows(self):
        payload = [
            {"service": {"id": "srv-1", "name": "web-stats", "type": "web_service", "status": "live", "dashboardUrl": "https://dashboard", "branch": "main"}},
            {"service": {"id": "srv-2", "name": "worker", "type": "background_worker", "status": "created", "dashboardUrl": "https://dashboard2", "branch": "main"}},
        ]

        with mock.patch('football.render_api._request', return_value=(payload, {'ok': True})):
            snapshot = list_render_services(limit=4)

        self.assertTrue(snapshot['enabled'])
        self.assertEqual(snapshot['service_count'], 2)
        self.assertEqual(snapshot['services'][0]['id'], 'srv-1')
        self.assertEqual(snapshot['services'][1]['type'], 'background_worker')

    def test_inspect_render_service_returns_env_and_deploy_summary(self):
        service = {
            'id': 'srv-1',
            'name': 'web-stats-ollana-operator',
            'type': 'background_worker',
            'branch': 'main',
            'slug': 'web-stats-ollana-operator',
            'dashboardUrl': 'https://dashboard.render.com',
            'suspended': 'not_suspended',
            'repo': 'https://github.com/example/repo',
            'rootDir': '',
            'serviceDetails': {},
        }
        env_payload = [
            {'envVar': {'key': 'OLLANA_RENDER_API_KEY'}, 'cursor': 'a'},
            {'envVar': {'key': 'DATABASE_URL'}, 'cursor': 'b'},
        ]
        deploy_payload = [
            {'deploy': {'id': 'dep-1', 'status': 'live', 'trigger': 'service_updated', 'createdAt': '2026-06-23T10:00:00Z'}},
            {'deploy': {'id': 'dep-0', 'status': 'build_failed', 'trigger': 'manual', 'createdAt': '2026-06-22T10:00:00Z'}},
        ]

        def fake_request(path, *, timeout=12):
            if path == '/services/srv-1':
                return service, {'ok': True}
            if path == '/services/srv-1/env-vars':
                return env_payload, {'ok': True}
            if path == '/services/srv-1/deploys':
                return deploy_payload, {'ok': True}
            raise AssertionError(path)

        with mock.patch('football.render_api._request', side_effect=fake_request):
            snapshot = inspect_render_service('srv-1')

        self.assertTrue(snapshot['enabled'])
        self.assertEqual(snapshot['service']['name'], 'web-stats-ollana-operator')
        self.assertEqual(snapshot['env']['keys'], ['OLLANA_RENDER_API_KEY', 'DATABASE_URL'])
        self.assertEqual(snapshot['deploys']['summary']['latest']['id'], 'dep-1')
