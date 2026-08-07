// Crea en la biblioteca una tarea por ficha del libro, con su texto, su clasificacion y el
// dibujo original de portada. Reanudable: lo ya creado se salta (el registro manda), asi que
// si se corta a mitad no se duplica nada.
import fs from 'node:fs'; import os from 'node:os';
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
const des=t=>String(t||'').replace(/&quot;/g,'"').replace(/&#x27;/g,"'").replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>');
function campos(form){
  const c=new URLSearchParams();
  for(const m of form.matchAll(/<input\b[^>]*name=["']([^"']+)["'][^>]*>/gi)){
    const tag=m[0]; if(/type=["'](file|submit|button|checkbox|radio)["']/i.test(tag)) continue;
    const v=(tag.match(/value=["']([^"']*)["']/)||[])[1]||''; c.append(m[1],des(v));
  }
  for(const m of form.matchAll(/<textarea\b[^>]*name=["']([^"']+)["'][^>]*>([\s\S]*?)<\/textarea>/gi)) c.append(m[1],des(m[2]));
  return c;
}
await entrar();
const textos=JSON.parse(fs.readFileSync('sesiones/textos_lu188.json','utf8'));
const RUTA='creadas_188.json';
const creadas = fs.existsSync(RUTA) ? JSON.parse(fs.readFileSync(RUTA,'utf8')) : {};
const claves=Object.keys(textos);
let hechas=0, fallos=0;
for (let i=0;i<claves.length;i++){
  const clave=claves[i], t=textos[clave];
  if (creadas[clave]) { hechas++; continue; }
  try{
    const nueva=`${B}/coach/sesiones/tareas/nueva/?repo=traditional&team=1&workspace=1`;
    const rg=await fetch(nueva,{headers:{Cookie:ch()},signal:AbortSignal.timeout(120000)}); save(rg);
    const c=campos(await rg.text());
    c.set('draw_task_title', t.titulo);
    c.set('draw_task_description', t.objetivo);
    c.set('draw_task_coaching_points', t.consignas);
    c.set('draw_task_minutes', String(t.minutos));
    c.set('draw_task_pitch_preset','full_pitch');
    c.set('draw_task_pitch_grass_style','flat_2d');
    if (t.familia) c.set('task_family', t.familia);
    if (t.momento) c.set('draw_task_game_moment', t.momento);
    const res=await fetch(nueva,{method:'POST',redirect:'manual',headers:{'Content-Type':'application/x-www-form-urlencoded',Cookie:ch(),Referer:nueva,Origin:B},body:c,signal:AbortSignal.timeout(240000)});
    save(res);
    const id=((res.headers.get('location')||'').match(/tareas?\/(\d+)\//)||[])[1];
    if(!id) throw new Error('http '+res.status);
    creadas[clave]=id;
    // portada: el dibujo del libro tal cual, para reconocerla de un vistazo
    try{
      const bin=fs.readFileSync(`lu_dibujos/${clave}.jpg`);
      const fd=new FormData();
      fd.append('task_id', id);
      fd.append('image', new Blob([bin],{type:'image/jpeg'}), `${clave}.jpg`);
      await fetch(`${B}/coach/sesiones/portadas/subir/`,{method:'POST',headers:{Cookie:ch(),'X-CSRFToken':ck.csrftoken||'',Referer:B+'/coach/sesiones/'},body:fd,signal:AbortSignal.timeout(120000)});
    }catch(e){ /* la portada no bloquea */ }
    hechas++;
  }catch(e){
    fallos++;
    if (fallos % 3 === 0) { try{ await entrar(); }catch(_){ } }
  }
  fs.writeFileSync(RUTA, JSON.stringify(creadas,null,1));
  if ((i+1) % 10 === 0 || i === claves.length-1) console.log(`[${i+1}/${claves.length}] creadas ${Object.keys(creadas).length} · fallos ${fallos}`);
  await new Promise(r=>setTimeout(r, 900));
}
console.log(`\nTERMINADO: ${Object.keys(creadas).length} tareas creadas, ${fallos} fallos`);
