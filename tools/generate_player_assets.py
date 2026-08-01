#!/usr/bin/env python3
from __future__ import annotations

import base64
import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import svgwrite
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "football" / "assets_library" / "players" / "premium"
SOURCE_DIR = ASSET_ROOT / "source"
SVG_DIR = ASSET_ROOT / "svg"
PNG_DIR = ASSET_ROOT / "png"
PREVIEW_DIR = ASSET_ROOT / "previews"
MODULAR_DIR = ASSET_ROOT / "modular"
TMP_HTML = ROOT / "tmp" / "player_assets_preview.html"
TMP_FRONT_V2_HTML = ROOT / "tmp" / "player_front_v2_preview.html"
TMP_FRONT_V3_HTML = ROOT / "tmp" / "comparison_v2_vs_v3.html"
TMP_MODULAR_HTML = ROOT / "tmp" / "player_modular_parts_preview.html"
DOWNLOADS_HTML = Path("/Volumes/Mac Satecchi/Mac/Downloads/player_assets_preview.html")

CANVAS_W = 512
CANVAS_H = 512
GROUND_Y = 436

KIT = {
    "shirt_primary": "#1563e8",
    "shirt_secondary": "#0f4fb7",
    "trim": "#ffffff",
    "shorts": "#111827",
    "shorts_light": "#283548",
    "socks": "#eef2ff",
    "sock_band": "#2b60d7",
    "boots": "#101216",
    "skin": "#e0b08b",
    "skin_shadow": "#bd8a64",
    "hair": "#261813",
    "hair_gloss": "#4b342d",
    "shadow": "#172033",
    "outline": "#0a0d12",
    "number": "#f9fafb",
    "number_shadow": "#0f172a",
}


@dataclass
class Pose:
    name: str
    body_tilt: float
    head_turn: float
    left_arm: float
    right_arm: float
    left_forearm: float
    right_forearm: float
    left_thigh: float
    right_thigh: float
    left_shin: float
    right_shin: float
    hip_shift: float = 0.0
    shoulder_shift: float = 0.0
    stride: float = 0.0
    support_bias: float = 0.0
    facing: int = 1
    number: str = "10"


@dataclass(frozen=True)
class FrontVariantChoice:
    head: Dict[str, float]
    torso: Dict[str, float]
    shorts: Dict[str, float]


POSES: Sequence[Pose] = (
    Pose("player_front", body_tilt=-4, head_turn=-3, left_arm=16, right_arm=-15, left_forearm=7, right_forearm=-8, left_thigh=7, right_thigh=-8, left_shin=-4, right_shin=2, number="10"),
    Pose("player_front_v2", body_tilt=-4, head_turn=-3, left_arm=16, right_arm=-15, left_forearm=7, right_forearm=-8, left_thigh=7, right_thigh=-8, left_shin=-4, right_shin=2, number="10"),
    Pose("player_front_v3", body_tilt=-2, head_turn=-2, left_arm=10, right_arm=-8, left_forearm=5, right_forearm=-4, left_thigh=2, right_thigh=-2, left_shin=0, right_shin=1, number="10"),
    Pose("player_back", body_tilt=3, head_turn=2, left_arm=10, right_arm=-8, left_forearm=2, right_forearm=-1, left_thigh=4, right_thigh=-5, left_shin=0, right_shin=3, number="10"),
    Pose("player_side_left", body_tilt=-8, head_turn=-12, left_arm=26, right_arm=-22, left_forearm=10, right_forearm=-9, left_thigh=19, right_thigh=-10, left_shin=-14, right_shin=12, stride=6, facing=-1, number="7"),
    Pose("player_side_right", body_tilt=8, head_turn=12, left_arm=22, right_arm=-24, left_forearm=8, right_forearm=-10, left_thigh=11, right_thigh=-17, left_shin=-10, right_shin=14, stride=6, facing=1, number="11"),
    Pose("player_run", body_tilt=-16, head_turn=-8, left_arm=48, right_arm=-52, left_forearm=30, right_forearm=-28, left_thigh=42, right_thigh=-36, left_shin=-54, right_shin=36, hip_shift=8, shoulder_shift=-4, stride=12, support_bias=-10, number="8"),
    Pose("player_pass", body_tilt=-10, head_turn=-5, left_arm=28, right_arm=-18, left_forearm=18, right_forearm=-8, left_thigh=14, right_thigh=-62, left_shin=-12, right_shin=70, hip_shift=6, shoulder_shift=-2, stride=16, support_bias=-6, number="6"),
    Pose("player_defend", body_tilt=-4, head_turn=4, left_arm=58, right_arm=-55, left_forearm=22, right_forearm=-18, left_thigh=28, right_thigh=-22, left_shin=-18, right_shin=18, hip_shift=0, shoulder_shift=0, stride=10, support_bias=-2, number="4"),
)


def ensure_dirs() -> None:
    for path in (SOURCE_DIR, SVG_DIR, PNG_DIR, PREVIEW_DIR, MODULAR_DIR, TMP_HTML.parent):
        path.mkdir(parents=True, exist_ok=True)


def deg_to_rad(value: float) -> float:
    return value * math.pi / 180.0


def rotate_point(px: float, py: float, ox: float, oy: float, deg: float) -> Tuple[float, float]:
    rad = deg_to_rad(deg)
    cos_v = math.cos(rad)
    sin_v = math.sin(rad)
    dx = px - ox
    dy = py - oy
    return (ox + dx * cos_v - dy * sin_v, oy + dx * sin_v + dy * cos_v)


def points_to_str(points: Iterable[Tuple[float, float]]) -> List[Tuple[float, float]]:
    return [(round(x, 2), round(y, 2)) for x, y in points]


def add_gradient(dwg: svgwrite.Drawing, gradient_id: str, colors: Sequence[Tuple[str, float]]) -> str:
    grad = dwg.linearGradient(id=gradient_id, start=("0%", "0%"), end=("0%", "100%"))
    for color, offset in colors:
        grad.add_stop_color(offset=f"{offset:.0%}", color=color)
    dwg.defs.add(grad)
    return f"url(#{gradient_id})"


def quad_path(points: Sequence[Tuple[float, float]]) -> str:
    start = points[0]
    cmds = [f"M {start[0]:.2f} {start[1]:.2f}"]
    for i in range(1, len(points), 2):
        if i + 1 < len(points):
            c = points[i]
            p = points[i + 1]
            cmds.append(f"Q {c[0]:.2f} {c[1]:.2f} {p[0]:.2f} {p[1]:.2f}")
    cmds.append("Z")
    return " ".join(cmds)


class PremiumPlayerAssetBuilder:
    def __init__(self, pose: Pose):
        self.pose = pose
        self.dwg = svgwrite.Drawing(size=(CANVAS_W, CANVAS_H), viewBox=f"0 0 {CANVAS_W} {CANVAS_H}")
        self.front_variant = self._select_front_variant() if pose.name in {"player_front", "player_front_v2", "player_front_v3"} else None
        self.shirt_fill = add_gradient(
            self.dwg,
            f"{pose.name}-shirt",
            ((KIT["shirt_secondary"], 0.0), (KIT["shirt_primary"], 0.45), ("#208bff", 1.0)),
        )
        self.shorts_fill = add_gradient(
            self.dwg,
            f"{pose.name}-shorts",
            ((KIT["shorts_light"], 0.0), (KIT["shorts"], 1.0)),
        )
        self.skin_fill = add_gradient(
            self.dwg,
            f"{pose.name}-skin",
            ((KIT["skin"], 0.0), (KIT["skin_shadow"], 1.0)),
        )
        self.socks_fill = add_gradient(
            self.dwg,
            f"{pose.name}-socks",
            ((KIT["trim"], 0.0), (KIT["socks"], 1.0)),
        )

    def draw(self) -> svgwrite.Drawing:
        self._draw_background()
        if self.pose.name == "player_front":
            self._draw_front_shadow()
            self._draw_front_player_premium()
            return self.dwg
        if self.pose.name == "player_front_v2":
            self._draw_front_shadow_v2()
            self._draw_front_player_premium_v2()
            return self.dwg
        if self.pose.name == "player_front_v3":
            self._draw_front_shadow_v3()
            self._draw_front_player_premium_v3()
            return self.dwg
        self._draw_shadow()
        if self.pose.facing == -1:
            self._draw_player(back=False, side=True, flip=True)
        elif self.pose.name == "player_back":
            self._draw_player(back=True, side=False, flip=False)
        elif "side" in self.pose.name:
            self._draw_player(back=False, side=True, flip=False)
        else:
            self._draw_player(back=False, side=False, flip=False)
        return self.dwg

    def _draw_background(self) -> None:
        self.dwg.add(self.dwg.rect(insert=(0, 0), size=(CANVAS_W, CANVAS_H), fill="none"))

    def _draw_shadow(self) -> None:
        cx = CANVAS_W / 2 + self.pose.hip_shift * 0.8
        cy = GROUND_Y + 18
        rx = 92 + abs(self.pose.stride) * 0.8
        ry = 28
        self.dwg.add(
            self.dwg.ellipse(
                center=(cx, cy),
                r=(rx, ry),
                fill=KIT["shadow"],
                opacity=0.18,
            )
        )

    def draw_wireframe(self) -> svgwrite.Drawing:
        wire = svgwrite.Drawing(size=(CANVAS_W, CANVAS_H), viewBox=f"0 0 {CANVAS_W} {CANVAS_H}")
        wire.add(wire.rect(insert=(0, 0), size=(CANVAS_W, CANVAS_H), fill="#ffffff"))
        if self.pose.name not in {"player_front", "player_front_v2", "player_front_v3"}:
            return wire
        palette = {
            "head": "#1d4ed8",
            "hair": "#0f172a",
            "neck": "#7c3aed",
            "torso": "#059669",
            "arms": "#ea580c",
            "shorts": "#dc2626",
            "legs": "#16a34a",
            "socks": "#0891b2",
            "boots": "#111827",
            "shadow": "#94a3b8",
        }
        if self.pose.name == "player_front":
            front_shapes = self._front_shape_layers()
        elif self.pose.name == "player_front_v2":
            front_shapes = self._front_shape_layers_v2()
        else:
            front_shapes = self._front_shape_layers_v3()
        for shape in front_shapes:
            if shape["name"] == "shadow":
                wire.add(wire.ellipse(center=shape["ellipse"][:2], r=shape["ellipse"][2:], fill="none", stroke=palette["shadow"], stroke_width=2))
                continue
            color = palette.get(shape["name"].split("_")[0], "#334155")
            if shape["kind"] == "path":
                wire.add(wire.path(d=shape["d"], fill="none", stroke=color, stroke_width=2.2, stroke_linejoin="round", stroke_linecap="round"))
            for px, py in shape.get("points", []):
                wire.add(wire.circle(center=(px, py), r=2.8, fill=color))
        return wire

    def _select_front_variant(self) -> FrontVariantChoice:
        head_options = (
            {"name": "compact", "head_w": 33, "head_h": 39, "jaw_w": 25, "chin_drop": 5, "temple_inset": 7, "crown_rise": 4},
            {"name": "balanced", "head_w": 34, "head_h": 40, "jaw_w": 26, "chin_drop": 5, "temple_inset": 6, "crown_rise": 4},
            {"name": "heroic", "head_w": 35, "head_h": 40, "jaw_w": 28, "chin_drop": 4, "temple_inset": 5, "crown_rise": 3},
        )
        torso_options = (
            {"name": "narrow", "shoulder_w": 136, "waist_w": 78, "hem_w": 88, "torso_h": 122, "sleeve_drop": 20},
            {"name": "balanced", "shoulder_w": 146, "waist_w": 82, "hem_w": 94, "torso_h": 124, "sleeve_drop": 22},
            {"name": "broad", "shoulder_w": 154, "waist_w": 86, "hem_w": 98, "torso_h": 124, "sleeve_drop": 24},
        )
        shorts_options = (
            {"name": "trim", "waist_w": 80, "hip_w": 98, "hem_w": 90, "drop": 50, "crotch_drop": 20},
            {"name": "balanced", "waist_w": 84, "hip_w": 104, "hem_w": 94, "drop": 52, "crotch_drop": 21},
            {"name": "wide", "waist_w": 88, "hip_w": 108, "hem_w": 98, "drop": 54, "crotch_drop": 22},
        )
        target = {
            "head_ratio": 0.84,
            "jaw_ratio": 0.78,
            "shoulder_ratio": 1.92,
            "waist_taper": 0.60,
            "shorts_ratio": 1.19,
            "drop_ratio": 0.41,
        }
        best_score = None
        best_choice = None
        for head in head_options:
            for torso in torso_options:
                for shorts in shorts_options:
                    head_ratio = head["head_w"] / head["head_h"]
                    jaw_ratio = head["jaw_w"] / head["head_w"]
                    shoulder_ratio = torso["shoulder_w"] / head["head_w"]
                    waist_taper = torso["waist_w"] / torso["shoulder_w"]
                    shorts_ratio = shorts["hip_w"] / shorts["waist_w"]
                    drop_ratio = shorts["drop"] / torso["torso_h"]
                    score = sum(
                        abs(metric - target[name])
                        for name, metric in (
                            ("head_ratio", head_ratio),
                            ("jaw_ratio", jaw_ratio),
                            ("shoulder_ratio", shoulder_ratio),
                            ("waist_taper", waist_taper),
                            ("shorts_ratio", shorts_ratio),
                            ("drop_ratio", drop_ratio),
                        )
                    )
                    if best_score is None or score < best_score:
                        best_score = score
                        best_choice = FrontVariantChoice(head=head, torso=torso, shorts=shorts)
        assert best_choice is not None
        return best_choice

    def _draw_front_shadow(self) -> None:
        self.dwg.add(
            self.dwg.ellipse(
                center=(256, 452),
                r=(78, 18),
                fill=KIT["shadow"],
                opacity=0.16,
            )
        )

    def _draw_front_shadow_v2(self) -> None:
        self.dwg.add(
            self.dwg.ellipse(
                center=(256, 454),
                r=(74, 16),
                fill=KIT["shadow"],
                opacity=0.14,
            )
        )

    def _draw_front_shadow_v3(self) -> None:
        self.dwg.add(
            self.dwg.ellipse(
                center=(256, 456),
                r=(70, 15),
                fill=KIT["shadow"],
                opacity=0.13,
            )
        )

    def _front_shape_layers(self) -> List[Dict[str, object]]:
        assert self.front_variant is not None
        head_v = self.front_variant.head
        torso_v = self.front_variant.torso
        shorts_v = self.front_variant.shorts
        cx = 256
        head_cy = 94
        chin_y = head_cy + head_v["head_h"] - 5
        neck_top_y = 130
        shoulder_y = 144
        hem_y = shoulder_y + torso_v["torso_h"]
        shorts_top_y = hem_y - 5
        shorts_bottom_y = shorts_top_y + shorts_v["drop"]
        knee_y = 350
        ankle_y = 420
        foot_y = 437

        head_left = cx - head_v["head_w"]
        head_right = cx + head_v["head_w"]
        jaw_left = cx - head_v["jaw_w"]
        jaw_right = cx + head_v["jaw_w"]
        temple_left = cx - head_v["head_w"] + head_v["temple_inset"]
        temple_right = cx + head_v["head_w"] - head_v["temple_inset"]
        crown_y = head_cy - head_v["head_h"] - head_v["crown_rise"]

        shoulder_left = cx - torso_v["shoulder_w"] / 2
        shoulder_right = cx + torso_v["shoulder_w"] / 2
        waist_left = cx - torso_v["waist_w"] / 2
        waist_right = cx + torso_v["waist_w"] / 2
        hem_left = cx - torso_v["hem_w"] / 2
        hem_right = cx + torso_v["hem_w"] / 2

        shorts_waist_left = cx - shorts_v["waist_w"] / 2
        shorts_waist_right = cx + shorts_v["waist_w"] / 2
        shorts_hip_left = cx - shorts_v["hip_w"] / 2
        shorts_hip_right = cx + shorts_v["hip_w"] / 2
        shorts_hem_left = cx - shorts_v["hem_w"] / 2
        shorts_hem_right = cx + shorts_v["hem_w"] / 2
        crotch_y = shorts_bottom_y - shorts_v["crotch_drop"]

        left_leg_outer = cx - 41
        left_leg_inner = cx - 16
        right_leg_outer = cx + 41
        right_leg_inner = cx + 16
        left_sock_outer = cx - 36
        left_sock_inner = cx - 17
        right_sock_outer = cx + 36
        right_sock_inner = cx + 17

        head_d = (
            f"M {cx:.2f} {chin_y:.2f} "
            f"C {jaw_left + 7:.2f} {chin_y + 1:.2f}, {head_left + 2:.2f} {head_cy + 15:.2f}, {temple_left:.2f} {head_cy - 4:.2f} "
            f"C {head_left - 3:.2f} {head_cy - 24:.2f}, {cx - 20:.2f} {crown_y + 9:.2f}, {cx:.2f} {crown_y:.2f} "
            f"C {cx + 20:.2f} {crown_y + 9:.2f}, {head_right + 3:.2f} {head_cy - 24:.2f}, {temple_right:.2f} {head_cy - 4:.2f} "
            f"C {head_right - 2:.2f} {head_cy + 15:.2f}, {jaw_right - 7:.2f} {chin_y + 1:.2f}, {cx:.2f} {chin_y:.2f} Z"
        )
        hair_d = (
            f"M {temple_left + 2:.2f} {head_cy - 8:.2f} "
            f"C {head_left + 2:.2f} {head_cy - 30:.2f}, {cx - 19:.2f} {crown_y + 5:.2f}, {cx:.2f} {crown_y + 2:.2f} "
            f"C {cx + 18:.2f} {crown_y + 4:.2f}, {head_right - 2:.2f} {head_cy - 28:.2f}, {temple_right - 2:.2f} {head_cy - 8:.2f} "
            f"C {cx + 17:.2f} {head_cy - 2:.2f}, {cx + 7:.2f} {head_cy + 5:.2f}, {cx:.2f} {head_cy + 1:.2f} "
            f"C {cx - 7:.2f} {head_cy + 5:.2f}, {cx - 17:.2f} {head_cy - 2:.2f}, {temple_left + 2:.2f} {head_cy - 8:.2f} Z"
        )
        neck_d = (
            f"M {cx - 12:.2f} {neck_top_y:.2f} "
            f"C {cx - 12:.2f} {neck_top_y + 5:.2f}, {cx - 11:.2f} {shoulder_y - 1:.2f}, {cx - 11:.2f} {shoulder_y + 5:.2f} "
            f"L {cx + 11:.2f} {shoulder_y + 5:.2f} "
            f"C {cx + 11:.2f} {shoulder_y - 1:.2f}, {cx + 12:.2f} {neck_top_y + 5:.2f}, {cx + 12:.2f} {neck_top_y:.2f} "
            f"C {cx + 8:.2f} {neck_top_y - 3:.2f}, {cx - 8:.2f} {neck_top_y - 3:.2f}, {cx - 12:.2f} {neck_top_y:.2f} Z"
        )
        torso_d = (
            f"M {cx - 24:.2f} {shoulder_y - 10:.2f} "
            f"C {shoulder_left + 28:.2f} {shoulder_y - 8:.2f}, {shoulder_left + 4:.2f} {shoulder_y + 2:.2f}, {shoulder_left:.2f} {shoulder_y + torso_v['sleeve_drop']:.2f} "
            f"C {shoulder_left + 5:.2f} {shoulder_y + 42:.2f}, {waist_left - 9:.2f} {hem_y - 42:.2f}, {waist_left:.2f} {hem_y - 10:.2f} "
            f"C {hem_left + 12:.2f} {hem_y + 4:.2f}, {cx - 24:.2f} {hem_y + 7:.2f}, {cx:.2f} {hem_y + 8:.2f} "
            f"C {cx + 24:.2f} {hem_y + 7:.2f}, {hem_right - 12:.2f} {hem_y + 4:.2f}, {waist_right:.2f} {hem_y - 10:.2f} "
            f"C {waist_right + 9:.2f} {hem_y - 42:.2f}, {shoulder_right - 5:.2f} {shoulder_y + 42:.2f}, {shoulder_right:.2f} {shoulder_y + torso_v['sleeve_drop']:.2f} "
            f"C {shoulder_right - 4:.2f} {shoulder_y + 2:.2f}, {shoulder_right - 28:.2f} {shoulder_y - 8:.2f}, {cx + 24:.2f} {shoulder_y - 10:.2f} "
            f"C {cx + 12:.2f} {shoulder_y - 1:.2f}, {cx - 12:.2f} {shoulder_y - 1:.2f}, {cx - 24:.2f} {shoulder_y - 10:.2f} Z"
        )
        left_arm_d = (
            f"M {shoulder_left + 18:.2f} {shoulder_y + 20:.2f} "
            f"C {shoulder_left - 10:.2f} {shoulder_y + 49:.2f}, {shoulder_left - 16:.2f} {shoulder_y + 90:.2f}, {shoulder_left - 3:.2f} {shoulder_y + 121:.2f} "
            f"C {shoulder_left + 5:.2f} {shoulder_y + 142:.2f}, {shoulder_left + 18:.2f} {shoulder_y + 163:.2f}, {shoulder_left + 34:.2f} {shoulder_y + 178:.2f} "
            f"C {shoulder_left + 42:.2f} {shoulder_y + 184:.2f}, {shoulder_left + 50:.2f} {shoulder_y + 181:.2f}, {shoulder_left + 54:.2f} {shoulder_y + 173:.2f} "
            f"C {shoulder_left + 49:.2f} {shoulder_y + 153:.2f}, {shoulder_left + 40:.2f} {shoulder_y + 131:.2f}, {shoulder_left + 35:.2f} {shoulder_y + 107:.2f} "
            f"C {shoulder_left + 32:.2f} {shoulder_y + 82:.2f}, {shoulder_left + 35:.2f} {shoulder_y + 60:.2f}, {shoulder_left + 45:.2f} {shoulder_y + 33:.2f} "
            f"C {shoulder_left + 39:.2f} {shoulder_y + 24:.2f}, {shoulder_left + 28:.2f} {shoulder_y + 18:.2f}, {shoulder_left + 18:.2f} {shoulder_y + 20:.2f} Z"
        )
        right_arm_d = (
            f"M {shoulder_right - 18:.2f} {shoulder_y + 20:.2f} "
            f"C {shoulder_right + 10:.2f} {shoulder_y + 49:.2f}, {shoulder_right + 16:.2f} {shoulder_y + 90:.2f}, {shoulder_right + 3:.2f} {shoulder_y + 121:.2f} "
            f"C {shoulder_right - 5:.2f} {shoulder_y + 142:.2f}, {shoulder_right - 18:.2f} {shoulder_y + 163:.2f}, {shoulder_right - 34:.2f} {shoulder_y + 178:.2f} "
            f"C {shoulder_right - 42:.2f} {shoulder_y + 184:.2f}, {shoulder_right - 50:.2f} {shoulder_y + 181:.2f}, {shoulder_right - 54:.2f} {shoulder_y + 173:.2f} "
            f"C {shoulder_right - 49:.2f} {shoulder_y + 153:.2f}, {shoulder_right - 40:.2f} {shoulder_y + 131:.2f}, {shoulder_right - 35:.2f} {shoulder_y + 107:.2f} "
            f"C {shoulder_right - 32:.2f} {shoulder_y + 82:.2f}, {shoulder_right - 35:.2f} {shoulder_y + 60:.2f}, {shoulder_right - 45:.2f} {shoulder_y + 33:.2f} "
            f"C {shoulder_right - 39:.2f} {shoulder_y + 24:.2f}, {shoulder_right - 28:.2f} {shoulder_y + 18:.2f}, {shoulder_right - 18:.2f} {shoulder_y + 20:.2f} Z"
        )
        shorts_d = (
            f"M {shorts_waist_left:.2f} {shorts_top_y:.2f} "
            f"C {shorts_hip_left + 10:.2f} {shorts_top_y + 5:.2f}, {shorts_hip_left - 14:.2f} {shorts_top_y + 20:.2f}, {shorts_hem_left - 2:.2f} {shorts_bottom_y - 15:.2f} "
            f"C {shorts_hem_left - 1:.2f} {shorts_bottom_y - 3:.2f}, {cx - 47:.2f} {shorts_bottom_y + 1:.2f}, {cx - 29:.2f} {shorts_bottom_y - 1:.2f} "
            f"C {cx - 20:.2f} {shorts_bottom_y - 8:.2f}, {cx - 14:.2f} {crotch_y + 2:.2f}, {cx - 9:.2f} {crotch_y + 8:.2f} "
            f"C {cx - 4:.2f} {crotch_y + 14:.2f}, {cx + 4:.2f} {crotch_y + 14:.2f}, {cx + 9:.2f} {crotch_y + 8:.2f} "
            f"C {cx + 14:.2f} {crotch_y + 2:.2f}, {cx + 20:.2f} {shorts_bottom_y - 8:.2f}, {cx + 29:.2f} {shorts_bottom_y - 1:.2f} "
            f"C {cx + 47:.2f} {shorts_bottom_y + 1:.2f}, {shorts_hem_right + 1:.2f} {shorts_bottom_y - 3:.2f}, {shorts_hem_right + 2:.2f} {shorts_bottom_y - 15:.2f} "
            f"C {shorts_hip_right + 14:.2f} {shorts_top_y + 20:.2f}, {shorts_hip_right - 10:.2f} {shorts_top_y + 5:.2f}, {shorts_waist_right:.2f} {shorts_top_y:.2f} "
            f"C {cx + 30:.2f} {shorts_top_y - 8:.2f}, {cx - 30:.2f} {shorts_top_y - 8:.2f}, {shorts_waist_left:.2f} {shorts_top_y:.2f} Z"
        )
        left_thigh_d = (
            f"M {cx - 22:.2f} {shorts_bottom_y - 4:.2f} "
            f"C {left_leg_outer:.2f} {shorts_bottom_y + 8:.2f}, {left_leg_outer - 1:.2f} {knee_y - 19:.2f}, {left_leg_outer + 2:.2f} {knee_y - 2:.2f} "
            f"C {left_leg_outer + 5:.2f} {knee_y + 12:.2f}, {left_leg_inner + 6:.2f} {knee_y + 10:.2f}, {left_leg_inner + 2:.2f} {knee_y - 2:.2f} "
            f"C {left_leg_inner - 2:.2f} {knee_y - 20:.2f}, {left_leg_inner - 4:.2f} {shorts_bottom_y + 13:.2f}, {cx - 8:.2f} {shorts_bottom_y - 5:.2f} Z"
        )
        right_thigh_d = (
            f"M {cx + 22:.2f} {shorts_bottom_y - 4:.2f} "
            f"C {right_leg_outer:.2f} {shorts_bottom_y + 8:.2f}, {right_leg_outer + 1:.2f} {knee_y - 19:.2f}, {right_leg_outer - 2:.2f} {knee_y - 2:.2f} "
            f"C {right_leg_outer - 5:.2f} {knee_y + 12:.2f}, {right_leg_inner - 6:.2f} {knee_y + 10:.2f}, {right_leg_inner - 2:.2f} {knee_y - 2:.2f} "
            f"C {right_leg_inner + 2:.2f} {knee_y - 20:.2f}, {right_leg_inner + 4:.2f} {shorts_bottom_y + 13:.2f}, {cx + 8:.2f} {shorts_bottom_y - 5:.2f} Z"
        )
        left_sock_d = (
            f"M {left_leg_outer + 1:.2f} {knee_y - 1:.2f} "
            f"C {left_sock_outer - 1:.2f} {knee_y + 24:.2f}, {left_sock_outer + 1:.2f} {ankle_y - 18:.2f}, {left_sock_outer + 3:.2f} {ankle_y:.2f} "
            f"C {left_sock_inner + 3:.2f} {ankle_y + 6:.2f}, {left_sock_inner - 1:.2f} {ankle_y + 6:.2f}, {left_sock_inner:.2f} {ankle_y - 2:.2f} "
            f"C {left_sock_inner - 2:.2f} {ankle_y - 20:.2f}, {left_sock_inner - 1:.2f} {knee_y + 18:.2f}, {left_leg_inner + 1:.2f} {knee_y - 1:.2f} Z"
        )
        right_sock_d = (
            f"M {right_leg_outer - 1:.2f} {knee_y - 1:.2f} "
            f"C {right_sock_outer + 1:.2f} {knee_y + 24:.2f}, {right_sock_outer - 1:.2f} {ankle_y - 18:.2f}, {right_sock_outer - 3:.2f} {ankle_y:.2f} "
            f"C {right_sock_inner - 3:.2f} {ankle_y + 6:.2f}, {right_sock_inner + 1:.2f} {ankle_y + 6:.2f}, {right_sock_inner:.2f} {ankle_y - 2:.2f} "
            f"C {right_sock_inner + 2:.2f} {ankle_y - 20:.2f}, {right_sock_inner + 1:.2f} {knee_y + 18:.2f}, {right_leg_inner - 1:.2f} {knee_y - 1:.2f} Z"
        )
        left_boot_d = (
            f"M {left_sock_outer + 1:.2f} {ankle_y - 3:.2f} "
            f"C {left_sock_outer - 6:.2f} {foot_y - 5:.2f}, {left_sock_outer - 3:.2f} {foot_y + 5:.2f}, {left_sock_outer + 10:.2f} {foot_y + 7:.2f} "
            f"C {left_sock_outer + 24:.2f} {foot_y + 8:.2f}, {left_sock_outer + 38:.2f} {foot_y + 4:.2f}, {left_sock_outer + 42:.2f} {foot_y - 2:.2f} "
            f"C {left_sock_outer + 40:.2f} {foot_y - 7:.2f}, {left_sock_outer + 31:.2f} {foot_y - 10:.2f}, {left_sock_outer + 18:.2f} {foot_y - 10:.2f} "
            f"C {left_sock_outer + 12:.2f} {foot_y - 11:.2f}, {left_sock_outer + 8:.2f} {foot_y - 9:.2f}, {left_sock_inner + 1:.2f} {ankle_y - 5:.2f} "
            f"C {left_sock_inner + 1:.2f} {ankle_y - 4:.2f}, {left_sock_outer - 1:.2f} {ankle_y - 3:.2f}, {left_sock_outer + 1:.2f} {ankle_y - 3:.2f} Z"
        )
        right_boot_d = (
            f"M {right_sock_outer - 1:.2f} {ankle_y - 3:.2f} "
            f"C {right_sock_outer + 6:.2f} {foot_y - 5:.2f}, {right_sock_outer + 3:.2f} {foot_y + 5:.2f}, {right_sock_outer - 10:.2f} {foot_y + 7:.2f} "
            f"C {right_sock_outer - 24:.2f} {foot_y + 8:.2f}, {right_sock_outer - 38:.2f} {foot_y + 4:.2f}, {right_sock_outer - 42:.2f} {foot_y - 2:.2f} "
            f"C {right_sock_outer - 40:.2f} {foot_y - 7:.2f}, {right_sock_outer - 31:.2f} {foot_y - 10:.2f}, {right_sock_outer - 18:.2f} {foot_y - 10:.2f} "
            f"C {right_sock_outer - 12:.2f} {foot_y - 11:.2f}, {right_sock_outer - 8:.2f} {foot_y - 9:.2f}, {right_sock_inner - 1:.2f} {ankle_y - 5:.2f} "
            f"C {right_sock_inner - 1:.2f} {ankle_y - 4:.2f}, {right_sock_outer + 1:.2f} {ankle_y - 3:.2f}, {right_sock_outer - 1:.2f} {ankle_y - 3:.2f} Z"
        )
        shirt_shadow_d = (
            f"M {cx - 52:.2f} {shoulder_y + 18:.2f} "
            f"C {cx - 36:.2f} {shoulder_y + 52:.2f}, {cx - 33:.2f} {hem_y - 12:.2f}, {cx - 9:.2f} {hem_y - 2:.2f} "
            f"C {cx - 5:.2f} {hem_y - 16:.2f}, {cx - 16:.2f} {shoulder_y + 22:.2f}, {cx - 52:.2f} {shoulder_y + 18:.2f} Z"
        )
        shorts_shadow_d = (
            f"M {cx - 13:.2f} {shorts_top_y + 5:.2f} "
            f"C {cx - 5:.2f} {shorts_top_y + 24:.2f}, {cx - 2:.2f} {shorts_bottom_y - 6:.2f}, {cx:.2f} {shorts_bottom_y + 4:.2f} "
            f"C {cx + 5:.2f} {shorts_bottom_y - 6:.2f}, {cx + 5:.2f} {shorts_top_y + 24:.2f}, {cx + 13:.2f} {shorts_top_y + 5:.2f} Z"
        )
        leg_shadow_left_d = (
            f"M {cx - 18:.2f} {shorts_bottom_y + 2:.2f} "
            f"C {cx - 14:.2f} {knee_y - 16:.2f}, {cx - 14:.2f} {ankle_y - 24:.2f}, {cx - 18:.2f} {ankle_y - 4:.2f}"
        )
        leg_shadow_right_d = (
            f"M {cx + 18:.2f} {shorts_bottom_y + 2:.2f} "
            f"C {cx + 14:.2f} {knee_y - 16:.2f}, {cx + 14:.2f} {ankle_y - 24:.2f}, {cx + 18:.2f} {ankle_y - 4:.2f}"
        )
        collar_outer_d = (
            f"M {cx - 18:.2f} {shoulder_y - 2:.2f} "
            f"Q {cx:.2f} {shoulder_y + 10:.2f} {cx + 18:.2f} {shoulder_y - 2:.2f}"
        )
        collar_inner_d = (
            f"M {cx - 12:.2f} {shoulder_y + 1:.2f} "
            f"Q {cx:.2f} {shoulder_y + 8:.2f} {cx + 12:.2f} {shoulder_y + 1:.2f}"
        )

        return [
            {"name": "shadow", "kind": "ellipse", "ellipse": (256, 452, 78, 18)},
            {"name": "left_thigh", "kind": "path", "d": left_thigh_d, "points": [(cx - 20, shorts_bottom_y - 6), (left_leg_outer + 4, knee_y), (left_leg_inner, knee_y - 1)]},
            {"name": "right_thigh", "kind": "path", "d": right_thigh_d, "points": [(cx + 20, shorts_bottom_y - 6), (right_leg_outer - 4, knee_y), (right_leg_inner, knee_y - 1)]},
            {"name": "left_sock", "kind": "path", "d": left_sock_d, "points": [(left_leg_outer + 3, knee_y - 2), (left_sock_outer + 4, ankle_y), (left_sock_inner, ankle_y - 1)]},
            {"name": "right_sock", "kind": "path", "d": right_sock_d, "points": [(right_leg_outer - 3, knee_y - 2), (right_sock_outer - 4, ankle_y), (right_sock_inner, ankle_y - 1)]},
            {"name": "left_boot", "kind": "path", "d": left_boot_d, "points": [(left_sock_outer + 1, ankle_y - 2), (left_sock_outer + 40, foot_y - 3)]},
            {"name": "right_boot", "kind": "path", "d": right_boot_d, "points": [(right_sock_outer - 1, ankle_y - 2), (right_sock_outer - 40, foot_y - 3)]},
            {"name": "left_arm", "kind": "path", "d": left_arm_d, "points": [(shoulder_left + 6, shoulder_y + 20), (shoulder_left + 1, shoulder_y + 113), (shoulder_left + 51, shoulder_y + 160)]},
            {"name": "right_arm", "kind": "path", "d": right_arm_d, "points": [(shoulder_right - 6, shoulder_y + 20), (shoulder_right - 1, shoulder_y + 113), (shoulder_right - 51, shoulder_y + 160)]},
            {"name": "torso", "kind": "path", "d": torso_d, "points": [(cx - 24, shoulder_y - 8), (shoulder_left, shoulder_y + torso_v["sleeve_drop"]), (waist_left, hem_y - 9), (cx, hem_y + 4)]},
            {"name": "shirt_shadow", "kind": "path", "d": shirt_shadow_d, "points": [(cx - 48, shoulder_y + 18), (cx - 8, hem_y - 2)]},
            {"name": "shorts", "kind": "path", "d": shorts_d, "points": [(shorts_waist_left, shorts_top_y), (shorts_hem_left, shorts_bottom_y - 12), (cx, shorts_bottom_y + 6)]},
            {"name": "shorts_shadow", "kind": "path", "d": shorts_shadow_d, "points": [(cx - 12, shorts_top_y + 4), (cx, shorts_bottom_y + 2), (cx + 12, shorts_top_y + 4)]},
            {"name": "neck", "kind": "path", "d": neck_d, "points": [(cx - 15, neck_top_y), (cx - 10, shoulder_y + 7), (cx + 15, neck_top_y)]},
            {"name": "head", "kind": "path", "d": head_d, "points": [(cx, chin_y), (temple_left, head_cy - 6), (cx, crown_y), (temple_right, head_cy - 6)]},
            {"name": "hair", "kind": "path", "d": hair_d, "points": [(temple_left + 2, head_cy - 8), (cx, crown_y + 2), (temple_right - 2, head_cy - 8)]},
            {"name": "leg_shadow_left", "kind": "path", "d": leg_shadow_left_d, "points": [(cx - 18, shorts_bottom_y + 2), (cx - 18, ankle_y - 4)]},
            {"name": "leg_shadow_right", "kind": "path", "d": leg_shadow_right_d, "points": [(cx + 18, shorts_bottom_y + 2), (cx + 18, ankle_y - 4)]},
            {"name": "collar_outer", "kind": "path", "d": collar_outer_d, "points": [(cx - 18, shoulder_y - 2), (cx, shoulder_y + 10), (cx + 18, shoulder_y - 2)]},
            {"name": "collar_inner", "kind": "path", "d": collar_inner_d, "points": [(cx - 12, shoulder_y + 1), (cx, shoulder_y + 8), (cx + 12, shoulder_y + 1)]},
        ]

    def _draw_front_player_premium(self) -> None:
        for shape in self._front_shape_layers():
            name = shape["name"]
            if name == "shadow":
                continue
            d = shape["d"]
            if name in {"left_thigh", "right_thigh", "left_arm", "right_arm", "neck", "head"}:
                self.dwg.add(self.dwg.path(d=d, fill=self.skin_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name in {"left_sock", "right_sock"}:
                self.dwg.add(self.dwg.path(d=d, fill=self.socks_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name in {"left_boot", "right_boot"}:
                self.dwg.add(self.dwg.path(d=d, fill=KIT["boots"], stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name == "torso":
                self.dwg.add(self.dwg.path(d=d, fill=self.shirt_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name == "shirt_shadow":
                self.dwg.add(self.dwg.path(d=d, fill="#103c88", opacity=0.25, stroke="none"))
            elif name == "shorts":
                self.dwg.add(self.dwg.path(d=d, fill=self.shorts_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name == "shorts_shadow":
                self.dwg.add(self.dwg.path(d=d, fill="#111827", opacity=0.22, stroke="none"))
            elif name == "hair":
                self.dwg.add(self.dwg.path(d=d, fill=KIT["hair"], stroke=KIT["outline"], stroke_width=2.8, stroke_linejoin="round", stroke_linecap="round"))
            elif name in {"leg_shadow_left", "leg_shadow_right"}:
                self.dwg.add(self.dwg.path(d=d, fill="none", stroke="#af7e59", stroke_width=4, opacity=0.26, stroke_linecap="round"))
            elif name == "collar_outer":
                self.dwg.add(self.dwg.path(d=d, fill="none", stroke=KIT["trim"], stroke_width=5.2, stroke_linecap="round"))
            elif name == "collar_inner":
                self.dwg.add(self.dwg.path(d=d, fill="none", stroke="#8dbaff", stroke_width=2.2, opacity=0.5, stroke_linecap="round"))
        self.dwg.add(self.dwg.path(d=f"M 216 169 Q 232 157 245 175", fill="none", stroke=KIT["trim"], stroke_width=5, stroke_linecap="round"))
        self.dwg.add(self.dwg.path(d=f"M 296 169 Q 280 157 267 175", fill="none", stroke=KIT["trim"], stroke_width=5, stroke_linecap="round"))
        self.dwg.add(self.dwg.path(d="M 232 183 Q 255 168 280 184", fill="none", stroke="#6dc0ff", stroke_width=2.4, opacity=0.36))
        self.dwg.add(self.dwg.path(d="M 226 258 Q 256 268 286 258", fill="none", stroke="#08111a", stroke_width=2.2, opacity=0.36))
        self.dwg.add(self.dwg.text(self.pose.number, insert=(256, 223), text_anchor="middle", font_size=37, font_family="Arial", font_weight="700", fill=KIT["number"], opacity=0.98))
        self.dwg.add(self.dwg.text(self.pose.number, insert=(258, 226), text_anchor="middle", font_size=37, font_family="Arial", font_weight="700", fill=KIT["number_shadow"], opacity=0.23))
        self.dwg.add(self.dwg.line(start=(224, 367), end=(245, 367), stroke=KIT["sock_band"], stroke_width=5, opacity=0.95))
        self.dwg.add(self.dwg.line(start=(267, 367), end=(288, 367), stroke=KIT["sock_band"], stroke_width=5, opacity=0.95))
        self.dwg.add(self.dwg.line(start=(242, 98), end=(249, 97), stroke=KIT["outline"], stroke_width=2.6, stroke_linecap="round"))
        self.dwg.add(self.dwg.line(start=(263, 97), end=(270, 98), stroke=KIT["outline"], stroke_width=2.6, stroke_linecap="round"))
        self.dwg.add(self.dwg.path(d="M 249 113 Q 256 118 263 113", fill="none", stroke=KIT["skin_shadow"], stroke_width=2.2, opacity=0.85))
        self.dwg.add(self.dwg.path(d="M 244 124 Q 256 132 268 124", fill="none", stroke=KIT["outline"], stroke_width=2.1, opacity=0.55))

    def _front_shape_layers_v2(self) -> List[Dict[str, object]]:
        assert self.front_variant is not None
        cx = 256
        head_cy = 96
        chin_y = 130
        neck_top_y = 132
        shoulder_y = 145
        hem_y = 272
        shorts_top_y = 266
        shorts_bottom_y = 321
        crotch_y = 304
        knee_y = 352
        ankle_y = 420
        foot_y = 438

        head_d = (
            f"M {cx:.2f} {chin_y:.2f} "
            f"C {cx - 20:.2f} {chin_y - 2:.2f}, {cx - 33:.2f} {115:.2f}, {cx - 29:.2f} {92:.2f} "
            f"C {cx - 25:.2f} {67:.2f}, {cx - 12:.2f} {53:.2f}, {cx:.2f} {52:.2f} "
            f"C {cx + 12:.2f} {53:.2f}, {cx + 25:.2f} {67:.2f}, {cx + 29:.2f} {92:.2f} "
            f"C {cx + 33:.2f} {115:.2f}, {cx + 20:.2f} {chin_y - 2:.2f}, {cx:.2f} {chin_y:.2f} Z"
        )
        hair_d = (
            f"M {cx - 27:.2f} 90 "
            f"C {cx - 31:.2f} 69, {cx - 15:.2f} 55, {cx:.2f} 54 "
            f"C {cx + 15:.2f} 55, {cx + 31:.2f} 68, {cx + 27:.2f} 90 "
            f"C {cx + 16:.2f} 100, {cx + 6:.2f} 104, {cx:.2f} 100 "
            f"C {cx - 6:.2f} 104, {cx - 16:.2f} 100, {cx - 27:.2f} 90 Z"
        )
        neck_d = (
            f"M {cx - 11:.2f} {neck_top_y:.2f} "
            f"C {cx - 11:.2f} 138, {cx - 10:.2f} 145, {cx - 9:.2f} 150 "
            f"L {cx + 9:.2f} 150 "
            f"C {cx + 10:.2f} 145, {cx + 11:.2f} 138, {cx + 11:.2f} {neck_top_y:.2f} "
            f"C {cx + 8:.2f} 129, {cx - 8:.2f} 129, {cx - 11:.2f} {neck_top_y:.2f} Z"
        )
        torso_d = (
            f"M {cx - 26:.2f} 136 "
            f"C {cx - 56:.2f} 139, {cx - 72:.2f} 151, {cx - 74:.2f} 172 "
            f"C {cx - 73:.2f} 199, {cx - 61:.2f} 228, {cx - 46:.2f} 252 "
            f"C {cx - 34:.2f} 268, {cx - 20:.2f} 274, {cx:.2f} 276 "
            f"C {cx + 20:.2f} 274, {cx + 34:.2f} 268, {cx + 46:.2f} 252 "
            f"C {cx + 61:.2f} 228, {cx + 73:.2f} 199, {cx + 74:.2f} 172 "
            f"C {cx + 72:.2f} 151, {cx + 56:.2f} 139, {cx + 26:.2f} 136 "
            f"C {cx + 13:.2f} 144, {cx - 13:.2f} 144, {cx - 26:.2f} 136 Z"
        )
        left_arm_d = (
            f"M {cx - 58:.2f} 165 "
            f"C {cx - 77:.2f} 183, {cx - 83:.2f} 214, {cx - 76:.2f} 243 "
            f"C {cx - 71:.2f} 264, {cx - 58:.2f} 286, {cx - 45:.2f} 305 "
            f"C {cx - 38:.2f} 314, {cx - 29:.2f} 314, {cx - 23:.2f} 307 "
            f"C {cx - 26:.2f} 286, {cx - 34:.2f} 262, {cx - 38:.2f} 237 "
            f"C {cx - 42:.2f} 214, {cx - 40:.2f} 190, {cx - 30:.2f} 171 "
            f"C {cx - 34:.2f} 163, {cx - 45:.2f} 160, {cx - 58:.2f} 165 Z"
        )
        right_arm_d = (
            f"M {cx + 58:.2f} 165 "
            f"C {cx + 77:.2f} 183, {cx + 83:.2f} 214, {cx + 76:.2f} 243 "
            f"C {cx + 71:.2f} 264, {cx + 58:.2f} 286, {cx + 45:.2f} 305 "
            f"C {cx + 38:.2f} 314, {cx + 29:.2f} 314, {cx + 23:.2f} 307 "
            f"C {cx + 26:.2f} 286, {cx + 34:.2f} 262, {cx + 38:.2f} 237 "
            f"C {cx + 42:.2f} 214, {cx + 40:.2f} 190, {cx + 30:.2f} 171 "
            f"C {cx + 34:.2f} 163, {cx + 45:.2f} 160, {cx + 58:.2f} 165 Z"
        )
        shorts_d = (
            f"M {cx - 40:.2f} {shorts_top_y:.2f} "
            f"C {cx - 54:.2f} 270, {cx - 58:.2f} 282, {cx - 53:.2f} 294 "
            f"C {cx - 48:.2f} 307, {cx - 40:.2f} 317, {cx - 27:.2f} 323 "
            f"C {cx - 18:.2f} 325, {cx - 11:.2f} 321, {cx - 8:.2f} 313 "
            f"C {cx - 6:.2f} 307, {cx - 4:.2f} {crotch_y:.2f}, {cx:.2f} 299 "
            f"C {cx + 4:.2f} {crotch_y:.2f}, {cx + 6:.2f} 307, {cx + 8:.2f} 313 "
            f"C {cx + 11:.2f} 321, {cx + 18:.2f} 325, {cx + 27:.2f} 323 "
            f"C {cx + 40:.2f} 317, {cx + 48:.2f} 307, {cx + 53:.2f} 294 "
            f"C {cx + 58:.2f} 282, {cx + 54:.2f} 270, {cx + 40:.2f} {shorts_top_y:.2f} "
            f"C {cx + 24:.2f} 260, {cx - 24:.2f} 260, {cx - 40:.2f} {shorts_top_y:.2f} Z"
        )
        left_thigh_d = (
            f"M {cx - 18:.2f} 314 "
            f"C {cx - 35:.2f} 322, {cx - 45:.2f} 338, {cx - 43:.2f} {knee_y:.2f} "
            f"C {cx - 40:.2f} 365, {cx - 28:.2f} 375, {cx - 17:.2f} 373 "
            f"C {cx - 10:.2f} 368, {cx - 8:.2f} 358, {cx - 9:.2f} 345 "
            f"C {cx - 10:.2f} 332, {cx - 11:.2f} 322, {cx - 18:.2f} 314 Z"
        )
        right_thigh_d = (
            f"M {cx + 18:.2f} 314 "
            f"C {cx + 35:.2f} 322, {cx + 45:.2f} 338, {cx + 43:.2f} {knee_y:.2f} "
            f"C {cx + 40:.2f} 365, {cx + 28:.2f} 375, {cx + 17:.2f} 373 "
            f"C {cx + 10:.2f} 368, {cx + 8:.2f} 358, {cx + 9:.2f} 345 "
            f"C {cx + 10:.2f} 332, {cx + 11:.2f} 322, {cx + 18:.2f} 314 Z"
        )
        left_sock_d = (
            f"M {cx - 39:.2f} {knee_y - 2:.2f} "
            f"C {cx - 43:.2f} 378, {cx - 41:.2f} 397, {cx - 37:.2f} {ankle_y:.2f} "
            f"C {cx - 30:.2f} 424, {cx - 21:.2f} 424, {cx - 15:.2f} 418 "
            f"C {cx - 15:.2f} 396, {cx - 15:.2f} 378, {cx - 17:.2f} {knee_y:.2f} "
            f"C {cx - 22:.2f} 348, {cx - 31:.2f} 348, {cx - 39:.2f} {knee_y - 2:.2f} Z"
        )
        right_sock_d = (
            f"M {cx + 39:.2f} {knee_y - 2:.2f} "
            f"C {cx + 43:.2f} 378, {cx + 41:.2f} 397, {cx + 37:.2f} {ankle_y:.2f} "
            f"C {cx + 30:.2f} 424, {cx + 21:.2f} 424, {cx + 15:.2f} 418 "
            f"C {cx + 15:.2f} 396, {cx + 15:.2f} 378, {cx + 17:.2f} {knee_y:.2f} "
            f"C {cx + 22:.2f} 348, {cx + 31:.2f} 348, {cx + 39:.2f} {knee_y - 2:.2f} Z"
        )
        left_boot_d = (
            f"M {cx - 38:.2f} 417 "
            f"C {cx - 48:.2f} 421, {cx - 50:.2f} 430, {cx - 44:.2f} 436 "
            f"C {cx - 35:.2f} 441, {cx - 20:.2f} 442, {cx - 5:.2f} 438 "
            f"C {cx + 2:.2f} 435, {cx + 4:.2f} 429, {cx + 1:.2f} 424 "
            f"C {cx - 5:.2f} 419, {cx - 15:.2f} 417, {cx - 24:.2f} 416 "
            f"C {cx - 29:.2f} 414, {cx - 34:.2f} 414, {cx - 38:.2f} 417 Z"
        )
        right_boot_d = (
            f"M {cx + 38:.2f} 417 "
            f"C {cx + 48:.2f} 421, {cx + 50:.2f} 430, {cx + 44:.2f} 436 "
            f"C {cx + 35:.2f} 441, {cx + 20:.2f} 442, {cx + 5:.2f} 438 "
            f"C {cx - 2:.2f} 435, {cx - 4:.2f} 429, {cx - 1:.2f} 424 "
            f"C {cx + 5:.2f} 419, {cx + 15:.2f} 417, {cx + 24:.2f} 416 "
            f"C {cx + 29:.2f} 414, {cx + 34:.2f} 414, {cx + 38:.2f} 417 Z"
        )
        shirt_shadow_d = (
            f"M {cx - 47:.2f} 171 "
            f"C {cx - 28:.2f} 192, {cx - 21:.2f} 224, {cx - 17:.2f} 263 "
            f"C {cx - 8:.2f} 271, {cx - 1:.2f} 274, {cx + 2:.2f} 275 "
            f"C {cx - 3:.2f} 251, {cx - 2:.2f} 206, {cx - 7:.2f} 173 "
            f"C {cx - 19:.2f} 164, {cx - 32:.2f} 163, {cx - 47:.2f} 171 Z"
        )
        shorts_shadow_d = (
            f"M {cx - 10:.2f} 269 "
            f"C {cx - 4:.2f} 284, {cx - 2:.2f} 296, {cx:.2f} 308 "
            f"C {cx + 3:.2f} 296, {cx + 4:.2f} 284, {cx + 10:.2f} 269 Z"
        )
        leg_shadow_left_d = f"M {cx - 22:.2f} 320 C {cx - 19:.2f} 343, {cx - 20:.2f} 382, {cx - 24:.2f} 412"
        leg_shadow_right_d = f"M {cx + 22:.2f} 320 C {cx + 19:.2f} 343, {cx + 20:.2f} 382, {cx + 24:.2f} 412"
        collar_outer_d = f"M {cx - 17:.2f} 147 Q {cx:.2f} 157 {cx + 17:.2f} 147"
        collar_inner_d = f"M {cx - 11:.2f} 150 Q {cx:.2f} 156 {cx + 11:.2f} 150"

        return [
            {"name": "shadow", "kind": "ellipse", "ellipse": (256, 454, 74, 16)},
            {"name": "left_thigh", "kind": "path", "d": left_thigh_d, "points": [(cx - 18, 314), (cx - 43, knee_y), (cx - 17, 372)]},
            {"name": "right_thigh", "kind": "path", "d": right_thigh_d, "points": [(cx + 18, 314), (cx + 43, knee_y), (cx + 17, 372)]},
            {"name": "left_sock", "kind": "path", "d": left_sock_d, "points": [(cx - 39, knee_y), (cx - 37, ankle_y), (cx - 16, 418)]},
            {"name": "right_sock", "kind": "path", "d": right_sock_d, "points": [(cx + 39, knee_y), (cx + 37, ankle_y), (cx + 16, 418)]},
            {"name": "left_boot", "kind": "path", "d": left_boot_d, "points": [(cx - 38, 417), (cx - 5, 438)]},
            {"name": "right_boot", "kind": "path", "d": right_boot_d, "points": [(cx + 38, 417), (cx + 5, 438)]},
            {"name": "left_arm", "kind": "path", "d": left_arm_d, "points": [(cx - 58, 165), (cx - 76, 243), (cx - 24, 307)]},
            {"name": "right_arm", "kind": "path", "d": right_arm_d, "points": [(cx + 58, 165), (cx + 76, 243), (cx + 24, 307)]},
            {"name": "torso", "kind": "path", "d": torso_d, "points": [(cx - 26, 136), (cx - 74, 172), (cx, 276)]},
            {"name": "shirt_shadow", "kind": "path", "d": shirt_shadow_d, "points": [(cx - 47, 171), (cx + 2, 275)]},
            {"name": "shorts", "kind": "path", "d": shorts_d, "points": [(cx - 40, shorts_top_y), (cx, 299), (cx + 40, shorts_top_y)]},
            {"name": "shorts_shadow", "kind": "path", "d": shorts_shadow_d, "points": [(cx - 10, 269), (cx, 308), (cx + 10, 269)]},
            {"name": "neck", "kind": "path", "d": neck_d, "points": [(cx - 11, neck_top_y), (cx + 11, neck_top_y)]},
            {"name": "head", "kind": "path", "d": head_d, "points": [(cx, chin_y), (cx - 29, 92), (cx, 52), (cx + 29, 92)]},
            {"name": "hair", "kind": "path", "d": hair_d, "points": [(cx - 27, 90), (cx, 54), (cx + 27, 90)]},
            {"name": "leg_shadow_left", "kind": "path", "d": leg_shadow_left_d, "points": [(cx - 22, 320), (cx - 24, 412)]},
            {"name": "leg_shadow_right", "kind": "path", "d": leg_shadow_right_d, "points": [(cx + 22, 320), (cx + 24, 412)]},
            {"name": "collar_outer", "kind": "path", "d": collar_outer_d, "points": [(cx - 17, 147), (cx, 157), (cx + 17, 147)]},
            {"name": "collar_inner", "kind": "path", "d": collar_inner_d, "points": [(cx - 11, 150), (cx, 156), (cx + 11, 150)]},
        ]

    def _draw_front_player_premium_v2(self) -> None:
        for shape in self._front_shape_layers_v2():
            name = shape["name"]
            if name == "shadow":
                continue
            d = shape["d"]
            if name in {"left_thigh", "right_thigh", "left_arm", "right_arm", "neck", "head"}:
                self.dwg.add(self.dwg.path(d=d, fill=self.skin_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name in {"left_sock", "right_sock"}:
                self.dwg.add(self.dwg.path(d=d, fill=self.socks_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name in {"left_boot", "right_boot"}:
                self.dwg.add(self.dwg.path(d=d, fill=KIT["boots"], stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name == "torso":
                self.dwg.add(self.dwg.path(d=d, fill=self.shirt_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name == "shirt_shadow":
                self.dwg.add(self.dwg.path(d=d, fill="#103c88", opacity=0.22, stroke="none"))
            elif name == "shorts":
                self.dwg.add(self.dwg.path(d=d, fill=self.shorts_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name == "shorts_shadow":
                self.dwg.add(self.dwg.path(d=d, fill="#111827", opacity=0.18, stroke="none"))
            elif name == "hair":
                self.dwg.add(self.dwg.path(d=d, fill=KIT["hair"], stroke=KIT["outline"], stroke_width=2.8, stroke_linejoin="round", stroke_linecap="round"))
            elif name in {"leg_shadow_left", "leg_shadow_right"}:
                self.dwg.add(self.dwg.path(d=d, fill="none", stroke="#af7e59", stroke_width=4, opacity=0.22, stroke_linecap="round"))
            elif name == "collar_outer":
                self.dwg.add(self.dwg.path(d=d, fill="none", stroke=KIT["trim"], stroke_width=5.2, stroke_linecap="round"))
            elif name == "collar_inner":
                self.dwg.add(self.dwg.path(d=d, fill="none", stroke="#8dbaff", stroke_width=2.2, opacity=0.45, stroke_linecap="round"))
        self.dwg.add(self.dwg.path(d="M 219 171 Q 234 159 246 176", fill="none", stroke=KIT["trim"], stroke_width=5, stroke_linecap="round"))
        self.dwg.add(self.dwg.path(d="M 293 171 Q 278 159 266 176", fill="none", stroke=KIT["trim"], stroke_width=5, stroke_linecap="round"))
        self.dwg.add(self.dwg.path(d="M 232 184 Q 256 170 280 184", fill="none", stroke="#6dc0ff", stroke_width=2.2, opacity=0.30))
        self.dwg.add(self.dwg.text(self.pose.number, insert=(256, 224), text_anchor="middle", font_size=37, font_family="Arial", font_weight="700", fill=KIT["number"], opacity=0.98))
        self.dwg.add(self.dwg.text(self.pose.number, insert=(258, 227), text_anchor="middle", font_size=37, font_family="Arial", font_weight="700", fill=KIT["number_shadow"], opacity=0.20))
        self.dwg.add(self.dwg.line(start=(221, 367), end=(241, 367), stroke=KIT["sock_band"], stroke_width=5, opacity=0.95))
        self.dwg.add(self.dwg.line(start=(271, 367), end=(291, 367), stroke=KIT["sock_band"], stroke_width=5, opacity=0.95))
        self.dwg.add(self.dwg.line(start=(243, 97), end=(249, 96), stroke=KIT["outline"], stroke_width=2.6, stroke_linecap="round"))
        self.dwg.add(self.dwg.line(start=(263, 96), end=(269, 97), stroke=KIT["outline"], stroke_width=2.6, stroke_linecap="round"))
        self.dwg.add(self.dwg.path(d="M 249 113 Q 256 118 263 113", fill="none", stroke=KIT["skin_shadow"], stroke_width=2.2, opacity=0.82))
        self.dwg.add(self.dwg.path(d="M 245 124 Q 256 131 267 124", fill="none", stroke=KIT["outline"], stroke_width=2.0, opacity=0.52))

    def _front_shape_layers_v3(self) -> List[Dict[str, object]]:
        cx = 256
        head_cy = 94
        chin_y = 128
        neck_top_y = 130
        shoulder_y = 144
        hem_y = 270
        shorts_top_y = 266
        shorts_bottom_y = 320
        crotch_y = 301
        knee_y = 357
        ankle_y = 424
        foot_y = 440

        head_d = (
            f"M {cx:.2f} {chin_y:.2f} "
            f"C {cx - 18:.2f} {chin_y - 1:.2f}, {cx - 31:.2f} 114.0, {cx - 28:.2f} 92.0 "
            f"C {cx - 24:.2f} 69.0, {cx - 12:.2f} 56.0, {cx:.2f} 55.0 "
            f"C {cx + 12:.2f} 56.0, {cx + 24:.2f} 69.0, {cx + 28:.2f} 92.0 "
            f"C {cx + 31:.2f} 114.0, {cx + 18:.2f} {chin_y - 1:.2f}, {cx:.2f} {chin_y:.2f} Z"
        )
        hair_d = (
            f"M {cx - 25:.2f} 89.0 "
            f"C {cx - 29:.2f} 70.0, {cx - 16:.2f} 57.0, {cx:.2f} 55.0 "
            f"C {cx + 14:.2f} 57.0, {cx + 29:.2f} 69.0, {cx + 25:.2f} 89.0 "
            f"C {cx + 13:.2f} 98.0, {cx + 5:.2f} 101.0, {cx:.2f} 98.0 "
            f"C {cx - 6:.2f} 101.0, {cx - 14:.2f} 97.0, {cx - 25:.2f} 89.0 Z"
        )
        neck_d = (
            f"M {cx - 10:.2f} {neck_top_y:.2f} "
            f"C {cx - 10:.2f} 136.0, {cx - 9:.2f} 141.0, {cx - 9:.2f} 146.0 "
            f"L {cx + 9:.2f} 146.0 "
            f"C {cx + 9:.2f} 141.0, {cx + 10:.2f} 136.0, {cx + 10:.2f} {neck_top_y:.2f} "
            f"C {cx + 7:.2f} 127.0, {cx - 7:.2f} 127.0, {cx - 10:.2f} {neck_top_y:.2f} Z"
        )
        torso_d = (
            f"M {cx - 28:.2f} 138.0 "
            f"C {cx - 59:.2f} 140.0, {cx - 80:.2f} 151.0, {cx - 86:.2f} 170.0 "
            f"C {cx - 89:.2f} 188.0, {cx - 83:.2f} 208.0, {cx - 69:.2f} 232.0 "
            f"C {cx - 55:.2f} 254.0, {cx - 38:.2f} 268.0, {cx - 15:.2f} {hem_y - 1:.2f} "
            f"C {cx - 6:.2f} {hem_y + 4:.2f}, {cx + 6:.2f} {hem_y + 4:.2f}, {cx + 15:.2f} {hem_y - 1:.2f} "
            f"C {cx + 38:.2f} 268.0, {cx + 55:.2f} 254.0, {cx + 69:.2f} 232.0 "
            f"C {cx + 83:.2f} 208.0, {cx + 89:.2f} 188.0, {cx + 86:.2f} 170.0 "
            f"C {cx + 80:.2f} 151.0, {cx + 59:.2f} 140.0, {cx + 28:.2f} 138.0 "
            f"C {cx + 13:.2f} 146.0, {cx - 13:.2f} 146.0, {cx - 28:.2f} 138.0 Z"
        )
        left_arm_d = (
            f"M {cx - 64:.2f} 164.0 "
            f"C {cx - 80:.2f} 182.0, {cx - 85:.2f} 208.0, {cx - 80:.2f} 234.0 "
            f"C {cx - 76:.2f} 258.0, {cx - 66:.2f} 279.0, {cx - 57:.2f} 295.0 "
            f"C {cx - 49:.2f} 308.0, {cx - 39:.2f} 313.0, {cx - 30:.2f} 309.0 "
            f"C {cx - 32:.2f} 289.0, {cx - 38:.2f} 267.0, {cx - 41:.2f} 244.0 "
            f"C {cx - 45:.2f} 219.0, {cx - 43:.2f} 193.0, {cx - 34:.2f} 171.0 "
            f"C {cx - 40:.2f} 164.0, {cx - 51:.2f} 161.0, {cx - 64:.2f} 164.0 Z"
        )
        right_arm_d = (
            f"M {cx + 64:.2f} 164.0 "
            f"C {cx + 80:.2f} 182.0, {cx + 85:.2f} 208.0, {cx + 80:.2f} 234.0 "
            f"C {cx + 76:.2f} 258.0, {cx + 66:.2f} 279.0, {cx + 57:.2f} 295.0 "
            f"C {cx + 49:.2f} 308.0, {cx + 39:.2f} 313.0, {cx + 30:.2f} 309.0 "
            f"C {cx + 32:.2f} 289.0, {cx + 38:.2f} 267.0, {cx + 41:.2f} 244.0 "
            f"C {cx + 45:.2f} 219.0, {cx + 43:.2f} 193.0, {cx + 34:.2f} 171.0 "
            f"C {cx + 40:.2f} 164.0, {cx + 51:.2f} 161.0, {cx + 64:.2f} 164.0 Z"
        )
        shorts_d = (
            f"M {cx - 38:.2f} {shorts_top_y:.2f} "
            f"C {cx - 52:.2f} 269.0, {cx - 57:.2f} 281.0, {cx - 54:.2f} 293.0 "
            f"C {cx - 51:.2f} 305.0, {cx - 42:.2f} 314.0, {cx - 28:.2f} 319.0 "
            f"C {cx - 18:.2f} 322.0, {cx - 10:.2f} 319.0, {cx - 5:.2f} 311.0 "
            f"C {cx - 2:.2f} 307.0, {cx - 1:.2f} {crotch_y + 2:.2f}, {cx:.2f} {crotch_y:.2f} "
            f"C {cx + 1:.2f} {crotch_y + 2:.2f}, {cx + 2:.2f} 307.0, {cx + 5:.2f} 311.0 "
            f"C {cx + 10:.2f} 319.0, {cx + 18:.2f} 322.0, {cx + 28:.2f} 319.0 "
            f"C {cx + 42:.2f} 314.0, {cx + 51:.2f} 305.0, {cx + 54:.2f} 293.0 "
            f"C {cx + 57:.2f} 281.0, {cx + 52:.2f} 269.0, {cx + 38:.2f} {shorts_top_y:.2f} "
            f"C {cx + 23:.2f} 261.0, {cx - 23:.2f} 261.0, {cx - 38:.2f} {shorts_top_y:.2f} Z"
        )
        left_thigh_d = (
            f"M {cx - 17:.2f} 312.0 "
            f"C {cx - 34:.2f} 320.0, {cx - 46:.2f} 336.0, {cx - 45:.2f} {knee_y - 2:.2f} "
            f"C {cx - 43:.2f} 372.0, {cx - 30:.2f} 382.0, {cx - 18:.2f} 379.0 "
            f"C {cx - 9:.2f} 373.0, {cx - 7:.2f} 362.0, {cx - 8:.2f} 347.0 "
            f"C {cx - 9:.2f} 333.0, {cx - 10:.2f} 322.0, {cx - 17:.2f} 312.0 Z"
        )
        right_thigh_d = (
            f"M {cx + 17:.2f} 312.0 "
            f"C {cx + 34:.2f} 320.0, {cx + 46:.2f} 336.0, {cx + 45:.2f} {knee_y - 2:.2f} "
            f"C {cx + 43:.2f} 372.0, {cx + 30:.2f} 382.0, {cx + 18:.2f} 379.0 "
            f"C {cx + 9:.2f} 373.0, {cx + 7:.2f} 362.0, {cx + 8:.2f} 347.0 "
            f"C {cx + 9:.2f} 333.0, {cx + 10:.2f} 322.0, {cx + 17:.2f} 312.0 Z"
        )
        left_sock_d = (
            f"M {cx - 41:.2f} {knee_y - 1:.2f} "
            f"C {cx - 45:.2f} 382.0, {cx - 43:.2f} 400.0, {cx - 39:.2f} {ankle_y:.2f} "
            f"C {cx - 32:.2f} 428.0, {cx - 22:.2f} 428.0, {cx - 15:.2f} 421.0 "
            f"C {cx - 15:.2f} 398.0, {cx - 15:.2f} 382.0, {cx - 17:.2f} {knee_y:.2f} "
            f"C {cx - 23:.2f} 352.0, {cx - 33:.2f} 352.0, {cx - 41:.2f} {knee_y - 1:.2f} Z"
        )
        right_sock_d = (
            f"M {cx + 41:.2f} {knee_y - 1:.2f} "
            f"C {cx + 45:.2f} 382.0, {cx + 43:.2f} 400.0, {cx + 39:.2f} {ankle_y:.2f} "
            f"C {cx + 32:.2f} 428.0, {cx + 22:.2f} 428.0, {cx + 15:.2f} 421.0 "
            f"C {cx + 15:.2f} 398.0, {cx + 15:.2f} 382.0, {cx + 17:.2f} {knee_y:.2f} "
            f"C {cx + 23:.2f} 352.0, {cx + 33:.2f} 352.0, {cx + 41:.2f} {knee_y - 1:.2f} Z"
        )
        left_boot_d = (
            f"M {cx - 40:.2f} 421.0 "
            f"C {cx - 50:.2f} 424.0, {cx - 52:.2f} 432.0, {cx - 46:.2f} 438.0 "
            f"C {cx - 38:.2f} 443.0, {cx - 24:.2f} 444.0, {cx - 10:.2f} 441.0 "
            f"C {cx - 2:.2f} 438.0, {cx + 1:.2f} 432.0, {cx - 1:.2f} 427.0 "
            f"C {cx - 7:.2f} 422.0, {cx - 18:.2f} 420.0, {cx - 27:.2f} 419.0 "
            f"C {cx - 32:.2f} 418.0, {cx - 36:.2f} 418.0, {cx - 40:.2f} 421.0 Z"
        )
        right_boot_d = (
            f"M {cx + 40:.2f} 421.0 "
            f"C {cx + 50:.2f} 424.0, {cx + 52:.2f} 432.0, {cx + 46:.2f} 438.0 "
            f"C {cx + 38:.2f} 443.0, {cx + 24:.2f} 444.0, {cx + 10:.2f} 441.0 "
            f"C {cx + 2:.2f} 438.0, {cx - 1:.2f} 432.0, {cx + 1:.2f} 427.0 "
            f"C {cx + 7:.2f} 422.0, {cx + 18:.2f} 420.0, {cx + 27:.2f} 419.0 "
            f"C {cx + 32:.2f} 418.0, {cx + 36:.2f} 418.0, {cx + 40:.2f} 421.0 Z"
        )
        shirt_shadow_d = (
            f"M {cx - 52:.2f} 170.0 "
            f"C {cx - 33:.2f} 191.0, {cx - 25:.2f} 225.0, {cx - 17:.2f} 264.0 "
            f"C {cx - 8:.2f} 270.0, {cx - 1:.2f} 273.0, {cx + 4:.2f} 273.0 "
            f"C {cx - 1:.2f} 248.0, {cx + 1:.2f} 207.0, {cx - 5:.2f} 171.0 "
            f"C {cx - 18:.2f} 163.0, {cx - 34:.2f} 162.0, {cx - 52:.2f} 170.0 Z"
        )
        shorts_shadow_d = (
            f"M {cx - 10:.2f} 268.0 "
            f"C {cx - 4:.2f} 282.0, {cx - 2:.2f} 293.0, {cx:.2f} 304.0 "
            f"C {cx + 3:.2f} 293.0, {cx + 4:.2f} 282.0, {cx + 10:.2f} 268.0 Z"
        )
        leg_shadow_left_d = f"M {cx - 22:.2f} 318.0 C {cx - 19:.2f} 341.0, {cx - 20:.2f} 383.0, {cx - 24:.2f} 414.0"
        leg_shadow_right_d = f"M {cx + 22:.2f} 318.0 C {cx + 19:.2f} 341.0, {cx + 20:.2f} 383.0, {cx + 24:.2f} 414.0"
        collar_outer_d = f"M {cx - 16:.2f} 147.0 Q {cx:.2f} 156.0 {cx + 16:.2f} 147.0"
        collar_inner_d = f"M {cx - 10:.2f} 150.0 Q {cx:.2f} 155.0 {cx + 10:.2f} 150.0"

        return [
            {"name": "shadow", "kind": "ellipse", "ellipse": (256, 456, 70, 15)},
            {"name": "left_thigh", "kind": "path", "d": left_thigh_d, "points": [(cx - 17, 312), (cx - 45, knee_y - 1), (cx - 18, 379)]},
            {"name": "right_thigh", "kind": "path", "d": right_thigh_d, "points": [(cx + 17, 312), (cx + 45, knee_y - 1), (cx + 18, 379)]},
            {"name": "left_sock", "kind": "path", "d": left_sock_d, "points": [(cx - 41, knee_y - 1), (cx - 39, ankle_y), (cx - 15, 421)]},
            {"name": "right_sock", "kind": "path", "d": right_sock_d, "points": [(cx + 41, knee_y - 1), (cx + 39, ankle_y), (cx + 15, 421)]},
            {"name": "left_boot", "kind": "path", "d": left_boot_d, "points": [(cx - 40, 421), (cx - 10, 441)]},
            {"name": "right_boot", "kind": "path", "d": right_boot_d, "points": [(cx + 40, 421), (cx + 10, 441)]},
            {"name": "left_arm", "kind": "path", "d": left_arm_d, "points": [(cx - 64, 164), (cx - 80, 234), (cx - 30, 309)]},
            {"name": "right_arm", "kind": "path", "d": right_arm_d, "points": [(cx + 64, 164), (cx + 80, 234), (cx + 30, 309)]},
            {"name": "torso", "kind": "path", "d": torso_d, "points": [(cx - 28, 138), (cx - 86, 170), (cx, hem_y + 3)]},
            {"name": "shirt_shadow", "kind": "path", "d": shirt_shadow_d, "points": [(cx - 52, 170), (cx + 4, 273)]},
            {"name": "shorts", "kind": "path", "d": shorts_d, "points": [(cx - 38, shorts_top_y), (cx, crotch_y), (cx + 38, shorts_top_y)]},
            {"name": "shorts_shadow", "kind": "path", "d": shorts_shadow_d, "points": [(cx - 10, 268), (cx, 304), (cx + 10, 268)]},
            {"name": "neck", "kind": "path", "d": neck_d, "points": [(cx - 10, neck_top_y), (cx + 10, neck_top_y)]},
            {"name": "head", "kind": "path", "d": head_d, "points": [(cx, chin_y), (cx - 28, 92), (cx, 55), (cx + 28, 92)]},
            {"name": "hair", "kind": "path", "d": hair_d, "points": [(cx - 25, 89), (cx, 55), (cx + 25, 89)]},
            {"name": "leg_shadow_left", "kind": "path", "d": leg_shadow_left_d, "points": [(cx - 22, 318), (cx - 24, 414)]},
            {"name": "leg_shadow_right", "kind": "path", "d": leg_shadow_right_d, "points": [(cx + 22, 318), (cx + 24, 414)]},
            {"name": "collar_outer", "kind": "path", "d": collar_outer_d, "points": [(cx - 16, 147), (cx, 156), (cx + 16, 147)]},
            {"name": "collar_inner", "kind": "path", "d": collar_inner_d, "points": [(cx - 10, 150), (cx, 155), (cx + 10, 150)]},
        ]

    def _draw_front_player_premium_v3(self) -> None:
        for shape in self._front_shape_layers_v3():
            name = shape["name"]
            if name == "shadow":
                continue
            d = shape["d"]
            if name in {"left_thigh", "right_thigh", "left_arm", "right_arm", "neck", "head"}:
                self.dwg.add(self.dwg.path(d=d, fill=self.skin_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name in {"left_sock", "right_sock"}:
                self.dwg.add(self.dwg.path(d=d, fill=self.socks_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name in {"left_boot", "right_boot"}:
                self.dwg.add(self.dwg.path(d=d, fill=KIT["boots"], stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name == "torso":
                self.dwg.add(self.dwg.path(d=d, fill=self.shirt_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name == "shirt_shadow":
                self.dwg.add(self.dwg.path(d=d, fill="#103c88", opacity=0.21, stroke="none"))
            elif name == "shorts":
                self.dwg.add(self.dwg.path(d=d, fill=self.shorts_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round", stroke_linecap="round"))
            elif name == "shorts_shadow":
                self.dwg.add(self.dwg.path(d=d, fill="#111827", opacity=0.17, stroke="none"))
            elif name == "hair":
                self.dwg.add(self.dwg.path(d=d, fill=KIT["hair"], stroke=KIT["outline"], stroke_width=2.8, stroke_linejoin="round", stroke_linecap="round"))
            elif name in {"leg_shadow_left", "leg_shadow_right"}:
                self.dwg.add(self.dwg.path(d=d, fill="none", stroke="#af7e59", stroke_width=4, opacity=0.20, stroke_linecap="round"))
            elif name == "collar_outer":
                self.dwg.add(self.dwg.path(d=d, fill="none", stroke=KIT["trim"], stroke_width=5.0, stroke_linecap="round"))
            elif name == "collar_inner":
                self.dwg.add(self.dwg.path(d=d, fill="none", stroke="#8dbaff", stroke_width=2.1, opacity=0.40, stroke_linecap="round"))
        self.dwg.add(self.dwg.path(d="M 215 170 Q 232 160 245 177", fill="none", stroke=KIT["trim"], stroke_width=4.8, stroke_linecap="round"))
        self.dwg.add(self.dwg.path(d="M 297 170 Q 280 160 267 177", fill="none", stroke=KIT["trim"], stroke_width=4.8, stroke_linecap="round"))
        self.dwg.add(self.dwg.path(d="M 234 184 Q 256 171 278 184", fill="none", stroke="#6dc0ff", stroke_width=2.0, opacity=0.26))
        self.dwg.add(self.dwg.text(self.pose.number, insert=(256, 223), text_anchor="middle", font_size=36, font_family="Arial", font_weight="700", fill=KIT["number"], opacity=0.98))
        self.dwg.add(self.dwg.text(self.pose.number, insert=(258, 226), text_anchor="middle", font_size=36, font_family="Arial", font_weight="700", fill=KIT["number_shadow"], opacity=0.18))
        self.dwg.add(self.dwg.line(start=(220, 372), end=(241, 372), stroke=KIT["sock_band"], stroke_width=5, opacity=0.95))
        self.dwg.add(self.dwg.line(start=(271, 372), end=(292, 372), stroke=KIT["sock_band"], stroke_width=5, opacity=0.95))
        self.dwg.add(self.dwg.line(start=(243, 97), end=(249, 96), stroke=KIT["outline"], stroke_width=2.5, stroke_linecap="round"))
        self.dwg.add(self.dwg.line(start=(263, 96), end=(269, 97), stroke=KIT["outline"], stroke_width=2.5, stroke_linecap="round"))
        self.dwg.add(self.dwg.path(d="M 249 113 Q 256 118 263 113", fill="none", stroke=KIT["skin_shadow"], stroke_width=2.0, opacity=0.78))
        self.dwg.add(self.dwg.path(d="M 245 124 Q 256 130 267 124", fill="none", stroke=KIT["outline"], stroke_width=1.9, opacity=0.50))

    def modular_piece_definitions_v3(self) -> Dict[str, Dict[str, object]]:
        pieces = {shape["name"]: shape for shape in self._front_shape_layers_v3()}
        shirt_fill = "#1f74f1"
        shorts_fill = "#1a2230"
        skin_fill = "#e0b08b"
        socks_fill = "#eef2ff"

        defs: Dict[str, Dict[str, object]] = {
            "head": {
                "bbox": (224, 52, 64, 82),
                "elements": [
                    {"type": "path", "d": pieces["head"]["d"], "fill": skin_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                    {"type": "path", "d": pieces["hair"]["d"], "fill": KIT["hair"], "stroke": KIT["outline"], "stroke_width": 2.8, "stroke_linejoin": "round", "stroke_linecap": "round"},
                    {"type": "line", "start": (243, 97), "end": (249, 96), "stroke": KIT["outline"], "stroke_width": 2.5, "stroke_linecap": "round"},
                    {"type": "line", "start": (263, 96), "end": (269, 97), "stroke": KIT["outline"], "stroke_width": 2.5, "stroke_linecap": "round"},
                    {"type": "path", "d": "M 249 113 Q 256 118 263 113", "fill": "none", "stroke": KIT["skin_shadow"], "stroke_width": 2.0, "opacity": 0.78},
                    {"type": "path", "d": "M 245 124 Q 256 130 267 124", "fill": "none", "stroke": KIT["outline"], "stroke_width": 1.9, "opacity": 0.50},
                ],
            },
            "neck": {
                "bbox": (240, 126, 32, 28),
                "elements": [
                    {"type": "path", "d": pieces["neck"]["d"], "fill": skin_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                ],
            },
            "torso": {
                "bbox": (164, 136, 184, 144),
                "elements": [
                    {"type": "path", "d": pieces["torso"]["d"], "fill": shirt_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                    {"type": "path", "d": pieces["shirt_shadow"]["d"], "fill": "#103c88", "opacity": 0.21, "stroke": "none"},
                    {"type": "path", "d": pieces["collar_outer"]["d"], "fill": "none", "stroke": KIT["trim"], "stroke_width": 5.0, "stroke_linecap": "round"},
                    {"type": "path", "d": pieces["collar_inner"]["d"], "fill": "none", "stroke": "#8dbaff", "stroke_width": 2.1, "opacity": 0.40, "stroke_linecap": "round"},
                    {"type": "path", "d": "M 215 170 Q 232 160 245 177", "fill": "none", "stroke": KIT["trim"], "stroke_width": 4.8, "stroke_linecap": "round"},
                    {"type": "path", "d": "M 297 170 Q 280 160 267 177", "fill": "none", "stroke": KIT["trim"], "stroke_width": 4.8, "stroke_linecap": "round"},
                    {"type": "path", "d": "M 234 184 Q 256 171 278 184", "fill": "none", "stroke": "#6dc0ff", "stroke_width": 2.0, "opacity": 0.26},
                    {"type": "text", "x": 258, "y": 226, "text": self.pose.number, "text_anchor": "middle", "font_size": 36, "font_family": "Arial", "font_weight": "700", "fill": KIT["number_shadow"], "opacity": 0.18},
                    {"type": "text", "x": 256, "y": 223, "text": self.pose.number, "text_anchor": "middle", "font_size": 36, "font_family": "Arial", "font_weight": "700", "fill": KIT["number"], "opacity": 0.98},
                ],
            },
            "left_upper_arm": {
                "bbox": (173, 157, 44, 83),
                "elements": [
                    {"type": "path", "d": "M 196 161 C 183 170, 175 188, 176 211 C 176 223, 180 232, 188 237 C 198 231, 206 221, 209 205 C 211 188, 207 173, 196 161 Z", "fill": skin_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                ],
            },
            "left_forearm": {
                "bbox": (176, 202, 43, 83),
                "elements": [
                    {"type": "path", "d": "M 191 203 C 182 216, 179 232, 182 250 C 185 264, 192 276, 202 282 C 210 277, 214 266, 214 251 C 213 232, 206 216, 191 203 Z", "fill": skin_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                ],
            },
            "left_hand": {
                "bbox": (196, 273, 26, 34),
                "elements": [
                    {"type": "path", "d": "M 202 281 C 198 286, 198 293, 202 299 C 208 304, 216 304, 221 299 C 222 293, 220 287, 216 282 C 211 278, 206 277, 202 281 Z", "fill": skin_fill, "stroke": KIT["outline"], "stroke_width": 2.6, "stroke_linejoin": "round", "stroke_linecap": "round"},
                ],
            },
            "right_upper_arm": {
                "bbox": (295, 157, 44, 83),
                "elements": [
                    {"type": "path", "d": "M 316 161 C 329 170, 337 188, 336 211 C 336 223, 332 232, 324 237 C 314 231, 306 221, 303 205 C 301 188, 305 173, 316 161 Z", "fill": skin_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                ],
            },
            "right_forearm": {
                "bbox": (293, 202, 43, 83),
                "elements": [
                    {"type": "path", "d": "M 321 203 C 330 216, 333 232, 330 250 C 327 264, 320 276, 310 282 C 302 277, 298 266, 298 251 C 299 232, 306 216, 321 203 Z", "fill": skin_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                ],
            },
            "right_hand": {
                "bbox": (290, 273, 26, 34),
                "elements": [
                    {"type": "path", "d": "M 310 281 C 314 286, 314 293, 310 299 C 304 304, 296 304, 291 299 C 290 293, 292 287, 296 282 C 301 278, 306 277, 310 281 Z", "fill": skin_fill, "stroke": KIT["outline"], "stroke_width": 2.6, "stroke_linejoin": "round", "stroke_linecap": "round"},
                ],
            },
            "shorts": {
                "bbox": (198, 260, 116, 68),
                "elements": [
                    {"type": "path", "d": "M 214 266 C 206 270, 201 279, 202 291 C 203 304, 211 314, 224 320 C 234 324, 244 323, 251 316 C 253 309, 254 304, 256 299 C 258 304, 259 309, 261 316 C 268 323, 278 324, 288 320 C 301 314, 309 304, 310 291 C 311 279, 306 270, 298 266 C 284 261, 228 261, 214 266 Z", "fill": shorts_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                    {"type": "path", "d": "M 238 269 C 245 279, 249 290, 251 304 C 248 309, 244 313, 239 315 C 232 311, 228 304, 227 294 C 228 284, 231 276, 238 269 Z", "fill": "#111827", "opacity": 0.14, "stroke": "none"},
                    {"type": "path", "d": "M 274 269 C 281 276, 284 284, 285 294 C 284 304, 280 311, 273 315 C 268 313, 264 309, 261 304 C 263 290, 267 279, 274 269 Z", "fill": "#111827", "opacity": 0.14, "stroke": "none"},
                    {"type": "path", "d": "M 255 276 C 254 286, 254 294, 256 302 C 258 294, 258 286, 257 276", "fill": "none", "stroke": "#364152", "stroke_width": 2.2, "opacity": 0.45},
                ],
            },
            "left_thigh": {
                "bbox": (207, 309, 48, 74),
                "elements": [
                    {"type": "path", "d": pieces["left_thigh"]["d"], "fill": skin_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                ],
            },
            "right_thigh": {
                "bbox": (257, 309, 48, 74),
                "elements": [
                    {"type": "path", "d": pieces["right_thigh"]["d"], "fill": skin_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                ],
            },
            "left_leg": {
                "bbox": (209, 350, 40, 77),
                "elements": [
                    {"type": "path", "d": "M 224 354 C 215 360, 212 375, 214 393 C 216 408, 220 418, 226 424 C 233 426, 239 424, 243 417 C 245 403, 243 388, 239 372 C 236 362, 231 356, 224 354 Z", "fill": skin_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                    {"type": "path", "d": "M 226 359 C 224 377, 225 395, 228 414", "fill": "none", "stroke": "#af7e59", "stroke_width": 3.5, "opacity": 0.18, "stroke_linecap": "round"},
                ],
            },
            "right_leg": {
                "bbox": (263, 350, 40, 77),
                "elements": [
                    {"type": "path", "d": "M 288 354 C 297 360, 300 375, 298 393 C 296 408, 292 418, 286 424 C 279 426, 273 424, 269 417 C 267 403, 269 388, 273 372 C 276 362, 281 356, 288 354 Z", "fill": skin_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                    {"type": "path", "d": "M 286 359 C 288 377, 287 395, 284 414", "fill": "none", "stroke": "#af7e59", "stroke_width": 3.5, "opacity": 0.18, "stroke_linecap": "round"},
                ],
            },
            "left_sock": {
                "bbox": (211, 362, 36, 63),
                "elements": [
                    {"type": "path", "d": "M 219 361 C 213 372, 212 386, 214 404 C 216 415, 220 421, 226 423 C 233 424, 238 422, 241 417 C 241 397, 240 378, 237 362 C 231 358, 225 358, 219 361 Z", "fill": socks_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                    {"type": "line", "start": (220, 372), "end": (241, 372), "stroke": KIT["sock_band"], "stroke_width": 5, "opacity": 0.95},
                ],
            },
            "right_sock": {
                "bbox": (265, 362, 36, 63),
                "elements": [
                    {"type": "path", "d": "M 293 361 C 299 372, 300 386, 298 404 C 296 415, 292 421, 286 423 C 279 424, 274 422, 271 417 C 271 397, 272 378, 275 362 C 281 358, 287 358, 293 361 Z", "fill": socks_fill, "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                    {"type": "line", "start": (271, 372), "end": (292, 372), "stroke": KIT["sock_band"], "stroke_width": 5, "opacity": 0.95},
                ],
            },
            "left_boot": {
                "bbox": (204, 417, 58, 30),
                "elements": [
                    {"type": "path", "d": "M 217 421 C 210 422, 205 426, 205 432 C 205 438, 211 442, 223 443 C 235 444, 248 443, 257 440 C 260 437, 259 433, 254 429 C 247 425, 239 423, 232 422 C 228 418, 222 418, 217 421 Z", "fill": KIT["boots"], "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                    {"type": "path", "d": "M 231 423 C 239 424, 246 426, 252 430", "fill": "none", "stroke": "#334155", "stroke_width": 2, "opacity": 0.45},
                ],
            },
            "right_boot": {
                "bbox": (250, 417, 58, 30),
                "elements": [
                    {"type": "path", "d": "M 295 421 C 302 422, 307 426, 307 432 C 307 438, 301 442, 289 443 C 277 444, 264 443, 255 440 C 252 437, 253 433, 258 429 C 265 425, 273 423, 280 422 C 284 418, 290 418, 295 421 Z", "fill": KIT["boots"], "stroke": KIT["outline"], "stroke_width": 3, "stroke_linejoin": "round", "stroke_linecap": "round"},
                    {"type": "path", "d": "M 281 423 C 273 424, 266 426, 260 430", "fill": "none", "stroke": "#334155", "stroke_width": 2, "opacity": 0.45},
                ],
            },
            "shadow": {
                "bbox": (180, 440, 152, 32),
                "elements": [
                    {"type": "ellipse", "center": (256, 456), "r": (70, 15), "fill": KIT["shadow"], "opacity": 0.18},
                ],
            },
        }
        return defs

    def _draw_player(self, back: bool, side: bool, flip: bool) -> None:
        group = self.dwg.g()
        hip_x = CANVAS_W / 2 + self.pose.hip_shift
        hip_y = 240 + self.pose.support_bias
        shoulder_y = 154 + self.pose.shoulder_shift
        shoulder_span = 98
        torso_height = 116
        head_center = (hip_x + self.pose.head_turn * 0.4, 94 + self.pose.body_tilt * 0.5)
        neck_y = 134
        left_shoulder = (hip_x - shoulder_span / 2, shoulder_y)
        right_shoulder = (hip_x + shoulder_span / 2, shoulder_y)
        left_hip = (hip_x - 34, hip_y)
        right_hip = (hip_x + 34, hip_y)

        if flip:
            left_shoulder, right_shoulder = right_shoulder, left_shoulder
            left_hip, right_hip = right_hip, left_hip

        # Legs behind shorts so silhouette reads naturally.
        self._draw_leg(group, left_hip, self.pose.left_thigh, self.pose.left_shin, support=not side, side=side)
        self._draw_leg(group, right_hip, self.pose.right_thigh, self.pose.right_shin, support=side, side=side)

        torso = self._torso_points(hip_x, shoulder_y, hip_y, shoulder_span, torso_height, back=back, side=side)
        group.add(
            self.dwg.path(
                d=quad_path(torso),
                fill=self.shirt_fill,
                stroke=KIT["outline"],
                stroke_width=3,
                stroke_linejoin="round",
            )
        )

        self._draw_shirt_details(group, hip_x, shoulder_y, hip_y, back=back, side=side)
        self._draw_arm(group, left_shoulder, self.pose.left_arm, self.pose.left_forearm, flip=flip)
        self._draw_arm(group, right_shoulder, self.pose.right_arm, self.pose.right_forearm, flip=flip, mirrored=True)
        self._draw_head(group, head_center, back=back, side=side, flip=flip)
        self._draw_shorts(group, hip_x, hip_y, side=side, back=back)
        self._draw_number(group, hip_x, shoulder_y, hip_y, back=back)
        self._draw_boot_overlay(group, hip_x)

        self.dwg.add(group)

    def _torso_points(self, hip_x: float, shoulder_y: float, hip_y: float, shoulder_span: float, torso_height: float, back: bool, side: bool) -> List[Tuple[float, float]]:
        left = hip_x - shoulder_span / 2
        right = hip_x + shoulder_span / 2
        waist_left = hip_x - 44
        waist_right = hip_x + 44
        hem_left = hip_x - 36
        hem_right = hip_x + 36
        chest_y = shoulder_y + 34
        mid_y = shoulder_y + torso_height * 0.52
        neck_left = hip_x - 22
        neck_right = hip_x + 22
        if side:
            left += 18 * self.pose.facing
            waist_left += 12 * self.pose.facing
            hem_left += 8 * self.pose.facing
            right -= 8 * self.pose.facing
        if back:
            chest_y += 4
        return [
            (neck_left, shoulder_y - 10),
            (left, shoulder_y + 6), (left + 6, chest_y),
            (waist_left, mid_y), (hem_left, hip_y - 12),
            (hip_x, hip_y + 8), (hem_right, hip_y - 12),
            (waist_right, mid_y), (right - 6, chest_y),
            (right, shoulder_y + 6), (neck_right, shoulder_y - 10),
            (hip_x + 10, shoulder_y - 4), (neck_left, shoulder_y - 10),
        ]

    def _draw_shirt_details(self, group: svgwrite.container.Group, hip_x: float, shoulder_y: float, hip_y: float, back: bool, side: bool) -> None:
        # Collar
        group.add(
            self.dwg.path(
                d=f"M {hip_x - 20:.2f} {shoulder_y - 2:.2f} Q {hip_x:.2f} {shoulder_y + 12:.2f} {hip_x + 20:.2f} {shoulder_y - 2:.2f}",
                fill="none",
                stroke=KIT["trim"],
                stroke_width=5,
                stroke_linecap="round",
            )
        )
        # Sleeve trim
        group.add(self.dwg.path(d=f"M {hip_x - 62:.2f} {shoulder_y + 18:.2f} Q {hip_x - 48:.2f} {shoulder_y + 10:.2f} {hip_x - 36:.2f} {shoulder_y + 28:.2f}", fill="none", stroke=KIT["trim"], stroke_width=6, stroke_linecap="round"))
        group.add(self.dwg.path(d=f"M {hip_x + 62:.2f} {shoulder_y + 18:.2f} Q {hip_x + 48:.2f} {shoulder_y + 10:.2f} {hip_x + 36:.2f} {shoulder_y + 28:.2f}", fill="none", stroke=KIT["trim"], stroke_width=6, stroke_linecap="round"))
        # Side highlight
        group.add(self.dwg.path(d=f"M {hip_x - 28:.2f} {shoulder_y + 24:.2f} Q {hip_x - 20:.2f} {hip_y - 18:.2f} {hip_x - 8:.2f} {hip_y - 6:.2f}", fill="none", stroke="#6dc0ff", stroke_width=3, opacity=0.45))
        if not back and not side:
            group.add(self.dwg.path(d=f"M {hip_x - 10:.2f} {shoulder_y + 10:.2f} H {hip_x + 10:.2f}", fill="none", stroke="#f9fbff", stroke_width=2.5, opacity=0.7))

    def _draw_arm(self, group: svgwrite.container.Group, shoulder: Tuple[float, float], upper_deg: float, lower_deg: float, flip: bool, mirrored: bool = False) -> None:
        upper_len = 44
        lower_len = 40
        upper_width = 20
        lower_width = 18
        sx, sy = shoulder
        if mirrored:
            upper_deg *= 1
        elbow = rotate_point(sx, sy + upper_len, sx, sy, upper_deg)
        wrist = rotate_point(elbow[0], elbow[1] + lower_len, elbow[0], elbow[1], upper_deg + lower_deg)
        upper = self._capsule_polygon((sx, sy), elbow, upper_width)
        lower = self._capsule_polygon(elbow, wrist, lower_width)
        hand = self._capsule_polygon(wrist, (wrist[0] + (10 if self.pose.facing > 0 else -10), wrist[1] + 8), 14)
        group.add(self.dwg.polygon(points=points_to_str(upper), fill=self.skin_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round"))
        group.add(self.dwg.polygon(points=points_to_str(lower), fill=self.skin_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round"))
        group.add(self.dwg.polygon(points=points_to_str(hand), fill=self.skin_fill, stroke=KIT["outline"], stroke_width=2.4, stroke_linejoin="round"))

    def _draw_leg(self, group: svgwrite.container.Group, hip: Tuple[float, float], thigh_deg: float, shin_deg: float, support: bool, side: bool) -> None:
        thigh_len = 68
        shin_len = 78
        thigh_width = 28
        shin_width = 22
        hx, hy = hip
        knee = rotate_point(hx, hy + thigh_len, hx, hy, thigh_deg)
        ankle = rotate_point(knee[0], knee[1] + shin_len, knee[0], knee[1], thigh_deg + shin_deg)
        thigh = self._capsule_polygon((hx, hy), knee, thigh_width)
        shin = self._capsule_polygon(knee, ankle, shin_width)
        group.add(self.dwg.polygon(points=points_to_str(thigh), fill=KIT["shorts_fill"] if False else self.skin_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round"))
        # shorts overlap at top
        sock_top = ((knee[0] + ankle[0]) / 2, (knee[1] + ankle[1]) / 2 + 8)
        calf = self._capsule_polygon(knee, ankle, shin_width)
        group.add(self.dwg.polygon(points=points_to_str(calf), fill=self.socks_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round"))
        band_y1 = (knee[1] * 0.65 + ankle[1] * 0.35)
        group.add(self.dwg.line(start=(knee[0] - 10, band_y1), end=(knee[0] + 10, band_y1), stroke=KIT["sock_band"], stroke_width=5, opacity=0.95))
        boot = self._boot_shape(ankle, angle=thigh_deg + shin_deg + (-8 if support else 6), support=support)
        group.add(self.dwg.path(d=quad_path(boot), fill=KIT["boots"], stroke=KIT["outline"], stroke_width=3))

    def _draw_shorts(self, group: svgwrite.container.Group, hip_x: float, hip_y: float, side: bool, back: bool) -> None:
        shorts = [
            (hip_x - 48, hip_y - 24),
            (hip_x - 42, hip_y + 12),
            (hip_x - 28, hip_y + 32),
            (hip_x - 2, hip_y + 18),
            (hip_x + 2, hip_y + 18),
            (hip_x + 28, hip_y + 32),
            (hip_x + 42, hip_y + 12),
            (hip_x + 48, hip_y - 24),
            (hip_x + 20, hip_y - 14),
            (hip_x - 20, hip_y - 14),
        ]
        group.add(self.dwg.path(d=quad_path(shorts), fill=self.shorts_fill, stroke=KIT["outline"], stroke_width=3, stroke_linejoin="round"))
        group.add(self.dwg.line(start=(hip_x, hip_y - 10), end=(hip_x, hip_y + 20), stroke="#364152", stroke_width=2.5, opacity=0.55))

    def _draw_head(self, group: svgwrite.container.Group, center: Tuple[float, float], back: bool, side: bool, flip: bool) -> None:
        cx, cy = center
        group.add(self.dwg.ellipse(center=(cx, cy), r=(38, 44), fill=self.skin_fill, stroke=KIT["outline"], stroke_width=3))
        hair_path = [
            (cx - 30, cy - 14),
            (cx - 24, cy - 42),
            (cx + 8, cy - 48),
            (cx + 28, cy - 26),
            (cx + 20, cy - 6),
            (cx - 2, cy - 12),
            (cx - 24, cy - 6),
        ]
        group.add(self.dwg.path(d=quad_path(hair_path), fill=KIT["hair"], stroke=KIT["outline"], stroke_width=2.4))
        group.add(self.dwg.path(d=f"M {cx - 18:.2f} {cy - 26:.2f} Q {cx + 4:.2f} {cy - 40:.2f} {cx + 18:.2f} {cy - 14:.2f}", fill="none", stroke=KIT["hair_gloss"], stroke_width=3, opacity=0.45))
        if not back:
            eye_y = cy - 6
            group.add(self.dwg.line(start=(cx - 14, eye_y), end=(cx - 4, eye_y - 2), stroke=KIT["outline"], stroke_width=2.8, stroke_linecap="round"))
            if not side:
                group.add(self.dwg.line(start=(cx + 2, eye_y - 1), end=(cx + 12, eye_y - 2), stroke=KIT["outline"], stroke_width=2.8, stroke_linecap="round"))
            group.add(self.dwg.path(d=f"M {cx - 6:.2f} {cy + 8:.2f} Q {cx + 2:.2f} {cy + 12:.2f} {cx + 8:.2f} {cy + 3:.2f}", fill="none", stroke=KIT['skin_shadow'], stroke_width=2.2, opacity=0.8))
            group.add(self.dwg.path(d=f"M {cx - 12:.2f} {cy + 20:.2f} Q {cx:.2f} {cy + 30:.2f} {cx + 14:.2f} {cy + 16:.2f}", fill="none", stroke=KIT['outline'], stroke_width=2.4, opacity=0.65))

    def _draw_number(self, group: svgwrite.container.Group, hip_x: float, shoulder_y: float, hip_y: float, back: bool) -> None:
        y = shoulder_y + 72 if back else hip_y - 36
        size = 48 if back else 34
        group.add(self.dwg.text(self.pose.number, insert=(hip_x, y), text_anchor="middle", font_size=size, font_family="Arial", font_weight="700", fill=KIT["number"], opacity=0.95))
        group.add(self.dwg.text(self.pose.number, insert=(hip_x + 2, y + 3), text_anchor="middle", font_size=size, font_family="Arial", font_weight="700", fill=KIT["number_shadow"], opacity=0.22))

    def _draw_boot_overlay(self, group: svgwrite.container.Group, hip_x: float) -> None:
        # Small highlight to avoid flat look near feet area.
        group.add(self.dwg.path(d=f"M {hip_x - 22:.2f} 382 Q {hip_x - 2:.2f} 392 {hip_x + 22:.2f} 384", fill="none", stroke="#f8fafc", stroke_width=2, opacity=0.12))

    def _capsule_polygon(self, start: Tuple[float, float], end: Tuple[float, float], width: float) -> List[Tuple[float, float]]:
        sx, sy = start
        ex, ey = end
        dx = ex - sx
        dy = ey - sy
        length = math.hypot(dx, dy) or 1.0
        nx = -dy / length
        ny = dx / length
        half = width / 2
        return [
            (sx + nx * half, sy + ny * half),
            (ex + nx * half, ey + ny * half),
            (ex - nx * half, ey - ny * half),
            (sx - nx * half, sy - ny * half),
        ]

    def _boot_shape(self, ankle: Tuple[float, float], angle: float, support: bool) -> List[Tuple[float, float]]:
        ax, ay = ankle
        length = 34 if support else 38
        width = 16
        toe = rotate_point(ax + length, ay + 4, ax, ay, angle)
        heel = rotate_point(ax - 6, ay - 4, ax, ay, angle)
        top1 = rotate_point(ax + 2, ay - width / 2, ax, ay, angle)
        top2 = rotate_point(ax + length * 0.9, ay - width / 2 + 3, ax, ay, angle)
        bot2 = rotate_point(ax + length * 0.9, ay + width / 2, ax, ay, angle)
        bot1 = rotate_point(ax - 6, ay + width / 2 - 1, ax, ay, angle)
        return [heel, top1, top2, toe, bot2, bot1]


def save_svg(dwg: svgwrite.Drawing, path: Path) -> None:
    path.write_text(dwg.tostring(), encoding="utf-8")


def svg_to_png(svg_path: Path, png_path: Path) -> None:
    try:
        import cairosvg  # type: ignore

        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(png_path),
            output_width=CANVAS_W,
            output_height=CANVAS_H,
        )
        return
    except Exception:
        pass

    node_bin = shutil.which("node")
    if node_bin:
        sharp_script = (
            "const sharp=require('sharp');"
            "const [input,output,w,h]=process.argv.slice(1);"
            "sharp(input).resize(Number(w),Number(h),{fit:'contain',background:{r:0,g:0,b:0,alpha:0}})"
            ".png().toFile(output).catch(err=>{console.error(err);process.exit(1);});"
        )
        subprocess.run(
            [node_bin, "-e", sharp_script, str(svg_path), str(png_path), str(CANVAS_W), str(CANVAS_H)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    inkscape_bin = shutil.which("inkscape")
    if not inkscape_bin:
        app_bin = Path("/Applications/Inkscape.app/Contents/MacOS/inkscape")
        if app_bin.exists():
            inkscape_bin = str(app_bin)
    if inkscape_bin:
        subprocess.run(
            [
                inkscape_bin,
                str(svg_path),
                "--export-type=png",
                f"--export-filename={png_path}",
                f"--export-width={CANVAS_W}",
                f"--export-height={CANVAS_H}",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    raise RuntimeError("No PNG renderer available: cairosvg failed and Inkscape CLI is unavailable.")


def build_contact_sheet(png_paths: Sequence[Path], output_path: Path) -> None:
    cols = 3
    thumb = (180, 180)
    title_h = 38
    margin = 18
    rows = math.ceil(len(png_paths) / cols)
    sheet = Image.new("RGBA", (cols * (thumb[0] + margin) + margin, rows * (thumb[1] + title_h + margin) + margin), (16, 21, 29, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, png_path in enumerate(png_paths):
        row = idx // cols
        col = idx % cols
        x = margin + col * (thumb[0] + margin)
        y = margin + row * (thumb[1] + title_h + margin)
        draw.rounded_rectangle((x, y, x + thumb[0], y + thumb[1] + title_h), radius=18, fill=(27, 36, 49, 255), outline=(58, 72, 88, 255), width=2)
        draw.text((x + 14, y + 12), png_path.stem, fill=(242, 246, 252, 255), font=font)
        image = Image.open(png_path).convert("RGBA")
        image.thumbnail((thumb[0] - 28, thumb[1] - 20))
        paste_x = x + (thumb[0] - image.width) // 2
        paste_y = y + title_h + (thumb[1] - image.height) // 2
        sheet.alpha_composite(image, (paste_x, paste_y))
    sheet.save(output_path)


def generate_preview_html(variants: Sequence[Path], png_variants: Sequence[Path], html_path: Path) -> None:
    cards = []
    for svg_path, png_path in zip(variants, png_variants):
        rel_svg = svg_path.relative_to(ROOT).as_posix()
        rel_png = png_path.relative_to(ROOT).as_posix()
        png_data = base64.b64encode(png_path.read_bytes()).decode("ascii")
        cards.append(
            f"""
            <article class=\"card\">
              <div class=\"preview\"><img src=\"data:image/png;base64,{png_data}\" alt=\"{svg_path.stem}\"></div>
              <div class=\"meta\">
                <h2>{svg_path.stem}</h2>
                <p>SVG: <code>{rel_svg}</code></p>
                <p>PNG: <code>{rel_png}</code></p>
              </div>
            </article>
            """
        )
    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Segunda Jugada · Player Assets Preview</title>
  <style>
    :root {{
      --bg: #08111a;
      --panel: #121e2c;
      --panel-2: #1a2738;
      --border: #2e4056;
      --text: #edf3fb;
      --muted: #9db0c8;
      --accent: #8ddc57;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, system-ui, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(141,220,87,.12), transparent 28%),
        linear-gradient(180deg, #08111a, #101923 55%, #08111a);
      color: var(--text);
      padding: 32px;
    }}
    .hero {{
      max-width: 1080px;
      margin: 0 auto 26px;
      padding: 28px 30px;
      border-radius: 26px;
      background: linear-gradient(135deg, rgba(17,30,46,.95), rgba(18,44,32,.94));
      border: 1px solid rgba(255,255,255,.08);
      box-shadow: 0 24px 48px rgba(0,0,0,.32);
    }}
    .hero h1 {{
      margin: 0 0 10px;
      font-size: clamp(30px, 5vw, 54px);
      line-height: .95;
      letter-spacing: -.05em;
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
      max-width: 860px;
    }}
    .grid {{
      max-width: 1080px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 18px;
    }}
    .card {{
      border-radius: 24px;
      overflow: hidden;
      background: var(--panel);
      border: 1px solid var(--border);
      box-shadow: 0 20px 32px rgba(0,0,0,.22);
    }}
    .preview {{
      aspect-ratio: 1 / 1;
      display: grid;
      place-items: center;
      background:
        radial-gradient(circle at 35% 18%, rgba(255,255,255,.16), transparent 30%),
        linear-gradient(180deg, #202d3f, #111b28 70%);
      padding: 18px;
    }}
    .preview img {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      filter: drop-shadow(0 18px 28px rgba(0,0,0,.42));
    }}
    .meta {{
      padding: 16px 18px 18px;
      background: var(--panel);
    }}
    .meta h2 {{
      margin: 0 0 10px;
      font-size: 20px;
      letter-spacing: -.03em;
    }}
    .meta p {{
      margin: 6px 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
      word-break: break-word;
    }}
    code {{
      color: #d5e4ff;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
  </style>
</head>
<body>
  <header class=\"hero\">
    <h1>Segunda Jugada Player Asset Kit</h1>
    <p>Pipeline vectorial premium generado por código. Variantes base para frente, espalda, perfil, carrera, pase y defensa. Este preview sirve como revisión visual rápida antes de conectar los assets a la biblioteca definitiva.</p>
  </header>
  <section class=\"grid\">
    {''.join(cards)}
  </section>
</body>
</html>"""
    html_path.write_text(html, encoding="utf-8")


def generate_front_comparison_html(
    left_png: Path,
    right_png: Path,
    html_path: Path,
    *,
    left_label: str = "player_front (actual)",
    right_label: str = "player_front_v2",
    title: str = "Player Front Comparison",
    description: str = "Comparativa directa entre la versión aprobada actual y la reinterpretación <code>player_front_v2</code>.",
) -> None:
    left_b64 = base64.b64encode(left_png.read_bytes()).decode("ascii")
    right_b64 = base64.b64encode(right_png.read_bytes()).decode("ascii")
    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      font-family: Inter, system-ui, sans-serif;
      background: linear-gradient(180deg, #eef2f7, #dde5ef);
      color: #0f172a;
      padding: 28px;
    }}
    .wrap {{ max-width: 1100px; margin: 0 auto; }}
    h1 {{ margin: 0 0 10px; font-size: 36px; letter-spacing: -.04em; }}
    p {{ margin: 0 0 24px; color: #475569; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 22px; }}
    .card {{
      background: rgba(255,255,255,.92);
      border: 1px solid rgba(15,23,42,.08);
      border-radius: 24px;
      box-shadow: 0 18px 38px rgba(15,23,42,.10);
      overflow: hidden;
    }}
    .label {{
      padding: 16px 18px;
      font-weight: 800;
      font-size: 18px;
      border-bottom: 1px solid rgba(15,23,42,.08);
      background: linear-gradient(90deg, rgba(21,99,232,.08), rgba(15,23,42,.03));
    }}
    .preview {{
      padding: 24px;
      display: grid;
      place-items: center;
      background: radial-gradient(circle at top, rgba(255,255,255,.9), rgba(226,232,240,.8));
    }}
    img {{ width: min(100%, 420px); height: auto; display: block; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>{title}</h1>
    <p>{description}</p>
    <div class="grid">
      <section class="card">
        <div class="label">{left_label}</div>
        <div class="preview"><img src="data:image/png;base64,{left_b64}" alt="{left_label}"></div>
      </section>
      <section class="card">
        <div class="label">{right_label}</div>
        <div class="preview"><img src="data:image/png;base64,{right_b64}" alt="{right_label}"></div>
      </section>
    </div>
  </div>
</body>
</html>"""
    html_path.write_text(html, encoding="utf-8")


def _draw_modular_element(dwg: svgwrite.Drawing, group: svgwrite.container.Group, element: Dict[str, object]) -> None:
    element_type = element["type"]
    common = {}
    for key in ("fill", "stroke", "stroke_width", "opacity", "stroke_linejoin", "stroke_linecap", "text_anchor", "font_size", "font_family", "font_weight"):
        if key in element:
            common[key] = element[key]
    if element_type == "path":
        group.add(dwg.path(d=element["d"], **common))
    elif element_type == "line":
        group.add(dwg.line(start=element["start"], end=element["end"], **common))
    elif element_type == "ellipse":
        group.add(dwg.ellipse(center=element["center"], r=element["r"], **common))
    elif element_type == "text":
        group.add(dwg.text(element["text"], insert=(element["x"], element["y"]), **common))


def _save_modular_piece_svg(piece_name: str, piece_def: Dict[str, object], output_path: Path) -> None:
    x, y, w, h = piece_def["bbox"]
    padding = 12
    dwg = svgwrite.Drawing(size=(w + padding * 2, h + padding * 2), viewBox=f"0 0 {w + padding * 2} {h + padding * 2}")
    group = dwg.g(transform=f"translate({padding - x:.2f},{padding - y:.2f})")
    for element in piece_def["elements"]:
        _draw_modular_element(dwg, group, element)
    dwg.add(group)
    save_svg(dwg, output_path)


def generate_modular_front_assets() -> Tuple[Path, Path, List[Tuple[str, Path]]]:
    builder = PremiumPlayerAssetBuilder(next(pose for pose in POSES if pose.name == "player_front_v3"))
    piece_defs = builder.modular_piece_definitions_v3()
    piece_paths: List[Tuple[str, Path]] = []
    for piece_name, piece_def in piece_defs.items():
        piece_path = MODULAR_DIR / f"{piece_name}.svg"
        _save_modular_piece_svg(piece_name, piece_def, piece_path)
        piece_paths.append((piece_name, piece_path))

    assembled = svgwrite.Drawing(size=(CANVAS_W, CANVAS_H), viewBox=f"0 0 {CANVAS_W} {CANVAS_H}")
    assembled.add(assembled.rect(insert=(0, 0), size=(CANVAS_W, CANVAS_H), fill="none"))
    order = [
        "shadow",
        "left_thigh",
        "right_thigh",
        "left_leg",
        "right_leg",
        "left_sock",
        "right_sock",
        "left_boot",
        "right_boot",
        "left_upper_arm",
        "right_upper_arm",
        "left_forearm",
        "right_forearm",
        "left_hand",
        "right_hand",
        "torso",
        "shorts",
        "neck",
        "head",
    ]
    for piece_name in order:
        piece_def = piece_defs[piece_name]
        group = assembled.g(id=piece_name)
        for element in piece_def["elements"]:
            _draw_modular_element(assembled, group, element)
        assembled.add(group)

    modular_svg = SVG_DIR / "player_front_modular.svg"
    modular_png = PNG_DIR / "player_front_modular.png"
    save_svg(assembled, modular_svg)
    svg_to_png(modular_svg, modular_png)
    return modular_svg, modular_png, piece_paths


def generate_modular_parts_preview_html(
    piece_paths: Sequence[Tuple[str, Path]],
    base_png: Path,
    modular_png: Path,
    html_path: Path,
) -> None:
    cards: List[str] = []
    for piece_name, piece_path in piece_paths:
        svg_b64 = base64.b64encode(piece_path.read_bytes()).decode("ascii")
        cards.append(
            f"""
            <article class="part-card">
              <div class="part-preview"><img src="data:image/svg+xml;base64,{svg_b64}" alt="{piece_name}"></div>
              <div class="part-meta">
                <strong>{piece_name}.svg</strong>
                <span>{piece_path.relative_to(ROOT).as_posix()}</span>
              </div>
            </article>
            """
        )
    base_b64 = base64.b64encode(base_png.read_bytes()).decode("ascii")
    modular_b64 = base64.b64encode(modular_png.read_bytes()).decode("ascii")
    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Player Modular Parts Preview</title>
  <style>
    :root {{
      --bg: #08111a;
      --panel: #121d2b;
      --panel-2: #182636;
      --line: #284157;
      --text: #ecf4ff;
      --muted: #9ab0c8;
      --accent: #79d257;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, system-ui, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(121,210,87,.12), transparent 28%),
        linear-gradient(180deg, #08111a, #0f1822 55%, #08111a);
      color: var(--text);
      padding: 30px;
    }}
    .wrap {{ max-width: 1380px; margin: 0 auto; }}
    .hero {{
      padding: 28px 30px;
      border-radius: 28px;
      background: linear-gradient(135deg, rgba(17,31,48,.96), rgba(17,44,37,.96));
      border: 1px solid rgba(255,255,255,.08);
      box-shadow: 0 24px 52px rgba(0,0,0,.34);
      margin-bottom: 26px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 42px; letter-spacing: -.04em; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.55; }}
    .comparison {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 20px;
      margin-bottom: 28px;
    }}
    .compare-card, .parts-section {{
      border-radius: 24px;
      overflow: hidden;
      border: 1px solid var(--line);
      background: var(--panel);
      box-shadow: 0 18px 42px rgba(0,0,0,.28);
    }}
    .section-head {{
      padding: 16px 20px;
      font-size: 18px;
      font-weight: 800;
      letter-spacing: .02em;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(90deg, rgba(121,210,87,.12), rgba(255,255,255,.02));
    }}
    .compare-preview {{
      display: grid;
      place-items: center;
      min-height: 420px;
      background:
        radial-gradient(circle at 32% 16%, rgba(255,255,255,.14), transparent 32%),
        linear-gradient(180deg, #1a2838, #101821 78%);
      padding: 18px;
    }}
    .compare-preview img {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      filter: drop-shadow(0 18px 28px rgba(0,0,0,.45));
    }}
    .parts-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      padding: 18px;
    }}
    .part-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
      background: var(--panel-2);
    }}
    .part-preview {{
      aspect-ratio: 1 / 1;
      display: grid;
      place-items: center;
      padding: 14px;
      background:
        radial-gradient(circle at 35% 18%, rgba(255,255,255,.16), transparent 32%),
        linear-gradient(180deg, #24364b, #172434 76%);
    }}
    .part-preview img {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }}
    .part-meta {{
      padding: 12px 14px 14px;
      display: grid;
      gap: 6px;
    }}
    .part-meta strong {{ font-size: 14px; }}
    .part-meta span {{
      color: var(--muted);
      font-size: 12px;
      word-break: break-word;
      line-height: 1.4;
    }}
    @media (max-width: 980px) {{
      .comparison {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>Segunda Jugada · Player Modular Library</h1>
      <p>Despiece SVG modular generado desde la base visual aprobada <code>player_front_v3</code>. La comparación permite validar el ensamblado completo y revisar cada pieza por separado antes de extender el SDK a más vistas y poses.</p>
    </header>
    <section class="comparison">
      <article class="compare-card">
        <div class="section-head">player_front_v3 · base visual aprobada</div>
        <div class="compare-preview"><img src="data:image/png;base64,{base_b64}" alt="player_front_v3"></div>
      </article>
      <article class="compare-card">
        <div class="section-head">player_front_modular · ensamblado por piezas</div>
        <div class="compare-preview"><img src="data:image/png;base64,{modular_b64}" alt="player_front_modular"></div>
      </article>
    </section>
    <section class="parts-section">
      <div class="section-head">Piezas SVG modulares</div>
      <div class="parts-grid">
        {''.join(cards)}
      </div>
    </section>
  </div>
</body>
</html>"""
    html_path.write_text(html, encoding="utf-8")


def maybe_copy_preview_to_downloads(source: Path) -> None:
    if shutil.which("cp") is None:
        return
    try:
        DOWNLOADS_HTML.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, DOWNLOADS_HTML)
    except Exception:
        pass


def maybe_generate_source_manifest() -> None:
    manifest = SOURCE_DIR / "README.txt"
    manifest.write_text(
        "Player Asset Kit premium generado por código con svgwrite/cairosvg.\\n"
        "Las poses viven en tools/generate_player_assets.py y se exportan a svg/, png/ y previews/.\\n",
        encoding="utf-8",
    )


def run_svgo_on_generated_assets() -> None:
    if shutil.which("npx") is None:
        return
    try:
        svg_targets = [str(path) for path in sorted(SVG_DIR.glob("*.svg"))]
        svg_targets.extend(str(path) for path in sorted(MODULAR_DIR.glob("*.svg")))
        subprocess.run(["npx", "svgo", *svg_targets], cwd=ROOT, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def main() -> None:
    ensure_dirs()
    maybe_generate_source_manifest()
    svg_paths: List[Path] = []
    png_paths: List[Path] = []
    for pose in POSES:
        builder = PremiumPlayerAssetBuilder(pose)
        drawing = builder.draw()
        svg_path = SVG_DIR / f"{pose.name}.svg"
        png_path = PNG_DIR / f"{pose.name}.png"
        save_svg(drawing, svg_path)
        svg_to_png(svg_path, png_path)
        svg_paths.append(svg_path)
        png_paths.append(png_path)
    build_contact_sheet(png_paths, PREVIEW_DIR / "player_contact_sheet.png")
    generate_preview_html(svg_paths, png_paths, TMP_HTML)
    generate_front_comparison_html(
        PNG_DIR / "player_front.png",
        PNG_DIR / "player_front_v2.png",
        TMP_FRONT_V2_HTML,
    )
    generate_front_comparison_html(
        PNG_DIR / "player_front_v2.png",
        PNG_DIR / "player_front_v3.png",
        TMP_FRONT_V3_HTML,
        left_label="player_front_v2",
        right_label="player_front_v3",
        title="Player Front Comparison v2 vs v3",
        description="Comparativa directa entre <code>player_front_v2</code> y la nueva reinterpretación <code>player_front_v3</code>.",
    )
    modular_svg, modular_png, modular_piece_paths = generate_modular_front_assets()
    generate_modular_parts_preview_html(
        modular_piece_paths,
        PNG_DIR / "player_front_v3.png",
        modular_png,
        TMP_MODULAR_HTML,
    )
    svg_paths.append(modular_svg)
    png_paths.append(modular_png)
    maybe_copy_preview_to_downloads(TMP_HTML)
    run_svgo_on_generated_assets()
    print(f"Generated {len(svg_paths)} SVG assets in {SVG_DIR}")
    print(f"Generated {len(png_paths)} PNG previews in {PNG_DIR}")
    print(f"Preview HTML: {TMP_HTML}")
    print(f"Front V2 Preview HTML: {TMP_FRONT_V2_HTML}")
    print(f"Front V3 Comparison HTML: {TMP_FRONT_V3_HTML}")
    print(f"Modular Preview HTML: {TMP_MODULAR_HTML}")


if __name__ == "__main__":
    main()
