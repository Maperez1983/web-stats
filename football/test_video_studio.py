import base64
import io
import json
import os
import zipfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from football.models import (
    AnalystVideoFolder,
    AppUserRole,
    Competition,
    Group,
    Player,
    RivalVideo,
    Season,
    Team,
    VideoClip,
    VideoTimelineEvent,
    VideoTelestrationProject,
    Workspace,
    WorkspaceMembership,
    WorkspacePreference,
)


class AnalysisVideoWorkspaceTests(TestCase):
    def setUp(self):
        cache.clear()
        self._fallback_env = patch.dict(os.environ, {'ALLOW_SINGLE_CLUB_FALLBACK': '1'}, clear=False)
        self._fallback_env.start()
        self.addCleanup(self._fallback_env.stop)
        self.user = get_user_model().objects.create_user(
            username='analyst-workspace',
            email='analyst-workspace@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_ANALYST)
        competition = Competition.objects.create(name='Liga Analista', slug='liga-analista', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo Analista', slug='grupo-analista')
        self.team = Team.objects.create(name='Benagalbon', slug='benagalbon-analista', group=group, is_primary=True)
        self.rival = Team.objects.create(name='Rival Analista', slug='rival-analista', group=group)
        self.player = Player.objects.create(team=self.team, name='Ivan', position='DC')
        self.client.force_login(self.user)

    def test_analysis_page_can_create_folder_and_assign_video_to_player(self):
        response = self.client.post(
            reverse('analysis'),
            {
                'form_action': 'create_video_folder',
                'video_team_id': self.rival.id,
                'folder_name': 'J24 · Clips DC',
                'team_id': self.rival.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        folder = AnalystVideoFolder.objects.get(name='J24 · Clips DC')
        self.assertEqual(folder.rival_team, self.rival)

        video_file = SimpleUploadedFile('clip.mp4', b'fake-video-content', content_type='video/mp4')
        response = self.client.post(
            reverse('analysis'),
            {
                'form_action': 'upload_video',
                'video_team_id': self.rival.id,
                'video_title': 'Clip delantero',
                'video_source': RivalVideo.SOURCE_MANUAL,
                'video_folder_id': folder.id,
                'video_notes': 'Atacar intervalo central',
                'assigned_player_ids': [self.player.id],
                'team_id': self.rival.id,
                'video_file': video_file,
            },
        )

        self.assertEqual(response.status_code, 200)
        video = RivalVideo.objects.get(title='Clip delantero')
        self.assertEqual(video.folder, folder)
        self.assertEqual(list(video.assigned_players.values_list('id', flat=True)), [self.player.id])

    def test_player_detail_shows_assigned_analysis_video(self):
        folder = AnalystVideoFolder.objects.create(team=self.team, rival_team=self.rival, name='J24 · ABP')
        video = RivalVideo.objects.create(
            rival_team=self.rival,
            folder=folder,
            title='ABP ofensiva rival',
            video=SimpleUploadedFile('abp.mp4', b'video', content_type='video/mp4'),
            source=RivalVideo.SOURCE_MANUAL,
            notes='Revisar bloqueos del primer palo',
        )
        video.assigned_players.add(self.player)

        response = self.client.get(reverse('player-detail', args=[self.player.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vídeos')
        self.assertContains(response, 'ABP ofensiva rival')


class VideoStudioProApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='video-studio-coach',
            email='video-studio@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        competition = Competition.objects.create(name='Liga VS', slug='liga-vs', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo VS', slug='grupo-vs')
        self.team = Team.objects.create(name='Equipo VS', slug='equipo-vs', group=group, is_primary=True)
        self.rival = Team.objects.create(name='Rival VS', slug='rival-vs', group=group)
        self.workspace = Workspace.objects.create(
            name='Workspace VS',
            slug='workspace-vs',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            enabled_modules={
                'analysis': True,
                'dashboard': True,
                'players': True,
            },
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_ADMIN,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['active_workspace_id'] = self.workspace.id
        session['active_team_by_workspace'] = {str(self.workspace.id): int(self.team.id)}
        session.save()

        self.folder = AnalystVideoFolder.objects.create(team=self.team, rival_team=self.rival, name='J1 · Clips')
        self.video = RivalVideo.objects.create(
            team=self.team,
            rival_team=self.rival,
            folder=self.folder,
            title='Clip 1',
            video=SimpleUploadedFile('clip.mp4', b'fake-video', content_type='video/mp4'),
            source=RivalVideo.SOURCE_MANUAL,
            notes='',
        )

    def test_video_studio_can_create_and_list_timeline_and_clips(self):
        clip_save = self.client.post(
            reverse('analysis-video-studio-clip-save-api'),
            data=json.dumps(
                {
                    'video_id': self.video.id,
                    'title': 'Presión tras pérdida',
                    'collection': 'J1',
                    'in_s': 12.0,
                    'out_s': 18.0,
                    'overlay': {'objects': []},
                }
            ),
            content_type='application/json',
        )
        self.assertEqual(clip_save.status_code, 200)
        payload = clip_save.json()
        self.assertTrue(payload.get('ok'))
        self.assertTrue(VideoClip.objects.filter(team=self.team, video=self.video).exists())

        clips_list = self.client.get(reverse('analysis-video-studio-clips-api') + f'?video_id={self.video.id}')
        self.assertEqual(clips_list.status_code, 200)
        items = clips_list.json().get('items') or []
        self.assertTrue(any((row.get('title') == 'Presión tras pérdida') for row in items))

        ev_save = self.client.post(
            reverse('analysis-video-studio-timeline-save-api'),
            data=json.dumps(
                {
                    'video_id': self.video.id,
                    'time_s': 15.4,
                    'kind': 'press',
                    'label': 'Presión alta',
                    'color': '#22d3ee',
                }
            ),
            content_type='application/json',
        )
        self.assertEqual(ev_save.status_code, 200)
        self.assertTrue(ev_save.json().get('ok'))
        self.assertTrue(VideoTimelineEvent.objects.filter(team=self.team, video=self.video).exists())

        ev_list = self.client.get(reverse('analysis-video-studio-timeline-api') + f'?video_id={self.video.id}')
        self.assertEqual(ev_list.status_code, 200)
        items = ev_list.json().get('items') or []
        self.assertTrue(any((row.get('kind') == 'press') for row in items))

    def test_video_studio_autoclip_prefs_learn_from_timeline_clip(self):
        # Creamos un evento en timeline.
        ev_save = self.client.post(
            reverse('analysis-video-studio-timeline-save-api'),
            data=json.dumps(
                {
                    'video_id': self.video.id,
                    'time_s': 15.4,
                    'kind': 'press',
                    'label': 'Presión alta',
                    'color': '#22d3ee',
                }
            ),
            content_type='application/json',
        )
        self.assertEqual(ev_save.status_code, 200)
        self.assertTrue(ev_save.json().get('ok'))

        # Clip creado alrededor del evento, replicando Timeline→Clip (tags 'timeline' + kind).
        clip_save = self.client.post(
            reverse('analysis-video-studio-clip-save-api'),
            data=json.dumps(
                {
                    'video_id': self.video.id,
                    'title': 'Presión alta',
                    'collection': 'Rival',
                    'in_s': 12.0,
                    'out_s': 18.0,
                    'tags': ['press', 'timeline'],
                    'overlay': {'objects': []},
                }
            ),
            content_type='application/json',
        )
        self.assertEqual(clip_save.status_code, 200)
        self.assertTrue(clip_save.json().get('ok'))

        # Abrir Video Studio siembra preferencias (aprende de cortes existentes).
        studio = self.client.get(reverse('analysis-video-studio', args=[self.video.id]))
        self.assertEqual(studio.status_code, 200)

        # La preferencia AutoClip se guarda en el workspace.
        key = f'vs_event_autoclip:v1:{self.team.id}:rival'
        pref = WorkspacePreference.objects.filter(workspace=self.workspace, key=key).first()
        self.assertIsNotNone(pref)
        self.assertIsInstance(pref.value, dict)
        # Evento en 15.4s y clip 12-18 => pre 3.4s, post 2.6s. Se redondea a enteros.
        self.assertEqual(int(pref.value.get('pre') or 0), 3)
        self.assertEqual(int(pref.value.get('post') or 0), 3)

    def test_video_studio_export_pdf_and_package(self):
        png_1x1 = base64.b64decode(
            b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQI12P4//8/AwAI/AL+Qxg9WAAAAABJRU5ErkJggg=='
        )
        slide_img = 'data:image/png;base64,' + base64.b64encode(png_1x1).decode('ascii')
        payload = {
            'video_id': self.video.id,
            'title': 'Export VS',
            'source': 'tests',
            'slides': [
                {'label': 'S1', 'time_s': 12.3, 'image_data': slide_img},
                {'label': 'S2', 'time_s': 45.0, 'image_data': slide_img},
            ],
        }

        pdf_resp = self.client.post(
            reverse('analysis-video-studio-export-pdf-api'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(pdf_resp.status_code, 200)
        self.assertIn('application/pdf', pdf_resp['Content-Type'])
        self.assertTrue(pdf_resp.content.startswith(b'%PDF'))

        zip_resp = self.client.post(
            reverse('analysis-video-studio-export-package-api'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(zip_resp.status_code, 200)
        self.assertIn('application/zip', zip_resp['Content-Type'])
        zf = zipfile.ZipFile(io.BytesIO(zip_resp.content))
        names = set(zf.namelist())
        self.assertIn('cover.html', names)
        self.assertIn('index.html', names)
        self.assertIn('export.json', names)
        self.assertTrue(any(n.startswith('slides/slide-') for n in names))
        self.assertTrue(any(n.startswith('thumbs/thumb-') for n in names))

    def test_video_studio_export_playlist_server_requires_ffmpeg(self):
        c1 = VideoClip.objects.create(
            team=self.team,
            video=self.video,
            title='C1',
            collection='',
            in_ms=0,
            out_ms=1000,
            tags=[],
            notes='',
            overlay={},
            created_by=self.user.username,
        )
        c2 = VideoClip.objects.create(
            team=self.team,
            video=self.video,
            title='C2',
            collection='',
            in_ms=1500,
            out_ms=2500,
            tags=[],
            notes='',
            overlay={},
            created_by=self.user.username,
        )
        with patch('football.views.shutil.which', return_value=None):
            resp = self.client.post(
                reverse('analysis-video-studio-export-server-playlist-api'),
                data=json.dumps({'video_id': self.video.id, 'clip_ids': [c1.id, c2.id], 'title': 'PL'}),
                content_type='application/json',
            )
        # Si no hay FFmpeg, devolvemos 400 con mensaje claro (no debe ser 5xx para no ensuciar logs de producción).
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json().get('ok'))

    def test_video_studio_music_upload_list_and_delete(self):
        up = SimpleUploadedFile('bgm.mp3', b'fake-audio', content_type='audio/mpeg')
        upload = self.client.post(
            reverse('analysis-video-studio-music-upload-api'),
            data={'video_id': self.video.id, 'title': 'BGM', 'file': up},
        )
        self.assertEqual(upload.status_code, 200)
        data = upload.json()
        self.assertTrue(data.get('ok'))
        music_id = int(data['item']['id'])

        listing = self.client.get(reverse('analysis-video-studio-music-api') + f'?video_id={self.video.id}')
        self.assertEqual(listing.status_code, 200)
        items = listing.json().get('items') or []
        self.assertTrue(any(int(row.get('id') or 0) == music_id for row in items))

        delete = self.client.post(
            reverse('analysis-video-studio-music-delete-api'),
            data=json.dumps({'id': music_id, 'video_id': self.video.id}),
            content_type='application/json',
        )
        self.assertEqual(delete.status_code, 200)
        self.assertTrue(delete.json().get('ok'))

        listing2 = self.client.get(reverse('analysis-video-studio-music-api') + f'?video_id={self.video.id}')
        self.assertEqual(listing2.status_code, 200)
        items2 = listing2.json().get('items') or []
        self.assertFalse(any(int(row.get('id') or 0) == music_id for row in items2))

    def test_video_studio_export_job_create_and_cancel(self):
        c1 = VideoClip.objects.create(
            team=self.team,
            video=self.video,
            title='C1',
            collection='',
            in_ms=0,
            out_ms=1000,
            tags=[],
            notes='',
            overlay={},
            created_by=self.user.username,
        )
        c2 = VideoClip.objects.create(
            team=self.team,
            video=self.video,
            title='C2',
            collection='',
            in_ms=1500,
            out_ms=2500,
            tags=[],
            notes='',
            overlay={},
            created_by=self.user.username,
        )
        with patch('football.views.shutil.which', return_value=None):
            create = self.client.post(
                reverse('analysis-video-studio-export-job-create-api'),
                data=json.dumps({'video_id': self.video.id, 'items': [{'clip_id': c1.id}, {'clip_id': c2.id}], 'title': 'Job'}),
                content_type='application/json',
            )
        self.assertEqual(create.status_code, 200)
        payload = create.json()
        self.assertTrue(payload.get('ok'))
        job_id = int(payload['job_id'])

        cancel = self.client.post(
            reverse('analysis-video-studio-export-job-cancel-api'),
            data=json.dumps({'job_id': job_id}),
            content_type='application/json',
        )
        self.assertEqual(cancel.status_code, 200)
        self.assertTrue(cancel.json().get('ok'))

        status = self.client.get(reverse('analysis-video-studio-export-job-status-api') + f'?job_id={job_id}')
        self.assertEqual(status.status_code, 200)
        job = status.json().get('job') or {}
        self.assertIn(job.get('status'), {'canceled', 'pending', 'running', 'error'})

    def test_media_video_supports_range_requests_for_safari(self):
        # Safari/iOS requiere 206 (Range) para cargar metadata y permitir seek en <video>.
        media_url = self.video.video.url
        self.assertTrue(media_url.startswith('/media/'))

        response = self.client.get(media_url, HTTP_RANGE='bytes=0-99')
        self.assertEqual(response.status_code, 206)
        size = int(getattr(self.video.video, 'size', 0) or 0)
        self.assertGreater(size, 0)
        expected_end = min(99, size - 1)
        self.assertTrue(response.get('Content-Range', '').startswith(f'bytes 0-{expected_end}/'))
        self.assertEqual(int(response.get('Content-Length') or 0), (expected_end - 0) + 1)


class VideoStudioPersonalLibraryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='video-studio-personal',
            email='video-studio-personal@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        competition = Competition.objects.create(name='Liga VS Personal', slug='liga-vs-personal', region='Andalucia')
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name='Grupo VS Personal', slug='grupo-vs-personal')
        self.team = Team.objects.create(name='Equipo VS Personal', slug='equipo-vs-personal', group=group, is_primary=True)
        self.workspace = Workspace.objects.create(
            name='Workspace VS Personal',
            slug='workspace-vs-personal',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            enabled_modules={'analysis': True, 'dashboard': True},
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_ADMIN,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['active_workspace_id'] = self.workspace.id
        session['active_team_by_workspace'] = {str(self.workspace.id): int(self.team.id)}
        session.save()

        self.video = RivalVideo.objects.create(
            team=None,
            folder=None,
            owner_user=self.user,
            title='Personal clip',
            video=SimpleUploadedFile('clip.mp4', b'fake-video', content_type='video/mp4'),
            source=RivalVideo.SOURCE_MANUAL,
            notes='',
        )

    def test_personal_video_can_create_clip_timeline_project_and_assign_to_team(self):
        clip_save = self.client.post(
            reverse('analysis-video-studio-clip-save-api'),
            data=json.dumps(
                {
                    'video_id': self.video.id,
                    'title': 'Salida de 3',
                    'collection': 'Personal',
                    'in_s': 1.0,
                    'out_s': 2.0,
                    'overlay': {'objects': []},
                }
            ),
            content_type='application/json',
        )
        self.assertEqual(clip_save.status_code, 200)
        self.assertTrue(clip_save.json().get('ok'))
        self.assertTrue(VideoClip.objects.filter(video=self.video, team__isnull=True, owner_user=self.user).exists())

        ev_save = self.client.post(
            reverse('analysis-video-studio-timeline-save-api'),
            data=json.dumps({'video_id': self.video.id, 'time_s': 1.2, 'kind': 'tag', 'label': 'Marca', 'color': '#22d3ee'}),
            content_type='application/json',
        )
        self.assertEqual(ev_save.status_code, 200)
        self.assertTrue(ev_save.json().get('ok'))
        self.assertTrue(VideoTimelineEvent.objects.filter(video=self.video, team__isnull=True, owner_user=self.user).exists())

        proj_save = self.client.post(
            reverse('analysis-video-studio-project-save-api'),
            data=json.dumps({'video_id': self.video.id, 'title': 'Proyecto', 'payload': {'a': 1}}),
            content_type='application/json',
        )
        self.assertEqual(proj_save.status_code, 200)
        self.assertTrue(proj_save.json().get('ok'))
        self.assertTrue(VideoTelestrationProject.objects.filter(video=self.video, team__isnull=True, owner_user=self.user).exists())

        assign = self.client.post(
            reverse('analysis-video-studio-assign-api'),
            data=json.dumps({'video_id': self.video.id, 'team_id': self.team.id}),
            content_type='application/json',
        )
        self.assertEqual(assign.status_code, 200)
        self.assertTrue(assign.json().get('ok'))
        self.video.refresh_from_db()
        self.assertEqual(self.video.team_id, self.team.id)
        self.assertTrue(VideoClip.objects.filter(video=self.video, team=self.team).exists())
        self.assertTrue(VideoTimelineEvent.objects.filter(video=self.video, team=self.team).exists())
        self.assertTrue(VideoTelestrationProject.objects.filter(video=self.video, team=self.team).exists())
