from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


SOURCE = Path("/Volumes/Mac Satecchi/Mac/Web-stats/media/rival-videos/video-youtube-analisis-proxy.mp4")
OUT = Path("/Volumes/Mac Satecchi/Mac/Downloads/IA_MaxCuts_SeniorCoach108_video_7/annotated_cv/annotated_cv_377_CORREGIDO_salto_presion_espacio.mp4")
START_S = 120.0
END_S = 172.0


def alpha_poly(frame, pts, color, alpha=0.28):
    overlay = frame.copy()
    cv2.fillPoly(overlay, [np.array(pts, dtype=np.int32)], color)
    return cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)


def arrow(frame, p1, p2, color=(0, 0, 255), thickness=4):
    cv2.arrowedLine(frame, p1, p2, color, thickness, cv2.LINE_AA, tipLength=0.12)


def label(frame, text, org, color=(255, 255, 255), bg=(10, 10, 10), scale=0.68):
    x, y = org
    font = cv2.FONT_HERSHEY_SIMPLEX
    (w, h), _ = cv2.getTextSize(text, font, scale, 2)
    cv2.rectangle(frame, (x - 10, y - h - 12), (x + w + 10, y + 10), bg, -1)
    cv2.rectangle(frame, (x - 10, y - h - 12), (x + w + 10, y + 10), color, 2)
    cv2.putText(frame, text, (x, y), font, scale, color, 2, cv2.LINE_AA)


def panel(frame, lines):
    h, w = frame.shape[:2]
    y0 = h - 156
    overlay = frame.copy()
    cv2.rectangle(overlay, (24, y0), (w - 24, h - 24), (8, 13, 24), -1)
    frame[:] = cv2.addWeighted(overlay, 0.74, frame, 0.26, 0)
    cv2.rectangle(frame, (24, y0), (w - 24, h - 24), (0, 220, 255), 3)
    cv2.putText(frame, lines[0], (52, y0 + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
    for idx, text in enumerate(lines[1:3]):
        cv2.putText(frame, text, (52, y0 + 78 + idx * 30), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (232, 244, 255), 2, cv2.LINE_AA)


def draw_correction(frame, t):
    # El broadcast cambia de plano. Las coordenadas son manuales por tramo para
    # convertir esta correccion del entrenador en un ejemplo visual claro.
    if 4.2 <= t <= 8.8:
        # Salto inicial: jugador del Malaga sale de zona y el intervalo queda abierto.
        player = (455, 405)
        space = [(570, 315), (785, 330), (770, 462), (555, 455)]
        frame[:] = alpha_poly(frame, space, (0, 0, 255), 0.24)
        cv2.ellipse(frame, player, (56, 76), 0, 0, 360, (0, 255, 255), 5, cv2.LINE_AA)
        arrow(frame, (455, 405), (392, 410), (0, 255, 255), 4)
        arrow(frame, (545, 392), (705, 388), (0, 0, 255), 5)
        label(frame, "salto fuera de estructura", (330, 315), (0, 255, 255), (20, 30, 35), 0.62)
        label(frame, "intervalo libre", (620, 300), (80, 210, 255), (45, 10, 10), 0.62)
        panel(frame, [
            "Correccion entrenador: salto mal coordinado",
            "El jugador de Malaga salta a presion y abandona la linea.",
            "La espalda queda libre: aparece inferioridad defensiva.",
        ])
    elif 8.8 < t <= 15.8:
        # Desarrollo: el espacio se usa para progresar hacia zona de remate.
        player = (906, 222)
        space = [(910, 255), (1060, 250), (1040, 390), (875, 382)]
        frame[:] = alpha_poly(frame, space, (0, 0, 255), 0.23)
        cv2.ellipse(frame, player, (42, 58), 0, 0, 360, (0, 255, 255), 5, cv2.LINE_AA)
        arrow(frame, (905, 222), (860, 210), (0, 255, 255), 4)
        arrow(frame, (920, 305), (1030, 322), (0, 0, 255), 5)
        arrow(frame, (950, 355), (1035, 405), (0, 0, 255), 5)
        label(frame, "jugador que salta", (805, 170), (0, 255, 255), (20, 30, 35), 0.62)
        label(frame, "espacio dejado", (930, 445), (80, 210, 255), (45, 10, 10), 0.62)
        panel(frame, [
            "Consecuencia: se rompe la estructura",
            "El salto no va acompanado de cobertura ni cierre interior.",
            "Las Palmas puede atacar el intervalo y generar ocasion.",
        ])
    elif 15.8 < t <= 23.5:
        # Consecuencia cerca del area / contra posterior.
        space = [(555, 245), (760, 245), (805, 375), (595, 410)]
        frame[:] = alpha_poly(frame, space, (0, 0, 255), 0.22)
        arrow(frame, (600, 300), (760, 325), (0, 0, 255), 5)
        label(frame, "inferioridad tras el salto", (530, 220), (80, 210, 255), (45, 10, 10), 0.62)
        panel(frame, [
            "Lectura correcta para la IA",
            "No es solo ABP/reinicio: es error de presion y cobertura.",
            "Corte util: mostrar salto, espacio libre y casi gol.",
        ])


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
    cap.set(cv2.CAP_PROP_POS_MSEC, START_S * 1000.0)
    while True:
        pos_s = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
        if pos_s > END_S:
            break
        ok, frame = cap.read()
        if not ok:
            break
        rel_t = pos_s - START_S
        draw_correction(frame, rel_t)
        writer.write(frame)
    writer.release()
    cap.release()
    print(OUT)


if __name__ == "__main__":
    main()
