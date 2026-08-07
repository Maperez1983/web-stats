// Fotografia la pizarra de cada tarea DESDE ESTA MAQUINA y sube la imagen.
// El servidor solo tiene que servir la pagina del editor; Chromium corre aqui, donde hay
// memoria de sobra. En Render (un worker) Chromium tumbaba la instancia.
import fs from 'node:fs'; import os from 'node:os';
import { chromium } from 'playwright';
const B='https://app.segundajugada.es';
const TOKEN=fs.readFileSync(`${os.homedir()}/.config/segundajugada/token`,'utf8').trim();

let ck={}; const ch=()=>Object.entries(ck).map(([k,v])=>`${k}=${v}`).join('; ');
const save=r=>{const raw=r.headers.getSetCookie?r.headers.getSetCookie():[r.headers.get('set-cookie')].filter(Boolean);for(const c of raw){const p=c.split(';')[0],i=p.indexOf('=');if(i>0)ck[p.slice(0,i).trim()]=p.slice(i+1).trim();}};
async function entrar(){
  ck={};
  let r=await fetch(B+'/service-login/',{redirect:'manual'});save(r);
  const csrf=((await r.text()).match(/name=["']csrfmiddlewaretoken["'] value=["']([^"']+)/)||[])[1]||'';
  r=await fetch(B+'/service-login/',{method:'POST',redirect:'manual',headers:{'Content-Type':'application/x-www-form-urlencoded',Cookie:ch(),Referer:B+'/service-login/'},body:new URLSearchParams({csrfmiddlewaretoken:csrf,token:TOKEN})});save(r);
}
await entrar();
const IDS=fs.readFileSync(process.argv[2]||'ids_sesiones.txt','utf8').trim().split('\n').filter(Boolean);

async function renovarSesion(ctx){
  await entrar();
  if(ctx){ await ctx.clearCookies(); await ctx.addCookies(Object.entries(ck).map(([name,value])=>({name,value,domain:'app.segundajugada.es',path:'/'}))); }
}
const navegador=await chromium.launch();
const contexto=await navegador.newContext({viewport:{width:1600,height:1000}, deviceScaleFactor:2});
await contexto.addCookies(Object.entries(ck).map(([name,value])=>({name,value,domain:'app.segundajugada.es',path:'/'})));

const hechas=[], fallos=[]; const t0=Date.now();
let seguidos=0;   // fallos consecutivos: si la instancia se cae, hay que dejarla respirar
for(let i=0;i<IDS.length;i++){
  const id=IDS[i];
  try{
    const est=await (await fetch(`${B}/coach/sesiones/tarea/${id}/foto-hd/`,{headers:{Cookie:ch()},signal:AbortSignal.timeout(60000)})).json();
    // Sin salto por 'ya esta al dia': el dibujo es el mismo, lo que cambio es
    // como lo pinta el editor, asi que la foto vieja tiene el fallo horneado.
    const pagina=await contexto.newPage();
    try{
      await pagina.goto(`${B}/coach/sesiones/tareas/${id}/editar/?embedded=1&snapshot=1`,{waitUntil:'domcontentloaded',timeout:120000});
      await pagina.waitForFunction(()=>window.__WEBSTATS_SNAPSHOT_READY===true,null,{timeout:120000});
      await pagina.waitForTimeout(2500);
      // JPEG YA AQUI: subir PNG de varios MB obligaba al servidor a reconvertirlo con Pillow
      // y la instancia se reiniciaba (502). Asi solo tiene que guardarlo.
      const jpg=await pagina.locator('#task-pitch-stage').screenshot({type:'jpeg', quality:88});

      const fd=new FormData();
      fd.append('image', new Blob([jpg],{type:'image/jpeg'}), `board-${id}.jpg`);
      fd.append('signature', String(est.signature||''));
      const rr=await fetch(`${B}/coach/sesiones/tarea/${id}/foto-hd/subir/`,{method:'POST',headers:{Cookie:ch(),'X-CSRFToken':ck.csrftoken||'',Referer:B+'/coach/sesiones/'},body:fd,signal:AbortSignal.timeout(120000)});
      let j=await rr.json().catch(()=>({}));
      if(rr.status===200 && j.al_dia){ hechas.push(id); }
      else {
        await new Promise(s=>setTimeout(s,20000));                      // 502 = instancia ocupada, darle aire
        await renovarSesion(contexto);                                  // 403 = sesion/CSRF caducados
        const fd2=new FormData();
        fd2.append('image', new Blob([jpg],{type:'image/jpeg'}), `board-${id}.jpg`);
        fd2.append('signature', String(est.signature||''));
        const r2=await fetch(`${B}/coach/sesiones/tarea/${id}/foto-hd/subir/`,{method:'POST',headers:{Cookie:ch(),'X-CSRFToken':ck.csrftoken||'',Referer:B+'/coach/sesiones/'},body:fd2,signal:AbortSignal.timeout(120000)});
        const j2=await r2.json().catch(()=>({}));
        if(r2.status===200 && j2.al_dia) hechas.push(id); else fallos.push(`${id}: subida ${rr.status}/${r2.status}`);
      }
    } finally { await pagina.close(); }
    seguidos = 0;
  }catch(e){
    fallos.push(`${id}: ${e.name}`); seguidos += 1;
    try{ await renovarSesion(contexto); }catch(_){}
    if(seguidos>=3){   // la instancia se ha caido: esperar a que vuelva
      console.log('   servidor ahogado, esperando 3 min');
      await new Promise(s=>setTimeout(s,180000)); seguidos=0;
    }
  }
  if((i+1)%25===0) await renovarSesion(contexto);
  await new Promise(s=>setTimeout(s,2500));   // servidor ampliado: se puede ir mas rapido
  const min=((Date.now()-t0)/60000).toFixed(0);
  console.log(`[${i+1}/${IDS.length}] hechas ${hechas.length} · fallos ${fallos.length} · ${min} min`);
  fs.writeFileSync('fotos_locales_estado.txt',`hechas ${hechas.length}\nfallos ${fallos.length}\n${fallos.join('\n')}`);
}
await navegador.close();
console.log(`\nTERMINADO: ${hechas.length} con foto, ${fallos.length} sin ella`);
