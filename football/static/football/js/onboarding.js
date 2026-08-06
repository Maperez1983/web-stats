/* Configuracion del club: portada, equipaciones 2D y vallas.
 *
 * Vivia incrustado en la plantilla (30 KB de JavaScript que el navegador no cachea). Lo unico
 * que dependia de Django era la URL de la portada actual, que ahora llega en un bloque de
 * configuracion diminuto (window.__ONBOARDING__).
 */
(function () {
        var coverInput = document.getElementById('id_cover_image');
        var crestInput = document.getElementById('id_crest_image');
        var pageCover = document.getElementById('page-cover-preview');
        var inlineCover = document.getElementById('cover-inline-preview');
        var inlineEmpty = document.getElementById('cover-inline-empty');
        var pageCrest = document.getElementById('page-crest-preview');
        var pageCrestEmpty = document.getElementById('page-crest-empty');
        var systemPreview = document.getElementById('system-theme-preview');
        var systemPanel = document.getElementById('system-panel-preview');
        var systemButton = document.getElementById('system-button-preview');
        var colorFields = {
          primary: document.getElementById('id_theme_primary'),
          secondary: document.getElementById('id_theme_secondary'),
          bg: document.getElementById('id_theme_bg'),
          text: document.getElementById('id_theme_text'),
          buttonBg: document.getElementById('id_theme_button_bg'),
          buttonText: document.getElementById('id_theme_button_text'),
          panel: document.getElementById('id_theme_panel_flat'),
          line: document.getElementById('id_theme_line'),
          shadow: document.getElementById('id_theme_shadow'),
          imageMode: document.getElementById('id_theme_system_image_mode'),
          font: document.getElementById('id_theme_font'),
          fontWeight: document.getElementById('id_theme_font_weight'),
          fontStyle: document.getElementById('id_theme_font_style'),
          fontDecoration: document.getElementById('id_theme_font_decoration'),
          fontSize: document.getElementById('id_theme_font_size')
        };
        var objectUrls = [];
        var currentCoverUrl = (window.__ONBOARDING__ || {}).coverPreviewUrl || '';
        var kit2dFileInputs = Array.prototype.slice.call(document.querySelectorAll('input[data-kit2d-slot]') || []);
        var kit2dSave = document.getElementById('kit2d-direct-save');
        var kit2dStatus = document.getElementById('kit2d-direct-status');
        var kit2dSlots = ['home', 'away', 'third', 'entreno', 'chandal', 'gk', 'gk2', 'gk3'];
        var kit2dGkGenerateButtons = Array.prototype.slice.call(document.querySelectorAll('button[data-kit2d-gk-target][data-kit2d-gk-source]') || []);
        var kit2dTemplateButtons = Array.prototype.slice.call(document.querySelectorAll('button[data-kit2d-template-slot]') || []);
        var kit2dExistingValue = {};
        var kit2dPrepared = {};

        function rememberUrl(url) {
          objectUrls.push(url);
          return url;
        }

        function firstImageUrl(input) {
          if (!input || !input.files || !input.files.length) return '';
          var file = input.files[0];
          if (!file || !String(file.type || '').startsWith('image/')) return '';
          return rememberUrl(URL.createObjectURL(file));
        }

        function valueOf(field, fallback) {
          return field && field.value ? field.value : fallback;
        }

        function previewShadow(value) {
          if (value === 'none') return 'none';
          if (value === 'soft') return '0 8px 20px rgba(0,0,0,0.12)';
          if (value === 'strong') return '0 22px 56px rgba(0,0,0,0.34)';
          return '0 16px 36px rgba(0,0,0,0.24)';
        }

        function previewFont(value) {
          if (value === 'system') return 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif';
          if (value === 'avenir') return '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif';
          if (value === 'segoe') return '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif';
          if (value === 'roboto') return 'Roboto, "Helvetica Neue", Arial, system-ui, sans-serif';
          if (value === 'georgia') return 'Georgia, "Times New Roman", serif';
          if (value === 'condensed') return '"Arial Narrow", "Roboto Condensed", "Helvetica Neue", Arial, sans-serif';
          return '"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif';
        }

        function previewWeight(value) {
          if (value === 'regular') return '400';
          if (value === 'semibold') return '650';
          if (value === 'bold') return '800';
          return '500';
        }

        function previewSize(value) {
          if (value === 'compact') return '15px';
          if (value === 'large') return '17px';
          return '16px';
        }

        function csrfToken() {
          var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
          return match ? decodeURIComponent(match[1]) : '';
        }

        function setKit2dStatus(message, isError) {
          if (!kit2dStatus) return;
          kit2dStatus.textContent = message;
          kit2dStatus.style.color = isError ? '#fecaca' : 'rgba(226,232,240,0.76)';
        }

        function renderKit2dDataUrl(sourceImage, size) {
          var canvas = document.createElement('canvas');
          var ctx = canvas.getContext('2d');
          var sourceWidth = sourceImage.naturalWidth || sourceImage.width || size;
          var sourceHeight = sourceImage.naturalHeight || sourceImage.height || size;
          var scale = Math.min(size / sourceWidth, size / sourceHeight);
          var width = Math.max(1, Math.round(sourceWidth * scale));
          var height = Math.max(1, Math.round(sourceHeight * scale));
          canvas.width = size;
          canvas.height = size;
          ctx.clearRect(0, 0, size, size);
          ctx.imageSmoothingEnabled = true;
          ctx.imageSmoothingQuality = 'high';
          ctx.drawImage(sourceImage, Math.round((size - width) / 2), Math.round((size - height) / 2), width, height);
          return canvas.toDataURL('image/png');
        }

        function hexToRgb(hex) {
          var normalized = String(hex || '').trim().replace('#', '');
          if (/^[0-9a-fA-F]{3}$/.test(normalized)) {
            normalized = normalized.split('').map(function (char) { return char + char; }).join('');
          }
          if (!/^[0-9a-fA-F]{6}$/.test(normalized)) normalized = '1d4ed8';
          return {
            r: parseInt(normalized.slice(0, 2), 16),
            g: parseInt(normalized.slice(2, 4), 16),
            b: parseInt(normalized.slice(4, 6), 16)
          };
        }

        function colorLuminance(rgb) {
          var r = (rgb && Number.isFinite(rgb.r) ? rgb.r : 0) / 255;
          var g = (rgb && Number.isFinite(rgb.g) ? rgb.g : 0) / 255;
          var b = (rgb && Number.isFinite(rgb.b) ? rgb.b : 0) / 255;
          return (r * 0.299) + (g * 0.587) + (b * 0.114);
        }

        function contrastDetailRgb(baseRgb) {
          return colorLuminance(baseRgb) < 0.54
            ? { r: 255, g: 255, b: 255, hex: '#ffffff' }
            : { r: 12, g: 18, b: 32, hex: '#0c1220' };
        }

        function loadKit2dImage(dataUrl, onLoad, onError) {
          var img = new Image();
          img.onload = function () { onLoad(img); };
          img.onerror = function () { if (onError) onError(); };
          img.src = dataUrl;
        }

        function renderRecoloredKit2dDataUrl(sourceImage, size, colorHex) {
          var canvas = document.createElement('canvas');
          var ctx = canvas.getContext('2d');
          var sourceWidth = sourceImage.naturalWidth || sourceImage.width || size;
          var sourceHeight = sourceImage.naturalHeight || sourceImage.height || size;
          var scale = Math.min(size / sourceWidth, size / sourceHeight);
          var width = Math.max(1, Math.round(sourceWidth * scale));
          var height = Math.max(1, Math.round(sourceHeight * scale));
          var x = Math.round((size - width) / 2);
          var y = Math.round((size - height) / 2);
          var rgb = hexToRgb(colorHex);
          canvas.width = size;
          canvas.height = size;
          ctx.clearRect(0, 0, size, size);
          ctx.imageSmoothingEnabled = true;
          ctx.imageSmoothingQuality = 'high';
          ctx.drawImage(sourceImage, x, y, width, height);
          var imageData = ctx.getImageData(0, 0, size, size);
          var data = imageData.data;
          for (var i = 0; i < data.length; i += 4) {
            var alpha = data[i + 3];
            if (!alpha) continue;
            var luminance = ((data[i] * 0.299) + (data[i + 1] * 0.587) + (data[i + 2] * 0.114)) / 255;
            var shade = 0.58 + (luminance * 0.58);
            data[i] = Math.max(0, Math.min(255, Math.round(rgb.r * shade)));
            data[i + 1] = Math.max(0, Math.min(255, Math.round(rgb.g * shade)));
            data[i + 2] = Math.max(0, Math.min(255, Math.round(rgb.b * shade)));
          }
          ctx.putImageData(imageData, 0, 0);
          return canvas.toDataURL('image/png');
        }

        function renderGoalkeeperKit2dDataUrl(sourceImage, size, colorHex) {
          var canvas = document.createElement('canvas');
          var ctx = canvas.getContext('2d');
          var sourceWidth = sourceImage.naturalWidth || sourceImage.width || size;
          var sourceHeight = sourceImage.naturalHeight || sourceImage.height || size;
          var scale = Math.min(size / sourceWidth, size / sourceHeight);
          var width = Math.max(1, Math.round(sourceWidth * scale));
          var height = Math.max(1, Math.round(sourceHeight * scale));
          var x = Math.round((size - width) / 2);
          var y = Math.round((size - height) / 2);
          var baseRgb = hexToRgb(colorHex);
          var detailRgb = contrastDetailRgb(baseRgb);
          canvas.width = size;
          canvas.height = size;
          ctx.clearRect(0, 0, size, size);
          ctx.imageSmoothingEnabled = true;
          ctx.imageSmoothingQuality = 'high';
          ctx.drawImage(sourceImage, x, y, width, height);
          var imageData = ctx.getImageData(0, 0, size, size);
          var data = imageData.data;
          for (var i = 0; i < data.length; i += 4) {
            var alpha = data[i + 3];
            if (!alpha) continue;
            var r = data[i];
            var g = data[i + 1];
            var b = data[i + 2];
            var max = Math.max(r, g, b);
            var min = Math.min(r, g, b);
            var luminance = ((r * 0.299) + (g * 0.587) + (b * 0.114)) / 255;
            var saturation = max ? (max - min) / max : 0;
            var isLikelyDetail = luminance < 0.20
              || luminance > 0.82
              || (saturation < 0.18 && (luminance < 0.42 || luminance > 0.62));
            if (isLikelyDetail) {
              var detailShade = detailRgb.hex === '#ffffff'
                ? 0.78 + (luminance * 0.22)
                : 0.38 + ((1 - luminance) * 0.28);
              data[i] = Math.max(0, Math.min(255, Math.round(detailRgb.r * detailShade)));
              data[i + 1] = Math.max(0, Math.min(255, Math.round(detailRgb.g * detailShade)));
              data[i + 2] = Math.max(0, Math.min(255, Math.round(detailRgb.b * detailShade)));
            } else {
              var shade = 0.62 + (luminance * 0.52);
              data[i] = Math.max(0, Math.min(255, Math.round(baseRgb.r * shade)));
              data[i + 1] = Math.max(0, Math.min(255, Math.round(baseRgb.g * shade)));
              data[i + 2] = Math.max(0, Math.min(255, Math.round(baseRgb.b * shade)));
            }
          }
          ctx.putImageData(imageData, 0, 0);
          return canvas.toDataURL('image/png');
        }

        function addTemplateJerseyPath(ctx, size) {
          var s = size / 128;
          ctx.beginPath();
          ctx.moveTo(33 * s, 32 * s);
          ctx.bezierCurveTo(33 * s, 22 * s, 39 * s, 18 * s, 47 * s, 18 * s);
          ctx.lineTo(54 * s, 18 * s);
          ctx.bezierCurveTo(57 * s, 25 * s, 71 * s, 25 * s, 74 * s, 18 * s);
          ctx.lineTo(82 * s, 18 * s);
          ctx.bezierCurveTo(90 * s, 18 * s, 96 * s, 22 * s, 96 * s, 32 * s);
          ctx.lineTo(111 * s, 43 * s);
          ctx.lineTo(101 * s, 62 * s);
          ctx.lineTo(93 * s, 58 * s);
          ctx.lineTo(93 * s, 108 * s);
          ctx.bezierCurveTo(93 * s, 113 * s, 89 * s, 116 * s, 84 * s, 116 * s);
          ctx.lineTo(44 * s, 116 * s);
          ctx.bezierCurveTo(39 * s, 116 * s, 35 * s, 113 * s, 35 * s, 108 * s);
          ctx.lineTo(35 * s, 58 * s);
          ctx.lineTo(27 * s, 62 * s);
          ctx.lineTo(17 * s, 43 * s);
          ctx.closePath();
        }

        function renderTemplateKit2dDataUrl(size, mainColor, trimColor, slot) {
          var canvas = document.createElement('canvas');
          var ctx = canvas.getContext('2d');
          var s = size / 128;
          canvas.width = size;
          canvas.height = size;
          ctx.clearRect(0, 0, size, size);
          ctx.save();
          addTemplateJerseyPath(ctx, size);
          ctx.clip();
          ctx.fillStyle = mainColor;
          ctx.fillRect(0, 0, size, size);
          if (slot === 'home') {
            var stripeW = 10 * s;
            for (var x = 24 * s; x < 104 * s; x += stripeW * 2) {
              ctx.fillStyle = trimColor;
              ctx.fillRect(x, 0, stripeW, size);
            }
          } else {
            ctx.fillStyle = trimColor;
            ctx.globalAlpha = 0.88;
            ctx.fillRect(28 * s, 50 * s, 72 * s, 10 * s);
            ctx.fillRect(56 * s, 18 * s, 16 * s, 98 * s);
            ctx.globalAlpha = 1;
          }
          ctx.fillStyle = 'rgba(255,255,255,0.12)';
          ctx.fillRect(0, 18 * s, size, 22 * s);
          ctx.restore();
          ctx.save();
          ctx.lineWidth = Math.max(2, 3 * s);
          ctx.strokeStyle = 'rgba(255,255,255,0.90)';
          addTemplateJerseyPath(ctx, size);
          ctx.stroke();
          ctx.restore();
          ctx.save();
          ctx.beginPath();
          ctx.moveTo(51 * s, 18 * s);
          ctx.bezierCurveTo(55 * s, 34 * s, 73 * s, 34 * s, 77 * s, 18 * s);
          ctx.lineTo(70 * s, 18 * s);
          ctx.bezierCurveTo(67 * s, 26 * s, 61 * s, 26 * s, 58 * s, 18 * s);
          ctx.closePath();
          ctx.fillStyle = 'rgba(15,23,42,0.28)';
          ctx.strokeStyle = 'rgba(255,255,255,0.24)';
          ctx.lineWidth = Math.max(1, 1.5 * s);
          ctx.fill();
          ctx.stroke();
          ctx.restore();
          return canvas.toDataURL('image/png');
        }

        function kit2dColorsForSlot(slot) {
          if (slot === 'away') {
            return {
              main: (document.getElementById('id_kit_away_main') || {}).value || '#0b1220',
              trim: (document.getElementById('id_kit_away_trim') || {}).value || '#f4b400'
            };
          }
          if (slot === 'third') {
            return {
              main: (document.getElementById('id_kit_away_trim') || {}).value || '#f4b400',
              trim: (document.getElementById('id_kit_home_main') || {}).value || '#06814d'
            };
          }
          if (slot === 'entreno') {
            return {
              main: (document.getElementById('id_kit_home_main') || {}).value || '#06814d',
              trim: (document.getElementById('id_kit_home_trim') || {}).value || '#ffffff'
            };
          }
          if (slot === 'chandal') {
            return {
              main: (document.getElementById('id_kit_home_main') || {}).value || '#20462d',
              trim: (document.getElementById('id_kit_home_trim') || {}).value || '#ffffff'
            };
          }
          if (slot === 'gk' || slot === 'gk2' || slot === 'gk3') {
            if (slot === 'gk2') {
              return {
                main: (document.getElementById('id_kit_away_main') || {}).value || '#f4b400',
                trim: (document.getElementById('id_kit_away_trim') || {}).value || '#111827'
              };
            }
            if (slot === 'gk3') {
              return {
                main: (document.getElementById('id_kit_home_trim') || {}).value || '#ffffff',
                trim: (document.getElementById('id_kit_home_main') || {}).value || '#06814d'
              };
            }
            return {
              main: (document.getElementById('id_kit_gk_main') || {}).value || '#1d4ed8',
              trim: (document.getElementById('id_kit_gk_trim') || {}).value || '#ffffff'
            };
          }
          return {
            main: (document.getElementById('id_kit_home_main') || {}).value || '#06814d',
            trim: (document.getElementById('id_kit_home_trim') || {}).value || '#ffffff'
          };
        }

        function kit2dSlotLabel(slot) {
          if (slot === 'away') return '2ª equipación';
          if (slot === 'third') return '3ª equipación';
          if (slot === 'entreno') return 'equipación de entrenamiento';
          if (slot === 'chandal') return 'chándal';
          if (slot === 'gk') return 'portero 1';
          if (slot === 'gk2') return 'portero 2';
          if (slot === 'gk3') return 'portero 3';
          return '1ª equipación';
        }

        function normalizeKit2dSlot(slot) {
          slot = String(slot || '').trim().toLowerCase();
          return kit2dSlots.indexOf(slot) >= 0 ? slot : 'home';
        }

        function kit2dClubDataUrlForSlot(slot) {
          slot = normalizeKit2dSlot(slot);
          return (kit2dPrepared[slot] && kit2dPrepared[slot].club_data_url)
            || kit2dExistingValue[slot + '_club_data_url']
            || (slot === 'home' ? kit2dExistingValue.club_data_url : '')
            || '';
        }

        function setKit2dPreview(slot, dataUrl) {
          var preview = document.getElementById('kit2d-' + slot + '-preview');
          var empty = document.getElementById('kit2d-' + slot + '-empty');
          if (preview && dataUrl) {
            preview.src = dataUrl;
            preview.style.display = 'block';
          }
          if (empty && dataUrl) empty.style.display = 'none';
        }

        function hasPreparedKit2d() {
          return Object.keys(kit2dPrepared || {}).some(function (slot) {
            return !!(kit2dPrepared[slot] && kit2dPrepared[slot].editor_data_url);
          });
        }

        function prepareKit2dUpload(file, slot) {
          slot = normalizeKit2dSlot(slot);
          if (!file || !String(file.type || '').startsWith('image/')) {
            delete kit2dPrepared[slot];
            if (kit2dSave) kit2dSave.disabled = !hasPreparedKit2d();
            setKit2dStatus('Selecciona una imagen PNG/WebP/JPG válida.', true);
            return;
          }
          var reader = new FileReader();
          reader.onload = function () {
            var img = new Image();
            img.onload = function () {
              var clubDataUrl = renderKit2dDataUrl(img, 128);
              var editorDataUrl = renderKit2dDataUrl(img, 64);
              kit2dPrepared[slot] = {
                club_data_url: clubDataUrl,
                editor_data_url: editorDataUrl,
                club_size: 128,
                editor_size: 64,
                source: 'upload',
                file_name: file.name || '',
                saved_at: new Date().toISOString()
              };
              setKit2dPreview(slot, clubDataUrl);
              if (kit2dSave) kit2dSave.disabled = false;
              setKit2dStatus(kit2dSlotLabel(slot) + ' cargada. Revisa la vista previa y pulsa guardar.', false);
            };
            img.onerror = function () {
              delete kit2dPrepared[slot];
              if (kit2dSave) kit2dSave.disabled = !hasPreparedKit2d();
              setKit2dStatus('No se pudo leer esa imagen. Prueba con un PNG transparente.', true);
            };
            img.src = reader.result;
          };
          reader.onerror = function () {
            delete kit2dPrepared[slot];
            if (kit2dSave) kit2dSave.disabled = !hasPreparedKit2d();
            setKit2dStatus('No se pudo cargar el archivo seleccionado.', true);
          };
          reader.readAsDataURL(file);
        }

        function generateGoalkeeperKitFromSource(targetSlot, sourceSlot) {
          targetSlot = normalizeKit2dSlot(targetSlot);
          sourceSlot = normalizeKit2dSlot(sourceSlot);
          if (targetSlot !== 'gk' && targetSlot !== 'gk2' && targetSlot !== 'gk3') targetSlot = 'gk';
          if (sourceSlot !== 'home' && sourceSlot !== 'away' && sourceSlot !== 'third') sourceSlot = 'home';
          var sourceDataUrl = kit2dClubDataUrlForSlot(sourceSlot);
          if (!sourceDataUrl) {
            setKit2dStatus('Carga primero la ' + kit2dSlotLabel(sourceSlot) + ' para generar el kit de ' + kit2dSlotLabel(targetSlot) + '.', true);
            return;
          }
          setKit2dStatus('Generando ' + kit2dSlotLabel(targetSlot) + ' desde la ' + kit2dSlotLabel(sourceSlot) + '...', false);
          loadKit2dImage(sourceDataUrl, function (img) {
            var recolorInput = document.getElementById('id_kit2d_' + targetSlot + '_recolor');
            var color = (recolorInput && recolorInput.value) || kit2dColorsForSlot(targetSlot).main || '#1d4ed8';
            var detailColor = contrastDetailRgb(hexToRgb(color)).hex;
            var clubDataUrl = renderGoalkeeperKit2dDataUrl(img, 128, color);
            var editorDataUrl = renderGoalkeeperKit2dDataUrl(img, 64, color);
            kit2dPrepared[targetSlot] = {
              club_data_url: clubDataUrl,
              editor_data_url: editorDataUrl,
              club_size: 128,
              editor_size: 64,
              source: 'generated_from_' + sourceSlot,
              base_slot: sourceSlot,
              file_name: targetSlot + '_desde_' + sourceSlot + '.png',
              color: color,
              detail_color: detailColor,
              saved_at: new Date().toISOString()
            };
            setKit2dPreview(targetSlot, clubDataUrl);
            if (kit2dSave) kit2dSave.disabled = false;
            setKit2dStatus(kit2dSlotLabel(targetSlot) + ' generado con detalles en ' + (detailColor === '#ffffff' ? 'blanco' : 'negro') + '. Pulsa guardar para aplicarlo.', false);
          }, function () {
            setKit2dStatus('No se pudo generar ' + kit2dSlotLabel(targetSlot) + ' desde la ' + kit2dSlotLabel(sourceSlot) + '.', true);
          });
        }

        function generateTemplateKit(slot) {
          slot = normalizeKit2dSlot(slot);
          var colors = kit2dColorsForSlot(slot);
          var clubDataUrl = renderTemplateKit2dDataUrl(128, colors.main, colors.trim, slot);
          var editorDataUrl = renderTemplateKit2dDataUrl(64, colors.main, colors.trim, slot);
          kit2dPrepared[slot] = {
            club_data_url: clubDataUrl,
            editor_data_url: editorDataUrl,
            club_size: 128,
            editor_size: 64,
            source: 'generated_template',
            file_name: 'kit_' + slot + '_colores.png',
            main_color: colors.main,
            trim_color: colors.trim,
            saved_at: new Date().toISOString()
          };
          setKit2dPreview(slot, clubDataUrl);
          if (kit2dSave) kit2dSave.disabled = false;
          setKit2dStatus(kit2dSlotLabel(slot) + ' generada con colores. Pulsa guardar para aplicarla.', false);
        }

        function buildKit2dPreferenceValue() {
          var value = Object.assign({}, kit2dExistingValue || {});
          kit2dSlots.forEach(function (slot) {
            var prepared = kit2dPrepared[slot];
            if (!prepared || !prepared.editor_data_url) return;
            value[slot + '_club_data_url'] = prepared.club_data_url;
            value[slot + '_editor_data_url'] = prepared.editor_data_url;
            value[slot + '_file_name'] = prepared.file_name || '';
          });
          if (kit2dPrepared.home && kit2dPrepared.home.editor_data_url) {
            value.club_data_url = kit2dPrepared.home.club_data_url;
            value.editor_data_url = kit2dPrepared.home.editor_data_url;
          } else if (!value.club_data_url && value.home_club_data_url) {
            value.club_data_url = value.home_club_data_url;
            value.editor_data_url = value.home_editor_data_url;
          }
          value.club_size = 128;
          value.editor_size = 64;
          value.source = 'upload';
          value.saved_at = new Date().toISOString();
          return value;
        }

        function loadExistingKit2dPreference() {
          fetch('/api/workspace/preferences/get/?key=kit2d.tokens', { credentials: 'same-origin' })
            .then(function (response) { return response.ok ? response.json() : null; })
            .then(function (data) {
              var value = data && data.ok && data.value && typeof data.value === 'object' ? data.value : {};
              kit2dExistingValue = value || {};
              setKit2dPreview('home', value.home_club_data_url || value.club_data_url || '');
              setKit2dPreview('away', value.away_club_data_url || '');
              setKit2dPreview('third', value.third_club_data_url || '');
              setKit2dPreview('entreno', value.entreno_club_data_url || value.training_club_data_url || '');
              setKit2dPreview('chandal', value.chandal_club_data_url || '');
              setKit2dPreview('gk', value.gk_club_data_url || value.goalkeeper_club_data_url || '');
              setKit2dPreview('gk2', value.gk2_club_data_url || '');
              setKit2dPreview('gk3', value.gk3_club_data_url || '');
            })
            .catch(function () {});
        }

        function saveKit2dUpload() {
          if (!hasPreparedKit2d() || !kit2dSave) return;
          kit2dSave.disabled = true;
          setKit2dStatus('Guardando kits 2D...', false);
          fetch('/api/workspace/preferences/set/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken()
            },
            body: JSON.stringify({
              key: 'kit2d.tokens',
              value: buildKit2dPreferenceValue()
            })
          })
            .then(function (response) {
              return response.json().catch(function () { return null; }).then(function (data) {
                if (!response.ok) {
                  var message = data && (data.error || data.message || data.detail);
                  throw new Error(message || ('HTTP ' + response.status));
                }
                return data;
              });
            })
            .then(function (data) {
              if (!data || data.ok === false) throw new Error(data && data.error ? data.error : 'save_failed');
              kit2dExistingValue = buildKit2dPreferenceValue();
              kit2dPrepared = {};
              setKit2dStatus('Kits 2D guardados. En la pizarra, tareas y 11 inicial se usará la camiseta correspondiente.', false);
            })
            .catch(function (error) {
              var message = error && error.message ? error.message : 'No se pudo guardar el kit 2D. Vuelve a intentarlo.';
              setKit2dStatus(message, true);
              kit2dSave.disabled = false;
            });
        }

        function updateSystemPreview() {
          if (!systemPreview || !systemPanel || !systemButton) return;
          var bg = valueOf(colorFields.bg, '#08111d');
          var text = valueOf(colorFields.text, '#f5f7fa');
          var line = valueOf(colorFields.line, '#90a1b9');
          var panel = valueOf(colorFields.panel, '#0e1727');
          var buttonBg = valueOf(colorFields.buttonBg, '#0f172a');
          var buttonText = valueOf(colorFields.buttonText, '#f5f7fa');
          var shadow = previewShadow(valueOf(colorFields.shadow, 'medium'));
          var mode = valueOf(colorFields.imageMode, 'home');
          var font = previewFont(valueOf(colorFields.font, 'plex'));
          var fontWeight = previewWeight(valueOf(colorFields.fontWeight, 'medium'));
          var fontStyle = valueOf(colorFields.fontStyle, 'normal') === 'italic' ? 'italic' : 'normal';
          var fontDecoration = valueOf(colorFields.fontDecoration, 'none') === 'underline' ? 'underline' : 'none';
          var fontSize = previewSize(valueOf(colorFields.fontSize, 'normal'));
          systemPreview.style.background = bg;
          systemPreview.style.color = text;
          systemPreview.style.fontFamily = font;
          systemPreview.style.fontWeight = fontWeight;
          systemPreview.style.fontStyle = fontStyle;
          systemPreview.style.textDecoration = fontDecoration;
          systemPreview.style.fontSize = fontSize;
          if ((mode === 'system' || mode === 'both') && currentCoverUrl) {
            systemPreview.style.backgroundImage = "linear-gradient(180deg, rgba(5,11,20,0.68), rgba(5,11,20,0.86)), url('" + currentCoverUrl + "')";
            systemPreview.style.backgroundSize = 'cover';
            systemPreview.style.backgroundPosition = 'center';
          } else {
            systemPreview.style.backgroundImage = '';
          }
          systemPanel.style.borderColor = line;
          systemPanel.style.background = panel;
          systemPanel.style.boxShadow = shadow;
          systemButton.style.borderColor = line;
          systemButton.style.background = buttonBg;
          systemButton.style.color = buttonText;
        }

        Object.keys(colorFields).forEach(function (key) {
          var field = colorFields[key];
          if (!field) return;
          field.addEventListener('input', updateSystemPreview);
          field.addEventListener('change', updateSystemPreview);
        });
        updateSystemPreview();

        if (coverInput && pageCover) {
          coverInput.addEventListener('change', function () {
            var url = firstImageUrl(coverInput);
            if (!url) return;
            currentCoverUrl = url;
            pageCover.style.setProperty('--preview-cover', "url('" + url + "')");
            if (inlineCover) {
              inlineCover.src = url;
            } else if (inlineEmpty) {
              inlineEmpty.style.background = "url('" + url + "') center/cover no-repeat";
              inlineEmpty.textContent = '';
            }
            updateSystemPreview();
          });
        }

        if (crestInput) {
          crestInput.addEventListener('change', function () {
            var url = firstImageUrl(crestInput);
            if (!url) return;
            if (pageCrest) {
              pageCrest.src = url;
            } else if (pageCrestEmpty) {
              var img = document.createElement('img');
              img.className = 'page-preview-crest';
              img.id = 'page-crest-preview';
              img.alt = 'Escudo';
              img.src = url;
              pageCrestEmpty.replaceWith(img);
              pageCrest = img;
            }
          });
        }

        if (kit2dFileInputs.length) {
          kit2dFileInputs.forEach(function (input) {
            input.addEventListener('change', function () {
              prepareKit2dUpload(input.files && input.files[0], input.dataset.kit2dSlot);
            });
          });
          loadExistingKit2dPreference();
        }

        if (kit2dSave) {
          kit2dSave.addEventListener('click', saveKit2dUpload);
        }

        if (kit2dGkGenerateButtons.length) {
          kit2dGkGenerateButtons.forEach(function (button) {
            button.addEventListener('click', function () {
              generateGoalkeeperKitFromSource(button.dataset.kit2dGkTarget, button.dataset.kit2dGkSource);
            });
          });
        }

        if (kit2dTemplateButtons.length) {
          kit2dTemplateButtons.forEach(function (button) {
            button.addEventListener('click', function () {
              generateTemplateKit(button.dataset.kit2dTemplateSlot);
            });
          });
        }

        window.addEventListener('pagehide', function () {
          objectUrls.forEach(function (url) {
            try { URL.revokeObjectURL(url); } catch (e) {}
          });
        });
      }());
