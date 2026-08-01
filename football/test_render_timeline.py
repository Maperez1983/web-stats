from django.test import SimpleTestCase

from football.render_engine.timeline import (
    build_animation_object_tracks,
    build_animation_object_tracks_from_simulation_pro,
    summarize_animation_object_tracks,
)


class RenderTimelineTests(SimpleTestCase):
    def test_build_animation_object_tracks_derives_tracks_from_legacy_snapshots(self):
        frames = [
            {
                'title': 'Inicio',
                'duration': 3,
                'canvas_state': {
                    'version': '5.3.0',
                    'objects': [
                        {'type': 'circle', 'left': 100, 'top': 120, 'data': {'layer_uid': 'player-1', 'label': '8', 'kind': 'player'}},
                        {'type': 'triangle', 'left': 200, 'top': 220, 'data': {'layer_uid': 'cone-1', 'label': 'Cono', 'kind': 'cone'}},
                    ],
                },
            },
            {
                'title': 'Progresión',
                'duration': 4,
                'canvas_state': {
                    'version': '5.3.0',
                    'objects': [
                        {'type': 'circle', 'left': 150, 'top': 160, 'data': {'layer_uid': 'player-1', 'label': '8', 'kind': 'player'}},
                        {'type': 'triangle', 'left': 200, 'top': 220, 'data': {'layer_uid': 'cone-1', 'label': 'Cono', 'kind': 'cone'}},
                    ],
                },
            },
        ]

        tracks = build_animation_object_tracks(frames)
        summary = summarize_animation_object_tracks(tracks)

        self.assertEqual(len(tracks), 2)
        self.assertEqual(summary['track_count'], 2)
        self.assertEqual(summary['keyframe_count'], 4)
        self.assertEqual(summary['moving_track_count'], 1)

        player_track = next(track for track in tracks if track['uid'] == 'player-1')
        cone_track = next(track for track in tracks if track['uid'] == 'cone-1')
        self.assertEqual(player_track['label'], '8')
        self.assertEqual(player_track['keyframe_count'], 2)
        self.assertTrue(player_track['moving'])
        self.assertGreater(player_track['distance'], 0)
        self.assertEqual(cone_track['keyframe_count'], 2)
        self.assertFalse(cone_track['moving'])

    def test_build_animation_object_tracks_uses_stable_fallback_uid_when_missing(self):
        frames = [
            {
                'title': 'Base',
                'duration': 2,
                'canvas_state': {
                    'version': '5.3.0',
                    'objects': [
                        {'type': 'line', 'left': 20, 'top': 40},
                    ],
                },
            }
        ]

        tracks = build_animation_object_tracks(frames)

        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0]['uid'], 'line:0')
        self.assertEqual(tracks[0]['keyframe_count'], 1)

    def test_build_animation_object_tracks_from_simulation_pro_reads_real_keyframes(self):
        raw_pro = {
            'enabled': True,
            'loop': True,
            'tracks': {
                'player-8': [
                    {'t_ms': 0, 'easing': 'ease', 'props': {'left': 100, 'top': 120, 'angle': 0, 'scaleX': 1, 'scaleY': 1, 'opacity': 1}},
                    {'t_ms': 1200, 'easing': 'linear', 'props': {'left': 130, 'top': 150, 'angle': 12, 'scaleX': 1, 'scaleY': 1, 'opacity': 1}},
                ],
                'ball-1': [
                    {'t_ms': 500, 'easing': 'easeOut', 'props': {'left': 220, 'top': 190, 'angle': 0, 'scaleX': 1, 'scaleY': 1, 'opacity': 1}},
                ],
            },
        }

        tracks = build_animation_object_tracks_from_simulation_pro(raw_pro)
        summary = summarize_animation_object_tracks(tracks)

        self.assertEqual(summary['track_count'], 2)
        self.assertEqual(summary['keyframe_count'], 3)
        self.assertEqual(summary['moving_track_count'], 1)
        self.assertEqual(tracks[0]['uid'], 'player-8')
        self.assertEqual(tracks[0]['keyframe_count'], 2)
        self.assertTrue(tracks[0]['moving'])
