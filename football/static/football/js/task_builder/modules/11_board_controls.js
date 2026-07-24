var cfg = window.__TASK_BUILDER_CONFIG || {};
      (function () {
        const boot = () => {
          const sideTabs = Array.from(document.querySelectorAll('#task-board-side-tabs .editor-side-tab'));
          const editPane = document.getElementById('task-side-pane-edit');
          const resourcesPane = document.getElementById('task-side-pane-resources');
          const commandBar = document.getElementById('task-command-bar');
          const selectionToolbar = document.getElementById('task-selection-toolbar');
          const selectionDock = document.getElementById('task-selection-dock');
          const commandSlot = document.getElementById('task-side-command-slot');
          const selectionSlot = document.getElementById('task-side-selection-slot');
          const selectionEmpty = document.getElementById('task-selection-empty');
          const selectionDockClose = document.getElementById('task-selection-dock-close');
          const guideButtons = Array.from(document.querySelectorAll('[data-guide-action]'));
          const presetButtons = Array.from(document.querySelectorAll('[data-guided-preset]'));
          const resourceTabs = Array.from(document.querySelectorAll('.resource-tab'));
          const materialFamilyButtons = Array.from(document.querySelectorAll('[data-material-family-toggle]'));
          const materialFamilyPanels = Array.from(document.querySelectorAll('[data-material-family]'));
          const materialEmptyState = document.getElementById('task-material-empty-state');
          const resourceEmptyState = document.getElementById('task-resource-empty-state');
          const topResourceButtons = Array.from(document.querySelectorAll('[data-top-resource]'));
          const laneTemplateButtons = Array.from(document.querySelectorAll('[data-lane-template]'));
          const commandMoreBtn = document.getElementById('task-command-more');
          const commandMenu = document.getElementById('task-command-menu');
          const workflowButtons = Array.from(document.querySelectorAll('[data-workflow-action]'));
          const kindButtons = Array.from(document.querySelectorAll('[data-task-kind]'));
          const presetSelect = document.getElementById('draw-task-preset');
          const surfaceTrigger = document.getElementById('surface-trigger');
          const playerBank = document.getElementById('task-player-bank');
          const quickDrawBtn = document.querySelector('#task-command-bar [data-action="draw_free"]');
          const resourcesToggle = document.getElementById('task-board-resources-toggle');
          const rosterToggle = document.getElementById('task-board-roster-toggle');
          const quickAddStep = document.getElementById('task-step-add-quick');
          const quickDuplicateStep = document.getElementById('task-step-duplicate-quick');
          const quickRemoveStep = document.getElementById('task-step-remove-quick');
          const quickPlayStep = document.getElementById('task-step-play-quick');
          const timelineDock = document.getElementById('task-timeline-dock');
          const timelineClose = document.getElementById('task-timeline-close');
          const scenariosBtn = document.getElementById('task-scenarios-btn');
          const baseAddStep = document.getElementById('task-step-add');
          const baseDuplicateStep = document.getElementById('task-step-duplicate');
          const baseRemoveStep = document.getElementById('task-step-remove');
          const basePlayStep = document.getElementById('task-step-play');
          const stepListQuick = document.getElementById('task-timeline-list-quick');
          const pitch3dOpenBtn = document.getElementById('pitch-3d-open-standard');
          const exportModeBtn = document.querySelector('#task-mode-tabs [data-task-mode="export"]');
          const boardModeBtn = document.querySelector('#task-mode-tabs [data-task-mode="board"]');
          if (!resourcesPane) return;

          if (commandBar && commandSlot && commandBar.parentElement !== commandSlot) {
            try { commandSlot.appendChild(commandBar); } catch (e) { /* ignore */ }
          }
          if (selectionToolbar && selectionSlot && selectionToolbar.parentElement !== selectionSlot) {
            try { selectionSlot.appendChild(selectionToolbar); } catch (e) { /* ignore */ }
          }

          const syncSelectionState = () => {
            if (!selectionSlot || !selectionToolbar) return;
            const hasSelection = selectionToolbar.hidden === false;
            selectionSlot.classList.toggle('has-selection', hasSelection);
            document.body.classList.toggle('task-board-has-selection', hasSelection);
            if (selectionDock) selectionDock.hidden = !hasSelection;
            if (selectionEmpty) selectionEmpty.hidden = hasSelection;
            if (hasSelection) {
              activate('edit');
              document.body.classList.remove('task-board-resources-open');
              document.body.classList.add('task-board-inspector-open');
              syncBoardDrawerButtons();
            }
          };

          const syncBoardDrawerButtons = () => {
            const resourcesOpen = document.body.classList.contains('task-board-resources-open');
            const inspectorOpen = document.body.classList.contains('task-board-inspector-open');
            const rosterOpen = resourcesOpen && !document.body.classList.contains('task-board-roster-collapsed');
            resourcesToggle?.classList.toggle('is-active', resourcesOpen);
            rosterToggle?.classList.toggle('is-active', rosterOpen);
            resourcesToggle?.setAttribute('aria-pressed', resourcesOpen ? 'true' : 'false');
            rosterToggle?.setAttribute('aria-pressed', rosterOpen ? 'true' : 'false');
          };

          const syncWorkflowUi = (key) => {
            const next = String(key || 'build').trim();
            workflowButtons.forEach((btn) => btn.classList.toggle('is-active', String(btn.dataset.workflowAction || '') === next));
          };

          const syncKindUi = (key) => {
            const next = String(key || '2d').trim();
            kindButtons.forEach((btn) => btn.classList.toggle('is-active', String(btn.dataset.taskKind || '') === next));
            document.body.classList.remove('task-editor-kind-2d', 'task-editor-kind-interactive', 'task-editor-kind-3d');
            document.body.classList.add(`task-editor-kind-${next}`);
            try {
              if (typeof window.__tpadApplyRecommendedTokenStyle === 'function') {
                window.__tpadApplyRecommendedTokenStyle(next);
              }
            } catch (e) { /* ignore */ }
          };

          const resourceLabelMap = {
            base: 'Jugadores',
            pro: 'Material',
            trazos: 'Flechas',
            figuras: 'Zonas',
            emoji: 'Emoji',
            importados: 'Extras',
            plantilla: 'Jugadores',
          };
          let activeMaterialFamily = '';

          const updateMaterialFamilyLayout = () => {
            materialFamilyPanels.forEach((panel) => {
              if (!panel) return;
              const strip = panel.querySelector('.resource-strip, .pdf-assets-strip');
              if (!strip) return;
              panel.dataset.materialColumns = '2';
              panel.dataset.materialDensity = 'regular';
              strip.style.maxHeight = '';
              strip.style.height = '';
              const host = resourcesPane || panel.closest('.editor-side-pane') || panel.closest('.pitch-side') || panel.closest('.resource-panel');
              const hostRect = host?.getBoundingClientRect?.();
              const stripRect = strip.getBoundingClientRect();
              let availableHeight = 0;
              if (hostRect && stripRect) {
                availableHeight = Math.floor(hostRect.bottom - stripRect.top - 14);
              }
              availableHeight = Math.max(140, availableHeight || 0);
              const resourceCount = strip.querySelectorAll('button').length;
              const compactDensity = availableHeight < 250;
              panel.dataset.materialDensity = compactDensity ? 'compact' : 'regular';
              if (availableHeight) {
                strip.style.maxHeight = `${availableHeight}px`;
                strip.style.height = resourceCount ? `${availableHeight}px` : 'auto';
              }
              const estimatedItemHeight = compactDensity ? 56 : 68;
              const rowsAvailable = Math.max(1, Math.floor((availableHeight + 6) / estimatedItemHeight));
              const requiredColumns = resourceCount ? Math.ceil(resourceCount / rowsAvailable) : 2;
              panel.dataset.materialColumns = String(Math.max(2, Math.min(4, requiredColumns)));
            });
          };

          const activateMaterialFamily = (family, options = {}) => {
            const next = String(family || '').trim();
            const available = next && materialFamilyPanels.some((panel) => String(panel.dataset.materialFamily || '').trim() === next);
            const resolved = available ? next : '';
            activeMaterialFamily = resolved;
            materialFamilyButtons.forEach((button) => {
              const isActive = String(button.dataset.materialFamilyToggle || '').trim() === resolved;
              button.classList.toggle('is-active', isActive);
              button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
            });
            materialFamilyPanels.forEach((panel) => {
              const visible = String(panel.dataset.materialFamily || '').trim() === resolved;
              panel.hidden = !visible;
              panel.classList.toggle('is-visible', visible);
            });
            if (materialEmptyState) materialEmptyState.hidden = !!resolved;
            try { window.requestAnimationFrame(updateMaterialFamilyLayout); } catch (e) { updateMaterialFamilyLayout(); }
            if (!options.silent) {
              try {
                window.dispatchEvent(new CustomEvent('webstats:tpad:material-family-ui-change', {
                  detail: { family: resolved },
                }));
              } catch (e) { /* ignore */ }
            }
          };

          const syncTopResourceButtons = (key) => {
            const next = String(key || 'base').trim();
            topResourceButtons.forEach((btn) => btn.classList.toggle('is-active', String(btn.dataset.topResource || '').trim() === next));
            const summary = document.getElementById('task-resource-summary-label');
            if (summary) summary.textContent = resourceLabelMap[next] || 'Selecciona…';
            if (resourceEmptyState) resourceEmptyState.hidden = !!next;
          };

          const activate = (pane) => {
            const next = String(pane || 'edit').trim().toLowerCase() === 'resources' ? 'resources' : 'edit';
            sideTabs.forEach((tab) => tab.classList.toggle('is-active', String(tab.dataset.sidePane || '') === next));
            const sideTabsWrap = document.getElementById('task-board-side-tabs');
            if (sideTabsWrap) sideTabsWrap.hidden = false;
            if (editPane) editPane.hidden = next !== 'edit';
            if (resourcesPane) resourcesPane.hidden = next !== 'resources';
          };

          const closeCommandMenu = () => {
            if (!commandMenu) return;
            commandMenu.hidden = true;
            commandMenu.classList.remove('opens-up');
            commandMoreBtn?.setAttribute('aria-expanded', 'false');
          };

          const openCommandMenu = () => {
            if (!commandMenu) return;
            commandMenu.hidden = false;
            commandMoreBtn?.setAttribute('aria-expanded', 'true');
            try {
              window.requestAnimationFrame(() => {
                if (commandMenu.hidden) return;
                const rect = commandMenu.getBoundingClientRect();
                const overflowsBottom = rect.bottom > (window.innerHeight - 8);
                commandMenu.classList.toggle('opens-up', overflowsBottom && rect.top > 8);
              });
            } catch (e) { /* ignore */ }
          };

          const openBoardDrawer = (pane) => {
            const next = String(pane || 'edit').trim().toLowerCase() === 'resources' ? 'resources' : 'edit';
            closeCommandMenu();
            activate(next);
            document.body.classList.toggle('task-board-resources-open', next === 'resources');
            document.body.classList.toggle('task-board-inspector-open', next === 'edit');
            syncBoardDrawerButtons();
          };

          const closeBoardDrawers = () => {
            const sideTabsWrap = document.getElementById('task-board-side-tabs');
            closeCommandMenu();
            document.body.classList.remove('task-board-resources-open', 'task-board-inspector-open');
            if (sideTabsWrap) sideTabsWrap.hidden = true;
            if (editPane) editPane.hidden = true;
            if (resourcesPane) resourcesPane.hidden = true;
            syncBoardDrawerButtons();
          };

          const activateResourceTab = (key) => {
            const match = resourceTabs.find((tab) => String(tab.dataset.resource || '').trim() === String(key || '').trim());
            if (match) {
              try { match.click(); } catch (e) { /* ignore */ }
            }
          };

          const proxyClick = (source) => {
            if (!source) return;
            try { source.click(); } catch (e) { /* ignore */ }
          };

          const openTimelineDock = () => {
            if (!timelineDock) return;
            timelineDock.hidden = false;
            timelineDock.setAttribute('aria-hidden', 'false');
            document.body.classList.add('task-sequence-open');
          };

          const closeTimelineDock = () => {
            if (!timelineDock) return;
            document.body.classList.remove('task-sequence-open');
            timelineDock.setAttribute('aria-hidden', 'true');
            window.setTimeout(() => {
              if (!document.body.classList.contains('task-sequence-open')) timelineDock.hidden = true;
            }, 180);
          };

          const toggleTimelineDock = () => {
            if (!timelineDock) return;
            if (document.body.classList.contains('task-sequence-open')) closeTimelineDock();
            else openTimelineDock();
          };

          sideTabs.forEach((tab) => {
            tab.addEventListener('click', (event) => {
              try { event.preventDefault(); } catch (e) { /* ignore */ }
              openBoardDrawer(tab.dataset.sidePane || 'edit');
            });
          });

          resourceTabs.forEach((tab) => {
            tab.addEventListener('click', () => {
              syncTopResourceButtons(String(tab.dataset.resource || '').trim());
            });
          });
          window.addEventListener('webstats:tpad:resource-panel-change', (event) => {
            const key = String(event?.detail?.key || '').trim();
            if (key) syncTopResourceButtons(key);
            if (key === 'pro') activateMaterialFamily(activeMaterialFamily, { silent: true });
            else activateMaterialFamily('', { silent: true });
          });
          window.addEventListener('webstats:tpad:material-family-change', (event) => {
            const family = String(event?.detail?.family || '').trim();
            if (family) activateMaterialFamily(family, { silent: true });
          });
          materialFamilyButtons.forEach((button) => {
            button.addEventListener('click', (event) => {
              try { event.preventDefault(); } catch (e) { /* ignore */ }
              const family = String(button.dataset.materialFamilyToggle || '').trim();
              if (!family) return;
              activateMaterialFamily(family);
            });
          });

          topResourceButtons.forEach((button) => {
            button.addEventListener('click', (event) => {
              try { event.preventDefault(); } catch (e) { /* ignore */ }
              const key = String(button.dataset.topResource || '').trim();
              if (!key) return;
              openBoardDrawer('resources');
              activateResourceTab(key);
              syncTopResourceButtons(key);
            });
          });

          laneTemplateButtons.forEach((button) => {
            button.addEventListener('click', (event) => {
              try { event.preventDefault(); } catch (e) { /* ignore */ }
              const kind = String(button.dataset.laneTemplate || '').trim();
              if (!kind) return;
              const item = { payload: { kind }, x: 0.5, y: 0.5 };
              if (kind === 'shape_lane_3') {
                item.scaleX = 5.1;
                item.scaleY = 12.0;
              } else if (kind === 'shape_lane_5') {
                item.scaleX = 5.1;
                item.scaleY = 12.0;
              } else if (kind === 'shape_grid_120') {
                item.scaleX = 4.1;
                item.scaleY = 4.0;
              }
              try {
                window.dispatchEvent(new CustomEvent('webstats:tpad:assistant-board', {
                  detail: { clear: false, items: [item] },
                }));
              } catch (e) { /* ignore */ }
            });
          });

          commandMoreBtn?.addEventListener('click', (event) => {
            try { event.preventDefault(); event.stopPropagation(); } catch (e) { /* ignore */ }
            if (!commandMenu) return;
            if (commandMenu.hidden) openCommandMenu();
            else closeCommandMenu();
          });
          commandMenu?.addEventListener('click', (event) => {
            try { event.stopPropagation(); } catch (e) { /* ignore */ }
          });

          resourcesToggle?.addEventListener('click', (event) => {
            try { event.preventDefault(); } catch (e) { /* ignore */ }
            openBoardDrawer('resources');
            activateResourceTab('');
            syncTopResourceButtons('');
            activateMaterialFamily('', { silent: true });
          });
          selectionDockClose?.addEventListener('click', (event) => {
            try { event.preventDefault(); } catch (e) { /* ignore */ }
            closeBoardDrawers();
          });
          rosterToggle?.addEventListener('click', (event) => {
            try { event.preventDefault(); } catch (e) { /* ignore */ }
            document.body.classList.remove('task-board-roster-collapsed');
            openBoardDrawer('resources');
            activateResourceTab('plantilla');
            syncTopResourceButtons('plantilla');
            syncBoardDrawerButtons();
          });
          document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
              closeBoardDrawers();
              closeTimelineDock();
              closeCommandMenu();
            }
          });

          quickAddStep?.addEventListener('click', () => {
            openTimelineDock();
            proxyClick(baseAddStep);
          });
          quickDuplicateStep?.addEventListener('click', () => proxyClick(baseDuplicateStep));
          quickRemoveStep?.addEventListener('click', () => proxyClick(baseRemoveStep));
          quickPlayStep?.addEventListener('click', () => proxyClick(basePlayStep));
          timelineClose?.addEventListener('click', (event) => {
            try { event.preventDefault(); } catch (e) { /* ignore */ }
            closeTimelineDock();
          });
          scenariosBtn?.addEventListener('click', (event) => {
            try { event.preventDefault(); } catch (e) { /* ignore */ }
            toggleTimelineDock();
          });
          timelineDock?.addEventListener('click', (event) => {
            try { event.stopPropagation(); } catch (e) { /* ignore */ }
          });
          document.addEventListener('click', (event) => {
            if (!timelineDock || timelineDock.hidden) return;
            if (!document.body.classList.contains('task-sequence-open')) return;
            const target = event.target;
            if (!(target instanceof Element)) return;
            if (timelineDock.contains(target)) return;
            if (scenariosBtn && (target === scenariosBtn || scenariosBtn.contains(target))) return;
            closeTimelineDock();
          });
          document.addEventListener('click', (event) => {
            if (!commandMenu || commandMenu.hidden) return;
            const target = event.target;
            if (!(target instanceof Element)) return;
            if (commandMenu.contains(target)) return;
            if (commandMoreBtn && (target === commandMoreBtn || commandMoreBtn.contains(target))) return;
            closeCommandMenu();
          });

          workflowButtons.forEach((btn) => {
            btn.addEventListener('click', () => {
              const action = String(btn.dataset.workflowAction || '').trim();
              if (action === 'build') {
                proxyClick(boardModeBtn);
                openBoardDrawer('resources');
                activateResourceTab('');
                syncTopResourceButtons('');
                syncWorkflowUi('build');
                syncKindUi('2d');
                return;
              }
              if (action === 'animate') {
                proxyClick(boardModeBtn);
                closeBoardDrawers();
                openTimelineDock();
                if (stepListQuick && !stepListQuick.children.length) proxyClick(baseAddStep);
                try { stepListQuick?.scrollIntoView({ block: 'nearest', inline: 'start' }); } catch (e) { /* ignore */ }
                syncWorkflowUi('animate');
                syncKindUi('interactive');
                return;
              }
              if (action === 'present3d') {
                proxyClick(boardModeBtn);
                proxyClick(pitch3dOpenBtn);
                syncWorkflowUi('present3d');
                syncKindUi('3d');
                return;
              }
              if (action === 'export') {
                proxyClick(exportModeBtn);
                syncWorkflowUi('export');
              }
            });
          });

          kindButtons.forEach((btn) => {
            btn.addEventListener('click', () => {
              const kind = String(btn.dataset.taskKind || '').trim();
              syncKindUi(kind || '2d');
              if (kind === 'interactive') {
                openTimelineDock();
                document.body.classList.remove('task-board-resources-open');
                document.body.classList.add('task-board-inspector-open');
                syncBoardDrawerButtons();
                return;
              }
              if (kind === '3d') {
                closeTimelineDock();
                closeBoardDrawers();
                proxyClick(pitch3dOpenBtn);
                return;
              }
              closeTimelineDock();
              // El modo 2D usa el campo cenital plano (fotorrealista, sin gradas).
              // Reutilizamos el handler del selector de césped para redibujar la superficie.
              try {
                const grassSel = document.getElementById('pitch-grass-select');
                if (grassSel && String(grassSel.value || '') !== 'flat_2d') {
                  grassSel.value = 'flat_2d';
                  grassSel.dispatchEvent(new Event('change', { bubbles: true }));
                }
              } catch (e) { /* ignore */ }
              openBoardDrawer('resources');
              activateResourceTab('');
              syncTopResourceButtons('');
            });
          });

          guideButtons.forEach((button) => {
            button.addEventListener('click', (event) => {
              try { event.preventDefault(); } catch (e) { /* ignore */ }
              const action = String(button.dataset.guideAction || '').trim();
              if (action === 'surface') {
                try { surfaceTrigger?.click(); } catch (e) { /* ignore */ }
                return;
              }
              if (action === 'resources') {
                openBoardDrawer('resources');
                activateResourceTab('base');
                return;
              }
              if (action === 'players') {
                openBoardDrawer('resources');
                activateResourceTab('base');
                return;
              }
              if (action === 'draw') {
                openBoardDrawer('edit');
                try { quickDrawBtn?.click(); } catch (e) { /* ignore */ }
                return;
              }
            });
          });

          presetButtons.forEach((button) => {
            button.addEventListener('click', (event) => {
              try { event.preventDefault(); } catch (e) { /* ignore */ }
              const preset = String(button.dataset.guidedPreset || '').trim();
              const resource = String(button.dataset.guidedResource || '').trim();
              if (presetSelect && preset) {
                try {
                  if (typeof window.__webstatsTaskBuilderSetPreset === 'function') {
                    window.__webstatsTaskBuilderSetPreset(preset);
                  } else {
                    presetSelect.value = preset;
                    presetSelect.dispatchEvent(new Event('change', { bubbles: true }));
                  }
                } catch (e) { /* ignore */ }
              }
              const template = String(button.dataset.guidedTemplate || '').trim();
              if (template && typeof window.__webstatsTaskBuilderApplyLocalTemplate === 'function') {
                try { window.__webstatsTaskBuilderApplyLocalTemplate(template); } catch (e) { /* ignore */ }
              }
              openBoardDrawer('resources');
              if (resource) activateResourceTab(resource);
            });
          });

          syncSelectionState();
          document.body.classList.remove('task-board-roster-collapsed');
          syncWorkflowUi('build');
          syncKindUi('2d');
          activateMaterialFamily('', { silent: true });
          try {
            window.addEventListener('resize', updateMaterialFamilyLayout, { passive: true });
          } catch (e) { /* ignore */ }
          try {
            const resizeObserver = new ResizeObserver(() => updateMaterialFamilyLayout());
            if (resourcesPane) resizeObserver.observe(resourcesPane);
          } catch (e) { /* ignore */ }
          try { window.requestAnimationFrame(updateMaterialFamilyLayout); } catch (e) { updateMaterialFamilyLayout(); }
          try {
            const observer = new MutationObserver(syncSelectionState);
            observer.observe(selectionToolbar, { attributes: true, attributeFilter: ['hidden'] });
          } catch (e) { /* ignore */ }

          if (window.matchMedia('(max-width: 980px)').matches) {
            activate('edit');
          }
          openBoardDrawer('resources');
          syncTopResourceButtons('plantilla');
        };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
        else boot();
      })();
