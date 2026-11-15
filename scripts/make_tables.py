"""Regenerate every results table from evals/results/*.json into docs/RESULTS.md and the README.

Tables are written between `<!-- results:NAME -->` and `<!-- /results:NAME -->` markers, so no number in the README
or the report is typed by hand. A table whose results file does not exist yet says so instead of showing numbers.

    python -m scripts.make_tables
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from common.config import ROOT

RESULTS = ROOT / "evals" / "results"
PENDING = "_Not measured yet: run `make eval` (needs a model key)._"


def load(name: str) -> dict | None:
    path = RESULTS / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def fmt(value, digits: int = 3, pct: bool = False) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if pct:
        return f"{value * 100:.1f}%"
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def table(header: list[str], rows: list[list[str]]) -> str:
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] +
                     ["| " + " | ".join(r) + " |" for r in rows])


RAG_FILES = ("rag_variants_offline", "rag_variants_model", "rag_variants_model_late")


def rag_variants() -> str:
    parts = [load(name) for name in RAG_FILES]
    results = [r for p in parts if p for r in p["results"]]
    if not results:
        return PENDING
    seen, rows = set(), []
    for r in results:
        if r["variant"] in seen:
            continue
        seen.add(r["variant"])
        o = r["overall"]
        rows.append([r["variant"], fmt(o["recall@5"]), fmt(o["recall@5_capped"]), fmt(o["mrr"]), fmt(o["ndcg@10"]),
                     fmt(o.get("p95_seconds"), 2), str(r["n"])])
    note = "Unit: a portfolio project (its case study, README, code and proposals). Dev set, all three personas."
    return note + "\n\n" + table(["Variant", "Recall@5", "Recall@5 (capped)", "MRR", "nDCG@10",
                                  "p95 retrieval (s)", "Jobs"], rows)


def main_results() -> str:
    """The brief's B5 table: V0 against the shipped pipeline."""
    rag = {r["variant"]: r for p in (load(name) for name in RAG_FILES) if p for r in p["results"]}
    v0, best = load("proposals_v0"), load("proposals_best")
    shipped = ((best or {}).get("meta", {}).get("rag_variant") or "").replace("_", "+")
    if not (v0 and best):
        return PENDING
    rows = []
    for label, variant, proposals in (("V0", "v0", v0), (f"Best ({shipped})", shipped, best)):
        retrieval = rag.get(variant, {}).get("overall", {})
        rows.append([label, fmt(retrieval.get("recall@5")), fmt(retrieval.get("ndcg@10")),
                     fmt(proposals["unsupported_claims_per_proposal"]["after_verification"], 2),
                     fmt(proposals["judge_overall"], 2), fmt(proposals["gigsim_reply_rate"], pct=True),
                     fmt(proposals["per_proposal"]["p95_seconds"], 1), fmt(proposals["per_proposal"]["mean_usd"], 5)])
    return table(["Variant", "Evidence Recall@5", "nDCG@10", "Unsupported claims per proposal", "Judge score",
                  "GigSim reply rate", "p95 latency (s)", "Cost per proposal (USD)"], rows)


def decisions() -> str:
    d = load("decisions")
    if not d:
        return PENDING
    rows = [["Bid-or-skip F1", fmt(d["bid_or_skip"]["f1"])], ["Bid-or-skip accuracy", fmt(d["bid_accuracy"])],
            ["Scam precision / recall", f"{fmt(d['scam_detection']['precision'])} / "
                                        f"{fmt(d['scam_detection']['recall'])}"],
            ["Injection detection recall", fmt(d["injection_detection"]["recall"])],
            ["Price inside the fair band", fmt(d["price_inside_fair_band"], pct=True)],
            ["p50 / p95 latency per job analysed (s)", f"{fmt(d['per_job_analysed']['p50_seconds'], 1)} / "
                                                        f"{fmt(d['per_job_analysed']['p95_seconds'], 1)}"],
            ["Cost per job analysed (USD)", fmt(d["per_job_analysed"]["mean_usd"], 5)],
            ["Jobs", str(d["n"])]]
    return table(["Metric (dev set)", "Value"], rows)


def claims() -> str:
    best = load("proposals_best")
    if not best:
        return PENDING
    u = best["unsupported_claims_per_proposal"]
    r = best["unsupported_claim_rate"]
    return table(["", "Before verification", "After verification"],
                 [["Unsupported claims per proposal", fmt(u["before_verification"], 2),
                   fmt(u["after_verification"], 2)],
                  ["Unsupported claim rate", fmt(r["before"], pct=True), fmt(r["after"], pct=True)]])


def architectures() -> str:
    a = load("architecture_comparison")
    if not a:
        return PENDING
    rows = []
    for name, label in (("single_react", "(a) one ReAct agent"), ("supervisor", "(b) prebuilt supervisor"),
                        ("graph", "(c) GigBid graph")):
        d = a["designs"][name]
        rows.append([label, f"{d['n']} of {d['n'] + d['errors']}", fmt(d["bid_or_skip_accuracy"]),
                     fmt(d["unsupported_claims_per_proposal"], 2),
                     str(d["violations_caught"]), str(d["violations_left_in_output"]),
                     f"{d['scams_bid_on']} / {d['injections_bid_on']}", fmt(d["gigsim_reply_rate"], pct=True),
                     str(d["mean_tokens"]), fmt(d["p95_seconds"], 1)])
    return table(["Design", "Jobs finished", "Bid-or-skip accuracy", "Unsupported claims", "Violations caught",
                  "Violations left", "Scams / injections bid on", "Reply rate", "Tokens per job", "p95 latency (s)"],
                 rows) + "\n\nA run that crashed on a provider rate limit is left out of every number in its row."


def tools() -> str:
    t = load("tool_granularity")
    if not t:
        return PENDING
    rows = [[name, str(r["tools"]), fmt(r["selection_accuracy"], pct=True), fmt(r["argument_accuracy"], pct=True),
             str(r["tokens_per_task"])] for name, r in t["results"].items()]
    return table(["Tool set", "Tools", "Selection accuracy", "Argument accuracy", "Tokens per task"], rows)


def injection() -> str:
    i = load("injection")
    if not i:
        return PENDING
    return table(["", "Attack success rate", "Detected", "Drafted"],
                 [[label, fmt(i[key]["attack_success_rate"], pct=True), fmt(i[key]["detected_rate"], pct=True),
                   fmt(i[key]["drafted_rate"], pct=True)]
                  for label, key in (("Defences off", "before_defences"), ("Defences on", "after_defences"))])


def models() -> str:
    m = load("model_comparison")
    if not m:
        return PENDING
    rows = [[p, fmt(r["bid_or_skip_f1"]), fmt(r["judge_overall"], 2), fmt(r["unsupported_after"], 2),
             fmt(r["gigsim_reply_rate"], pct=True), fmt(r["per_proposal"]["p95_seconds"], 1),
             fmt(r["per_proposal"]["mean_usd"], 5) if r["judge_overall"] is not None and r["per_proposal"]["mean_usd"]
             else "n/a"] for p, r in m["results"].items()]
    return table(["Profile", "Bid F1", "Judge", "Unsupported", "Reply rate", "p95 per proposal (s)",
                  "USD per proposal"], rows) + \
        "\n\nn/a in the proposal columns: no proposal finished for that profile (the free Gemini endpoint " \
        "returned many server errors during the run). Gemma has no list price in `agent/config.yaml`, so its " \
        "cost is n/a, not zero."


def x2() -> str:
    x = load("x2_ab_test")
    if not x:
        return PENDING
    return table(["Arm", "Reply rate", "Only this arm replied"],
                 [["A: problem first", fmt(x["reply_rate_A"], pct=True), str(x["only_A_replied"])],
                  ["B: credentials first", fmt(x["reply_rate_B"], pct=True), str(x["only_B_replied"])]]) + \
        f"\n\nPaired jobs: {x['paired_jobs']}; exact McNemar p = {x['mcnemar_exact_p']}; two-proportion z-test " \
        f"p = {x['two_proportion_z_p']}."


def holdout() -> str:
    h = load("holdout")
    if not h:
        return PENDING
    # latency needs live model calls: when the result file comes from a replay of the cache, the latency of the
    # first, fully live holdout run is read from its archived console output
    console = RESULTS / "archive" / "holdout_first_run_console.txt"
    live = dict(re.findall(r"^(\w+): declared [\d.]+, measured ([\d.]+)", console.read_text(encoding="utf-8"), re.M)) \
        if console.exists() else {}
    rows, from_archive = [], False
    for k in h["declared"]:
        measured = h["measured"][k]
        if measured is None and k in live:
            measured, from_archive = float(live[k]), True
        verdict = "not measured" if measured is None else "met" if measured <= h["declared"][k] else "missed"
        rows.append([k.replace("_", " "), fmt(h["declared"][k], 4), fmt(measured, 4), verdict])
    note = ("\n\nLatency rows come from the first holdout run, whose model calls were all live "
            "(`evals/results/archive/holdout_first_run_console.txt`); the other rows from `holdout.json`."
            if from_archive else "")
    return table(["Budget", "Declared", "Measured (holdout)", "Verdict"], rows) + note


def ablation() -> str:
    """The shipped retrieval with one component removed at a time (no model calls, dev set)."""
    a = load("ablation")
    if not a:
        return PENDING
    full = a["results"]["full"]["overall"]
    rows = [[label, fmt(r["overall"]["recall@5"]), fmt(r["overall"]["ndcg@10"]),
             fmt(r["overall"]["ndcg@10"] - full["ndcg@10"], 3) if label != "full" else "",
             str(r["n"])] for label, r in a["results"].items()]
    return table([f"Shipped ({a['best']})", "Recall@5", "nDCG@10", "Change in nDCG@10", "Jobs"], rows)


def breakdown() -> str:
    """V0 against the shipped retrieval by persona, job type and number of requirements (dev set)."""
    offline = load("rag_variants_offline")
    best = (load("proposals_best") or {}).get("meta", {}).get("rag_variant", "v2_v4").replace("_", "+")
    if not offline:
        return PENDING
    by_variant = {r["variant"]: r for r in offline["results"]}
    if "v0" not in by_variant or best not in by_variant:
        return PENDING
    v0, shipped = by_variant["v0"], by_variant[best]
    rows = []
    for group, label in (("by_persona", "persona"), ("by_requirements", "requirements"), ("by_job_type", "job type")):
        for name, metrics in sorted(shipped[group].items()):
            base = v0[group].get(name)
            if base:
                rows.append([f"{label}: {name}", str(metrics["n"]), fmt(base["recall@5"]), fmt(metrics["recall@5"]),
                             fmt(base["ndcg@10"]), fmt(metrics["ndcg@10"])])
    return table(["Group", "Jobs", "V0 Recall@5", f"{best} Recall@5", "V0 nDCG@10", f"{best} nDCG@10"], rows)


def failures() -> str:
    f = load("failures")
    if not f:
        return PENDING
    counts = sorted(f["counts"].items(), key=lambda item: -item[1])
    return table(["Failure category", "Dev jobs"], [[name, str(count)] for name, count in counts])


SECTIONS = {"main": main_results, "rag": rag_variants, "decisions": decisions, "claims": claims,
            "architectures": architectures, "tools": tools, "injection": injection, "models": models, "x2": x2,
            "holdout": holdout, "failures": failures, "ablation": ablation, "breakdown": breakdown}


def fill(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for name, builder in SECTIONS.items():
        pattern = re.compile(rf"(<!-- results:{name} -->)(.*?)(<!-- /results:{name} -->)", re.S)
        body = builder()
        text = pattern.sub(lambda m, body=body: f"{m.group(1)}\n{body}\n{m.group(3)}", text)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    results_md = ROOT / "docs" / "RESULTS.md"
    if not results_md.exists():
        results_md.write_text("# Results\n\nGenerated by `python -m scripts.make_tables` from evals/results/.\n\n" +
                              "\n\n".join(f"## {name}\n\n<!-- results:{name} -->\n<!-- /results:{name} -->"
                                          for name in SECTIONS) + "\n", encoding="utf-8", newline="\n")
    for path in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]:
        if path.exists() and "<!-- results:" in path.read_text(encoding="utf-8"):
            fill(path)
            print(f"updated {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
