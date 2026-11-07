"""Golden-path smoke check: run one analysis through the real pipeline and print what happened. Owner: agent-1.

    python backend/scripts/smoke.py                      # golden query, current mode (mock unless a key is set)
    python backend/scripts/smoke.py --mode cached        # force a mode
    python backend/scripts/smoke.py --query "Cut corporation tax to 23%" --draws 500
    python backend/scripts/smoke.py --json               # machine-readable summary (for agent-11 / CI)

Uses an in-memory database unless --db is given, so it never touches backend/.data. Exit codes: 0 = completed,
1 = pipeline failed, 2 = completed but a check the caller asked for failed (--expect-approved / --max-seconds).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
GOLDEN_QUERY = "What would happen if the UK increased corporation tax from 25% to 28%?"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--query", default=GOLDEN_QUERY)
    p.add_argument("--mode", choices=("mock", "live", "cached"), help="override JANE_MODE")
    p.add_argument("--draws", type=int, default=2000, help="Monte Carlo draws (default 2000)")
    p.add_argument("--no-research", action="store_true", help="skip the research stage")
    p.add_argument("--no-cache", action="store_true", help="do not replay cached research")
    p.add_argument("--db", default=":memory:", help="SQLite path (default in-memory)")
    p.add_argument("--json", action="store_true", help="print a JSON summary instead of tables")
    p.add_argument("--expect-approved", action="store_true", help="exit 2 if the forecast is withheld")
    p.add_argument("--max-seconds", type=float, help="exit 2 if the whole run takes longer than this")
    return p.parse_args(argv)


def _summary(a, elapsed_s: float, n_events: int) -> dict:
    sim = a.simulation
    central = sim.scenarios[0].result if sim and sim.scenarios else None
    headline = {}
    if central:
        for m in central.metrics:
            if m.values:
                headline[m.metric] = {"first_year": m.values[0].value, "final_year": m.values[-1].value, "unit": m.unit}
    placeholders = sorted(s.source_id for s in a.sources if s.is_placeholder)
    if sim and (n := sum(x.is_placeholder for x in sim.assumptions)):
        placeholders.append(f"{n} assumptions")
    if a.precedents and (n := sum(m.change.is_placeholder for m in a.precedents.matches)):
        placeholders.append(f"{n} precedents")
    v = a.verification
    return {
        "analysis_id": a.analysis_id,
        "status": a.status,
        "error": a.error,
        "mode": a.mode,
        "research_mode": a.research.mode if a.research else None,
        "policy": a.policy.description if a.policy else None,
        "scope": a.scope.status if a.scope else None,
        "stage_timings_ms": a.stage_timings_ms,
        "total_seconds": round(elapsed_s, 3),
        "events": n_events,
        "sources": len(a.sources),
        "evidence": len(a.research.evidence) if a.research else 0,
        "precedents": len(a.precedents.matches) if a.precedents else 0,
        "verification": None if v is None else {
            "overall": v.overall, "counts": v.counts, "summary": v.summary,
            "failing": [f"{c.check_id} ({c.severity}): {c.detail}" for c in v.checks if c.status in ("fail", "warn")],
        },
        "report": None if a.report is None else {"generated_by": a.report.generated_by,
                                                  "withheld": a.report.forecast_withheld,
                                                  "markdown_chars": len(a.report.markdown)},
        "headline_central": headline,
        "placeholder_sources": placeholders,
    }


def _print_tables(s: dict) -> None:
    print(f"Analysis {s['analysis_id']}  status={s['status']}  mode={s['mode']}  research={s['research_mode']}")
    print(f"Policy:  {s['policy']}  (scope: {s['scope']})")
    if s["error"]:
        print(f"ERROR:   {s['error']}")
    print("\nStage timings")
    print(f"  {'stage':<12} {'ms':>8}")
    for stage, ms in s["stage_timings_ms"].items():
        print(f"  {stage:<12} {ms:>8}")
    print(f"  {'total':<12} {round(s['total_seconds'] * 1000):>8}   ({s['events']} events)")
    print(f"\nCounts:  sources={s['sources']}  evidence={s['evidence']}  precedents={s['precedents']}")
    v = s["verification"]
    if v:
        print(f"\nVerification: {v['overall']}  {v['counts']}")
        print(f"  {v['summary']}")
        for line in v["failing"]:
            print(f"  - {line}")
    if s["headline_central"]:
        print("\nCentral scenario (change vs baseline)")
        for metric, h in s["headline_central"].items():
            print(f"  {metric:<28} year1={h['first_year']:>10.4f}  final={h['final_year']:>10.4f} {h['unit']}")
    if s["report"]:
        r = s["report"]
        print(f"\nReport: generated_by={r['generated_by']} withheld={r['withheld']} ({r['markdown_chars']} chars)")
    if s["placeholder_sources"]:
        print(f"\nPLACEHOLDERS still on this path: {', '.join(s['placeholder_sources'])}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:  # Windows consoles default to a legacy code page; "£" must not garble
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass
    if args.mode:
        os.environ["JANE_MODE"] = args.mode
    sys.path.insert(0, str(BACKEND_DIR))

    from jane_avenue.contracts import AnalysisOptions, AnalysisRequest
    from jane_avenue.orchestrator import create_analysis, run_analysis
    from jane_avenue.store import AnalysisStore

    store = AnalysisStore(args.db)
    request = AnalysisRequest(query=args.query, options=AnalysisOptions(
        run_research=not args.no_research, use_research_cache=not args.no_cache, monte_carlo_draws=args.draws))
    t0 = time.perf_counter()
    created = create_analysis(store, request)
    analysis = run_analysis(store, created.analysis_id)
    elapsed = time.perf_counter() - t0
    summary = _summary(analysis, elapsed, len(store.events_after(analysis.analysis_id)))
    store.close()

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        _print_tables(summary)

    if analysis.status != "completed":
        return 1
    if args.expect_approved and (analysis.verification is None or not analysis.verification.forecast_allowed):
        print("\nFAIL: forecast was withheld but --expect-approved was given", file=sys.stderr)
        return 2
    if args.max_seconds is not None and elapsed > args.max_seconds:
        print(f"\nFAIL: took {elapsed:.2f}s, over --max-seconds {args.max_seconds}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
