#!/usr/bin/env python3
"""Pipeline diagnostic and evolution analysis script.

Run this after pipeline executions to understand what's improving, what's
regressing, and where the system needs attention.

Usage:
    python scripts/diagnose.py                    # Full diagnostic report
    python scripts/diagnose.py --section runs     # Just recent runs
    python scripts/diagnose.py --section learnings
    python scripts/diagnose.py --section prompts
    python scripts/diagnose.py --section quality
    python scripts/diagnose.py --section health
    python scripts/diagnose.py --run <artifact_id> # Deep-dive a single run
    python scripts/diagnose.py --diff <run_a> <run_b>  # Compare two runs
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_engine():
    from artifactforge.db.session import engine
    return engine


def section_header(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


# -------------------------------------------------------------------------
# Section: Recent Runs
# -------------------------------------------------------------------------
def diagnose_runs(engine, limit: int = 10) -> None:
    from sqlalchemy import text

    section_header("RECENT PIPELINE RUNS")

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT a.id, a.type, a.status, a.created_at, a.completed_at,
                   m.total_duration_ms, m.total_input_tokens,
                   m.estimated_cost_cents, m.evaluation_score
            FROM artifacts a
            LEFT JOIN artifact_metrics m ON m.artifact_id = a.id
            WHERE a.status IN ('completed', 'failed')
            ORDER BY a.created_at DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()

    if not rows:
        print("  No completed runs found.")
        return

    print(f"  {'ID':<38} {'Type':<8} {'Status':<10} {'Duration':>8} {'Tokens':>8} {'Cost':>6} {'Score':>5} {'Date'}")
    print(f"  {'-'*110}")

    for r in rows:
        rid = str(r[0])[:36]
        rtype = (r[1] or "")[:7]
        status = r[2] or ""
        dur = f"{r[5] / 1000:.0f}s" if r[5] else "-"
        tokens = f"{r[6] // 1000}k" if r[6] and r[6] > 999 else str(r[6] or 0)
        cost = f"${r[7] / 100:.2f}" if r[7] else "-"
        score = f"{r[8]:.2f}" if r[8] is not None else "-"
        date = str(r[3])[:16] if r[3] else ""
        print(f"  {rid:<38} {rtype:<8} {status:<10} {dur:>8} {tokens:>8} {cost:>6} {score:>5} {date}")

    # Trend analysis
    completed = [r for r in rows if r[2] == "completed"]
    failed = [r for r in rows if r[2] == "failed"]
    print(f"\n  Completed: {len(completed)}  Failed: {len(failed)}  "
          f"Success rate: {len(completed) / len(rows) * 100:.0f}%")

    if len(completed) >= 2:
        durations = [r[5] for r in completed if r[5]]
        if durations:
            print(f"  Duration range: {min(durations) / 1000:.0f}s - {max(durations) / 1000:.0f}s  "
                  f"Avg: {sum(durations) / len(durations) / 1000:.0f}s")

        scores = [r[8] for r in completed if r[8] is not None]
        if len(scores) >= 2:
            trend = "improving" if scores[0] > scores[-1] else "declining" if scores[0] < scores[-1] else "stable"
            print(f"  Quality trend: {trend} (latest: {scores[0]:.2f}, oldest: {scores[-1]:.2f})")


# -------------------------------------------------------------------------
# Section: Learnings Health
# -------------------------------------------------------------------------
def diagnose_learnings(engine) -> None:
    from sqlalchemy import text

    section_header("LEARNINGS HEALTH")

    with engine.connect() as conn:
        # Overall stats
        total = conn.execute(text("SELECT COUNT(*) FROM learnings")).scalar()
        above_threshold = conn.execute(text(
            "SELECT COUNT(*) FROM learnings WHERE confidence >= 0.7"
        )).scalar()
        validated = conn.execute(text(
            "SELECT COUNT(*) FROM learnings WHERE is_validated = true"
        )).scalar()
        ever_applied = conn.execute(text(
            "SELECT COUNT(*) FROM learnings WHERE times_applied > 0"
        )).scalar()
        effective = conn.execute(text(
            "SELECT COUNT(*) FROM learnings WHERE times_succeeded > 0"
        )).scalar()

        print(f"  Total learnings:        {total}")
        print(f"  Above threshold (0.7):  {above_threshold} ({above_threshold / total * 100:.0f}%)" if total else "")
        print(f"  Human-validated:        {validated}")
        print(f"  Ever applied:           {ever_applied}")
        print(f"  Proven effective:       {effective}")

        # Breakdown by source
        print(f"\n  By source:")
        sources = conn.execute(text(
            "SELECT source, COUNT(*), AVG(confidence)::numeric(4,2) "
            "FROM learnings GROUP BY source ORDER BY COUNT(*) DESC"
        )).fetchall()
        for s in sources:
            print(f"    {s[0]:<25} {s[1]:>3} learnings  avg confidence: {s[2]}")

        # Stale/ineffective learnings
        stale = conn.execute(text("""
            SELECT COUNT(*) FROM learnings
            WHERE times_applied >= 3 AND times_succeeded = 0
        """)).scalar()
        if stale:
            print(f"\n  WARNING: {stale} learnings applied 3+ times with zero successes (candidates for pruning)")

        # Age distribution
        age_90 = conn.execute(text("""
            SELECT COUNT(*) FROM learnings
            WHERE created_at < NOW() - INTERVAL '90 days'
        """)).scalar()
        if age_90:
            print(f"  WARNING: {age_90} learnings older than 90 days (will be excluded from injection)")

        # Top learnings by effectiveness
        top = conn.execute(text("""
            SELECT failure_mode, confidence, times_applied, times_succeeded, source
            FROM learnings
            WHERE times_applied > 0
            ORDER BY confidence DESC
            LIMIT 5
        """)).fetchall()
        if top:
            print(f"\n  Top learnings by confidence:")
            for t in top:
                rate = f"{t[3]}/{t[2]}" if t[2] else "0/0"
                print(f"    [{t[4]}] conf={t[1]:.2f} ({rate} success) {t[0][:70]}")


# -------------------------------------------------------------------------
# Section: Prompt Evolution
# -------------------------------------------------------------------------
def diagnose_prompts(engine) -> None:
    from sqlalchemy import text

    section_header("PROMPT SNAPSHOTS")

    with engine.connect() as conn:
        total = conn.execute(text(
            "SELECT COUNT(*) FROM prompt_snapshots"
        )).scalar()

        if not total:
            print("  No prompt snapshots yet. Run a pipeline to start capturing.")
            return

        print(f"  Total snapshots: {total}")

        # By agent
        by_agent = conn.execute(text("""
            SELECT agent_name, COUNT(*), AVG(response_tokens)::int,
                   AVG(duration_ms)::int, AVG(quality_score)::numeric(4,2)
            FROM prompt_snapshots
            GROUP BY agent_name
            ORDER BY COUNT(*) DESC
        """)).fetchall()
        print(f"\n  {'Agent':<25} {'Calls':>5} {'Avg Tokens':>10} {'Avg ms':>7} {'Avg Quality':>11}")
        print(f"  {'-'*65}")
        for r in by_agent:
            quality = f"{r[4]}" if r[4] is not None else "-"
            print(f"  {r[0]:<25} {r[1]:>5} {r[2] or 0:>10} {r[3] or 0:>7} {quality:>11}")

        # Learnings injection rate
        with_learnings = conn.execute(text(
            "SELECT COUNT(*) FROM prompt_snapshots WHERE learnings_injected IS NOT NULL"
        )).scalar()
        print(f"\n  Snapshots with learnings injected: {with_learnings}/{total}")

        # Quality-scored snapshots (usable for dataset)
        scored = conn.execute(text(
            "SELECT COUNT(*) FROM prompt_snapshots WHERE quality_score IS NOT NULL"
        )).scalar()
        print(f"  Snapshots with quality scores (dataset-ready): {scored}/{total}")

        # Prompt size trends
        recent = conn.execute(text("""
            SELECT agent_name,
                   LENGTH(system_prompt) as sys_len,
                   LENGTH(user_prompt) as usr_len,
                   created_at
            FROM prompt_snapshots
            ORDER BY created_at DESC
            LIMIT 5
        """)).fetchall()
        if recent:
            print(f"\n  Latest prompt sizes:")
            for r in recent:
                print(f"    {r[0]:<25} sys={r[1]:,} chars  user={r[2]:,} chars  {str(r[3])[:16]}")


# -------------------------------------------------------------------------
# Section: Quality Gates
# -------------------------------------------------------------------------
def diagnose_quality(engine) -> None:
    from sqlalchemy import text

    section_header("QUALITY & EVALUATIONS")

    with engine.connect() as conn:
        evals = conn.execute(text("""
            SELECT evaluator, COUNT(*),
                   SUM(CASE WHEN passed THEN 1 ELSE 0 END) as passed,
                   AVG(overall_score)::numeric(4,2),
                   AVG(confidence)::numeric(4,2)
            FROM evaluations
            GROUP BY evaluator
            ORDER BY evaluator
        """)).fetchall()

        if not evals:
            print("  No evaluations recorded.")
            return

        print(f"  {'Evaluator':<25} {'Total':>5} {'Passed':>6} {'Pass%':>5} {'Avg Score':>9} {'Avg Conf':>8}")
        print(f"  {'-'*65}")
        for e in evals:
            pct = f"{e[2] / e[1] * 100:.0f}%" if e[1] else "-"
            print(f"  {e[0]:<25} {e[1]:>5} {e[2]:>6} {pct:>5} {e[3] or '-':>9} {e[4] or '-':>8}")

        # Common issue types from evaluations
        issues = conn.execute(text("""
            SELECT e.issues
            FROM evaluations e
            WHERE e.issues IS NOT NULL AND e.issues != '[]'::jsonb
            ORDER BY e.created_at DESC
            LIMIT 5
        """)).fetchall()

        if issues:
            print(f"\n  Recent evaluation issues:")
            for row in issues:
                if isinstance(row[0], list):
                    for issue in row[0][:2]:
                        severity = issue.get("severity", "?")
                        ptype = issue.get("problem_type", "unknown")
                        print(f"    [{severity}] {ptype}")


# -------------------------------------------------------------------------
# Section: System Health
# -------------------------------------------------------------------------
def diagnose_health(engine) -> None:
    from sqlalchemy import text

    section_header("SYSTEM HEALTH")

    with engine.connect() as conn:
        # Node execution success rates
        nodes = conn.execute(text("""
            SELECT step, COUNT(*),
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as ok,
                   AVG(duration_ms)::int
            FROM executions
            GROUP BY step
            ORDER BY step
        """)).fetchall()

        if nodes:
            print(f"  {'Node':<25} {'Runs':>5} {'OK':>4} {'Fail':>4} {'Avg ms':>7}")
            print(f"  {'-'*50}")
            for n in nodes:
                fail = n[1] - n[2]
                marker = " <-- FAILURES" if fail > 0 else ""
                print(f"  {n[0]:<25} {n[1]:>5} {n[2]:>4} {fail:>4} {n[3] or 0:>7}{marker}")

        # DB table sizes
        print(f"\n  Table sizes:")
        tables = conn.execute(text("""
            SELECT relname, n_live_tup
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
            ORDER BY n_live_tup DESC
        """)).fetchall()
        for t in tables:
            if t[1] > 0:
                print(f"    {t[0]:<25} {t[1]:>6} rows")


# -------------------------------------------------------------------------
# Deep-dive: Single Run
# -------------------------------------------------------------------------
def diagnose_single_run(engine, run_id: str) -> None:
    from sqlalchemy import text

    section_header(f"DEEP DIVE: {run_id[:36]}")

    with engine.connect() as conn:
        # Artifact info
        art = conn.execute(text("""
            SELECT a.type, a.status, a.user_description, a.created_at, a.completed_at,
                   a.verification_status,
                   m.total_duration_ms, m.total_input_tokens, m.estimated_cost_cents,
                   m.evaluation_score
            FROM artifacts a
            LEFT JOIN artifact_metrics m ON m.artifact_id = a.id
            WHERE a.id = :rid
        """), {"rid": run_id}).fetchone()

        if not art:
            print(f"  Run {run_id} not found.")
            return

        print(f"  Type: {art[0]}  Status: {art[1]}  Verification: {art[5]}")
        print(f"  Prompt: {(art[2] or '')[:100]}")
        print(f"  Created: {art[3]}  Completed: {art[4]}")
        dur = f"{art[6] / 1000:.0f}s" if art[6] else "-"
        print(f"  Duration: {dur}  Tokens: {art[7] or 0}  Cost: ${(art[8] or 0) / 100:.2f}  Score: {art[9]}")

        # Node execution timeline
        nodes = conn.execute(text("""
            SELECT step, status, duration_ms, error_message
            FROM executions
            WHERE artifact_id = :rid
            ORDER BY started_at
        """), {"rid": run_id}).fetchall()

        if nodes:
            print(f"\n  Execution timeline:")
            for n in nodes:
                status = "OK" if n[1] == "success" else "FAIL"
                err = f" -- {n[3][:60]}" if n[3] else ""
                print(f"    {n[0]:<25} {status:<5} {n[2] or 0:>6}ms{err}")

        # Prompt snapshots for this run
        snaps = conn.execute(text("""
            SELECT agent_name, model, LENGTH(system_prompt), LENGTH(user_prompt),
                   response_tokens, duration_ms, quality_score,
                   CASE WHEN learnings_injected IS NOT NULL THEN true ELSE false END
            FROM prompt_snapshots
            WHERE artifact_id = :rid
            ORDER BY created_at
        """), {"rid": run_id}).fetchall()

        if snaps:
            print(f"\n  Prompt snapshots ({len(snaps)}):")
            for s in snaps:
                quality = f"q={s[6]:.2f}" if s[6] is not None else ""
                learn = "  +learnings" if s[7] else ""
                print(f"    {s[0]:<25} model={s[1] or '?':<20} sys={s[2]:,} usr={s[3]:,} "
                      f"resp={s[4] or 0} {s[5] or 0:.0f}ms {quality}{learn}")

        # Evaluations for this run
        evals = conn.execute(text("""
            SELECT evaluator, passed, overall_score, confidence
            FROM evaluations
            WHERE artifact_id = :rid
            ORDER BY created_at
        """), {"rid": run_id}).fetchall()

        if evals:
            print(f"\n  Evaluations:")
            for e in evals:
                status = "PASS" if e[1] else "FAIL"
                print(f"    {e[0]:<25} {status}  score={e[2]}  conf={e[3]}")

        # Learnings extracted from this run
        learnings = conn.execute(text("""
            SELECT source, failure_mode, confidence
            FROM learnings
            WHERE artifact_id = :rid
            ORDER BY confidence DESC
        """), {"rid": run_id}).fetchall()

        if learnings:
            print(f"\n  Learnings extracted ({len(learnings)}):")
            for l in learnings:
                print(f"    [{l[0]}] conf={l[2]:.2f} {l[1][:70]}")


# -------------------------------------------------------------------------
# Diff: Compare Two Runs
# -------------------------------------------------------------------------
def diagnose_diff(engine, run_a: str, run_b: str) -> None:
    from sqlalchemy import text

    section_header(f"DIFF: {run_a[:12]}... vs {run_b[:12]}...")

    with engine.connect() as conn:
        # Compare metrics
        metrics = conn.execute(text("""
            SELECT a.id, m.total_duration_ms, m.total_input_tokens,
                   m.estimated_cost_cents, m.evaluation_score
            FROM artifacts a
            JOIN artifact_metrics m ON m.artifact_id = a.id
            WHERE a.id IN (:a, :b)
            ORDER BY a.created_at
        """), {"a": run_a, "b": run_b}).fetchall()

        if len(metrics) == 2:
            ma, mb = metrics
            print(f"  {'Metric':<20} {'Run A':>12} {'Run B':>12} {'Delta':>12}")
            print(f"  {'-'*60}")

            def delta(va, vb, fmt=".0f"):
                if va is None or vb is None:
                    return "-"
                d = vb - va
                return f"{'+' if d > 0 else ''}{d:{fmt}}"

            print(f"  {'Duration (ms)':<20} {ma[1] or 0:>12} {mb[1] or 0:>12} {delta(ma[1], mb[1]):>12}")
            print(f"  {'Tokens':<20} {ma[2] or 0:>12} {mb[2] or 0:>12} {delta(ma[2], mb[2]):>12}")
            print(f"  {'Cost (cents)':<20} {ma[3] or 0:>12.1f} {mb[3] or 0:>12.1f} {delta(ma[3], mb[3], '.1f'):>12}")
            print(f"  {'Eval Score':<20} {ma[4] or 0:>12.2f} {mb[4] or 0:>12.2f} {delta(ma[4], mb[4], '.2f'):>12}")

        # Compare prompt snapshots per agent
        snaps_a = conn.execute(text("""
            SELECT agent_name, LENGTH(system_prompt), LENGTH(user_prompt), response_tokens
            FROM prompt_snapshots WHERE artifact_id = :rid ORDER BY created_at
        """), {"rid": run_a}).fetchall()

        snaps_b = conn.execute(text("""
            SELECT agent_name, LENGTH(system_prompt), LENGTH(user_prompt), response_tokens
            FROM prompt_snapshots WHERE artifact_id = :rid ORDER BY created_at
        """), {"rid": run_b}).fetchall()

        if snaps_a or snaps_b:
            print(f"\n  Prompt size comparison:")
            agents_a = {s[0]: s for s in snaps_a}
            agents_b = {s[0]: s for s in snaps_b}
            all_agents = sorted(set(agents_a.keys()) | set(agents_b.keys()))

            print(f"  {'Agent':<25} {'Sys A':>7} {'Sys B':>7} {'Usr A':>7} {'Usr B':>7} {'Note'}")
            print(f"  {'-'*65}")
            for agent in all_agents:
                sa = agents_a.get(agent)
                sb = agents_b.get(agent)
                sys_a = f"{sa[1]:,}" if sa else "-"
                sys_b = f"{sb[1]:,}" if sb else "-"
                usr_a = f"{sa[2]:,}" if sa else "-"
                usr_b = f"{sb[2]:,}" if sb else "-"
                note = ""
                if sa and sb and sa[1] != sb[1]:
                    note = "SYSTEM CHANGED"
                if sa and sb and sa[2] != sb[2]:
                    note += " USER CHANGED" if note else "USER CHANGED"
                print(f"  {agent:<25} {sys_a:>7} {sys_b:>7} {usr_a:>7} {usr_b:>7} {note}")

            # Show actual diffs for changed prompts
            if snaps_a and snaps_b:
                import difflib
                for agent in all_agents:
                    if agent not in agents_a or agent not in agents_b:
                        continue
                    # Fetch full prompts
                    full_a = conn.execute(text("""
                        SELECT system_prompt, user_prompt FROM prompt_snapshots
                        WHERE artifact_id = :rid AND agent_name = :agent LIMIT 1
                    """), {"rid": run_a, "agent": agent}).fetchone()
                    full_b = conn.execute(text("""
                        SELECT system_prompt, user_prompt FROM prompt_snapshots
                        WHERE artifact_id = :rid AND agent_name = :agent LIMIT 1
                    """), {"rid": run_b, "agent": agent}).fetchone()

                    if full_a and full_b:
                        for label, idx in [("system", 0), ("user", 1)]:
                            lines_a = (full_a[idx] or "").splitlines(keepends=True)
                            lines_b = (full_b[idx] or "").splitlines(keepends=True)
                            diff = list(difflib.unified_diff(
                                lines_a, lines_b,
                                fromfile=f"run_a/{agent}/{label}",
                                tofile=f"run_b/{agent}/{label}",
                                n=1,
                            ))
                            if diff:
                                # Only show first 30 lines of diff to keep output manageable
                                print(f"\n  --- {agent} {label} prompt diff ---")
                                print("  " + "  ".join(diff[:30]))
                                if len(diff) > 30:
                                    print(f"  ... ({len(diff) - 30} more diff lines)")


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Pipeline diagnostic report")
    parser.add_argument("--section", choices=["runs", "learnings", "prompts", "quality", "health"],
                        help="Run only one section")
    parser.add_argument("--run", help="Deep-dive a single run by artifact ID")
    parser.add_argument("--diff", nargs=2, metavar=("RUN_A", "RUN_B"),
                        help="Compare two runs")
    parser.add_argument("--limit", type=int, default=10, help="Limit for recent runs")
    args = parser.parse_args()

    engine = get_engine()

    if args.run:
        diagnose_single_run(engine, args.run)
        return

    if args.diff:
        diagnose_diff(engine, args.diff[0], args.diff[1])
        return

    sections = {
        "runs": lambda: diagnose_runs(engine, args.limit),
        "learnings": lambda: diagnose_learnings(engine),
        "prompts": lambda: diagnose_prompts(engine),
        "quality": lambda: diagnose_quality(engine),
        "health": lambda: diagnose_health(engine),
    }

    if args.section:
        sections[args.section]()
    else:
        for fn in sections.values():
            fn()

        section_header("RECOMMENDATIONS")
        print("  Run `python scripts/diagnose.py --run <id>` to deep-dive a specific run.")
        print("  Run `python scripts/diagnose.py --diff <run_a> <run_b>` to compare two runs.")
        print("  Run `artifactforge learnings prune` to clean up ineffective learnings.")
        print("  Run `artifactforge prompts diff <agent> <run_a> <run_b>` for prompt-level diffs.")


if __name__ == "__main__":
    main()
