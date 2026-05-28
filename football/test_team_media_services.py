import base64
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from football import team_media_services
from football.models import Team, Workspace, WorkspaceTeam


class TeamCoverGuardrailTests(TestCase):
    @override_settings(MEDIA_URL='/media-test/')
    def test_cover_image_is_ignored_in_multi_team_when_missing_updated_at(self):
        png_bytes = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Zl4QAAAAASUVORK5CYII='
        )
        upload = SimpleUploadedFile('cover.png', png_bytes, content_type='image/png')
        media_root = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=media_root):
                team1 = Team.objects.create(name='Senior', slug='senior-cover-guard', short_name='Senior', is_primary=True)
                team1.cover_image = upload
                team1.save(update_fields=['cover_image'])
                team2 = Team.objects.create(name='Pre', slug='pre-cover-guard', short_name='Pre', is_primary=False)
                workspace = Workspace.objects.create(name='Club', slug='club-cover-guard', kind=Workspace.KIND_CLUB, primary_team=team1)
                WorkspaceTeam.objects.create(workspace=workspace, team=team1, is_default=True)
                WorkspaceTeam.objects.create(workspace=workspace, team=team2, is_default=False)

                self.assertFalse(team_media_services.should_use_team_cover_image(None, workspace, team1))
                team1.cover_updated_at = timezone.now()
                team1.save(update_fields=['cover_updated_at'])
                self.assertTrue(team_media_services.should_use_team_cover_image(None, workspace, team1))
        finally:
            shutil.rmtree(media_root, ignore_errors=True)

    @override_settings(MEDIA_URL='/media-test/')
    def test_cover_image_is_allowed_in_single_team_workspace_even_without_updated_at(self):
        png_bytes = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Zl4QAAAAASUVORK5CYII='
        )
        upload = SimpleUploadedFile('cover.png', png_bytes, content_type='image/png')
        media_root = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=media_root):
                team1 = Team.objects.create(name='Único', slug='unico-cover-guard', short_name='Único', is_primary=True)
                team1.cover_image = upload
                team1.save(update_fields=['cover_image'])
                workspace = Workspace.objects.create(name='Club único', slug='club-unico-cover-guard', kind=Workspace.KIND_CLUB, primary_team=team1)
                WorkspaceTeam.objects.create(workspace=workspace, team=team1, is_default=True)
                self.assertTrue(team_media_services.should_use_team_cover_image(None, workspace, team1))
        finally:
            shutil.rmtree(media_root, ignore_errors=True)
