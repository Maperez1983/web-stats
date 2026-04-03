import io

from django.test import SimpleTestCase


class PdfImportRecreateCanvasTests(SimpleTestCase):
    def test_recreate_detects_rect_outline_as_shape(self):
        try:
            from PIL import Image, ImageDraw
        except Exception:  # pragma: no cover
            self.skipTest("Pillow no disponible")

        from football.views import _recreate_canvas_state_from_preview_image_bytes

        # Green background + a grey rectangle outline + a grey arrow.
        img = Image.new("RGB", (900, 600), (40, 120, 40))
        draw = ImageDraw.Draw(img)
        draw.rectangle((240, 160, 520, 380), outline=(70, 70, 70), width=6)
        draw.line((120, 520, 360, 460), fill=(90, 90, 90), width=6)
        draw.polygon([(360, 460), (340, 454), (346, 474)], fill=(90, 90, 90))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw = buf.getvalue()

        state = _recreate_canvas_state_from_preview_image_bytes(raw, canvas_width=1054, canvas_height=684) or {}
        objects = state.get("objects") or []
        kinds = {((obj.get("data") or {}).get("kind") if isinstance(obj, dict) else None) for obj in objects}

        self.assertIn("shape-rect", kinds)
        self.assertIn("arrow", kinds)

