// Importa una tarea del PPT a la PIZARRA del editor, elemento a elemento y EDITABLE.
// No pinta una imagen: usa las propias herramientas del editor, así cada objeto queda
// seleccionable, movible y con su inspector, igual que si lo hubieras puesto tú.
//
// uso: node importar_pizarra.mjs <taskId> <elementos.json> <salida.png>
import { chromium } from 'playwright';
import fs from 'node:fs';

const HOST = 'http://127.0.0.1:8048';
const [TASK, JSON_PATH, OUT] = process.argv.slice(2);
const elementos = JSON.parse(fs.readFileSync(JSON_PATH, 'utf8'));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 950 }, deviceScaleFactor: 2 });
await page.goto(`${HOST}/login/`, { waitUntil: 'domcontentloaded' });
await page.fill('input[name=username]', 'localadmin');
await page.fill('input[name=password]', 'local1234');
await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), page.click('button[type=submit], input[type=submit]')]);
await page.goto(`${HOST}/coach/sesiones/tareas/${TASK}/editar/`, { waitUntil: 'networkidle' });
await page.waitForFunction(() => !!window.__tpadActivateTool && !!window.__webstatsTpadPlaceToken, null, { timeout: 40000 });
await page.waitForTimeout(3500);

// tamaño del mundo del editor y rectángulo del lienzo en pantalla
const info = await page.evaluate(() => {
  const w = parseInt(document.getElementById('draw-canvas-width')?.value || '0', 10);
  const h = parseInt(document.getElementById('draw-canvas-height')?.value || '0', 10);
  const el = document.getElementById('create-task-canvas') || document.querySelector('canvas.lower-canvas');
  const r = el.getBoundingClientRect();
  return { W: w, H: h, box: { x: r.x, y: r.y, w: r.width, h: r.height } };
});
console.log('mundo del editor:', info.W + 'x' + info.H);

// engancha el canvas de fabric para poder ajustar flechas y añadir trazos
await page.evaluate(() => {
  const GP = fabric.Group.prototype;
  if (!GP.__gi) { const o = GP.render; GP.render = function (c) { try { if (this.canvas && !window.__cv) window.__cv = this.canvas; } catch (e) {} return o.call(this, c); }; GP.__gi = true; }
});

const pantalla = (fx, fy) => [info.box.x + info.box.w * fx, info.box.y + info.box.h * fy];
const cuenta = {};
const suma = (k) => { cuenta[k] = (cuenta[k] || 0) + 1; };

// 1) FICHAS (coordenadas de mundo)
for (const e of elementos.filter((x) => x.tipo === 'ficha')) {
  await page.evaluate(([kind, x, y]) => window.__webstatsTpadPlaceToken({ kind, style: 'disk', name: '', number: '', left: x, top: y }),
    [e.kind, e.fx * info.W, e.fy * info.H]);
  suma('ficha');
}
await page.waitForTimeout(500);

// 2) MATERIAL. Se coloca con la herramienta y se le pone el COLOR real del PPT
//    (setas verdes / conos rojos): esa diferencia distingue recorridos dentro de la tarea.
for (const e of elementos.filter((x) => x.tipo === 'material')) {
  const antes = await page.evaluate(() => (window.__cv ? window.__cv.getObjects().length : -1));
  await page.evaluate((k) => window.__tpadActivateTool(k), e.kind);
  // Igual que las flechas: se crea en una esquina libre y luego se lleva a su sitio.
  const [x, y] = pantalla(0.035, 0.035);
  await page.mouse.click(x, y);
  await page.waitForTimeout(130);
  const puesto = await page.evaluate(([color, antesN, dx, dy, W, H]) => {
    const cv = window.__cv; if (!cv) return false;
    const objs = cv.getObjects();
    if (objs.length <= antesN) return false;
    const o = objs[objs.length - 1];
    o.set({ left: dx * W, top: dy * H });
    if (color) {
      const pinta = (n) => {
        if (!n) return;
        if (n.fill && typeof n.fill === 'string' && n.fill !== 'transparent') n.set({ fill: color });
        (n._objects || []).forEach(pinta);
      };
      pinta(o);
      o.dirty = true;
    }
    o.setCoords(); cv.requestRenderAll();
    return true;
  }, [e.color || '', antes, e.fx, e.fy, info.W, info.H]);
  suma(puesto ? e.kind : e.kind + '_fallido');
}

// 3) FLECHAS Y LÍNEAS. La flecha es un GRUPO (línea + punta): se coloca con la
//    herramienta y luego se le da el punto A y el punto B reales del PPT. Al estirar
//    el grupo hay que CANCELAR la escala de la punta o sale deformada (gorda).
for (const e of elementos.filter((x) => x.tipo === 'flecha')) {
  const antes = await page.evaluate(() => (window.__cv ? window.__cv.getObjects().length : -1));
  await page.evaluate((k) => window.__tpadActivateTool(k), e.kind);
  // Se coloca SIEMPRE en una esquina libre: si el clic cae sobre otro objeto, el
  // editor lo selecciona en vez de crear la flecha (asi se perdian 2 de cada 6).
  const [x, y] = pantalla(0.035, 0.035);
  await page.mouse.click(x, y);
  await page.waitForTimeout(150);
  const ok = await page.evaluate(([x1, y1, x2, y2, W, H, antesN]) => {
    const cv = window.__cv; if (!cv) return 'sin canvas';
    const objs = cv.getObjects();
    if (objs.length <= antesN) return 'no se colocó';
    const o = objs[objs.length - 1];
    const ax = x1 * W, ay = y1 * H, bx = x2 * W, by = y2 * H;
    const len = Math.hypot(bx - ax, by - ay);
    if (o.type === 'line') {
      o.set({ x1: ax, y1: ay, x2: bx, y2: by });
    } else {
      const base = o.width || 1;
      o.set({ originX: 'center', originY: 'center', left: (ax + bx) / 2, top: (ay + by) / 2,
              angle: Math.atan2(by - ay, bx - ax) * 180 / Math.PI,
              scaleX: len / base, scaleY: 1 });
      const sx = o.scaleX || 1, sy = o.scaleY || 1;
      (o._objects || []).forEach((c) => {
        if (c && c.type === 'triangle') c.set({ scaleX: 1 / sx, scaleY: 1 / sy });
      });
      o.dirty = true;
    }
    o.setCoords(); cv.requestRenderAll();
    return 'ok';
  }, [e.x1, e.y1, e.x2, e.y2, info.W, info.H, antes]);
  if (ok === 'ok') suma('flecha'); else suma('flecha_fallida');
}

// 4) TRAZOS A MANO: path de fabric añadido al lienzo (equivale al dibujo libre).
const trazos = elementos.filter((x) => x.tipo === 'trazo');
if (trazos.length) {
  await page.evaluate(([lista, W, H]) => {
    const cv = window.__cv; if (!cv) return 0;
    let n = 0;
    lista.forEach((t) => {
      const d = t.cmds.map((c) => (c[0] === 'C'
        ? `C ${c[1] * W} ${c[2] * H} ${c[3] * W} ${c[4] * H} ${c[5] * W} ${c[6] * H}`
        : `${c[0]} ${c[1] * W} ${c[2] * H}`)).join(' ');
      const p = new fabric.Path(d, { fill: '', stroke: '#0f172a', strokeWidth: 3, strokeLineCap: 'round', strokeLineJoin: 'round' });
      p.data = { kind: 'free_draw', label: 'Trazo' };
      cv.add(p); n += 1;
    });
    cv.requestRenderAll();
    return n;
  }, [trazos, info.W, info.H]);
  cuenta.trazo = trazos.length;
}

// 5) COLAS DE JUGADORES: en el PPT son puntos pequenos y muy juntos; nuestras fichas
//    son mayores y se solapan. Se reducen y se separan las que quedan encima.
await page.evaluate(() => {
  const cv = window.__cv; if (!cv) return;
  const toks = (cv.getObjects() || []).filter((o) => o && o.data && o.data.kind === 'token');
  toks.forEach((t) => { t.set({ scaleX: 0.72, scaleY: 0.72 }); t.setCoords(); });
  const MIN = 58;   // diametro aproximado de la ficha ya reducida
  for (let paso = 0; paso < 24; paso += 1) {
    let movido = false;
    for (let i = 0; i < toks.length; i += 1) {
      for (let j = i + 1; j < toks.length; j += 1) {
        const a = toks[i], b = toks[j];
        let dx = b.left - a.left, dy = b.top - a.top;
        const d = Math.hypot(dx, dy);
        if (d >= MIN) continue;
        if (d < 0.01) { dx = 1; dy = 0; }
        const emp = (MIN - d) / 2 + 0.5;
        const ux = dx / (d || 1), uy = dy / (d || 1);
        a.set({ left: a.left - ux * emp, top: a.top - uy * emp });
        b.set({ left: b.left + ux * emp, top: b.top + uy * emp });
        a.setCoords(); b.setCoords();
        movido = true;
      }
    }
    if (!movido) break;
  }
  cv.requestRenderAll();
});
await page.waitForTimeout(600);

await page.keyboard.press('Escape');
await page.waitForTimeout(1500);

const final = await page.evaluate(() => {
  const cv = window.__cv; if (!cv) return { error: 'sin canvas' };
  const objs = cv.getObjects() || [];
  const porKind = {}; let editables = 0;
  objs.forEach((o) => { const k = (o.data && (o.data.kind || o.data.role)) || o.type; porKind[k] = (porKind[k] || 0) + 1; if (o.selectable !== false) editables += 1; });
  return { total: objs.length, editables, porKind };
});
console.log('colocado:', JSON.stringify(cuenta));
console.log('en la pizarra:', JSON.stringify(final));

await page.screenshot({ path: OUT, clip: { x: info.box.x, y: info.box.y, width: info.box.w, height: info.box.h } });
console.log('captura', OUT);
await browser.close();
