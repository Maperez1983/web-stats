const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1800, height: 1200 } });
  await page.goto('http://127.0.0.1:8010/coach/sesiones/tarea/357/editar/', { waitUntil: 'networkidle' });
  await page.click('#task-board-resources-toggle');
  await page.waitForTimeout(1500);
  const info = await page.evaluate(() => {
    const proTab = document.querySelector('.resource-tab[data-resource="pro"]');
    const proPanel = document.querySelector('.resource-panel[data-panel="pro"]');
    const equip = document.querySelector('.task-material-family[data-material-family="equipamiento"]');
    const empty = document.getElementById('task-resource-empty-state');
    const materialEmpty = document.getElementById('task-material-empty-state');
    return {
      proTabActive: !!proTab && proTab.classList.contains('is-active'),
      proPanelHidden: proPanel ? proPanel.hidden : null,
      proPanelVisibleClass: !!proPanel && proPanel.classList.contains('is-visible'),
      equipHidden: equip ? equip.hidden : null,
      resourceEmptyHidden: empty ? empty.hidden : null,
      materialEmptyHidden: materialEmpty ? materialEmpty.hidden : null,
      bodyResourcesOpen: document.body.classList.contains('task-board-resources-open'),
      bodyInspectorOpen: document.body.classList.contains('task-board-inspector-open'),
      resourceSummary: document.getElementById('task-resource-summary-label')?.textContent?.trim() || '',
      visibleButtons: Array.from(document.querySelectorAll('.resource-panel[data-panel="pro"] button'))
        .filter((btn) => {
          const rect = btn.getBoundingClientRect();
          return !btn.hidden && rect.width > 0 && rect.height > 0;
        })
        .slice(0, 20)
        .map((btn) => btn.getAttribute('title') || btn.textContent.trim()),
    };
  });
  console.log(JSON.stringify(info, null, 2));
  await page.screenshot({ path: 'tmp/material_panel_check.png', fullPage: true });
  await browser.close();
})();
