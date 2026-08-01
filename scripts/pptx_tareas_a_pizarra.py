#!/usr/bin/env python3
"""Convierte una diapositiva del PPT en objetos EDITABLES de nuestra pizarra 2D.

No convierte el dibujo en una imagen plana: traduce cada elemento del PPTX
(circulos, triangulos, lineas con punta, trazos a mano, imagenes de material)
al modelo de objetos del editor (`meta.graphic_editor.canvas_state.objects`),
que el editor rehidrata como fichas, conos, flechas, etc.

Referencia de coordenadas: la imagen de campo mas grande de la diapositiva se
toma como el rectangulo del campo y todo se mapea proporcionalmente al lienzo.
"""
from __future__ import annotations

import re
import zipfile
from xml.dom import minidom

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# Nombres de media -> material de nuestro editor (por tamaño/uso tipico).
MEDIA_A_KIND = {
    "cono": "cone", "seta": "cone", "pica": "pole_marker", "aro": "ring",
    "valla": "hurdle", "escalera": "ladder", "maniqui": "mannequin",
}


def _child(node, ns, name):
    for c in node.childNodes:
        if c.nodeType == 1 and c.localName == name and c.namespaceURI == ns:
            return c
    return None


def _xfrm(sp):
    spPr = _child(sp, P, "spPr")
    if spPr is None:
        return None
    x = _child(spPr, A, "xfrm")
    if x is None:
        return None
    off, ext = _child(x, A, "off"), _child(x, A, "ext")
    if off is None or ext is None:
        return None
    return {
        "x": int(off.getAttribute("x")), "y": int(off.getAttribute("y")),
        "cx": int(ext.getAttribute("cx")), "cy": int(ext.getAttribute("cy")),
        "flipH": x.getAttribute("flipH") == "1", "flipV": x.getAttribute("flipV") == "1",
    }


def _fill_rgb(spPr):
    if spPr is None:
        return None
    f = _child(spPr, A, "solidFill")
    if f is None:
        return None
    s = _child(f, A, "srgbClr")
    if s is None:
        return None
    h = s.getAttribute("val")
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _equipo(rgb):
    """Verde -> local; rojo/amarillo/azul -> rival. Devuelve None si no parece ficha."""
    if not rgb:
        return None
    r, g, b = rgb
    if g > 120 and g > r + 40:
        return "player_local"
    if r > 120 and r > g + 40:
        return "player_rival"
    if r > 150 and g > 150 and b < 110:
        return "player_rival"
    if b > 120 and b > r + 40:
        return "player_rival"
    return None


def convertir(pptx_path, slide_no, canvas_w=1280, canvas_h=720):
    z = zipfile.ZipFile(pptx_path)
    rels_raw = z.read(f"ppt/slides/_rels/slide{slide_no}.xml.rels").decode("utf8", "ignore")
    rels = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels_raw))
    dom = minidom.parseString(z.read(f"ppt/slides/slide{slide_no}.xml"))
    tree = dom.getElementsByTagNameNS(P, "spTree")[0]

    # 1) El campo: la imagen mas grande de la diapositiva marca el marco de referencia.
    campo = None
    for pic in tree.getElementsByTagNameNS(P, "pic"):
        xf = _xfrm(pic) or (lambda: None)()
        if xf is None:
            spPr = _child(pic, P, "spPr")
            xf = None
            if spPr is not None:
                x = _child(spPr, A, "xfrm")
                if x is not None:
                    off, ext = _child(x, A, "off"), _child(x, A, "ext")
                    if off is not None and ext is not None:
                        xf = {"x": int(off.getAttribute("x")), "y": int(off.getAttribute("y")),
                              "cx": int(ext.getAttribute("cx")), "cy": int(ext.getAttribute("cy")),
                              "flipH": False, "flipV": False}
        if xf and (campo is None or xf["cx"] * xf["cy"] > campo["cx"] * campo["cy"]):
            campo = xf
    if not campo:
        return None, {"error": "sin imagen de campo"}

    def mx(v):
        return round((v - campo["x"]) / campo["cx"] * canvas_w, 1)

    def my(v):
        return round((v - campo["y"]) / campo["cy"] * canvas_h, 1)

    objetos = []
    cuenta = {"ficha": 0, "cono": 0, "flecha": 0, "trazo": 0, "material": 0, "zona": 0, "balon": 0}

    for sp in tree.getElementsByTagNameNS(P, "sp"):
        xf = _xfrm(sp)
        if not xf:
            continue
        spPr = _child(sp, P, "spPr")
        prst = _child(spPr, A, "prstGeom") if spPr is not None else None
        cust = _child(spPr, A, "custGeom") if spPr is not None else None
        rgb = _fill_rgb(spPr)
        cx, cy = mx(xf["x"] + xf["cx"] / 2), my(xf["y"] + xf["cy"] / 2)
        ancho = xf["cx"] / campo["cx"] * canvas_w

        if prst is not None:
            kind = prst.getAttribute("prst")
            if kind == "ellipse" and ancho < 60:
                equipo = _equipo(rgb)
                if equipo:
                    objetos.append({"type": "group", "left": cx, "top": cy,
                                    "data": {"kind": equipo, "label": ""}})
                    cuenta["ficha"] += 1
                    continue
                objetos.append({"type": "circle", "left": cx, "top": cy, "data": {"kind": "ball", "label": "Balón"}})
                cuenta["balon"] += 1
                continue
            if kind == "triangle" and ancho < 60:
                # Guardamos el color real: el PPT distingue setas verdes de conos rojos y eso
                # significa algo dentro de la tarea (dos recorridos, dos equipos...).
                hexc = "#%02x%02x%02x" % rgb if rgb else ""
                objetos.append({"type": "group", "left": cx, "top": cy,
                                "data": {"kind": "cone", "label": "Cono", "color": hexc}})
                cuenta["cono"] += 1
                continue
            if kind == "line":
                x1, y1 = mx(xf["x"]), my(xf["y"])
                x2, y2 = mx(xf["x"] + xf["cx"]), my(xf["y"] + xf["cy"])
                if xf["flipH"]:
                    x1, x2 = x2, x1
                if xf["flipV"]:
                    y1, y2 = y2, y1
                ln = _child(spPr, A, "ln")
                punta = ln is not None and (_child(ln, A, "headEnd") is not None or _child(ln, A, "tailEnd") is not None)
                objetos.append({"type": "line", "left": x1, "top": y1, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                                "data": {"kind": "arrow_run" if punta else "line_solid",
                                         "label": "Carrera" if punta else "Línea"}})
                cuenta["flecha"] += 1
                continue
            if kind in ("rect", "roundRect") and ancho > 120:
                objetos.append({"type": "rect", "left": mx(xf["x"]), "top": my(xf["y"]),
                                "width": round(xf["cx"] / campo["cx"] * canvas_w, 1),
                                "height": round(xf["cy"] / campo["cy"] * canvas_h, 1),
                                "fill": "rgba(56,189,248,0.16)", "stroke": "#38bdf8",
                                "strokeDashArray": [8, 6], "data": {"kind": "zone", "label": "Zona"}})
                cuenta["zona"] += 1
                continue

        if cust is not None:
            # Trazo a mano alzada -> path de fabric (el editor lo trata como dibujo libre).
            path = _child(cust, A, "pathLst")
            p = path.getElementsByTagNameNS(A, "path")[0] if path is not None and path.getElementsByTagNameNS(A, "path") else None
            if p is None:
                continue
            pw = int(p.getAttribute("w") or xf["cx"] or 1)
            ph = int(p.getAttribute("h") or xf["cy"] or 1)
            cmds = []
            for cmd in p.childNodes:
                if cmd.nodeType != 1:
                    continue
                pts = [(int(c.getAttribute("x")), int(c.getAttribute("y")))
                       for c in cmd.getElementsByTagNameNS(A, "pt")]
                conv = [(round(mx(xf["x"] + px_ / pw * xf["cx"]), 1), round(my(xf["y"] + py_ / ph * xf["cy"]), 1))
                        for px_, py_ in pts]
                if cmd.localName == "moveTo" and conv:
                    cmds.append(["M", conv[0][0], conv[0][1]])
                elif cmd.localName == "lnTo" and conv:
                    cmds.append(["L", conv[0][0], conv[0][1]])
                elif cmd.localName == "cubicBezTo" and len(conv) == 3:
                    cmds.append(["C", conv[0][0], conv[0][1], conv[1][0], conv[1][1], conv[2][0], conv[2][1]])
            if len(cmds) > 1:
                objetos.append({"type": "path", "path": cmds, "fill": None, "stroke": "#0f172a",
                                "strokeWidth": 3, "left": mx(xf["x"]), "top": my(xf["y"]),
                                "data": {"kind": "free_draw", "label": "Trazo"}})
                cuenta["trazo"] += 1

    # 2) Material dibujado como IMAGEN (conos, balones, porterias...).
    for pic in tree.getElementsByTagNameNS(P, "pic"):
        spPr = _child(pic, P, "spPr")
        if spPr is None:
            continue
        x = _child(spPr, A, "xfrm")
        if x is None:
            continue
        off, ext = _child(x, A, "off"), _child(x, A, "ext")
        if off is None or ext is None:
            continue
        cxE, cyE = int(ext.getAttribute("cx")), int(ext.getAttribute("cy"))
        if cxE >= campo["cx"] * 0.5:  # es el campo de fondo
            continue
        ancho = cxE / campo["cx"] * canvas_w
        cx = mx(int(off.getAttribute("x")) + cxE / 2)
        cy = my(int(off.getAttribute("y")) + cyE / 2)
        kind = "cone" if ancho < 34 else "goal_mini"
        objetos.append({"type": "group", "left": cx, "top": cy, "data": {"kind": kind, "label": kind}})
        cuenta["material"] += 1

    return objetos, cuenta


if __name__ == "__main__":
    import json
    import sys
    objs, c = convertir(sys.argv[1], int(sys.argv[2]))
    print(json.dumps(c, ensure_ascii=False), "-> total", len(objs))


# --- Superficie: que trozo de campo usa cada tarea -------------------------------
# Los fondos del PPT son pocos y repetidos: 2 imagenes cubren 166 de las 179 tareas.
FONDO_A_SUPERFICIE = {
    "image2.jpeg": ("full_pitch", "portrait"),        # campo completo vertical (98 tareas)
    "image6.jpeg": ("attacking_third", "portrait"),   # tres cuartos vertical  (68 tareas)
    "image233.png": ("full_pitch", "portrait"),
    "image234.png": ("full_pitch", "portrait"),
    "image243.png": ("full_pitch", "portrait"),
    "image171.png": ("half_pitch", "landscape"),
    "image196.png": ("futsal", "landscape"),
}


def superficie(pptx_path, slide_no):
    """Devuelve (preset, orientacion) mirando la imagen de campo de la diapositiva."""
    import zipfile as _zip
    z = _zip.ZipFile(pptx_path)
    rels = z.read(f"ppt/slides/_rels/slide{slide_no}.xml.rels").decode("utf8", "ignore")
    rid_target = dict(re.findall(r'Id="([^"]+)"[^>]*Target="\.\./media/([^"]+)"', rels))
    s = z.read(f"ppt/slides/slide{slide_no}.xml").decode("utf8", "ignore")
    mayor = None
    for m in re.finditer(r"<p:pic>.*?</p:pic>", s, re.S):
        blk = m.group(0)
        rid = re.search(r'r:embed="([^"]+)"', blk)
        ext = re.search(r'<a:ext cx="(\d+)" cy="(\d+)"', blk)
        if not rid or not ext:
            continue
        area = int(ext.group(1)) * int(ext.group(2))
        if mayor is None or area > mayor[0]:
            mayor = (area, rid_target.get(rid.group(1), ""))
    nombre = mayor[1] if mayor else ""
    return FONDO_A_SUPERFICIE.get(nombre, ("full_pitch", "landscape")), nombre
