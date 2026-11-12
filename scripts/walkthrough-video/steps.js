// The walkthrough: each step is one subtitle + voice clip, with the on-screen actions that accompany it.
// Every figure quoted here was read from the running site (cached mode, seed 42) before recording.
const GOLDEN = 'What would happen if the UK increased corporation tax from 25% to 28%?';

const CHECKLIST = [
  'Check the parsed policy and its assumptions match what you mean.',
  'Read the verification verdict first. If the forecast is withheld, quote no numbers.',
  'Quote central figures with their p5–p95 range and their “Model scenario” label.',
  'Use the tornado chart to find the assumptions that matter, then test them with the sliders.',
  'Back claims with verified evidence and precedents, and name the confounders.',
  'Check the Evaluation page for how reliable the method has been on past data.',
  'Share the Report (Markdown or PDF) with its warnings and caveats.',
];

module.exports = (h) => [
  // ───────────────────────── Introduction
  { ch: 'Introduction', do: async () => {
      await h.goto('/');
      await h.card(`<div class="kick">Agentverse · Jane Avenue</div><h1>How to use Jane Avenue<span class="dot">.</span></h1>
        <p>A walkthrough of the website, and how to turn its results into evidence for a decision.</p>
        <p style="font-size:16px;color:#8aa39a;margin-top:18px">Recorded on the real site, running locally from the GitHub code in Cached Research mode.</p>`);
    },
    say: 'This video shows how to use Jane Avenue, the UK fiscal policy simulator built in the Agentverse project, and how to turn its results into evidence for a decision.' },
  { do: async () => { await h.card(null); await h.wait(500); await h.show({ text: 'Mode: Cached Research', within: 'header' }, 'Run mode'); },
    say: 'Everything you see is the real website, running from the code on GitHub. It is in Cached Research mode, shown by this badge, which replays recorded, verified research runs, so no API key is needed.' },
  { do: async () => { await h.show({ sel: 'footer' }, 'Disclaimer'); },
    say: 'Note the footer: this is a prototype, not official government analysis. Keep that in mind whenever you present its results.' },

  // ───────────────────────── 1. Ask
  { ch: '1 · Ask a policy question', do: async () => { await h.show({ sel: '#policy-query-input', card: 8 }, 'Policy question box'); },
    say: 'Start on the home page. You type a proposed tax, benefit or spending change in plain English into this box. Pressing Enter runs the analysis.' },
  { do: async () => { await h.show({ sel: '[aria-label="Example policy queries"]', pad: 10 }, 'Six example prompts'); },
    say: 'Or pick one of six example prompts. They cover corporation tax, VAT, the personal allowance, and NHS spending.' },
  { do: async () => { await h.show({ sel: '[aria-label="Example policy queries"] button', nth: 0 }, 'Golden path example'); await h.wait(1600); await h.click(h.page.getByText(GOLDEN, { exact: true })); },
    say: 'We will use the first one, which asks what would happen if the UK increased corporation tax from 25% to 28%.' },

  // ───────────────────────── 2. Parse & scope gate
  { ch: '2 · Check the parsed policy and scope gate', do: async () => {
      await h.page.getByText('Parsed Policy Specification & Scope Gate').waitFor();
      await h.wait(400);
      await h.scroll({ text: 'Parsed Policy Specification & Scope Gate' }, 'start');
      await h.show({ text: 'Parsed Policy Specification & Scope Gate', card: true }, 'How the site understood the question', { noScroll: true });
    },
    say: 'Before anything runs, the site shows how it understood your question, so you can check it.' },
  { do: async () => { await h.show([{ text: 'Policy Type', up: 1, label: 'Policy type' }, { text: 'Rate Change', up: 1, label: '+3pp' }], null, { noScroll: true }); },
    say: 'The policy type is the UK corporation tax main rate. The baseline rate is 25% and the proposed rate is 28%: a rise of 3 percentage points.' },
  { do: async () => { await h.show({ sel: '[aria-label="Parser assumptions and ambiguities"]' }, 'Defaults the parser assumed'); },
    say: 'Anything you did not state is listed as an assumption. Here the effective date is assumed to be 1 April 2027, and the horizon 5 years. If that is not what you mean, edit the fields before running.' },
  { do: async () => { await h.show({ sel: '[aria-label="Scope gate assessment"]' }, 'Scope gate'); },
    say: 'The scope gate checks the proposal against UK history. It reads: quantitative forecast allowed. The historical UK corporation tax range is 19% to 52%, with a largest single change of 6 points.' },
  { do: async () => { await h.show({ text: 'Simulation & Research Options', card: true }, 'Run options'); },
    say: 'Below are the run options: the number of Monte Carlo draws, whether to run the research agent, and whether to use cached research. We keep the defaults and click Run analysis.' },

  // ───────────────────────── 3. Pipeline
  { ch: '3 · Run the analysis and watch the pipeline', do: async () => {
      await h.clear();
      await h.click(h.page.getByRole('button', { name: /Run analysis/ }));
      await h.page.waitForURL(/analyses\//);
      await h.wait(400);
      await h.top();
      await h.show({ text: 'PIPELINE', up: 1, pad: 8 }, 'Six pipeline stages', { noScroll: true, fixed: true });
    },
    say: 'The analysis page opens and runs six stages live: parse and scope, research, precedents, model and Monte Carlo, verify, and report. The ticks on the left mark each completed stage.' },
  { do: async () => { await h.show({ text: 'Live Research Agent Timeline', card: true }, 'Research agent, step by step', { noScroll: true }); },
    say: 'While it runs, the research timeline streams every step the research agent takes: the questions it planned, each search, each document it fetched, and each quote it extracted.' },
  { do: async () => {
      await h.page.waitForFunction(() => document.querySelector('main')?.innerText.includes('· completed'), null, { timeout: 60000 });
      await h.wait(600);
      const toast = h.page.getByText('Your policy assessment is ready');
      await h.page.evaluate(() => window.__jv.capTop(true));
      if (await toast.count()) await h.show({ text: 'Your policy assessment is ready', card: true }, 'Finished', { noScroll: true });
      await h.wait(3800);
      const dismiss = h.page.getByRole('button', { name: 'Dismiss completion notification' });
      if (await dismiss.count()) await h.click(dismiss);
      await h.clear();
      await h.page.evaluate(() => window.__jv.capTop(false));
      await h.click(h.page.getByRole('tab', { name: /Overview/ }));
      await h.page.getByText('Headline Projections (Central Scenario)').waitFor();
      await h.top();
    },
    say: 'When it finishes, a notice says the policy assessment is ready, with the verdict: approved with warnings. We close it and open the Overview tab.' },

  // ───────────────────────── 4. Overview
  { ch: '4 · Overview: the headline numbers', do: async () => { await h.show({ text: 'Approved with warnings', nth: 0 }, 'Verification verdict', { noScroll: true }); },
    say: 'The header repeats the policy, the mode, and the verification verdict. Always check this verdict first: it tells you whether the numbers can be used, and with which caveats.' },
  { do: async () => { await h.show({ text: '01 Headline Projections (Central Scenario)', up: 2, pad: 10 }, 'Headline projections', { noScroll: true, raw: true }); },
    say: 'These four cards are the headline projections, taken from the central scenario.' },
  { do: async () => { await h.show({ text: 'Behavioural Revenue (2027-28)', card: true }, 'Year 1', { noScroll: true }); },
    say: 'Behavioural revenue in 2027-28, the first year, is £7.0 billion, with a 5th to 95th percentile range of £5.3 billion to £8.5 billion.' },
  { do: async () => { await h.show({ text: 'Behavioural Revenue (2031-32)', card: true }, 'Year 5', { noScroll: true }); },
    say: 'By 2031-32, the fifth year, it is £13.3 billion, with a range of £10.7 billion to £15.1 billion.' },
  { do: async () => { await h.show([{ text: 'Business Investment (2031-32)', card: true, label: 'Investment' }, { text: 'GDP Level (2031-32)', card: true, label: 'GDP' }], null, { noScroll: true }); },
    say: 'Business investment is 0.56% lower in 2031-32, through the cost of capital. The GDP level is 0.10% lower, and that card is marked low confidence, indicative only.' },
  { do: async () => { await h.show([{ text: 'Model scenario', nth: 2, label: 'Evidence label' }, { text: 'medium confidence', nth: 0, label: 'Confidence' }], null, { noScroll: true }); },
    say: 'Every number carries a label. Model scenario means it was calculated by the econometric engine, not written by the AI. The confidence badge tells you how much weight it can bear.' },
  { do: async () => { await h.show({ text: 'Behavioural Revenue (2027-28)', card: true }, 'Quote it like this', { noScroll: true }); },
    say: 'For a decision, quote the central figure with its range. For example: about £7 billion in the first year, between £5.3 billion and £8.5 billion under the model’s assumptions.' },
  { do: async () => { await h.show({ text: 'Research & Precedent Highlights', card: true }, 'Research summary'); },
    say: 'Below, the policy and evidence summary gives the research findings in brief. The bracketed E numbers point to individual pieces of evidence, and the S numbers to sources.' },
  { do: async () => { await h.show({ text: '03 Explore Analysis Workstreams', up: 1, pad: 8 }, 'Links to each detailed view', { block: 'start' }); },
    say: 'These cards link to each detailed view: 37 evidence items across 24 sources, 5 historical precedents, the scenarios, 19 assumptions, 18 audit checks, and the report.' },

  // ───────────────────────── 5. Research
  { ch: '5 · Research: the evidence base', do: async () => {
      await h.clear(); await h.click(h.page.getByRole('tab', { name: /Research/ })); await h.wait(900); await h.top();
      await h.show({ text: 'Live Research Agent Timeline', card: true }, 'What the agent did', { noScroll: true });
    },
    say: 'The Research tab shows what the AI research agent did. It planned 6 research questions, ran searches, and fetched documents from sources such as GOV.UK, the IFS and the American Economic Association.' },
  { do: async () => { await h.scroll({ text: 'Evidence Browser (37 of 37)' }, 'start'); await h.show([{ text: 'Evidence Browser (37 of 37)', label: '37 evidence items' }, { text: '✓ 35 verified', label: '35 verified' }, { text: '✕ 2 failed', label: '2 failed', below: true }], null, { noScroll: true }); },
    say: 'The evidence browser lists 37 extracted items. 35 have a verbatim quote verified against the source text. 2 failed verification, and they are flagged in red rather than hidden.' },
  { do: async () => { await h.show({ text: 'Search claims or quotes', up: 2, pad: 8 }, 'Filters', { noScroll: true }); },
    say: 'You can filter by topic, verification status or kind of evidence, or search the claims and quotes.' },
  { do: async () => { await h.show({ sel: '#evidence-E1' }, 'Evidence E1'); },
    say: 'Each item gives the claim, the exact quote and its source. For example, E1 says onshore corporation tax receipts are projected to reach 3.5% of GDP in 2027-28.' },
  { do: async () => {
      await h.clear();
      await h.click(h.page.locator('#evidence-E1 button').first());
      await h.page.locator('[aria-label^="Source details for"]').waitFor();
      await h.wait(500);
      await h.show({ sel: '[aria-label^="Source details for"] > div' , pad: -2 }, 'Source S4', { noScroll: true, noDim: true });
    },
    say: 'Clicking the source opens its details. This is source S4, the October 2026 Economic and fiscal outlook on GOV.UK, with every quote taken from it and whether each was verified.' },
  { do: async () => { await h.wait(4000); await h.clear(); await h.click(h.page.getByRole('button', { name: 'Close source drawer' })); },
    say: 'For a decision, cite only evidence marked quote verified, and treat failed or unverified items with caution.' },

  // ───────────────────────── 6. Precedents
  { ch: '6 · Precedents: what happened before', do: async () => {
      await h.click(h.page.getByRole('tab', { name: /Precedents/ })); await h.wait(900); await h.top();
      await h.show({ text: 'UK Corporation Tax Main Rate Timeline (1982–Present)', card: true }, 'Rate history since 1982', { block: 'start' });
    },
    say: 'The Precedents tab puts the proposal in historical context. The timeline shows the UK main rate since 1982. Blue markers are the 5 past changes matched to this proposal.' },
  { do: async () => { await h.show({ text: 'Ranked Precedent Matches (5)', up: 1, pad: 8 }, 'Closest match', { block: 'start' }); },
    say: 'The closest match is the April 2023 rise from 19% to 25%, with a similarity of 60%.' },
  { do: async () => { await h.show({ text: 'COMPARABILITY NOTES & POLICY CONFOUNDERS', up: 1, pad: 8 }, 'Confounders'); },
    say: 'Its notes flag confounders. Full expensing, and the small profits rate with marginal relief, came in at the same time, so the receipts that followed are not the effect of the rate rise alone.' },
  { do: async () => { await h.scroll({ text: 'Official Policy Costings (Ex-ante)', nth: 0 }, 'start'); await h.show([{ text: 'Official Policy Costings (Ex-ante)', nth: 0, up: 2, pad: 4, label: 'Official costing (before)' }, { text: 'Observed CT Receipts Outturn (Levels)', nth: 0, up: 2, pad: 4, label: 'Observed outcome (after)' }], null, { noScroll: true }); },
    say: 'Two kinds of evidence are kept apart. Official costings are estimates made at the Budget, before the change. Observed outcomes are actual receipts: £83.3 billion in 2022-23, and £92.4 billion in 2023-24.' },
  { do: async () => { await h.top(); await h.show({ text: '5 historical changes ranked by direction, magnitude, rate level, macro context and recency. Official costings and observed outcomes are distinct evidence; similarity does not establish causation.' }, 'Read precedents as context', { noScroll: true }); },
    say: 'Use precedents as context and a sense check, not as proof of cause and effect. As the site says, similarity does not establish causation.' },

  // ───────────────────────── 7. Scenarios
  { ch: '7 · Scenarios: uncertainty and what-ifs', do: async () => {
      await h.clear(); await h.click(h.page.getByRole('tab', { name: /Scenarios/ })); await h.wait(900); await h.top();
      await h.show({ text: 'Metric Selector & Confidence', card: true }, 'Choose an output', { block: 'start' });
    },
    say: 'The Scenarios tab is where uncertainty is shown. First, choose one of the 7 modelled outputs here. We stay on behavioural revenue.' },
  { do: async () => { await h.show({ text: 'Scenario Paths — Behavioural revenue change', card: true }, 'Central, optimistic, pessimistic', { block: 'start' }); },
    say: 'This chart shows the central, optimistic and pessimistic paths. Optimistic and pessimistic combine favourable or unfavourable assumptions. They are a stress test, not forecasts.' },
  { do: async () => { await h.show({ text: 'Monte Carlo Uncertainty — Behavioural revenue change', card: true }, 'Monte Carlo bands', { block: 'start' }); },
    say: 'The Monte Carlo chart reruns the model 2,000 times with the uncertain assumptions varied together. The shaded bands span the 5th to 95th and the 25th to 75th percentiles.' },
  { do: async () => { await h.show({ text: 'Interval note:', up: 3, pad: 2 }, 'Read the interval note', { block: 'center' }); },
    say: 'The interval note matters: these are assumption-driven ranges, not statistical prediction intervals, and they exclude model and data uncertainty.' },
  { do: async () => { await h.show({ text: 'Parameter Sensitivity Tornado (2031-32)', card: true }, 'Which assumptions matter most', { block: 'start' }); },
    say: 'The tornado chart ranks which assumptions move the 2031-32 result most. The top two are the profit base deviation from baseline and the taxable profit elasticity. These are the assumptions to scrutinise and discuss with experts.' },
  { do: async () => {
      await h.show({ text: 'Live Assumption Sliders', card: true }, 'Live what-if sliders', { block: 'start' });
    },
    say: 'The live sliders let you test a what-if instantly. As an example, we lower the proposed rate from 28% to 26%.' },
  { do: async () => {
      const sl = h.page.locator('input[type=range]').first();
      await h.clear();
      await h.moveTo(sl); await sl.focus();
      for (let i = 0; i < 4; i++) { await h.page.keyboard.press('ArrowLeft'); await h.wait(350); }
      await h.wait(700);
      await h.scroll({ text: 'Scenario Paths — Behavioural revenue change' }, 'start');
      await h.show([{ text: 'Scenario Paths — Behavioural revenue change', card: true, label: 'Custom path (dashed purple)' }, { text: 'Proposed CT main rate', card: true, label: '26%' }], null, { noScroll: true });
    },
    say: 'The model recomputes in milliseconds, and a dashed purple custom path appears on the chart. With a smaller rise, it sits well below the central path.' },
  { do: async () => {
      await h.show({ text: 'Re-run full analysis with these assumptions', card: 10 }, 'Re-run with your assumptions');
      await h.wait(4200);
      await h.clear();
      await h.scroll({ text: 'Live Assumption Sliders' }, 'start');
      await h.click(h.page.getByRole('button', { name: 'Reset all' }));
    },
    say: 'You can also re-run the full analysis with your chosen assumptions, which repeats the verification and the report. Here we reset the sliders instead.' },

  // ───────────────────────── 8. Assumptions
  { ch: '8 · Assumptions: every input on the table', do: async () => {
      await h.clear(); await h.click(h.page.getByRole('tab', { name: /Assumptions/ })); await h.wait(900); await h.top();
      await h.show({ text: 'Model Assumptions & Provenance Registry', card: true }, '19 parameters', { noScroll: true, raw: true });
    },
    say: 'The Assumptions tab lists all 19 model parameters, each with a central value, a low to high range, a distribution, its basis and its sources.' },
  { do: async () => { await h.show({ text: 'Taxable profit elasticity', nth: 0, up: 2, pad: 4 }, 'Example: taxable profit elasticity'); },
    say: 'The basis column says whether a value comes from the literature, an official source, or team judgement. For example, the taxable profit elasticity is 0.2, with a range of 0.05 to 0.5, from the literature.' },
  { do: async () => { await h.show({ text: 'How was this calculated? (Calculation Inspector)', card: true }, 'Calculation inspector', { block: 'start' }); },
    say: 'The calculation inspector shows exactly how each number was produced: every step’s formula, inputs and linked parameters, in order. Pick a metric and a fiscal year to trace any result.' },

  // ───────────────────────── 9. Verification
  { ch: '9 · Verification: can the numbers be trusted?', do: async () => {
      await h.clear(); await h.click(h.page.getByRole('tab', { name: /Verification/ })); await h.wait(900); await h.top();
      await h.show({ text: 'Independent Verification Summary', card: true }, 'Independent audit', { block: 'start' });
    },
    say: 'The Verification tab is an independent audit. 18 checks ran: 16 passed, 1 gave a warning, and 1 failed. The verdict is approved with warnings.' },
  { do: async () => { await h.show({ text: 'CITE-002', up: 3, pad: 2 }, 'The failed check'); },
    say: 'The failed check, CITE-002, reports that evidence item E19 is not verified against its source text. Its severity is error, not blocking, so the forecast is still shown, with the warning.' },
  { do: async () => { await h.show({ text: 'DATA-002', up: 3, pad: 2 }, 'The warning'); },
    say: 'The warning, DATA-002, notes that baseline years after 2031-32 are extrapolated rather than official forecasts.' },
  { do: async () => { await h.show({ text: 'CALC-001', up: 3, pad: 2 }, 'Independent recompute'); },
    say: 'Other checks confirm, for example, that an independent recompute reproduces all 35 central-scenario values.' },
  { do: async () => { await h.show({ text: 'SCOPE-001', up: 3, pad: 2 }, 'Blocking check'); },
    say: 'Blocking checks matter most: if one fails, the forecast is withheld. Before using the numbers, read this page and mention any warnings.' },

  // ───────────────────────── 10. Report
  { ch: '10 · Report: the document to share', do: async () => {
      await h.clear(); await h.click(h.page.getByRole('tab', { name: /Report/ })); await h.wait(1200); await h.top();
      await h.show({ text: 'Policy Assessment: Raise the CT main rate from 25% to 28% from 1 April 2027', up: 1, pad: 8 }, 'Policy assessment report', { noScroll: true });
    },
    say: 'The Report tab is the shareable policy assessment, with ten sections, from the executive summary to sources and data provenance.' },
  { do: async () => {
      const b = h.page.locator('main button', { hasText: '£7.0bn' }).first();
      await h.scrollLoc(b);
      await h.show({ text: 'KEY FIGURES', up: 1, pad: 8 }, '8 traceable figures', { noScroll: true });
      await h.wait(2500);
      await h.clear(); await h.moveTo(b); await b.hover();
    },
    say: 'Numbers in the report are inserted by code, not written by the AI. Hover over any of the 8 key figures to see the calculation steps and sources behind it.' },
  { do: async () => { await h.page.mouse.move(1300, 700, { steps: 10 }); await h.top(); await h.show([{ text: 'Download .md', up: 1, label: 'Editable copy' }, { text: 'Print / Save as PDF', up: 1, label: 'PDF', below: true }], null, { noScroll: true }); },
    say: 'Use Download .md for an editable Markdown copy, or Print / Save as PDF to circulate it.' },

  // ───────────────────────── 11. Withheld
  { ch: '11 · When the site refuses to forecast', do: async () => {
      await h.clear(); await h.click(h.page.getByRole('link', { name: 'New Policy Analysis' }));
      await h.wait(900);
      await h.click(h.page.getByText('Raise corporation tax to 45%', { exact: true }));
      await h.page.getByText('Parsed Policy Specification & Scope Gate').waitFor();
      await h.wait(500);
      await h.scroll({ text: 'Parsed Policy Specification & Scope Gate' }, 'start');
      await h.show({ text: 'Parsed Policy Specification & Scope Gate', card: true }, 'Raise corporation tax to 45%', { noScroll: true });
    },
    say: 'Now an out-of-scope example: raise corporation tax to 45%. As no baseline was given, the current rate of 25% is assumed.' },
  { do: async () => { await h.show({ sel: '[aria-label="Scope gate assessment"]' }, 'Forecast will be withheld'); },
    say: 'The scope gate marks it unsupported. A 20-point change is far outside any UK precedent, where the limit is 15 points, so the quantitative forecast will be withheld.' },
  { do: async () => {
      await h.clear();
      await h.click(h.page.getByRole('button', { name: /Run analysis/ }));
      await h.page.waitForURL(/analyses\//);
      await h.page.waitForFunction(() => document.querySelector('main')?.innerText.includes('· completed'), null, { timeout: 60000 });
      const dismiss = h.page.getByRole('button', { name: 'Dismiss completion notification' });
      if (await dismiss.count()) await h.click(dismiss);
      await h.click(h.page.getByRole('tab', { name: /Overview/ }));
      await h.page.getByText('Headline Projections (Central Scenario)').waitFor();
      await h.top();
      await h.show({ text: 'Quantitative forecast withheld', card: true, nth: 1 }, 'Forecast withheld', { noScroll: true });
    },
    say: 'After running, a banner says the quantitative forecast is withheld, and the headline cards show forecast withheld instead of numbers.' },
  { do: async () => { await h.show({ text: '01 Headline Projections (Central Scenario)', up: 2, pad: 10 }, 'No numbers shown', { block: 'start', raw: true }); },
    say: 'The research and historical precedents are still available. For decision-makers, a withheld forecast is itself a finding: the proposal is beyond what the evidence supports, so no figure should be quoted.' },

  // ───────────────────────── 12. Other policies
  { ch: '12 · Other taxes, benefits and spending', do: async () => {
      await h.clear(); await h.click(h.page.getByRole('link', { name: 'New Policy Analysis' }));
      await h.wait(900);
      await h.click(h.page.getByText('Raise VAT from 20% to 21% from April 2027', { exact: true }));
      await h.page.getByText('Parsed Policy Specification & Scope Gate').waitFor();
      await h.wait(500);
      await h.scroll({ text: 'Parsed Policy Specification & Scope Gate' }, 'start');
      await h.show({ text: 'Parsed Policy Specification & Scope Gate', card: true }, 'VAT 20% to 21%', { noScroll: true });
    },
    say: 'Other taxes and benefits in HMRC’s ready reckoner, such as VAT, are partially supported. Their revenue is scaled from HMRC’s official costings.' },
  { do: async () => { await h.show({ sel: '[aria-label="Scope gate assessment"]' }, 'How it is estimated'); },
    say: 'As the scope gate explains, HMRC costs the first 3 years, and later years repeat the third-year effect, grown with nominal GDP.' },
  { do: async () => {
      await h.clear();
      await h.click(h.page.getByRole('button', { name: /Run analysis/ }));
      await h.page.waitForURL(/analyses\//);
      await h.page.waitForFunction(() => document.querySelector('main')?.innerText.includes('· completed'), null, { timeout: 60000 });
      const dismiss = h.page.getByRole('button', { name: 'Dismiss completion notification' });
      if (await dismiss.count()) await h.click(dismiss);
      await h.click(h.page.getByRole('tab', { name: /Overview/ }));
      await h.page.getByText('Headline Projections (Central Scenario)').waitFor();
      await h.top();
      await h.show({ text: 'Behavioural Revenue (2027-28)', card: true }, 'Year 1', { noScroll: true });
    },
    say: 'For a 1-point VAT rise, the first-year revenue is £9.1 billion, with a range of £7.8 billion to £9.7 billion.' },
  { do: async () => { await h.show({ text: 'Placeholder (unverified)', nth: 0 }, 'Placeholder research', { noScroll: true }); },
    say: 'Note this placeholder badge. This offline recording has no recorded research for VAT, so the research shown is a labelled placeholder. With a Gemini API key in live mode, it is researched for real. Never quote placeholder material.' },
  { do: async () => {
      await h.clear(); await h.click(h.page.getByRole('link', { name: 'New Policy Analysis' }));
      await h.wait(900);
      await h.click(h.page.getByText('Increase NHS spending by £10bn a year', { exact: true }));
      await h.page.getByText('Parsed Policy Specification & Scope Gate').waitFor();
      await h.wait(500);
      await h.scroll({ text: 'Parsed Policy Specification & Scope Gate' }, 'start');
      await h.show({ sel: '[aria-label="Scope gate assessment"]' }, 'Research only', { noScroll: true });
    },
    say: 'Spending policies, such as more NHS spending, are research only. No validated model exists for them yet, so they are researched and reported, but no forecast is made.' },

  // ───────────────────────── 13. History
  { ch: '13 · History: return to past analyses', do: async () => {
      await h.clear(); await h.click(h.page.getByRole('link', { name: 'History' }));
      await h.page.getByText('Analysis History').waitFor(); await h.wait(600);
      await h.show({ sel: 'main table', card: 10 }, 'Every analysis you ran', { noScroll: true });
    },
    say: 'The History page lists every analysis with its status and verification verdict. Click Open on any row to return to its results.' },

  // ───────────────────────── 14. Evaluation
  { ch: '14 · Evaluation: how reliable is the method?', do: async () => {
      await h.clear(); await h.click(h.page.getByRole('link', { name: 'Evaluation' }));
      await h.page.getByText('Central Engine Out-of-Sample MAE (jane_behavioural)').waitFor(); await h.wait(600);
      await h.show({ text: 'Central Engine Out-of-Sample MAE (jane_behavioural)', card: true }, 'Backtest on unseen years');
    },
    say: 'The Evaluation page tests the method on past data. In a backtest on 17 unseen years, 2008-09 through 2024-25, the central engine’s mean absolute error was £5.54 billion, better than the best simple baseline, at £5.71 billion.' },
  { do: async () => { await h.show({ text: 'ML Experiment Verdict (LightGBM)', card: true }, 'Machine learning rejected', { noScroll: true }); },
    say: 'A machine learning model, LightGBM, was tested and rejected, because its test error of £6.33 billion was worse than the baseline.' },
  { do: async () => { await h.show([{ text: 'Research Citation & Quote Validity', card: true, label: 'Research accuracy' }, { text: 'Verifier Fault Detection Rate', card: true, label: 'Verifier' }], null, { noScroll: true }); },
    say: 'On a 15-question benchmark, the research agent’s facts, source links and quotes were 100% accurate, with no hallucinated sources. The verifier caught 18 of 18 deliberately injected faults.' },
  { do: async () => { await h.show({ text: 'Methodological Limitations & Honest Caveats', card: true }, 'Caveats to state', { block: 'start' }); },
    say: 'Finally, the limitations section lists caveats to weigh alongside any result, such as the small number of past rate changes, and reforms that happened at the same time.' },

  // ───────────────────────── 15. Decision checklist
  { ch: '15 · Using the results in a decision', do: async () => {
      await h.clear();
      await h.card(`<div class="kick">Decision checklist</div><h1 style="font-size:36px">Using Jane Avenue to inform a decision</h1><ol>${CHECKLIST.map((c) => `<li class="dim">${c}</li>`).join('')}</ol>`);
    },
    noCap: true, say: 'To finish, here is how governments, and our team, should use these results in a decision.' },
  ...CHECKLIST.map((c, i) => ({ noCap: true, do: async () => { await h.cardStep(i); }, say: c.replace('p5–p95', '5th to 95th percentile') })),
  { do: async () => { await h.cardStep(99); }, say: 'That is the full workflow: ask, check, run, read the evidence, test the uncertainty, verify, and share. Thank you for watching.', tail: 2500 },
];
