'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.argv[2] || 'playwright-core');

const root = path.resolve(__dirname, '..');
const output = path.join(root, 'output', 'web');
const errors = [];

async function settle(page) {
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function seek(page, time) {
  await page.locator('#timeline').evaluate((input, value) => {
    input.value = String(value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }, time);
  await settle(page);
}

async function isPlaying(page) {
  return await page.locator('#playText').textContent() === '暂停';
}

async function pause(page) {
  if (await isPlaying(page)) await page.locator('#playPause').click();
  await settle(page);
}

async function main() {
  await fs.mkdir(output, { recursive: true });
  process.chdir(output);
  const browser = await chromium.launch({ headless: true, ...(process.argv[3] ? { executablePath: process.argv[3] } : {}) });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1060 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('requestfailed', (request) => errors.push(`${request.url()}: ${request.failure()?.errorText}`));
    await page.goto(pathToFileURL(path.join(root, 'web', 'index.html')).href);
    await page.waitForSelector('body[data-ready="true"]');
    assert.equal(await page.locator('#loadingCover').isVisible(), false);
    assert.equal(await isPlaying(page), false);

    await page.locator('#playPause').click();
    await page.waitForFunction(() => Number(document.querySelector('#stage').dataset.time) > 0.12);
    await pause(page);
    const stoppedAt = Number(await page.locator('#stage').getAttribute('data-time'));
    await page.waitForTimeout(130);
    assert.equal(Number(await page.locator('#stage').getAttribute('data-time')), stoppedAt, 'Pause must stop the clock.');

    await seek(page, 9);
    assert.equal(await page.locator('#stage').getAttribute('data-phase'), '2');
    await page.locator('[data-harmonics="4"]').click();
    await settle(page);
    assert.equal(await page.locator('#stage').getAttribute('data-harmonics'), '4');
    const simple = await page.locator('#stage').screenshot();
    await page.locator('[data-harmonics="750"]').click();
    await settle(page);
    const detailed = await page.locator('#stage').screenshot();
    assert.notDeepEqual(simple, detailed, 'Harmonic controls must change the rendered animation.');

    await page.locator('#showWheels').uncheck();
    await settle(page);
    const noWheels = await page.locator('#stage').screenshot();
    assert.notDeepEqual(detailed, noWheels, 'Wheel switch must change the canvas.');
    await page.locator('#showWheels').check();
    await page.locator('#showTrace').uncheck();
    await settle(page);
    assert.notDeepEqual(detailed, await page.locator('#stage').screenshot(), 'Trace switch must change the canvas.');
    await page.locator('#showTrace').check();
    await page.locator('#followCamera').uncheck();
    await settle(page);
    assert.notDeepEqual(detailed, await page.locator('#stage').screenshot(), 'Camera switch must change the canvas.');
    await page.locator('#followCamera').check();

    for (const [time, phase] of [[0, '1'], [8, '2'], [18, '3'], [23, '4']]) {
      await seek(page, time);
      assert.equal(await page.locator('#stage').getAttribute('data-phase'), phase);
    }
    await page.locator('[data-speed="2"]').click();
    assert.equal(await page.locator('#speedValue').textContent(), '2×');
    assert.equal(await page.locator('#soundtrack').evaluate((audio) => audio.playbackRate), 2);
    await page.locator('[data-speed="1"]').click();

    await page.locator('#laugh').click();
    await page.waitForFunction(() => Number(document.querySelector('#stage').dataset.time) > 20.45);
    assert.equal(await page.locator('#stage').getAttribute('data-phase'), '4');
    assert.equal(await page.locator('#sound').getAttribute('aria-pressed'), 'true');
    const sound = await page.locator('#soundtrack').evaluate((audio) => ({ paused: audio.paused, muted: audio.muted, time: audio.currentTime }));
    assert.equal(sound.paused, false, 'Laugh audio must actually play.');
    assert.equal(sound.muted, false);
    assert.ok(Math.abs(sound.time - Number(await page.locator('#stage').getAttribute('data-time'))) < 0.25, 'Audio and canvas clocks must stay aligned.');
    await pause(page);
    await page.locator('#sound').click();
    assert.equal(await page.locator('#sound').getAttribute('aria-pressed'), 'false');

    await seek(page, 18.5);
    await page.locator('#stage').click({ position: { x: 210, y: 400 } });
    await page.waitForFunction(() => Number(document.querySelector('#stage').dataset.time) > 20.45);
    assert.equal(await page.locator('#stage').getAttribute('data-phase'), '4');
    await pause(page);

    await page.locator('#loop').uncheck();
    await seek(page, 28.7);
    await page.locator('#playPause').click();
    await page.waitForFunction(() => document.querySelector('#playText').textContent === '播放' && document.querySelector('#currentTime').textContent === '28.8');
    await page.locator('#loop').check();
    await seek(page, 28.7);
    await page.locator('#playPause').click();
    await page.waitForFunction(() => Number(document.querySelector('#stage').dataset.time) < 1 && document.querySelector('#playText').textContent === '暂停');
    await pause(page);
    await seek(page, 28.8);
    assert.equal(await page.locator('#currentTime').textContent(), '28.8');
    assert.equal(await isPlaying(page), false);

    await seek(page, 18.5);
    await page.waitForFunction(() => getComputedStyle(document.querySelector('#notice')).opacity === '0');
    await page.screenshot({ path: path.join(output, 'preview-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await seek(page, 18.5);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, 'Mobile layout must not overflow horizontally.');
    await page.screenshot({ path: path.join(output, 'preview-mobile.png'), fullPage: true });
    await page.locator('#laugh').click();
    await page.waitForFunction(() => Number(document.querySelector('#stage').dataset.time) > 20.45);
    await pause(page);

    const offline = await browser.newContext({ offline: true, viewport: { width: 1280, height: 900 } });
    const standalone = await offline.newPage();
    standalone.on('pageerror', (error) => errors.push(error.message));
    await standalone.goto(pathToFileURL(path.join(output, 'naiwa_fourier_playground.html')).href);
    await standalone.waitForSelector('body[data-ready="true"]');
    await standalone.locator('#laugh').click();
    await standalone.waitForFunction(() => Number(document.querySelector('#stage').dataset.time) > 20.45);
    await pause(standalone);
    assert.equal(await standalone.locator('#stage').getAttribute('data-phase'), '4');
    assert.deepEqual(errors, [], 'The page must not have uncaught errors or missing resources.');

    const result = { desktop: 'passed', mobile: 'passed', standaloneOffline: 'passed', errors };
    await fs.writeFile(path.join(output, 'browser-test.json'), JSON.stringify(result, null, 2), 'utf8');
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(error.stack + '\n');
  process.exitCode = 1;
});
