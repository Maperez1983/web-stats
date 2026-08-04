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
RUTA_MATERIAL_PPT = "/static/football/images/ppt_material/"

MEDIA_A_KIND = {
    "cono": "cone", "seta": "cone", "pica": "pole_marker", "aro": "ring",
    "valla": "hurdle", "escalera": "ladder", "maniqui": "mannequin",
}



# --- Que es cada imagen del PPT ---------------------------------------------------
# Mirando las 24 mas usadas (cubren la gran mayoria de apariciones) una por una.
# Antes se decidia por TAMANO y cualquier imagen grande acababa siendo una porteria:
# por eso los banderines de la tarea 143 salian como nueve porterias.
IMAGEN_A_KIND = {
    "image5.png": ("ball", ""),            "image24.png": ("ball", ""),
    "image115.png": ("ball", ""),
    "image9.png": ("cone", "#3ad12a"),     # seta verde
    "image13.png": ("cone", "#e03127"),    # seta roja
    "image154.png": ("cone", ""),          # cono naranja
    "image146.png": ("cone", "#e8dcb0"),   # seta beige
    "image143.png": ("cone_striped", ""),
    "image3.png": ("goal", ""),            "image7.png": ("goal", ""),
    "image23.png": ("goal", ""),           "image166.png": ("goal", ""),
    "image38.png": ("goal_mini", ""),      "image30.png": ("goal_mini", ""),
    "image28.png": ("pole_marker", ""),    "image56.png": ("pole_marker", ""),
    "image152.png": ("pole_marker", ""),   "image33.png": ("pole_marker", ""),
    "image34.GIF": ("pole_marker", ""),    "image19.png": ("pole_marker", ""),
    "image27.jpeg": ("hurdle", ""),
    "image4.png": ("goalkeeper_local", ""), "image215.png": ("goalkeeper_local", ""),
}


def _kind_por_imagen(nombre, ancho, alto, zonas):
    """Devuelve (kind, color) de una imagen del PPT. `zonas` = manchas de color."""
    if nombre in IMAGEN_A_KIND:
        return IMAGEN_A_KIND[nombre]
    if nombre in zonas:
        return ("zone", zonas[nombre])
    # El PPT trae su PROPIA biblioteca de material (setas de seis colores, aros, vallas,
    # escaleras, mini-porterias, bosu, step, balon medicinal, petos y porteros con distintas
    # equipaciones): 41 imagenes que aparecen 147 veces. Antes se las aproximaba con el
    # material nuestro que "mas se le pareciera", que muchas veces no se le parecia nada.
    # Ahora se coloca la IMAGEN DEL PPT tal cual.
    return ("image_url:" + RUTA_MATERIAL_PPT + nombre, "")


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
        "rot": int(x.getAttribute("rot") or 0) // 60000,
    }


def _caja_visual(xf):
    """Caja tal y como SE VE, aplicando el giro.

    `ext` guarda el tamaño SIN girar. La foto de campo del PPT (`image2.jpeg`) es un campo
    VERTICAL girado 90° para verse horizontal, y se usa así en 97 de las 179 diapositivas:
    tomar su `ext` a pelo daba un marco de referencia TRANSPUESTO (720x1280 en vez de
    1280x720) y colocaba media tarea fuera del campo. El giro es alrededor del centro.
    """
    if not xf:
        return xf
    if (xf.get("rot") or 0) % 180 != 90:
        return xf
    cxc = xf["x"] + xf["cx"] / 2.0
    cyc = xf["y"] + xf["cy"] / 2.0
    nueva = dict(xf)
    nueva["cx"], nueva["cy"] = xf["cy"], xf["cx"]
    nueva["x"] = cxc - nueva["cx"] / 2.0
    nueva["y"] = cyc - nueva["cy"] / 2.0
    return nueva


def _marco_por_contenido(tree):
    """Marco deducido de lo DIBUJADO, para las diapositivas sin foto de campo.

    Son 7 (118, 119, 123, 124, 138, 139, 140). Ahí el campo está dibujado con formas, así
    que el encuadre bueno es la caja que envuelve todo lo que hay, con un pequeño respiro.
    """
    x0 = y0 = None
    x1 = y1 = None
    for etiqueta in (P,):
        for nodo in list(tree.getElementsByTagNameNS(etiqueta, "sp")) + list(tree.getElementsByTagNameNS(etiqueta, "pic")):
            xf = _caja_visual(_xfrm(nodo))
            if not xf:
                continue
            x0 = xf["x"] if x0 is None else min(x0, xf["x"])
            y0 = xf["y"] if y0 is None else min(y0, xf["y"])
            x1 = xf["x"] + xf["cx"] if x1 is None else max(x1, xf["x"] + xf["cx"])
            y1 = xf["y"] + xf["cy"] if y1 is None else max(y1, xf["y"] + xf["cy"])
    if x0 is None or x1 <= x0 or y1 <= y0:
        return None
    respiro_x = (x1 - x0) * 0.04
    respiro_y = (y1 - y0) * 0.04
    return {"x": x0 - respiro_x, "y": y0 - respiro_y,
            "cx": (x1 - x0) + 2 * respiro_x, "cy": (y1 - y0) + 2 * respiro_y,
            "flipH": False, "flipV": False, "rot": 0}


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


def _texto_corto(sp):
    """Texto de la forma si es un dorsal (1-3 caracteres). '' si no lo es."""
    t = "".join(n.firstChild.nodeValue for n in sp.getElementsByTagNameNS(A, "t") if n.firstChild).strip()
    return t if t and len(t) <= 3 else ""


def _tiene_degradado(spPr):
    """True si la forma se rellena con un DEGRADADO.

    Importa porque el jugador numerado del PPT es una elipse gris metalizada
    (gradiente negro->blanco->negro) con el dorsal dentro. Como `_fill_rgb` solo miraba
    `solidFill`, devolvia None y esas fichas acababan convertidas en BALONES: 410
    jugadores perdidos en 72 de las 179 tareas.
    """
    if spPr is None:
        return False
    return any(n.nodeType == 1 and n.localName == "gradFill" for n in spPr.childNodes)


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


def _agrupar_trozos(trozos, radio=34.0, minimo=4):
    """Agrupa los trocitos de una figura vectorial en las FIGURAS que forman.

    Cada jugador dibujado a vector son decenas de piezas pequenas muy juntas (pelo, piel,
    camiseta...). Se agrupan por cercania y cada monton pasa a ser una ficha. El equipo se
    deduce del color dominante de la ropa, descartando piel y pelo.
    """
    _PIEL_PELO = {(255, 192, 192), (153, 102, 51), (160, 80, 0), (224, 224, 224),
                  (0, 0, 0), (255, 255, 255), (64, 64, 64)}
    sin_ver = list(trozos)
    grupos = []
    while sin_ver:
        semilla = sin_ver.pop()
        monton = [semilla]
        cambio = True
        while cambio:
            cambio = False
            for t in list(sin_ver):
                if any((t["cx"] - m["cx"]) ** 2 + (t["cy"] - m["cy"]) ** 2 <= radio ** 2 for m in monton):
                    monton.append(t)
                    sin_ver.remove(t)
                    cambio = True
        if len(monton) < minimo:
            continue
        cx = sum(m["cx"] for m in monton) / len(monton)
        cy = sum(m["cy"] for m in monton) / len(monton)
        ropa = [m["rgb"] for m in monton if m["rgb"] and m["rgb"] not in _PIEL_PELO]
        equipo = "player_local"
        if ropa:
            from collections import Counter
            dom = Counter(ropa).most_common(1)[0][0]
            e = _equipo(dom)
            if e:
                equipo = e
        grupos.append({"cx": round(cx, 1), "cy": round(cy, 1), "equipo": equipo})
    return grupos


def convertir(pptx_path, slide_no, canvas_w=1280, canvas_h=720, zonas_medios=None):
    import json as _json
    import os as _os
    if zonas_medios is None:
        ruta = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "medios_zona.json")
        try:
            zonas_medios = _json.load(open(ruta))
        except Exception:
            zonas_medios = {}
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
        xf = _caja_visual(xf)
        if xf and (campo is None or xf["cx"] * xf["cy"] > campo["cx"] * campo["cy"]):
            campo = xf
    # Una imagen pequeña (un balón, un maniquí) NO es el campo. Si la mayor no llega ni a un
    # tercio de la diapositiva, es que esta tarea no trae foto de campo: hay 7 así, y tomar
    # un sprite de 43 px como marco disparaba la escala y tiraba la tarea entera.
    _AREA_DIAPO = 1280 * 720 * 9525 * 9525
    if campo is None or campo["cx"] * campo["cy"] < _AREA_DIAPO * 0.30:
        campo = _marco_por_contenido(tree) or campo
    if not campo:
        return None, {"error": "sin imagen de campo"}

    # Todo tiene que caer DENTRO de la superficie de juego: en el PPT hay elementos
    # dibujados fuera del campo (en el margen blanco de la diapositiva) y alli no pintan nada.
    _M = 0.015  # margen para que no se peguen a la linea

    def mx(v):
        f = (v - campo["x"]) / campo["cx"]
        return round(min(max(f, _M), 1 - _M) * canvas_w, 1)

    def my(v):
        f = (v - campo["y"]) / campo["cy"]
        return round(min(max(f, _M), 1 - _M) * canvas_h, 1)

    objetos = []
    trozos_figura = []
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
        # Tamano REAL en la diapositiva (px). El umbral de "esto es una ficha" tiene que ir
        # aqui y no en unidades de lienzo: con un campo estrecho (los de ficha ocupan media
        # diapositiva) la misma ficha de 28 px pasaba a 68 y se descartaba sin dejar rastro.
        ancho_pt = xf["cx"] / 9525.0

        if prst is not None:
            kind = prst.getAttribute("prst")
            if kind in ("ellipse", "dodecagon") and ancho_pt <= 45:
                dorsal = _texto_corto(sp)
                equipo = _equipo(rgb)
                # El jugador numerado va en gris metalizado (degradado) con el dorsal dentro:
                # sin color solido no hay equipo que deducir, pero ficha es. Es nuestro.
                if not equipo and (dorsal or _tiene_degradado(spPr)):
                    equipo = "player_local"
                if equipo:
                    objetos.append({"type": "group", "left": cx, "top": cy,
                                    "data": {"kind": equipo, "label": dorsal, "number": dorsal}})
                    cuenta["ficha"] += 1
                    continue
                objetos.append({"type": "circle", "left": cx, "top": cy, "data": {"kind": "ball", "label": "Balón"}})
                cuenta["balon"] += 1
                continue
            if kind == "triangle" and ancho_pt <= 45:
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
                # El PPT usa DOS colores de flecha con significado: negra (652) y ambar (362).
                # Los arrastramos igual que el color de los conos.
                trazo = _fill_rgb(ln) if ln is not None else None
                hexl = "#%02x%02x%02x" % trazo if trazo else "#000000"
                objetos.append({"type": "line", "left": x1, "top": y1, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                                "data": {"kind": "arrow_run" if punta else "line_solid",
                                         "color": hexl,
                                         "label": "Carrera" if punta else "Línea"}})
                cuenta["flecha"] += 1
                continue
            if kind in ("rect", "roundRect") and ancho_pt > 60:
                objetos.append({"type": "rect", "left": mx(xf["x"]), "top": my(xf["y"]),
                                "width": round(xf["cx"] / campo["cx"] * canvas_w, 1),
                                "height": round(xf["cy"] / campo["cy"] * canvas_h, 1),
                                "fill": "rgba(56,189,248,0.16)", "stroke": "#38bdf8",
                                "strokeDashArray": [8, 6], "data": {"kind": "zone", "label": "Zona"}})
                cuenta["zona"] += 1
                continue

        if cust is not None:
            # OJO: no todo custGeom es un trazo. En las diapositivas con ficha (124-138) los
            # jugadores estan DIBUJADOS a vector: cada figura son decenas de trocitos rellenos
            # y sin contorno. Convertirlos uno a uno daba tareas de 800 rayas oscuras sin
            # sentido. Se apartan aqui y luego se agrupan en la figura que forman.
            _ln = _child(spPr, A, "ln") if spPr is not None else None
            _sin_trazo = _ln is None or _child(_ln, A, "noFill") is not None
            _ancho_pt = xf["cx"] / 9525.0
            _alto_pt = xf["cy"] / 9525.0
            if _sin_trazo and max(_ancho_pt, _alto_pt) <= 20:
                trozos_figura.append({"cx": cx, "cy": cy, "rgb": rgb})
                continue
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
                # El PPT distingue trazos AMBAR (365), negros (306) y algunos rojos, y ademas
                # marca los discontinuos con `custDash` (no con el discontinuo estandar, que es
                # lo que yo miraba y por eso salian todos continuos y del mismo color).
                _trazo_rgb = _fill_rgb(_ln) if _ln is not None else None
                _color = "#%02x%02x%02x" % _trazo_rgb if _trazo_rgb else "#0f172a"
                _discontinuo = _ln is not None and (
                    _child(_ln, A, "custDash") is not None or _child(_ln, A, "prstDash") is not None
                )
                _con_punta = _ln is not None and (
                    _child(_ln, A, "headEnd") is not None or _child(_ln, A, "tailEnd") is not None
                )
                objetos.append({"type": "path", "path": cmds, "fill": None, "stroke": _color,
                                "strokeWidth": 3, "left": mx(xf["x"]), "top": my(xf["y"]),
                                "dashed": _discontinuo, "arrow": _con_punta,
                                "data": {"kind": "free_draw", "label": "Flecha" if _con_punta else "Trazo",
                                         "color": _color, "dashed": _discontinuo}})
                cuenta["trazo"] += 1

    # 1.b) Los trocitos apartados se agrupan por cercania: cada monton es UN jugador.
    for _grupo in _agrupar_trozos(trozos_figura):
        objetos.append({"type": "group", "left": _grupo["cx"], "top": _grupo["cy"],
                        "data": {"kind": _grupo["equipo"], "label": "", "number": ""}})
        cuenta["ficha"] += 1

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
        alto = cyE / campo["cy"] * canvas_h
        cx = mx(int(off.getAttribute("x")) + cxE / 2)
        cy = my(int(off.getAttribute("y")) + cyE / 2)
        rid = ""
        blip = pic.getElementsByTagNameNS(A, "blip")
        if blip:
            rid = blip[0].getAttributeNS(R, "embed")
        nombre = rels.get(rid, "").split("/")[-1]
        kind, color = _kind_por_imagen(nombre, cxE, cyE, zonas_medios)
        if kind == "zone":
            # ESPACIO DE INTERVENCION: se dibuja como imagen de color en el PPT.
            objetos.append({"type": "rect",
                            "left": mx(int(off.getAttribute("x"))), "top": my(int(off.getAttribute("y"))),
                            "width": round(ancho, 1), "height": round(alto, 1),
                            "data": {"kind": "zone", "label": "Espacio", "color": color}})
            cuenta["zona"] += 1
            continue
        objetos.append({"type": "group", "left": cx, "top": cy,
                        "data": {"kind": kind, "label": kind, "color": color}})
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
