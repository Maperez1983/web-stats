#!/usr/bin/env python3
"""Render aproximado de diapositivas PPTX a PNG (sin LibreOffice).

Dibuja imagenes, formas preestablecidas (elipse/rect/linea/triangulo), formas libres
(custGeom con moveTo/lnTo/cubicBezTo) y texto. No es fiel al 100%, pero basta para
leer QUE hay dibujado en cada tarea.
"""
import io
import math
import re
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from xml.dom import minidom  # solo LECTURA, no reescribimos el pptx

EMU_IN = 914400
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def child(node, ns, name):
    for c in node.childNodes:
        if c.nodeType == 1 and c.localName == name and c.namespaceURI == ns:
            return c
    return None


def descend(node, ns, name):
    return [n for n in node.getElementsByTagNameNS(ns, name)]


def get_xfrm(sp):
    spPr = child(sp, P, "spPr") or child(sp, P, "grpSpPr")
    if spPr is None:
        return None
    x = child(spPr, A, "xfrm")
    if x is None:
        return None
    off = child(x, A, "off")
    ext = child(x, A, "ext")
    if off is None or ext is None:
        return None
    return {
        "x": int(off.getAttribute("x")), "y": int(off.getAttribute("y")),
        "cx": int(ext.getAttribute("cx")), "cy": int(ext.getAttribute("cy")),
        "rot": int(x.getAttribute("rot") or 0) / 60000.0,
        "flipH": x.getAttribute("flipH") == "1",
        "flipV": x.getAttribute("flipV") == "1",
        "node": x,
    }


def solid_color(node):
    if node is None:
        return None
    fill = child(node, A, "solidFill")
    if fill is None:
        return None
    srgb = child(fill, A, "srgbClr")
    if srgb is not None:
        h = srgb.getAttribute("val")
        try:
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return None
    sch = child(fill, A, "schemeClr")
    if sch is not None:
        return {"dk1": (20, 20, 20), "lt1": (255, 255, 255), "tx1": (20, 20, 20),
                "bg1": (255, 255, 255), "accent1": (60, 110, 200)}.get(sch.getAttribute("val"), (90, 90, 90))
    return None


def render(pptx_path, slide_no, out_path, width=1400):
    z = zipfile.ZipFile(pptx_path)
    pres = minidom.parseString(z.read("ppt/presentation.xml"))
    sz = pres.getElementsByTagNameNS(P, "sldSz")[0]
    W, H = int(sz.getAttribute("cx")), int(sz.getAttribute("cy"))
    scale = width / W
    img = Image.new("RGB", (width, int(H * scale)), (255, 255, 255))
    dr = ImageDraw.Draw(img, "RGBA")

    rels_raw = z.read(f"ppt/slides/_rels/slide{slide_no}.xml.rels").decode("utf8", "ignore")
    rels = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels_raw))
    dom = minidom.parseString(z.read(f"ppt/slides/slide{slide_no}.xml"))
    tree = dom.getElementsByTagNameNS(P, "spTree")[0]

    def px(v):
        return int(round(v * scale))

    def walk(node, dx=0, dy=0):
        for sp in node.childNodes:
            if sp.nodeType != 1:
                continue
            if sp.localName == "grpSp":
                walk(sp, dx, dy)
                continue
            if sp.localName == "pic":
                xf = get_xfrm(sp)
                blip = descend(sp, A, "blip")
                if not xf or not blip:
                    continue
                rid = blip[0].getAttributeNS(R, "embed")
                tgt = rels.get(rid, "")
                name = tgt.split("/")[-1]
                try:
                    src = Image.open(io.BytesIO(z.read(f"ppt/media/{name}"))).convert("RGBA")
                except Exception:
                    continue
                w, h = max(1, px(xf["cx"])), max(1, px(xf["cy"]))
                src = src.resize((w, h), Image.LANCZOS)
                if xf["flipH"]:
                    src = src.transpose(Image.FLIP_LEFT_RIGHT)
                if xf["flipV"]:
                    src = src.transpose(Image.FLIP_TOP_BOTTOM)
                if abs(xf["rot"]) > 0.5:
                    src = src.rotate(-xf["rot"], expand=True, resample=Image.BICUBIC)
                img.paste(src, (px(xf["x"] + dx), px(xf["y"] + dy)), src)
                continue
            if sp.localName != "sp":
                continue
            xf = get_xfrm(sp)
            if not xf:
                continue
            x0, y0 = px(xf["x"] + dx), px(xf["y"] + dy)
            x1, y1 = x0 + px(xf["cx"]), y0 + px(xf["cy"])
            spPr = child(sp, P, "spPr")
            fill = solid_color(spPr)
            ln = child(spPr, A, "ln")
            stroke = solid_color(ln) or ((0, 0, 0) if ln is not None else None)
            lw = 2
            if ln is not None and ln.getAttribute("w"):
                lw = max(1, px(int(ln.getAttribute("w"))))
            prst = child(spPr, A, "prstGeom")
            cust = child(spPr, A, "custGeom")
            if cust is not None:
                paths = descend(cust, A, "path")
                for p in paths:
                    pw = int(p.getAttribute("w") or xf["cx"] or 1)
                    ph = int(p.getAttribute("h") or xf["cy"] or 1)
                    sx = xf["cx"] / pw if pw else 1
                    sy = xf["cy"] / ph if ph else 1
                    pts, cur = [], None
                    for cmd in p.childNodes:
                        if cmd.nodeType != 1:
                            continue
                        cps = descend(cmd, A, "pt")
                        coords = [(int(c.getAttribute("x")) * sx, int(c.getAttribute("y")) * sy) for c in cps]
                        if cmd.localName == "moveTo" and coords:
                            if len(pts) > 1:
                                dr.line(pts, fill=(stroke or (30, 30, 30)) + (255,), width=lw, joint="curve")
                            cur = coords[0]
                            pts = [(x0 + px(cur[0]), y0 + px(cur[1]))]
                        elif cmd.localName == "lnTo" and coords:
                            cur = coords[0]
                            pts.append((x0 + px(cur[0]), y0 + px(cur[1])))
                        elif cmd.localName == "cubicBezTo" and len(coords) == 3 and cur:
                            p0 = cur
                            for t in [i / 8 for i in range(1, 9)]:
                                mt = 1 - t
                                bx = (mt ** 3) * p0[0] + 3 * (mt ** 2) * t * coords[0][0] + 3 * mt * (t ** 2) * coords[1][0] + (t ** 3) * coords[2][0]
                                by = (mt ** 3) * p0[1] + 3 * (mt ** 2) * t * coords[0][1] + 3 * mt * (t ** 2) * coords[1][1] + (t ** 3) * coords[2][1]
                                pts.append((x0 + px(bx), y0 + px(by)))
                            cur = coords[2]
                    if len(pts) > 1:
                        col = (stroke or (30, 30, 30))
                        dr.line(pts, fill=col + (255,), width=lw, joint="curve")
                        # OJO: no rellenamos. En este mazo las flechas y trazos van como
                        # formas libres CON relleno (es el color de la punta), y pintarlas
                        # como poligono inventaba bloques de color que no existen.
            elif prst is not None:
                kind = prst.getAttribute("prst")
                box = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
                fl = (fill + (200,)) if fill else None
                st = (stroke + (255,)) if stroke else None
                if kind == "ellipse":
                    dr.ellipse(box, fill=fl, outline=st, width=lw)
                elif kind in ("rect", "roundRect", "snip2SameRect"):
                    dr.rectangle(box, fill=fl, outline=st, width=lw)
                elif kind == "triangle":
                    dr.polygon([( (box[0]+box[2])//2, box[1]), (box[0], box[3]), (box[2], box[3])], fill=fl, outline=st)
                elif kind == "line":
                    a = (x0, y0); b = (x0 + px(xf["cx"]), y0 + px(xf["cy"]))
                    if xf["flipH"]:
                        a, b = (b[0], a[1]), (a[0], b[1])
                    if xf["flipV"]:
                        a, b = (a[0], b[1]), (b[0], a[1])
                    dr.line([a, b], fill=st or (30, 30, 30, 255), width=lw)
                    if ln is not None and (child(ln, A, "headEnd") is not None or child(ln, A, "tailEnd") is not None):
                        ang = math.atan2(b[1] - a[1], b[0] - a[0]); s = max(6, lw * 3)
                        dr.polygon([b,
                                    (b[0] - s * math.cos(ang - .5), b[1] - s * math.sin(ang - .5)),
                                    (b[0] - s * math.cos(ang + .5), b[1] - s * math.sin(ang + .5))],
                                   fill=st or (30, 30, 30, 255))
                else:
                    dr.rectangle(box, outline=st or (120, 120, 120, 255), width=1)
            # texto
            words = [t.firstChild.nodeValue for t in descend(sp, A, "t") if t.firstChild]
            txt = " ".join(w for w in words if w and w.strip())
            if txt.strip():
                try:
                    f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", max(11, px(xf["cy"]) // 2))
                except Exception:
                    f = ImageFont.load_default()
                dr.text((x0 + 3, y0 + 2), txt[:60], fill=(10, 10, 10, 255), font=f)

    walk(tree)
    img.save(out_path)
    return out_path


if __name__ == "__main__":
    deck = sys.argv[1]
    nums = [int(x) for x in sys.argv[2].split(",")]
    outdir = Path(sys.argv[3]); outdir.mkdir(exist_ok=True, parents=True)
    for n in nums:
        p = render(deck, n, outdir / f"slide{n:03d}.png")
        print("ok", p)
