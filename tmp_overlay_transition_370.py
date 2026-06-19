from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


SOURCE = Path("/Volumes/Mac Satecchi/Mac/Web-stats/media/rival-videos/video-youtube-analisis-proxy.mp4")
OUT = Path("/Volumes/Mac Satecchi/Mac/Downloads/IA_MaxCuts_SeniorCoach108_video_7/annotated_cv/annotated_cv_370_CORREGIDO_presion_orientada_pase_espalda.mp4")
START_S = 2.0
END_S = 48.0


def alpha_poly(frame, pts, color, alpha=0.25):
    overlay = frame.copy()
    cv2.fillPoly(overlay, [np.array(pts, dtype=np.int32)], color)
    return cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)


def arrow(frame, p1, p2, color=(0, 0, 255), thickness=4):
    cv2.arrowedLine(frame, p1, p2, color, thickness, cv2.LINE_AA, tipLength=0.12)


def ellipse(frame, center, axes, color=(0, 255, 255), thickness=5):
    cv2.ellipse(frame, center, axes, 0, 0, 360, color, thickness, cv2.LINE_AA)


def label(frame, text, org, color=(255, 255, 255), bg=(10, 10, 10), scale=0.62):
    x, y = org
    font = cv2.FONT_HERSHEY_SIMPLEX
    (w, h), _ = cv2.getTextSize(text, font, scale, 2)
    cv2.rectangle(frame, (x - 10, y - h - 12), (x + w + 10, y + 10), bg, -1)
    cv2.rectangle(frame, (x - 10, y - h - 12), (x + w + 10, y + 10), color, 2)
    cv2.putText(frame, text, (x, y), font, scale, color, 2, cv2.LINE_AA)


def panel(frame, title, line1, line2):
    h, w = frame.shape[:2]
    y0 = h - 154
    overlay = frame.copy()
    cv2.rectangle(overlay, (24, y0), (w - 24, h - 24), (8, 13, 24), -1)
    frame[:] = cv2.addWeighted(overlay, 0.74, frame, 0.26, 0)
    cv2.rectangle(frame, (24, y0), (w - 24, h - 24), (0, 220, 255), 3)
    cv2.putText(frame, title, (52, y0 + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.86, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, line1, (52, y0 + 78), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (232, 244, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, line2, (52, y0 + 108), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (232, 244, 255), 2, cv2.LINE_AA)


def draw_phase(frame, rel_t):
    # Coordenadas manuales por plano de broadcast para convertir la correccion
    # del entrenador en un ejemplo visual que la IA pueda aprender.
    if 5.8 <= rel_t <= 9.4:
        # Presion orientada del Malaga: se cierra dentro y se invita salida derecha.
        press_zone = [(475, 230), (745, 230), (810, 420), (500, 450)]
        right_exit = [(840, 300), (1210, 260), (1220, 455), (870, 500)]
        frame[:] = alpha_poly(frame, press_zone, (0, 190, 255), 0.22)
        frame[:] = alpha_poly(frame, right_exit, (0, 0, 255), 0.14)
        ellipse(frame, (630, 330), (70, 48), (0, 255, 255), 5)
        arrow(frame, (565, 320), (690, 330), (0, 255, 255), 4)
        arrow(frame, (720, 350), (975, 380), (0, 0, 255), 5)
        label(frame, "presion orientada Malaga", (470, 205), (0, 255, 255), (20, 30, 35))
        label(frame, "salida forzada a derecha", (850, 285), (80, 210, 255), (45, 10, 10))
        panel(
            frame,
            "Fase 1: presion orientada",
            "Malaga cierra dentro y obliga a Las Palmas a sacar por derecha.",
            "La IA debe capturar direccion de la presion, no solo posesion.",
        )
    elif 12.0 < rel_t <= 22.0:
        # El lanzador no tiene oposicion y el carrilero esta alto.
        launcher = (795, 315)
        wingback = (935, 245)
        back_space = [(910, 230), (1160, 205), (1180, 365), (940, 395)]
        frame[:] = alpha_poly(frame, back_space, (0, 0, 255), 0.24)
        ellipse(frame, launcher, (50, 45), (0, 255, 255), 5)
        ellipse(frame, wingback, (42, 56), (255, 170, 0), 4)
        arrow(frame, (795, 315), (1065, 285), (0, 0, 255), 5)
        arrow(frame, (930, 245), (1030, 235), (255, 170, 0), 4)
        label(frame, "lanzador sin presion", (680, 245), (0, 255, 255), (20, 30, 35))
        label(frame, "carrilero adelantado", (885, 195), (255, 210, 100), (20, 25, 45))
        label(frame, "pase a espalda facil", (980, 410), (80, 210, 255), (45, 10, 10))
        panel(
            frame,
            "Fase 2: no hay oposicion al lanzador",
            "Al no saltar sobre el pasador, el pase a la espalda queda limpio.",
            "El carrilero adelantado abre el espacio que se ataca.",
        )
    elif 22.0 < rel_t <= 34.0:
        # Transicion defensa-ataque y superioridad en carril derecho.
        lane = [(690, 255), (1245, 205), (1260, 545), (720, 560)]
        frame[:] = alpha_poly(frame, lane, (0, 0, 255), 0.18)
        arrow(frame, (675, 360), (930, 330), (0, 0, 255), 5)
        arrow(frame, (820, 470), (1040, 390), (0, 0, 255), 5)
        ellipse(frame, (870, 340), (48, 52), (0, 255, 255), 5)
        ellipse(frame, (1025, 380), (48, 52), (0, 255, 255), 5)
        label(frame, "superioridad carril derecho", (740, 230), (80, 210, 255), (45, 10, 10))
        panel(
            frame,
            "Fase 3: transicion defensa-ataque",
            "La salida forzada se convierte en ventaja por carril derecho.",
            "Hay superioridad y carrera a espalda antes de la ocasion.",
        )
    elif 34.0 < rel_t <= 44.5:
        # Consecuencia: ocasion de gol.
        danger = [(720, 165), (1180, 155), (1180, 480), (730, 500)]
        frame[:] = alpha_poly(frame, danger, (0, 0, 255), 0.16)
        arrow(frame, (760, 320), (1010, 270), (0, 0, 255), 5)
        arrow(frame, (900, 430), (1080, 345), (0, 0, 255), 5)
        label(frame, "ocasion generada", (780, 145), (80, 210, 255), (45, 10, 10))
        panel(
            frame,
            "Fase 4: la superioridad termina en ocasion",
            "La ventaja nace antes: presion orientada, pasador libre y espalda atacada.",
            "Este corte debe etiquetarse como secuencia completa, no como accion aislada.",
        )


def main():
    cap = cv2.VideoCapture(str(SOURCE))
    if not cap.isOpened():
        raise SystemExit(f"No se pudo abrir {SOURCE}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(OUT), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise SystemExit(f"No se pudo escribir {OUT}")
    start_frame = int(round(START_S * fps))
    max_frames = int(round((END_S - START_S) * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frame_idx = 0
    while True:
        if frame_idx > max_frames:
            break
        ok, frame = cap.read()
        if not ok:
            break
        draw_phase(frame, frame_idx / fps)
        writer.write(frame)
        frame_idx += 1
    writer.release()
    cap.release()
    print(OUT)


if __name__ == "__main__":
    main()
