// Converts subtitle text into words that the speech engine reads unambiguously.
const ONES = ['zero','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen'];
const TENS = ['','','twenty','thirty','forty','fifty','sixty','seventy','eighty','ninety'];
function int(n) {
  n = Number(n);
  if (n < 20) return ONES[n];
  if (n < 100) return TENS[Math.floor(n/10)] + (n%10 ? '-' + ONES[n%10] : '');
  if (n < 1000) return ONES[Math.floor(n/100)] + ' hundred' + (n%100 ? ' and ' + int(n%100) : '');
  if (n < 1000000) return int(Math.floor(n/1000)) + ' thousand' + (n%1000 ? (n%1000 < 100 ? ' and ' : ' ') + int(n%1000) : '');
  throw new Error('too big ' + n);
}
function year(y) {
  y = Number(y);
  if (y >= 2000 && y < 2010) return 'two thousand and ' + ONES[y-2000];
  const hi = Math.floor(y/100), lo = y%100;
  return int(hi) + ' ' + (lo === 0 ? 'hundred' : lo < 10 ? 'oh ' + ONES[lo] : int(lo));
}
function two(s) { const n = Number(s); return n < 10 ? 'oh ' + ONES[n] : int(n); }
function ORD(w) { const m = {one:'first',two:'second',three:'third',five:'fifth',eight:'eighth',nine:'ninth',twelve:'twelfth'}; const parts = w.split(/([ -])/); let last = parts.pop(); last = m[last] || (last.endsWith('y') ? last.slice(0,-1)+'ieth' : last + 'th'); return parts.join('') + last; }
function num(s) {
  if (s.includes('.')) s = s.replace(/0+$/, '').replace(/\.$/, '');
  s = s.replace(/,/g, '');
  if (s.includes('.')) { const [a, b] = s.split('.'); return int(a) + ' point ' + b.split('').map(d => ONES[+d]).join(' '); }
  return int(s);
}
const ACR = { OBR:'O B R', IFS:'I F S', HMRC:"H M R C", NHS:'N H S', VAT:'V A T', API:'A P I', PDF:'P D F', GDP:'G D P', AI:'A I', CT:'C T', UK:'U K', LightGBM:'Light G B M', 'GOV.UK':'gov dot U K', 'Markdown':'markdown' };
function speak(t) {
  let s = t;
  s = s.replace(/Download \.md/g, 'Download dot M D').replace(/ \/ /g, ' or ').replace(/Agentverse/g, 'Agent verse');
  s = s.replace(/[“”"]/g, '').replace(/–|—/g, ', ').replace(/→/g, ' to ').replace(/·/g, ',');
  s = s.replace(/\b(\d{4})-(\d{2})\b/g, (_, a, b) => Number(a) < 2010 ? year(a) + ' to ' + year(Math.floor(Number(a)/100)*100 + Number(b)) : year(a) + ' to ' + two(b));
  s = s.replace(/\b(\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December)\b/g, (_, d, m) => 'the ' + ORD(int(d)) + ' of ' + m);
  s = s.replace(/£(\d[\d,]*(?:\.\d+)?) to £(\d[\d,]*(?:\.\d+)?) ?billion/g, (_, a, b) => num(a) + ' to ' + num(b) + ' billion pounds');
  s = s.replace(/£(\d[\d,]*(?:\.\d+)?) ?billion/g, (_, a) => num(a) + ' billion pounds');
  s = s.replace(/£(\d[\d,]*(?:\.\d+)?)bn/g, (_, a) => num(a) + ' billion pounds');
  s = s.replace(/(\d+(?:\.\d+)?)pp\b/g, (_, a) => num(a) + ' percentage points');
  s = s.replace(/(\d+(?:\.\d+)?)%/g, (_, a) => num(a) + ' percent');
  s = s.replace(/\b(\d+)(st|nd|rd|th)\b/g, (_, a) => ORD(int(a)));
  s = s.replace(/\b([ES])(\d{1,2})\b/g, (_, l, d) => l + ' ' + int(d));
  s = s.replace(/\b([A-Z]+)-(\d{3})\b/g, (_, w, d) => w.toLowerCase() + ' ' + d.split('').map(x => ONES[+x]).join(' '));
  s = s.replace(/\b(1[89]\d\d|20\d\d)\b/g, (_, y) => year(y));
  s = s.replace(/\b\d[\d,]*(?:\.\d+)?\b/g, (m) => num(m));
  for (const [k, v] of Object.entries(ACR)) s = s.replace(new RegExp('(^|[^A-Za-z.])' + k.replace('.', '\\.') + '(?![A-Za-z])', 'g'), (_, p) => p + v);
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}
module.exports = { speak };
if (require.main === module) console.log(speak(process.argv.slice(2).join(' ')));
