// Injected into every page: subtitles, chapter label, a visible cursor, highlight boxes and title cards.
(() => {
  if (window.__jv) return;
  const css = `
  #jv-cap{position:fixed;left:364px;bottom:44px;width:972px;box-sizing:border-box;
    background:rgba(6,10,8,.94);border:1px solid rgba(52,211,153,.55);border-left:5px solid #34d399;border-radius:8px;
    padding:11px 20px 13px;color:#fff;font:500 19px/1.42 "IBM Plex Sans",Inter,system-ui,sans-serif;z-index:2147483640;
    pointer-events:none;box-shadow:0 10px 40px rgba(0,0,0,.6);transition:opacity .25s}
  #jv-cap .ch{display:block;font:600 12px/1.2 "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:#34d399;margin-bottom:5px}
  #jv-cap.hide{opacity:0}
  #jv-cap.top{bottom:auto;top:70px}
  #jv-cursor{position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;transform:translate(-3px,-2px);transition:none}
  .jv-ripple{position:fixed;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;border:3px solid #fbbf24;z-index:2147483646;pointer-events:none;animation:jvr .6s ease-out forwards}
  @keyframes jvr{from{transform:scale(.3);opacity:1}to{transform:scale(1.4);opacity:0}}
  .jv-hl{position:absolute;border:3px solid #fbbf24;border-radius:10px;box-shadow:0 0 0 4000px rgba(0,0,0,.28),0 0 22px rgba(251,191,36,.65);
    z-index:2147483600;pointer-events:none;animation:jvp 1.6s ease-in-out infinite}
  .jv-hl.multi{box-shadow:0 0 22px rgba(251,191,36,.65)}
  .jv-hl .lbl{position:absolute;left:-3px;top:-30px;background:#fbbf24;color:#111;font:700 13px/1 "IBM Plex Sans",system-ui,sans-serif;padding:6px 9px;border-radius:6px 6px 6px 0;white-space:nowrap}
  .jv-hl .lbl.below{top:auto;bottom:-30px;border-radius:0 6px 6px 6px}
  @keyframes jvp{0%,100%{border-color:#fbbf24}50%{border-color:#fde68a}}
  #jv-card{position:fixed;inset:0;z-index:2147483630;display:flex;align-items:center;justify-content:center;
    background:rgba(4,8,6,.9);backdrop-filter:blur(6px);color:#fff;font-family:"IBM Plex Sans",Inter,system-ui,sans-serif;transition:opacity .4s}
  #jv-card .box{max-width:1000px;padding:40px 54px;border:1px solid rgba(52,211,153,.45);border-radius:14px;background:rgba(10,18,14,.85)}
  #jv-card .kick{font:600 14px "IBM Plex Mono",monospace;letter-spacing:.18em;color:#34d399;text-transform:uppercase}
  #jv-card h1{font-size:46px;margin:12px 0 10px;font-weight:700;line-height:1.15}
  #jv-card h1 .dot{color:#34d399}
  #jv-card p{font-size:21px;color:#cbd5d1;margin:6px 0;line-height:1.5}
  #jv-card ol{margin:16px 0 0;padding-left:0;list-style:none;counter-reset:i}
  #jv-card li{counter-increment:i;font-size:20px;line-height:1.45;margin:9px 0;padding-left:46px;position:relative;color:#e5ebe8;transition:color .3s,opacity .3s}
  #jv-card li::before{content:counter(i);position:absolute;left:0;top:1px;width:30px;height:30px;border-radius:50%;background:#134e3a;color:#6ee7b7;font:700 15px/30px monospace;text-align:center}
  #jv-card li.dim{opacity:.38}
  #jv-card li.on{color:#fff}
  #jv-card li.on::before{background:#fbbf24;color:#111}
  `;
  const install = () => {
    if (document.getElementById('jv-style')) return;
    const st = document.createElement('style'); st.id = 'jv-style'; st.textContent = css; document.documentElement.appendChild(st);
    const cur = document.createElement('div'); cur.id = 'jv-cursor';
    cur.innerHTML = '<svg width="26" height="26" viewBox="0 0 26 26"><path d="M3 2 L3 21 L8.2 16.3 L11.6 24 L15 22.5 L11.7 15 L19 15 Z" fill="#fff" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(cur);
    const pos = window.__jvPos || { x: 720, y: 450 };
    cur.style.left = pos.x + 'px'; cur.style.top = pos.y + 'px';
    const cap = document.createElement('div'); cap.id = 'jv-cap'; cap.className = 'hide'; document.documentElement.appendChild(cap);
    const sp = document.createElement('div'); sp.id = 'jv-spacer'; sp.style.height = '360px'; sp.setAttribute('aria-hidden', 'true');
    (document.body || document.documentElement).appendChild(sp);
  };
  window.addEventListener('mousemove', (e) => {
    window.__jvPos = { x: e.clientX, y: e.clientY };
    const c = document.getElementById('jv-cursor'); if (c) { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }
  }, true);
  window.addEventListener('mousedown', (e) => {
    const r = document.createElement('div'); r.className = 'jv-ripple'; r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
    document.documentElement.appendChild(r); setTimeout(() => r.remove(), 700);
  }, true);

  const visible = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();
  // Find an element by its own text, optionally climbing to the enclosing bordered card.
  function find(spec) {
    if (spec.sel) {
      const all = [...document.querySelectorAll(spec.sel)].filter(visible);
      let el = all[spec.nth || 0];
      if (el && spec.up) for (let i = 0; i < spec.up; i++) el = el.parentElement;
      if (el && spec.card) el = climb(el);
      return el || null;
    }
    const want = norm(spec.text);
    const cands = [];
    const walker = document.createTreeWalker(document.querySelector(spec.within || 'body'), NodeFilter.SHOW_ELEMENT);
    while (walker.nextNode()) {
      const el = walker.currentNode;
      if (el.closest('#jv-cap,#jv-card,.jv-hl')) continue;
      const t = norm(el.innerText);
      const ok = spec.prefix ? t.startsWith(want) : t === want;
      if (ok && visible(el)) cands.push(el);
    }
    // keep the deepest matches only
    const deep = cands.filter((el) => !cands.some((o) => o !== el && el.contains(o)));
    let el = deep[spec.nth || 0];
    if (!el) return null;
    if (spec.up) for (let i = 0; i < spec.up; i++) el = el.parentElement;
    if (spec.card) el = climb(el, spec.card === true ? 30 : spec.card);
    return el;
  }
  function climb(el, extra = 30) {
    const h0 = el.getBoundingClientRect().height;
    let cur = el.parentElement;
    while (cur && cur !== document.body) {
      const cs = getComputedStyle(cur);
      if (parseFloat(cs.borderTopWidth) > 0 && parseFloat(cs.borderLeftWidth) > 0 && cur.getBoundingClientRect().height > h0 + extra) return cur;
      cur = cur.parentElement;
    }
    return el;
  }
  function rectOf(el, pad) {
    const r = el.getBoundingClientRect();
    return { x: r.left + scrollX - pad, y: r.top + scrollY - pad, w: r.width + 2 * pad, h: r.height + 2 * pad, vx: r.left, vy: r.top, vw: r.width, vh: r.height };
  }
  window.__jv = {
    install,
    caption(ch, text) {
      install();
      const cap = document.getElementById('jv-cap');
      if (!text) { cap.className = 'hide'; return; }
      cap.innerHTML = (ch ? '<span class="ch">' + ch + '</span>' : '') + text;
      cap.className = '';
    },
    rect(spec) { const el = find(spec); if (!el) return null; return rectOf(el, 0); },
    scrollTo(spec, block = 'center', offset = 0) {
      const el = find(spec); if (!el) return false;
      const r = el.getBoundingClientRect();
      let top;
      if (block === 'start') top = r.top + scrollY - 76 - offset;
      else top = r.top + scrollY - Math.max(76, (innerHeight - 170 - r.height) / 2 + 40);
      window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
      return true;
    },
    scrollBy(dy) { window.scrollBy({ top: dy, behavior: 'smooth' }); },
    highlight(specs, label, opts = {}) {
      install();
      this.clear();
      const list = Array.isArray(specs) ? specs : [specs];
      let n = 0;
      list.forEach((spec, i) => {
        const el = find(spec); if (!el) return;
        const pad = spec.pad ?? 6;
        const r = rectOf(el, pad);
        const d = document.createElement('div');
        d.className = 'jv-hl' + (list.length > 1 || opts.noDim ? ' multi' : '');
        if (spec.fixed || opts.fixed) Object.assign(d.style, { position: 'fixed', left: (r.vx - pad) + 'px', top: (r.vy - pad) + 'px', width: r.w + 'px', height: r.h + 'px' });
        else Object.assign(d.style, { left: r.x + 'px', top: r.y + 'px', width: r.w + 'px', height: r.h + 'px' });
        const lab = spec.label ?? (i === 0 ? label : null);
        if (lab) { const l = document.createElement('div'); l.className = 'lbl' + (r.vy - pad < 100 || spec.below ? ' below' : ''); l.textContent = lab; d.appendChild(l); }
        document.body.appendChild(d); n++;
      });
      return n;
    },
    capTop(on) { install(); document.getElementById('jv-cap').classList.toggle('top', !!on); },
    clear() { document.querySelectorAll('.jv-hl').forEach((e) => e.remove()); },
    card(html) {
      install();
      let c = document.getElementById('jv-card');
      if (!html) { if (c) { c.style.opacity = '0'; setTimeout(() => c.remove(), 400); } return; }
      if (!c) { c = document.createElement('div'); c.id = 'jv-card'; document.documentElement.appendChild(c); }
      c.style.opacity = '1';
      c.innerHTML = '<div class="box">' + html + '</div>';
    },
    cardStep(i) { document.querySelectorAll('#jv-card li').forEach((li, j) => { li.className = j === i ? 'on' : (j < i ? '' : 'dim'); }); },
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install); else install();
})();
