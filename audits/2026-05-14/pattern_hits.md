# Hallazgos por patrones (generado)

Archivos analizados: 344  
Hits totales: 192

## `csrf_exempt` (63)

- `football/views.py:59` from django.views.decorators.csrf import csrf_exempt
- `football/views.py:911` @csrf_exempt
- `football/views.py:4101` @csrf_exempt
- `football/views.py:4380` @csrf_exempt
- `football/views.py:7296` @csrf_exempt
- `football/views.py:19106` @csrf_exempt
- `football/views.py:22101` @csrf_exempt
- `football/views.py:22506` @csrf_exempt
- `football/views.py:22573` @csrf_exempt
- `football/views.py:22702` @csrf_exempt
- `football/views.py:40173` @csrf_exempt
- `football/views.py:40608` @csrf_exempt
- `football/views.py:41235` @csrf_exempt
- `football/views.py:41296` @csrf_exempt
- `football/views.py:42220` @csrf_exempt
- `football/views.py:42226` @csrf_exempt
- `football/views.py:42241` @csrf_exempt
- `football/views.py:42247` @csrf_exempt
- `football/views.py:42262` @csrf_exempt
- `football/views.py:42268` @csrf_exempt
- `football/views.py:46694` @csrf_exempt
- `football/views.py:46750` @csrf_exempt
- `football/views.py:47002` @csrf_exempt
- `football/views.py:47125` @csrf_exempt
- `football/views.py:47246` @csrf_exempt
- `football/views.py:47316` @csrf_exempt
- `football/views.py:47363` @csrf_exempt
- `football/views.py:48348` @csrf_exempt
- `football/views.py:48488` @csrf_exempt
- `football/views.py:48579` @csrf_exempt
- `football/views.py:48954` @csrf_exempt
- `football/views.py:49015` @csrf_exempt
- `football/views.py:49056` @csrf_exempt
- `football/views.py:49117` @csrf_exempt
- `football/views.py:49162` @csrf_exempt
- `football/views.py:49306` @csrf_exempt
- `football/views.py:49349` @csrf_exempt
- `football/views.py:49411` @csrf_exempt
- `football/views.py:49581` @csrf_exempt
- `football/views.py:49707` @csrf_exempt
- `football/views.py:49742` @csrf_exempt
- `football/views.py:49936` @csrf_exempt
- `football/views.py:50019` @csrf_exempt
- `football/views.py:50062` @csrf_exempt
- `football/views.py:50372` @csrf_exempt
- `football/views.py:50490` @csrf_exempt
- `football/views.py:50685` @csrf_exempt
- `football/views.py:51880` @csrf_exempt
- `football/views.py:52345` @csrf_exempt
- `football/views.py:52567` @csrf_exempt
- `football/views.py:53261` @csrf_exempt
- `football/views.py:53385` @csrf_exempt
- `football/views.py:53542` @csrf_exempt
- `football/views.py:53608` @csrf_exempt
- `football/views.py:53838` @csrf_exempt
- `football/views.py:55649` @csrf_exempt
- `football/views.py:59283` @csrf_exempt
- `football/views.py:59518` @csrf_exempt
- `football/views.py:59723` @csrf_exempt
- `football/views.py:59799` @csrf_exempt
- `football/views.py:59992` @csrf_exempt
- `football/views.py:61538` @csrf_exempt
- `football/views.py:61557` @csrf_exempt

## `eval` (4)

- `scripts/e2e_audit_playwright.js:433` .$$eval('a[href]', (anchors) => anchors.map((a) => a.getAttribute('href') || ''))
- `scripts/e2e_audit_playwright.js:493` .$$eval('a[href^="/player/"]', (anchors) => anchors.map((a) => a.getAttribute('href') || ''))
- `scripts/e2e_editor_drag_playwright.js:121` .$eval('#task-builder-form', (el) => (el && el.dataset ? String(el.dataset.draftKey || '') : ''))
- `scripts/e2e_tacticalpad_smoke.js:205` .$eval('#task-builder-form', (el) => (el && el.dataset ? String(el.dataset.draftKey || '') : ''))

## `exec` (5)

- `football/static/football/js/kpi_explorer.js:43` const m = /filename=\"([^\"]+)\"/i.exec(cd);
- `football/static/football/js/analysis_video_studio.js:782` const m = /filename=\"([^\"]+)\"/i.exec(cd);
- `football/static/vendor/three.min.js:7` function(t,e){"object"==typeof exports&&"undefined"!=typeof module?e(exports):"function"==typeof define&&define.amd?define(["exports"],e):e((t="undefined"!=typeof globalThis?globalThis:t||self).THREE={})}(this,(function(t){"use strict";const e="160",n=1,i=2,r=3,s=0,a=1,o=100,l=204,c=205,h=0,u=1,d=2,p=0,m=1,f=2,g=3,_=4,v=5,x=6,y="attached",M="detached",S=300,b=301,T=302,E=303,w=304,A=306,R=1e3,C=10
- `football/static/vendor/fabric.min.js:1` var fabric=fabric||{version:"5.3.0"};if("undefined"!=typeof exports?exports.fabric=fabric:"function"==typeof define&&define.amd&&define([],function(){return fabric}),"undefined"!=typeof document&&"undefined"!=typeof window)document instanceof("undefined"!=typeof HTMLDocument?HTMLDocument:Document)?fabric.document=document:fabric.document=document.implementation.createHTMLDocument(""),fabric.window
- `football/templates/football/task_builder.html:8797` while ((match = rx.exec(text)) !== null) {

## `openai_api_key_env` (1)

- `football/views.py:50244` api_key = str(os.getenv('OPENAI_API_KEY') or '').strip()

## `requests_http` (12)

- `football/services.py:393` response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=15)
- `football/services.py:399` file_response = requests.get(file_url, headers={'User-Agent': USER_AGENT}, timeout=15)
- `football/views.py:8722` response = requests.post(
- `football/views.py:8732` response = requests.post(
- `football/views.py:8845` response = requests.post(url, headers=headers, data=data or {}, timeout=UNIVERSO_API_TIMEOUT_SECONDS)
- `football/views.py:8856` response = requests.post(url, headers=headers, data=data or {}, timeout=UNIVERSO_API_TIMEOUT_SECONDS)
- `football/views.py:8882` response = requests.post(url, headers=headers, data=data or {}, timeout=UNIVERSO_API_TIMEOUT_SECONDS)
- `football/views.py:9190` response = requests.get(
- `football/views.py:50294` resp = requests.post(
- `football/management/commands/scrape_preferente.py:88` response = requests.get(
- `scripts/import_from_rfef.py:128` response = requests.get(URL, headers=headers, timeout=30)
- `scripts/import_from_rfef.py:381` response = requests.get(url, headers=headers, timeout=30)

## `stripe` (43)

- `football/models.py:142` # Stripe billing (opcional). Mantener campos vacíos si Stripe no está configurado.
- `football/models.py:251` Registro idempotente de eventos Stripe procesados.
- `football/models.py:253` Evita procesar dos veces el mismo webhook cuando Stripe reintenta.
- `football/urls.py:29` path('stripe/webhook/', views.stripe_webhook, name='stripe-webhook'),
- `football/views.py:278` # Stripe (opcional). No debe romper el sistema si no está configurado.
- `football/views.py:280` import stripe  # type: ignore
- `football/views.py:282` stripe = None
- `football/views.py:573` Map interno (plan_key, interval) -> Stripe price id.
- `football/views.py:594` return bool(_stripe_secret_key() and stripe is not None)
- `football/views.py:605` stripe.api_key = _stripe_secret_key()
- `football/views.py:624` Crea una sesión de Stripe Checkout (suscripción) y devuelve URL para redirigir.
- `football/views.py:634` return JsonResponse({'ok': False, 'error': 'Stripe no está configurado.'}, status=501)
- `football/views.py:714` # En modo subscription, Stripe crea el customer automáticamente.
- `football/views.py:719` session = stripe.checkout.Session.create(**params)
- `football/views.py:732` Abre Stripe Customer Portal para gestionar/cancelar la suscripción.
- `football/views.py:738` return JsonResponse({'ok': False, 'error': 'Stripe no está configurado.'}, status=501)
- `football/views.py:741` return JsonResponse({'ok': False, 'error': 'Este club no tiene cliente Stripe todavía.'}, status=400)
- `football/views.py:748` portal = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
- `football/views.py:915` Webhook Stripe: activa/actualiza la suscripción del workspace.
- `football/views.py:917` if stripe is None:
- `football/views.py:918` return JsonResponse({'ok': False, 'error': 'Stripe lib not available.'}, status=501)
- `football/views.py:925` event = stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=secret)
- `football/views.py:970` sub = stripe.Subscription.retrieve(subscription_id, expand=['items.data.price'])
- `football/views.py:989` sub_full = stripe.Subscription.retrieve(sub_id, expand=['items.data.price'])
- `football/static/football/js/sessions_tactical_pad.js:871` const tokenStripeColorInput = document.getElementById('task-token-stripe-color');
- `football/static/football/js/sessions_tactical_pad.js:872` const tokenStripeColorHexInput = document.getElementById('task-token-stripe-color-hex');
- `football/static/football/js/sessions_tactical_pad.js:3530` const stripeHex = parseColorToHex(options.stripe, parseColorToHex(group?.data?.token_stripe_color, baseHex)) || baseHex;
- `football/static/football/js/sessions_tactical_pad.js:4245` stripe: safeText(active?.data?.token_stripe_color) || safeText(active?.data?.color) || '#0f7a35',
- `football/static/football/js/sessions_tactical_pad.js:5928` const stripe = safeText(data.token_stripe_color || data.color || fill);
- `football/static/football/js/sessions_tactical_pad.js:5929` const key = tokenKind.includes('rival') ? stripe : stripe;
- `football/static/football/js/sessions_tactical_pad.js:13971` const stripeColor = parseColorToHex(options?.stripe, parseColorToHex(player?.token_stripe_color, defaultStripe)) || defaultStripe;
- `football/static/football/js/sessions_tactical_pad.js:14094` const stripe = new fabric.Rect({
- `football/static/football/js/sessions_tactical_pad.js:14103` stripe.data = { role: isStripe ? 'token_stripe' : 'token_stripe_base' };
- `football/static/football/js/sessions_tactical_pad.js:14104` stripes.push(stripe);
- `football/static/football/js/sessions_tactical_pad.js:14266` const stripe = new fabric.Rect({
- `football/static/football/js/sessions_tactical_pad.js:14275` stripe.data = { role: isGreen ? 'token_stripe' : 'token_stripe_base' };
- `football/static/football/js/sessions_tactical_pad.js:14276` stripes.push(stripe);
- `football/static/football/js/sessions_tactical_pad.js:14446` applyTokenPalette(group, { base: baseColor, stripe: stripeColor, pattern });
- `football/static/football/js/sessions_tactical_pad.js:18563` applyTokenPalette(active, { stripe: tokenStripeColorInput.value });
- `football/static/football/js/sessions_tactical_pad.js:18580` applyTokenPalette(active, { stripe: hex });
- `football/templates/football/billing.html:185` Stripe no está configurado en este entorno. Contacta con soporte para activar manualmente.
- `football/templates/football/task_builder.html:4916` <input type="color" id="task-token-stripe-color" value="#0f7a35" />
- `football/templates/football/task_builder.html:4919` id="task-token-stripe-color-hex"

## `subprocess_popen` (4)

- `football/video_autocut.py:118` proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)  # noqa: S603
- `football/video_autocut.py:192` proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)  # noqa: S603
- `football/video_autocut.py:303` proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)  # noqa: S603
- `football/views.py:48730` proc = subprocess.Popen(cmd_track, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603

## `subprocess_run` (30)

- `football/views.py:29516` subprocess.run(
- `football/views.py:31009` subprocess.run(
- `football/views.py:35246` subprocess.run(
- `football/views.py:40788` subprocess.run(
- `football/views.py:40818` subprocess.run(
- `football/views.py:48166` out = subprocess.run(
- `football/views.py:48195` subprocess.run(
- `football/views.py:48545` subprocess.run(
- `football/views.py:48669` proc = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)  # noqa: S603
- `football/views.py:51072` subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
- `football/views.py:51142` subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
- `football/views.py:51247` subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
- `football/views.py:51281` subprocess.run(cmd_concat, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
- `football/views.py:51375` proc = subprocess.run(
- `football/views.py:51507` subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
- `football/views.py:51592` subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
- `football/views.py:51624` subprocess.run(cmd_concat, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
- `football/views.py:51652` proc = subprocess.run(
- `football/views.py:51767` subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
- `football/views.py:51867` subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
- `football/views.py:51874` subprocess.run(cmd2, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
- `football/views.py:60250` proc = subprocess.run(
- `football/views.py:60307` proc = subprocess.run(
- `football/views.py:60441` proc = subprocess.run(
- `football/management/commands/seed_video_ocr.py:23` p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
- `football/management/commands/import_rival_video_mp4.py:17` p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
- `football/management/commands/refresh_federation_standings.py:31` result = subprocess.run(
- `football/management/commands/import_player_licenses_pdf.py:97` return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)
- `scripts/ig_video_to_clip.py:34` proc = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
- `scripts/import_from_rfef.py:486` subprocess.run(

## `template_safe_filter` (30)

- `football/templates/football/training_session_detail.html:302` {{ t.sheet.coaching_html|safe }}
- `football/templates/football/training_session_detail.html:308` <div style="margin-top:10px; color:#0f172a;">{{ t.sheet.description_html|safe }}</div>
- `football/templates/football/training_session_detail.html:343` {{ t.sheet.rules_html|safe }}
- `football/templates/football/session_task_pdf.html:596` <div class="rich-text">{{ description_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:605` <div class="rich-text">{{ coaching_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:624` <div class="rich-text">{{ rules_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:638` <div class="rich-text">{{ success_criteria_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:648` <div class="rich-text">{{ progression_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:664` <div class="rich-text">{{ description_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:673` <div class="rich-text">{{ coaching_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:694` <div class="rich-text">{{ rules_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:708` <div class="rich-text">{{ success_criteria_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:718` <div class="rich-text">{{ progression_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:880` <div class="rich-text">{{ description_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:889` <div class="rich-text">{{ coaching_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:900` <div class="rich-text">{{ rules_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:912` <div class="rich-text">{{ progression_rich_html|safe }}</div>
- `football/templates/football/session_task_pdf.html:922` <div class="rich-text">{{ success_criteria_rich_html|safe }}</div>
- `football/templates/football/task_builder.html:5331` {% if initial.description_html %}{{ initial.description_html|safe }}{% else %}{{ initial.description|linebreaksbr }}{% endif %}
- `football/templates/football/task_builder.html:5351` {% if initial.coaching_points_html %}{{ initial.coaching_points_html|safe }}{% else %}{{ initial.coaching_points|linebreaksbr }}{% endif %}
- `football/templates/football/task_builder.html:5371` {% if initial.confrontation_rules_html %}{{ initial.confrontation_rules_html|safe }}{% else %}{{ initial.confrontation_rules|linebreaksbr }}{% endif %}
- `football/templates/football/task_builder.html:5704` {% if initial.organization_html %}{{ initial.organization_html|safe }}{% else %}{{ initial.organization|linebreaksbr }}{% endif %}
- `football/templates/football/task_builder.html:5753` {% if initial.progression_html %}{{ initial.progression_html|safe }}{% else %}{{ initial.progression|linebreaksbr }}{% endif %}
- `football/templates/football/task_builder.html:5773` {% if initial.regression_html %}{{ initial.regression_html|safe }}{% else %}{{ initial.regression|linebreaksbr }}{% endif %}
- `football/templates/football/task_builder.html:5793` {% if initial.success_criteria_html %}{{ initial.success_criteria_html|safe }}{% else %}{{ initial.success_criteria|linebreaksbr }}{% endif %}
- `football/templates/football/convocation.html:624` const opponentOptions = {{ opponent_options_json|safe }};
- `football/templates/football/convocation.html:675` const selectedSet = new Set(({{ selected_player_ids_json|safe }} || []).map((item) => String(item)));
- `football/templates/football/convocation.html:676` const initialCaptainId = {{ captain_id_json|safe }};
- `football/templates/football/convocation.html:677` const initialGoalkeeperId = {{ goalkeeper_id_json|safe }};
- `football/templates/football/convocation.html:680` const injuredPlayerIds = new Set(({{ injured_player_ids_json|safe }} || []).map((item) => String(item)));
