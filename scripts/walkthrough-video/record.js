// Records the walkthrough: drives the real site, captures frames over CDP, logs step timings.
// Usage: node record.js <outDir> [--dry]   (--dry: no audio wait, screenshot per step for checking)
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { speak } = require('./speak');

const OUT = path.resolve(process.argv[2] || 'out');
const DRY = process.argv.includes('--dry');
const BASE = 'http://localhost:5173';
fs.mkdirSync(path.join(OUT, 'frames'), { recursive: true });
fs.mkdirSync(path.join(OUT, 'audio'), { recursive: true });
fs.mkdirSync(path.join(OUT, 'shots'), { recursive: true });

function tts(i, text) {
  const wav = path.join(OUT, 'audio', `s${String(i).padStart(3, '0')}.wav`);
  if (!fs.existsSync(wav)) execFileSync('RHVoice-test', ['-p', 'alan', '-r', '100', '-o', wav], { input: speak(text) });
  const dur = parseFloat(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', wav]).toString());
  return { wav, dur };
}

(async () => {
  const browser = await chromium.launch({ args: ['--lang=en-GB'], env: { ...process.env, LANG: 'en_GB.UTF-8', LANGUAGE: 'en_GB' } });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 4 / 3, locale: 'en-GB', timezoneId: 'Europe/London' });
  await context.addInitScript({ path: path.join(__dirname, 'overlay.js') });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // ── frame capture
  const frames = [];
  let cdp;
  if (!DRY) {
    cdp = await context.newCDPSession(page);
    cdp.on('Page.screencastFrame', async (f) => {
      const n = frames.length;
      const file = path.join(OUT, 'frames', `f${String(n).padStart(6, '0')}.jpg`);
      fs.writeFileSync(file, Buffer.from(f.data, 'base64'));
      frames.push({ file, t: f.metadata.timestamp });
      try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch {}
    });
  }

  const h = {
    page,
    wait: (ms) => sleep(DRY ? Math.min(ms, 300) : ms),
    goto: async (p) => { await page.goto(BASE + p); await page.waitForLoadState('networkidle'); await sleep(400); },
    card: (html) => page.evaluate((x) => window.__jv.card(x), html),
    cardStep: (i) => page.evaluate((x) => window.__jv.cardStep(x), i),
    clear: () => page.evaluate(() => window.__jv && window.__jv.clear()),
    top: async () => { await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' })); await sleep(900); },
    scroll: async (spec, block = 'center') => {
      const ok = await page.evaluate(([s, b]) => window.__jv.scrollTo(s, b), [spec, block]);
      if (!ok) throw new Error('scroll target not found: ' + JSON.stringify(spec));
      await sleep(1000);
    },
    scrollLoc: async (loc) => {
      await loc.evaluate((el) => { const r = el.getBoundingClientRect(); window.scrollTo({ top: r.top + scrollY - 600, behavior: 'smooth' }); });
      await sleep(1000);
    },
    moveTo: async (loc) => {
      const b = await loc.boundingBox();
      if (b) await page.mouse.move(b.x + Math.min(b.width / 2, 120), b.y + b.height / 2, { steps: 18 });
    },
    click: async (loc) => {
      await loc.scrollIntoViewIfNeeded();
      await h.moveTo(loc);
      await sleep(250);
      await loc.click();
      await sleep(350);
    },
    show: async (specs, label, opts = {}) => {
      const list = Array.isArray(specs) ? specs : [specs];
      if (!opts.noScroll) await h.scroll(list[0], opts.block || 'center');
      const n = await page.evaluate(([s, l, o]) => window.__jv.highlight(s, l, o), [list, label, opts]);
      if (n !== list.length) throw new Error(`highlight found ${n}/${list.length}: ${JSON.stringify(specs)}`);
      // point the cursor at the first highlighted element
      const r = await page.evaluate((s) => window.__jv.rect(s), list[0]);
      if (r) {
        const x = r.vx > 60 ? r.vx - 22 : Math.min(r.vx + r.vw + 18, 1420), y = Math.max(70, Math.min(r.vy + Math.min(r.vh / 2, 28), 820));
        await page.mouse.move(x, y, { steps: 16 });
      }
    },
  };

  const steps = require('./steps')(h);
  // Pre-generate speech so durations are known.
  const clips = steps.map((s, i) => tts(i, s.say));
  console.log('speech total', clips.reduce((a, c) => a + c.dur, 0).toFixed(1), 's over', steps.length, 'steps');

  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  if (!DRY) await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 88, maxWidth: 1920, maxHeight: 1200, everyNthFrame: 1 });
  await sleep(500);
  const t0 = Date.now() / 1000;
  const log = [];
  let chapter = '';
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (s.ch) chapter = s.ch;
    const start = Date.now() / 1000;
    const capText = s.noCap ? '' : s.say;
    await page.evaluate(([c, t]) => { window.__jv.install(); window.__jv.caption(c, t); }, [chapter, capText]);
    const audioDone = sleep(DRY ? 0 : clips[i].dur * 1000 + 450);
    try {
      if (s.do) await s.do();
      // captions must survive navigations
      await page.evaluate(([c, t]) => { window.__jv.install(); window.__jv.caption(c, t); }, [chapter, capText]);
    } catch (e) {
      console.error(`STEP ${i} FAILED (${chapter}): ${e.message}`);
      await page.screenshot({ path: path.join(OUT, 'shots', `FAIL-${i}.png`) });
      if (DRY) continue; else throw e;
    }
    await audioDone;
    if (s.tail && !DRY) await sleep(s.tail);
    if (DRY) await page.screenshot({ path: path.join(OUT, 'shots', `s${String(i).padStart(3, '0')}.png`) });
    log.push({ i, chapter, isChapterStart: !!s.ch, start: start - t0, wavStart: start - t0, dur: clips[i].dur, wav: clips[i].wav, say: s.say });
    process.stdout.write(`${i} `);
  }
  const tEnd = Date.now() / 1000;
  if (!DRY) { await cdp.send('Page.stopScreencast'); await sleep(500); }
  fs.writeFileSync(path.join(OUT, 'timeline.json'), JSON.stringify({ t0, tEnd, steps: log, frames }, null, 1));
  console.log('\ndone; duration', (tEnd - t0).toFixed(1), 's; frames', frames.length);
  await browser.close();
})();
