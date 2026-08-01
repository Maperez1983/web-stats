const { chromium } = require('playwright');
const path = require('path');
const { pathToFileURL } = require('url');

async function shot(page, htmlName, pngName) {
  const htmlPath = path.resolve(__dirname, '..', 'tmp', htmlName);
  const pngPath = path.resolve(__dirname, '..', 'tmp', pngName);
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'networkidle' });
  await page.screenshot({ path: pngPath, fullPage: true });
  console.log(pngPath);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 2200 }, deviceScaleFactor: 2 });
  await shot(page, 'session_plan_club_sample.html', 'session_plan_club_sample.png');
  await shot(page, 'session_plan_uefa_sample.html', 'session_plan_uefa_sample.png');
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
