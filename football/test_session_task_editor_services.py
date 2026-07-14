import copy
import io
import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.base import ContentFile
from django.test import RequestFactory, TestCase
from django.utils import timezone

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

from football.models import (
    AppUserRole,
    SessionTask,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)
from football.session_task_editor_services import (
    _forbid_if_workspace_module_disabled,
    _task_builder_initial_values,
)


class SessionTaskEditorServicesTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="editor-services-user",
            email="editor-services@example.com",
            password="pass-1234",
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.team = Team.objects.create(name="Equipo servicios", slug="equipo-servicios", is_primary=True)
        self.workspace = Workspace.objects.create(
            name="Workspace servicios",
            slug="workspace-servicios",
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            owner_user=self.user,
            enabled_modules={"sessions": True, "dashboard": True, "players": True},
            subscription_status="trial",
            trial_expires_at=timezone.now() + timedelta(days=7),
            is_active=True,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_OWNER,
            module_access={"sessions": True, "dashboard": True, "players": True},
        )
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title="Micro servicios",
            week_start=date(2026, 7, 13),
            week_end=date(2026, 7, 19),
        )
        self.session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 7, 14),
            focus="Salida de balón",
            duration_minutes=90,
        )

    def _request(self, path="/editor/", *, user=None, workspace=None, secure=False, accept="application/json"):
        request = self.factory.get(path, secure=secure, HTTP_ACCEPT=accept)
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        request.user = user or self.user
        if workspace is not None:
            request.session["active_workspace_id"] = workspace.id
        return request

    def _sample_png_bytes(self):
        if Image is None:
            return (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02"
                b"\x08\x02\x00\x00\x00\xfd\xd4\x9as\x00\x00\x00\x0cIDATx\x9cc`\xf8\xcf"
                b"\xc0\x00\x00\x04\x00\x01\xe2&\x05\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
            )
        image = Image.new("RGBA", (16, 16), "#1f7a3f")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _task(self, **kwargs):
        defaults = {
            "session": self.session,
            "title": "Tarea servicios",
            "block": SessionTask.BLOCK_MAIN_1,
            "duration_minutes": 18,
            "tactical_layout": {"meta": {}},
        }
        defaults.update(kwargs)
        return SessionTask.objects.create(**defaults)

    def test_forbid_returns_none_without_active_workspace_for_coach(self):
        request = self._request(workspace=None)
        response = _forbid_if_workspace_module_disabled(request, "sessions", label="sesiones")
        self.assertIsNone(response)

    def test_forbid_returns_none_when_module_access_is_allowed(self):
        request = self._request(workspace=self.workspace)
        response = _forbid_if_workspace_module_disabled(request, "sessions", label="sesiones")
        self.assertIsNone(response)

    def test_forbid_returns_403_when_workspace_module_is_disabled(self):
        self.workspace.enabled_modules = {"sessions": False, "dashboard": True}
        self.workspace.save(update_fields=["enabled_modules"])
        request = self._request(workspace=self.workspace)
        response = _forbid_if_workspace_module_disabled(request, "sessions", label="sesiones")
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
        self.assertIn("sesiones", response.content.decode("utf-8"))
        self.assertIn("no está activo", response.content.decode("utf-8"))

    def test_forbid_returns_403_when_membership_blocks_module(self):
        member = get_user_model().objects.create_user(username="member-services", password="pass-1234")
        AppUserRole.objects.create(user=member, role=AppUserRole.ROLE_COACH)
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=member,
            role=WorkspaceMembership.ROLE_MEMBER,
            module_access={"sessions": False},
        )
        request = self._request(user=member, workspace=self.workspace)
        response = _forbid_if_workspace_module_disabled(request, "sessions", label="editor")
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
        self.assertIn("editor", response.content.decode("utf-8"))

    def test_forbid_requires_subscription_and_redirects_html_requests(self):
        self.workspace.subscription_status = "trial"
        self.workspace.trial_expires_at = timezone.now() - timedelta(days=1)
        self.workspace.save(update_fields=["subscription_status", "trial_expires_at"])
        request = self._request(
            path="/coach/sesiones/?foo=1",
            workspace=self.workspace,
            secure=True,
            accept="text/html",
        )
        response = _forbid_if_workspace_module_disabled(request, "sessions", label="sesiones")
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/billing/", response["Location"])
        self.assertIn("next=", response["Location"])

    def test_forbid_returns_402_when_subscription_is_missing_for_json_request(self):
        self.workspace.subscription_status = "trial"
        self.workspace.trial_expires_at = timezone.now() - timedelta(days=1)
        self.workspace.save(update_fields=["subscription_status", "trial_expires_at"])
        request = self._request(workspace=self.workspace, accept="application/json")
        response = _forbid_if_workspace_module_disabled(request, "sessions", label="sesiones")
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 402)
        self.assertIn("Periodo de prueba finalizado", response.content.decode("utf-8"))
        self.assertIn("/billing/", response.content.decode("utf-8"))

    def test_forbid_allows_active_subscription_when_paid_module_is_enabled(self):
        self.workspace.subscription_status = "active"
        self.workspace.plan_key = "starter"
        self.workspace.paid_modules = {"sessions": True}
        self.workspace.enabled_modules = {"sessions": False, "dashboard": True}
        self.workspace.save(update_fields=["subscription_status", "plan_key", "paid_modules", "enabled_modules"])
        request = self._request(workspace=self.workspace)
        response = _forbid_if_workspace_module_disabled(request, "sessions", label="sesiones")
        self.assertIsNone(response)

    def test_forbid_allows_platform_admin_without_workspace(self):
        admin = get_user_model().objects.create_user(username="platform-admin", password="pass-1234", is_staff=True)
        request = self._request(user=admin, workspace=None)
        response = _forbid_if_workspace_module_disabled(request, "sessions", label="sesiones")
        self.assertIsNone(response)

    def test_forbid_handles_workspace_without_optional_team_data(self):
        orphan = Workspace.objects.create(
            name="Workspace huérfano",
            slug="workspace-huerfano",
            kind=Workspace.KIND_CLUB,
            owner_user=self.user,
            enabled_modules={"sessions": True, "dashboard": True},
            subscription_status="trial",
            trial_expires_at=timezone.now() + timedelta(days=5),
            is_active=True,
        )
        request = self._request(workspace=orphan)
        response = _forbid_if_workspace_module_disabled(request, "sessions", label="sesiones")
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
        self.assertIn("Completa el onboarding", response.content.decode("utf-8"))

    def test_task_builder_initial_values_returns_defaults_for_empty_task(self):
        task = SessionTask(
            session=self.session,
            title="Tarea servicios",
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=18,
            tactical_layout=None,
            objective=None,
            coaching_points=None,
            confrontation_rules=None,
        )
        result = _task_builder_initial_values(task)
        self.assertEqual(result["title"], "Tarea servicios")
        self.assertEqual(result["block"], SessionTask.BLOCK_MAIN_1)
        self.assertEqual(result["minutes"], 18)
        self.assertEqual(result["canvas_width"], 1280)
        self.assertEqual(result["canvas_height"], 720)
        self.assertEqual(json.loads(result["canvas_state"])["objects"], [])
        self.assertEqual(result["pitch_orientation"], "landscape")
        self.assertEqual(result["pitch_grass_style"], "stadium_native")
        json.dumps(result, ensure_ascii=False)

    def test_task_builder_initial_values_supports_complete_nested_configuration(self):
        layout = {
            "meta": {
                "multi_board": True,
                "space": "Medio campo",
                "organization": "2 equipos + 2 comodines",
                "organization_html": "<p>Organización</p>",
                "work_rest": "4x3'",
                "load_target": "Alta",
                "players_distribution": "6v6+2",
                "progression": "Añadir comodín",
                "progression_html": "<p>Prog</p>",
                "regression": "Reducir espacio",
                "regression_html": "<p>Reg</p>",
                "success_criteria": "10 pases",
                "success_criteria_html": "<p>Éxito</p>",
                "surface": "Césped artificial",
                "pitch_format": "8v8",
                "game_phase": "Ataque",
                "game_moment": "Inicio",
                "principle": "Progresión",
                "subprinciple": "Fijar",
                "provocation_rule": "2 toques",
                "dominant_structure": "1-4-3-3",
                "secondary_structure": "1-4-4-2",
                "physical_load": "Alta",
                "cognitive_load": "Media",
                "emotional_load": "Alta",
                "rpe_scale": "cr10",
                "planned_rpe": 7,
                "planned_srpe_load": 126,
                "wellness_target": 8,
                "monotony_target": "1.2",
                "strain_target": "430",
                "md_day": "MD-2",
                "dominant_load": "Velocidad",
                "load_notes": "Picos controlados",
                "methodology": "Integrada",
                "complexity": "Alta",
                "strategy": "Superioridad interior",
                "coordination": "Intermedia",
                "coordination_skills": "Orientación",
                "tactical_intent": "Atraer para progresar",
                "dynamics": "Oposición",
                "structure": "Posicional",
                "template_key": "club",
                "pitch_preset": "half_pitch",
                "pitch_orientation": "portrait",
                "pitch_zoom": "1.25",
                "pitch_grass_style": "premium_turf",
                "series": "3",
                "repetitions": "4",
                "player_count": "14",
                "age_group": "Cadete",
                "training_type": "Táctica",
                "category_tags": ["Salida", "Presión"],
                "assigned_player_ids": [1, "2", "bad"],
                "constraints": ["2 toques", "", "comodín interior"],
                "drills": ["cone", "goal", "cone"],
                "drills_icon_color": "#123456",
                "analysis": {
                    "task_sheet": {
                        "description": "Conservar para progresar",
                        "description_html": "<p>Descripción</p>",
                        "coaching_html": "<p>Coaching</p>",
                        "rules_html": "<p>Reglas</p>",
                        "players": "6v6 + 2 porteros",
                        "materials": "8 conos",
                        "dimensions": "40x30",
                        "space": "Zona 2",
                    }
                },
                "graphic_editor": {
                    "canvas_state": {"version": "5.3.0", "objects": [{"id": "cone-1", "type": "circle"}]},
                    "canvas_width": 900,
                    "canvas_height": 600,
                },
            },
            "timeline": [
                {
                    "title": "Paso 1",
                    "duration": 5,
                    "canvas_state": '{"version":"5.3.0","objects":[{"id":"frame-1"}]}',
                    "canvas_width": 500,
                    "canvas_height": 300,
                }
            ],
        }
        task = self._task(tactical_layout=layout)
        original_layout = copy.deepcopy(task.tactical_layout)
        result = _task_builder_initial_values(task)
        state = json.loads(result["canvas_state"])
        self.assertTrue(result["multi_board_enabled"])
        self.assertEqual(result["space"], "Medio campo")
        self.assertEqual(result["description"], "Conservar para progresar")
        self.assertEqual(result["description_html"], "<p>Descripción</p>")
        self.assertEqual(result["coaching_points_html"], "<p>Coaching</p>")
        self.assertEqual(result["confrontation_rules_html"], "<p>Reglas</p>")
        self.assertEqual(result["materials"], "8 conos")
        self.assertEqual(result["pitch_preset"], "half_pitch")
        self.assertEqual(result["pitch_orientation"], "portrait")
        self.assertEqual(result["pitch_grass_style"], "premium_turf")
        self.assertEqual(result["canvas_width"], 900)
        self.assertEqual(result["canvas_height"], 600)
        self.assertEqual(result["assigned_player_ids"], [1, 2])
        self.assertEqual(result["constraints"], ["2 toques", "comodín interior"])
        self.assertEqual(result["category_tags"], "Salida, Presión")
        self.assertEqual(result["drills_icon_color"], "#123456")
        self.assertEqual(state["objects"][0]["id"], "cone-1")
        self.assertEqual(state["timeline"][0]["canvas_state"]["objects"][0]["id"], "frame-1")
        self.assertEqual(state["active_step_index"], 0)
        self.assertEqual(task.tactical_layout, original_layout)
        json.dumps(result, ensure_ascii=False)

    def test_task_builder_initial_values_handles_string_and_invalid_json(self):
        task = self._task()
        task.tactical_layout = json.dumps(
            {
                "meta": {
                    "pitch_grass_style": "stadium_top",
                    "graphic_editor": {
                        "canvas_state": '{"version":"5.3.0","objects":[{"id":"a"}]}',
                    },
                    "analysis": {"task_sheet": {"materials": "4 picas"}},
                }
            }
        )
        result = _task_builder_initial_values(task)
        self.assertEqual(result["materials"], "4 picas")
        self.assertEqual(result["pitch_grass_style"], "stadium_native")
        self.assertEqual(json.loads(result["canvas_state"])["objects"][0]["id"], "a")

        task.tactical_layout = "{invalid json"
        invalid_result = _task_builder_initial_values(task)
        self.assertEqual(json.loads(invalid_result["canvas_state"])["objects"], [])
        self.assertEqual(invalid_result["materials"], "")

    def test_task_builder_initial_values_builds_preview_background_when_only_preview_exists(self):
        task = self._task(
            tactical_layout={
                "meta": {
                    "pitch_orientation": "portrait",
                    "graphic_editor": {"canvas_state": {"version": "5.3.0", "objects": []}},
                }
            }
        )
        task.task_preview_image.save("preview.png", ContentFile(self._sample_png_bytes()), save=True)
        result = _task_builder_initial_values(task)
        state = json.loads(result["canvas_state"])
        self.assertEqual(result["canvas_width"], 684)
        self.assertEqual(result["canvas_height"], 1054)
        self.assertEqual(state["objects"][0]["data"]["kind"], "preview-background")
        self.assertIn("/coach/sesiones/tarea/", state["objects"][0]["src"])

    def test_task_builder_initial_values_uses_tokens_as_fabric_fallback(self):
        task = self._task(
            tactical_layout={
                "tokens": [{"type": "circle", "left": 120, "top": 90}],
                "meta": {"pitch_orientation": "landscape"},
            }
        )
        result = _task_builder_initial_values(task)
        state = json.loads(result["canvas_state"])
        self.assertEqual(state["objects"][0]["type"], "circle")
        self.assertEqual(result["canvas_width"], 1054)
        self.assertEqual(result["canvas_height"], 684)
