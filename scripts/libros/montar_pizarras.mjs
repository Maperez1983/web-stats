// Rehace la PIZARRA de una tarea en produccion con el conversor ya corregido:
// vacia el lienzo y vuelve a colocar cada elemento con las herramientas del editor,
// asi todo queda editable. Guarda con el propio boton de la app.
import fs from 'node:fs'; import os from 'node:os';
import { chromium } from 'playwright';
const B='https://app.segundajugada.es';
const EQUIVALENTE = {   // reserva cuando la herramienta principal no crea nada
  pole_marker:'emoji_pole', ring:'emoji_ring', hurdle:'emoji_hurdle', ladder:'emoji_ladder',
  mannequin:'emoji_mannequin', goal_mini:'emoji_mini_goal', cone_striped:'cone',
};

const TOKEN=fs.readFileSync(`${os.homedir()}/.config/segundajugada/token`,'utf8').trim();
const mapa=JSON.parse(fs.readFileSync('mapa_todo.json','utf8'));

let ck={}; const ch=()=>Object.entries(ck).map(([k,v])=>`${k}=${v}`).join('; ');
const save=r=>{const raw=r.headers.getSetCookie?r.headers.getSetCookie():[r.headers.get('set-cookie')].filter(Boolean);for(const c of raw){const p=c.split(';')[0],i=p.indexOf('=');if(i>0)ck[p.slice(0,i).trim()]=p.slice(i+1).trim();}};
let r=await fetch(B+'/service-login/',{redirect:'manual'});save(r);
const csrf=((await r.text()).match(/name=["']csrfmiddlewaretoken["'] value=["']([^"']+)/)||[])[1]||'';
r=await fetch(B+'/service-login/',{method:'POST',redirect:'manual',headers:{'Content-Type':'application/x-www-form-urlencoded',Cookie:ch(),Referer:B+'/service-login/'},body:new URLSearchParams({csrfmiddlewaretoken:csrf,token:TOKEN})});save(r);

const nav=await chromium.launch();
const ctx=await nav.newContext({viewport:{width:1600,height:950}, deviceScaleFactor:1});
await ctx.addCookies(Object.entries(ck).map(([name,value])=>({name,value,domain:'app.segundajugada.es',path:'/'})));

const NUMS = fs.readFileSync(process.argv[2]||'nums_lu_todas.txt','utf8').trim().split('\n').filter(Boolean);
const hechas=[]; const problemas=[];
const t0=Date.now();
for (let i=0;i<NUMS.length;i++) {
  const NUM = NUMS[i];
  const TASK = mapa[NUM];
  let elementos;
  try { elementos = JSON.parse(fs.readFileSync(`sesiones/els_${NUM}.json`,'utf8')); }
  catch(err){ problemas.push(`${NUM}: sin elementos`); continue; }
  try {
    const page=await ctx.newPage();
page.on('dialog', d=>d.accept());   // 'vaciar lienzo' pide confirmacion
await page.goto(`${B}/coach/sesiones/tareas/${TASK}/editar/`,{waitUntil:'domcontentloaded',timeout:240000});
await page.waitForFunction(()=>!!window.__tpadActivateTool && !!window.__webstatsTpadPlaceToken,null,{timeout:240000});
await page.waitForTimeout(3000);
const box0=await page.evaluate(()=>{const el=document.getElementById('create-task-canvas')||document.querySelector('canvas.lower-canvas');const r=el.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};});
await page.evaluate(()=>{
  // Capturar el lienzo por el RENDER DEL LIENZO, no por el de un grupo: enganchando
  // Group.render solo funcionaba si algun grupo se pintaba DESPUES, y al abrir ya estaba
  // pintado -> window.__cv se quedaba null y todo el material fallaba en silencio.
  // Enganchar el render de CUALQUIER objeto: pasa por ahi todo lo que se pinta, asi que
  // captura el lienzo aunque el tablero ya estuviera dibujado al abrir la pagina.
  const O = window.fabric && fabric.Object;
  if (O && O.prototype && !O.prototype.__gi) {
    const orig = O.prototype.render;
    O.prototype.render = function(){ try { if (this.canvas) window.__cv = this.canvas; } catch(e){} return orig.apply(this, arguments); };
    O.prototype.__gi = true;
  }
});
await page.evaluate(()=>{ try{ window.__cv || (window.fabric && document.querySelector('canvas.lower-canvas') && null); }catch(e){} });
const info=await page.evaluate(()=>{
  const w=parseInt(document.getElementById('draw-canvas-width')?.value||'0',10);
  const h=parseInt(document.getElementById('draw-canvas-height')?.value||'0',10);
  const el=document.getElementById('create-task-canvas')||document.querySelector('canvas.lower-canvas');
  const r=el.getBoundingClientRect();
  return {W:w,H:h,box:{x:r.x,y:r.y,w:r.width,h:r.height}};
});
// VACIAR con la accion del PROPIO editor: el enganche a fabric todavia no ha capturado
// el lienzo al abrir (solo se activa al pintar un grupo), y borrando 'a mano' se quedaba
// el dibujo viejo debajo: la tarea salia DUPLICADA.
await page.evaluate(()=>{ try{ window.__tpadCanvasAction && window.__tpadCanvasAction('clear'); }catch(e){} });
await page.waitForTimeout(1200);
const fallos=[];
const antes=await page.evaluate(()=>window.__cv?window.__cv.getObjects().length:-1);
const pantalla=(fx,fy)=>[info.box.x+info.box.w*fx, info.box.y+info.box.h*fy];


    // El lienzo no repinta solo al abrir, asi que `__cv` sigue vacio hasta que algo se dibuja.
    // Las fichas ya lo han provocado; si la tarea no lleva ninguna (montajes de material), se
    // pone una de usar y tirar y se borra. Sin esto, TODO el material se colocaba en la esquina.
    if (!(await page.evaluate(()=>!!window.__cv))) {
      await page.evaluate(()=>window.__webstatsTpadPlaceToken({kind:'player_local',style:'disk',name:'',number:'',left:50,top:50}));
      await page.waitForFunction(()=>!!window.__cv, null, {timeout:30000});

    // ESPACIOS DE INTERVENCION primero, para que queden DEBAJO de todo lo demas.
    {
      const vistas=new Set();
      const zonas=elementos.filter(x=>x.tipo==='zona').filter(x=>{
        const k=[x.fx,x.fy,x.w,x.h].map(v=>Math.round(v*400)).join('|');
        if(vistas.has(k)) return false; vistas.add(k); return true;
      }).map(x=>({...x, w:Math.min(x.w,0.985-x.fx), h:Math.min(x.h,0.985-x.fy)}));
      // Las zonas recien creadas son IDENTICAS entre si, asi que no hay que averiguar cual es
      // cual (el editor las manda al fondo y el orden del array deja de valer): se crean todas
      // y luego se reparten las geometrias una a una. Cualquier reparto es correcto.
      let creadas=0;
      for (let z=0; z<zonas.length; z++) {
        const n0=await page.evaluate(()=>window.__cv?window.__cv.getObjects().filter(o=>o.data&&o.data.kind==='zone').length:-1);
        await page.evaluate(()=>window.__tpadActivateTool('zone'));
        const [zx,zy]=pantalla(0.035,0.035); await page.mouse.click(zx,zy);
        try { await page.waitForFunction(n=>window.__cv && window.__cv.getObjects().filter(o=>o.data&&o.data.kind==='zone').length>n, n0, {timeout:20000}); creadas++; }
        catch(err){ fallos.push('zona no se creo'); }
        await page.keyboard.press('Escape');
      }
      if (creadas) {
        await page.evaluate(([lista,W,H])=>{
          const cv=window.__cv; if(!cv) return;
          const objs=cv.getObjects().filter(o=>o.data&&o.data.kind==='zone');
          lista.slice(0,objs.length).forEach((e,i)=>{
            const o=objs[i];
            const ancho=Math.max(30,e.w*W), alto=Math.max(30,e.h*H);
            const aw=(o.getScaledWidth?o.getScaledWidth():(o.width||1))||1;
            const ah=(o.getScaledHeight?o.getScaledHeight():(o.height||1))||1;
            o.set({scaleX:(o.scaleX||1)*(ancho/aw), scaleY:(o.scaleY||1)*(alto/ah),
                   left:(e.fx+e.w/2)*W, top:(e.fy+e.h/2)*H});
            if(e.color){
              const r=parseInt(e.color.slice(1,3),16),g=parseInt(e.color.slice(3,5),16),b=parseInt(e.color.slice(5,7),16);
              (o._objects||[]).forEach(c=>{ if(!c) return; const rol=(c.data&&c.data.role)||'';
                if(rol==='zone_base') c.set({fill:`rgba(${r},${g},${b},0.38)`, dirty:true});
                else if(rol==='zone_border') c.set({stroke:e.color, strokeWidth:2, strokeDashArray:null, dirty:true});
                else if(rol==='zone_hatch_group') c.set({visible:false}); });
              if(o.data){ o.data.color=e.color; o.data.zone_style='solid'; }
              o.dirty=true;
            }
            o.setCoords(); cv.sendToBack(o);
          });
          cv.discardActiveObject(); cv.requestRenderAll();
        }, [zonas, info.W, info.H]);
      }
    }

    for (const e of elementos.filter(x=>x.tipo==='ficha')) {
  // La equipacion va aparte del tipo: el comodin es un jugador con la chapa turquesa,
  // que es lo que lo distingue de los diez en posesion.
  await page.evaluate(([kind,x,y,num,kit])=>window.__webstatsTpadPlaceToken({kind,style:'disk',name:'',number:num||'',left:x,top:y,kit:kit||''}),
    [e.kind, e.fx*info.W, e.fy*info.H, e.dorsal||'', e.kit||'']);
}
  // NO borrar "la ultima ficha". Esa linea venia de cuando el editor anadia una ficha suelta
  // al abrir; ahora se lleva por delante la ULTIMA QUE COLOCO YO -el comodin- y el repaso de
  // mas abajo rescataba en su lugar la ficha sobrante, con la equipacion de por defecto. De
  // sobrar alguna, el repaso ya la coloca.
}
await page.waitForFunction(()=>!!window.__cv, null, {timeout:30000});

// MATERIAL: se crea todo primero y se reparte despues por tipo. Mover "el ultimo objeto"
// justo tras crearlo no vale: hay herramientas (las porterias) cuyo objeto no queda el
// ultimo del array, y las cuatro se amontonaban en la esquina donde se crean.
{
  const mats = elementos.filter(x=>x.tipo==='material');
  let iMat = 0;
  for (const e of mats) {
    const n0=await page.evaluate(()=>window.__cv?window.__cv.getObjects().length:-1);
    await page.evaluate(k=>window.__tpadActivateTool(k), e.kind);
    // Cada uno en un punto LIBRE distinto: si se pincha siempre en el mismo sitio, a partir
    // del segundo el clic cae encima del objeto anterior y lo selecciona en vez de crear.
    let nacio=false;
    for (let intento=0; intento<3 && !nacio; intento++) {
      const [x,y]=pantalla(0.04 + ((iMat+intento*4)%9)*0.035, 0.05 + (Math.floor((iMat+intento*4)/9)%7)*0.07);
      await page.mouse.click(x,y);
      try { await page.waitForFunction(n=>window.__cv && window.__cv.getObjects().length>n, n0, {timeout:9000}); nacio=true; }
      catch(err){ await page.keyboard.press('Escape'); await page.evaluate(k=>window.__tpadActivateTool(k), e.kind); }
    }
    iMat += 1;
    if(!nacio) fallos.push(`${e.kind} no se creo`);
    await page.keyboard.press('Escape');
  }
  await page.evaluate(([lista,W,H])=>{
    const cv=window.__cv; if(!cv) return;
    // El editor guarda algunos tipos con GUION ('pole-marker') y las listas los nombran con
    // raya baja ('pole_marker'): sin normalizar, las cuatro picas se quedaban amontonadas en
    // la esquina donde se crean y nadie se enteraba.
    const norm = t => String(t||'').replace(/-/g,'_');
    const porTipo={};
    cv.getObjects().forEach(o=>{ const k=norm((o.data&&o.data.kind)||''); if(!k||k==='token'||k==='zone') return;
      (porTipo[k]=porTipo[k]||[]).push(o); });
    const usados={};
    lista.forEach(e0=>{
      const e={...e0, kind: norm(e0.kind)};
      const k=e.kind==='goal_mini' ? (porTipo['goal_mini']?'goal_mini':'goal') : e.kind;
      const arr=porTipo[k]; if(!arr) return;
      const i=(usados[k]=(usados[k]||0)); usados[k]=i+1;
      const o=arr[i]; if(!o) return;
      o.set({left:e.fx*W, top:e.fy*H});
      if(e.color){ const pinta=n=>{ if(!n) return;
        if(n.fill && typeof n.fill==='string' && n.fill!=='transparent') n.set({fill:e.color});
        (n._objects||[]).forEach(pinta); }; pinta(o); o.dirty=true; }
      o.setCoords();
    });
    cv.discardActiveObject(); cv.requestRenderAll();
  }, [mats, info.W, info.H]);
}
for (const e of elementos.filter(x=>x.tipo==='flecha')) {
  const n0=await page.evaluate(()=>window.__cv?window.__cv.getObjects().length:-1);
  // El TRAZO importa: en una rueda de pases el libro usa flechas discontinuas para el
  // recorrido y continuas para la conduccion. Pintarlo todo continuo borra esa diferencia.
  const herramienta = e.estilo==='discontinua' ? 'arrow_dash' : (e.kind || 'arrow_solid');
  await page.evaluate(k=>window.__tpadActivateTool(k), herramienta);
  // ARRASTRE de punto a punto: hay herramientas (arrow_solid) que con un simple clic no
  // crean nada, y al quedarse el modo activo se llevaban por delante a las siguientes.
  const [ax,ay]=pantalla(e.x1,e.y1), [bx,by]=pantalla(e.x2,e.y2);
  await page.mouse.move(ax,ay); await page.mouse.down();
  await page.mouse.move((ax+bx)/2,(ay+by)/2,{steps:6}); await page.mouse.move(bx,by,{steps:6});
  await page.mouse.up();
  let nacio=true;
  try { await page.waitForFunction(n=>window.__cv && window.__cv.getObjects().length>n, n0, {timeout:8000}); }
  catch(err){ nacio=false; }
  if(nacio && e.color){
    // Y EL COLOR: negro, rojo y amarillo marcan secuencias distintas en el mismo dibujo.
    await page.evaluate(col=>{
      const cv=window.__cv; if(!cv) return;
      const f=[...cv.getObjects()].reverse().find(o=>o.data&&String(o.data.kind||'').startsWith('arrow'));
      if(!f) return;
      const pinta=n=>{ if(!n) return;
        if(n.stroke) n.set({stroke:col});
        if(n.fill && typeof n.fill==='string' && n.fill!=='transparent') n.set({fill:col});
        (n._objects||[]).forEach(pinta); };
      pinta(f); if(f.data) f.data.color=col; f.dirty=true; cv.requestRenderAll();
    }, e.color);
  }
  if(!nacio){   // reserva: la de siempre, clic en una esquina y colocar
    await page.keyboard.press('Escape');
    await page.evaluate(k=>window.__tpadActivateTool(k), herramienta);
    const [cx0,cy0]=pantalla(0.035,0.035); await page.mouse.click(cx0,cy0);
    try { await page.waitForFunction(n=>window.__cv && window.__cv.getObjects().length>n, n0, {timeout:8000}); }
    catch(err2){
      const alt = EQUIVALENTE[e.kind];
      if(!alt){ fallos.push(`${e.kind} no se creo`); await page.keyboard.press('Escape'); continue; }
      await page.keyboard.press('Escape');
      await page.evaluate(k=>window.__tpadActivateTool(k), alt);
      const [ex,ey]=pantalla(0.035,0.035); await page.mouse.click(ex,ey);
      try { await page.waitForFunction(n=>window.__cv && window.__cv.getObjects().length>n, n0, {timeout:12000}); }
      catch(err3){ fallos.push(`${e.kind} no se creo`); await page.keyboard.press('Escape'); continue; }
    }
  }
  await page.evaluate(([n0,x1,y1,x2,y2,W,H,color,coloca])=>{
    const cv=window.__cv; const os=cv.getObjects(); const o=os[os.length-1];
    if(coloca){
      const cx=(x1+x2)/2*W, cy=(y1+y2)/2*H;
      const largo=Math.hypot((x2-x1)*W,(y2-y1)*H)||1;
      const actual=(o.getScaledWidth?o.getScaledWidth():(o.width||1))||1;
      o.set({left:cx, top:cy, angle:Math.atan2((y2-y1)*H,(x2-x1)*W)*180/Math.PI, scaleX:(o.scaleX||1)*(largo/actual)});
    }
    if(color){ const pinta=n=>{ if(!n) return;
        if(n.stroke) n.set({stroke:color});
        if(n.fill && typeof n.fill==='string' && n.fill!=='transparent') n.set({fill:color});
        (n._objects||[]).forEach(pinta); }; pinta(o); o.dirty=true; }
    o.setCoords(); cv.discardActiveObject(); cv.requestRenderAll();
  }, [n0,e.x1,e.y1,e.x2,e.y2,info.W,info.H,e.color||'', !nacio]);
  await page.keyboard.press('Escape');
}
const trazos=elementos.filter(x=>x.tipo==='trazo');
if(trazos.length) await page.evaluate(([lista,W,H])=>{const cv=window.__cv; if(!cv) return;
  lista.forEach(t=>{const d=t.cmds.map(c=>(c[0]==='C'?`C ${c[1]*W} ${c[2]*H} ${c[3]*W} ${c[4]*H} ${c[5]*W} ${c[6]*H}`:`${c[0]} ${c[1]*W} ${c[2]*H}`)).join(' ');
    // Color y discontinuo REALES del PPT: el ambar y el negro distinguen recorridos dentro
    // de la misma tarea, igual que las setas verdes y los conos rojos.
    const p=new fabric.Path(d,{fill:'',stroke:t.color||'#0f172a',strokeWidth:3,
      strokeDashArray: t.dashed ? [12,8] : null, strokeLineCap:'round',strokeLineJoin:'round'});
    p.data={kind:'free_draw', label: t.arrow ? 'Flecha' : 'Trazo', color: t.color||'#0f172a'};
    cv.add(p);});
  cv.requestRenderAll();}, [trazos,info.W,info.H]);

// CONTORNO Y DIVISIONES. El libro parte el espacio con LINEAS, continuas o discontinuas, no
// con recuadros rellenos: un recuadro amarillo en nuestro sistema significa zona de
// intervencion, que es otra cosa.
// Se crean todas primero y se COLOCAN DESPUES por dato: arrastrando, estas herramientas
// crean el objeto del tamanio por defecto y se quedan donde les parece (lo mismo que pasaba
// con las zonas), asi que el arrastre no sirve para dar la geometria.
{
  const trazos = elementos.filter(x=>x.tipo==='linea' || x.tipo==='contorno');
  for (const t of trazos) {
    const herramienta = t.tipo==='contorno' ? 'shape_rect'
                      : (t.estilo==='discontinua' ? 'line_dash' : 'line_solid');
    const n0=await page.evaluate(()=>window.__cv?window.__cv.getObjects().length:-1);
    await page.evaluate(k=>window.__tpadActivateTool(k), herramienta);
    let nacio=false;
    // Se dibuja en el MARGEN, lejos de las fichas ya puestas: arrastrando por el medio, el
    // gesto empieza encima de una ficha y el editor la selecciona en vez de crear la linea.
    // Seis sitios distintos, que con tres se quedaba alguna sin nacer.
    const sitios=[[0.03,0.05],[0.03,0.20],[0.03,0.35],[0.03,0.50],[0.03,0.65],[0.03,0.80]];
    for (let intento=0; intento<sitios.length && !nacio; intento++) {
      const [px,py]=pantalla(sitios[intento][0], sitios[intento][1]);
      await page.mouse.move(px,py); await page.mouse.down();
      await page.mouse.move(px+80,py+45,{steps:5}); await page.mouse.up();
      try { await page.waitForFunction(n=>window.__cv && window.__cv.getObjects().length>n, n0, {timeout:9000}); nacio=true; }
      catch(err){ await page.keyboard.press('Escape'); await page.evaluate(k=>window.__tpadActivateTool(k), herramienta); }
    }
    if(!nacio) fallos.push(`${herramienta} no se creo`);
  }
  await page.keyboard.press('Escape');
  await page.evaluate(([lista,W,H])=>{
    const cv=window.__cv; if(!cv) return;
    const esTrazo=o=>{ const k=(o.data&&o.data.kind)||''; return k.startsWith('line')||k.startsWith('shape'); };
    const objetos=cv.getObjects().filter(esTrazo);
    lista.forEach((t,i)=>{
      const o=objetos[i]; if(!o) return;
      const x1=t.x1*W, y1=t.y1*H, x2=t.x2*W, y2=t.y2*H;
      if(t.tipo==='contorno'){
        const anchoQuiere=Math.abs(x2-x1), altoQuiere=Math.abs(y2-y1);
        const aw=o.getScaledWidth()||1, ah=o.getScaledHeight()||1;
        o.set({scaleX:(o.scaleX||1)*(anchoQuiere/aw), scaleY:(o.scaleY||1)*(altoQuiere/ah),
               left:(x1+x2)/2, top:(y1+y2)/2, angle:0});
      } else {
        const largo=Math.hypot(x2-x1, y2-y1);
        const actual=o.getScaledWidth()||1;
        o.set({scaleX:(o.scaleX||1)*(largo/actual),
               angle:Math.atan2(y2-y1, x2-x1)*180/Math.PI,
               left:(x1+x2)/2, top:(y1+y2)/2});
      }
      o.setCoords(); o.dirty=true; cv.sendToBack(o);
    });
    cv.discardActiveObject(); cv.requestRenderAll();
  }, [trazos, info.W, info.H]);
}

// RÓTULOS. Cuatro de las siete zonas de este ejercicio sólo significan algo por su texto:
// sin él son recuadros vacíos. La herramienta de texto no crea nada con un clic programado,
// así que se construye el MISMO objeto que crea el editor (IText con data.kind 'text'), que
// queda igual de editable a mano.
{
  const rotulos = elementos.filter(x=>x.tipo==='texto');
  if (rotulos.length) {
    const puestos = await page.evaluate(([lista,W,H])=>{
      const cv=window.__cv; if(!cv || !window.fabric) return 0;
      let n=0;
      lista.forEach(r=>{
        // TIPOGRAFÍA: el lienzo trae una serif por defecto y yo le puse encima un borde
        // blanco; entre las dos cosas el rótulo se leía mal sobre el verde. Se usa IBM Plex
        // Sans, la del sistema (la app la sirve como woff2 propio), sin contorno y con una
        // sombra suave detrás.
        const t=new window.fabric.IText(String(r.texto||''), {
          left:r.fx*W, top:r.fy*H, originX:'center', originY:'center',
          fontFamily:'"IBM Plex Sans", system-ui, sans-serif',
          fontSize:r.tam||18, fontWeight:'600', angle:r.angulo||0,
          charSpacing:40, fill:'#12211a',
          shadow:new window.fabric.Shadow({color:'rgba(255,255,255,0.85)', blur:4, offsetX:0, offsetY:0}),
        });
        t.data={kind:'text', color:'#0f172a'};
        cv.add(t); n++;
      });
      cv.discardActiveObject(); cv.requestRenderAll();
      return n;
    }, [rotulos, info.W, info.H]);
    if (puestos !== rotulos.length) fallos.push(`rotulos: ${puestos}/${rotulos.length}`);
  }
}

// REPASO FINAL: alguna ficha se queda en la esquina donde se crean (hay tipos que el
// colocador no acepta y caen al sitio por defecto). En vez de darlo por bueno, se busca qué
// posición de la lista no ha ocupado nadie y se le pone ahí.
await page.evaluate(([fichas,W,H])=>{
  const cv=window.__cv; if(!cv) return;
  const tokens=cv.getObjects().filter(o=>o.data&&o.data.kind==='token');
  const cerca=(o,e)=>Math.hypot(o.left-e.fx*W, o.top-e.fy*H) < Math.max(W,H)*0.04;
  const huerfanos=tokens.filter(o=>!fichas.some(e=>cerca(o,e)));
  const libres=fichas.filter(e=>!tokens.some(o=>cerca(o,e)));
  huerfanos.forEach((o,i)=>{ const e=libres[i];
    if(e){ o.set({left:e.fx*W, top:e.fy*H}); o.setCoords(); o.dirty=true; }
    // Si ya no queda hueco que llenar, es la ficha que el editor anade sola: fuera.
    else { cv.remove(o); }
  });
  cv.discardActiveObject(); cv.requestRenderAll();
}, [elementos.filter(x=>x.tipo==='ficha'), info.W, info.H]);

await page.keyboard.press('Escape'); await page.waitForTimeout(1200);
const puestos=await page.evaluate(()=>window.__cv?window.__cv.getObjects().length:-1);
// El boton de guardar vive en un cajon plegado: no es 'visible' para el raton, pero
// pulsarlo por JS dispara igual el submit y sus manejadores (que serializan el lienzo).
await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded',timeout:180000}).catch(()=>null),
  page.evaluate(()=>{const b=document.getElementById('task-submit-btn'); if(b) b.click();})]);
await page.waitForTimeout(2000);



    hechas.push(`${NUM}:${puestos}`);
    if(fallos.length) problemas.push(`${NUM} elementos: ${fallos.join(', ')}`);
    await page.close();
  } catch(err){ problemas.push(`${NUM}: ${err.name}`); }
  const min=((Date.now()-t0)/60000).toFixed(0);
  console.log(`[${i+1}/${NUMS.length}] Tarea ${NUM} · rehechas ${hechas.length} · problemas ${problemas.length} · ${min} min`);
  fs.writeFileSync('rehacer_estado3.txt', `rehechas ${hechas.length}\nproblemas ${problemas.length}\n${problemas.join('\n')}`);
}
console.log(`\nTERMINADO: ${hechas.length} rehechas, ${problemas.length} con problema`);
await nav.close();
