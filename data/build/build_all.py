"""Build all seed and evaluation data.   Run:  python -m data.build.build_all

Fixed seed 2026, deterministic. Needs data/raw/ (python -m data.build.download).
"""
from __future__ import annotations

import json
import random
import shutil
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from data.build import gold, jobs_seed, persona_build, real_jobs
from data.build.persona_defs import PERSONAS

SEED = 2026
ROOT = Path(__file__).resolve().parents[2]
PERSONA_DIR = ROOT / "data" / "personas"
GIGSIM_DIR = ROOT / "data" / "gigsim"
EVAL_DIR = ROOT / "evals" / "datasets"

# job mix per evaluation set: real relevant, real partly relevant, real unrelated, then synthetic kinds
DEV_MIX = {"pos": 86, "partial": 40, "zero": 34, "injection": 12, "scam": 14, "duplicate": 14}
HOLDOUT_MIX = {"pos": 21, "partial": 10, "zero": 8, "injection": 3, "scam": 4, "duplicate": 4}
LIVE_PER_PERSONA = {"pos": 150, "partial": 60}
LIVE_UNRELATED = 270
LIVE_EXTRA = {"scam": 64, "injection": 42, "duplicate": 53}
HISTORY_QUOTA = {"AI & Machine Learning": 450, "Data Analytics & BI": 450, "Web Development": 450}
HISTORY_OTHER = 150


class Picker:
    """Draws real jobs without reuse across the dev set, the hold-out set, the live stream and the history."""

    def __init__(self, jobs: list[dict], coverage: list[dict[str, float]], rng: random.Random):
        self.jobs, self.coverage, self.rng = jobs, coverage, rng
        self.used: set[int] = set()
        self.order = list(range(len(jobs)))
        rng.shuffle(self.order)

    def take(self, n: int, keep) -> list[dict]:
        chosen = []
        for index in self.order:
            if len(chosen) == n:
                break
            if index not in self.used and keep(index):
                self.used.add(index)
                chosen.append(self.jobs[index])
        if len(chosen) < n:
            raise RuntimeError(f"only found {len(chosen)} of {n} jobs")
        return chosen

    def rest(self) -> list[dict]:
        return [job for index, job in enumerate(self.jobs) if index not in self.used]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")


def renumber(jobs: list[dict], prefix: str) -> None:
    """Sort by posted_at and give stable ids; fix duplicate_of and urls."""
    jobs.sort(key=lambda j: (j["posted_at"], j["job_id"]))
    mapping = {job["job_id"]: f"{prefix}-{i + 1:04d}" for i, job in enumerate(jobs)}
    for job in jobs:
        job["job_id"] = mapping[job["job_id"]]
        job["url"] = f"https://gigsim.local/jobs/{job['job_id']}"
        if job["duplicate_of"]:
            job["duplicate_of"] = mapping[job["duplicate_of"]]


def add_duplicates(base: list[dict], count: int, rng: random.Random, latest: datetime) -> list[dict]:
    """Reposts of earlier regular jobs. Originals are picked from the first part of the stream."""
    originals = [j for j in base if j["kind"] == "regular" and j["posted_at"] < jobs_seed.iso(latest)]
    dups = []
    for number, original in enumerate(rng.sample(originals, count)):
        start = datetime.strptime(original["posted_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC)
        when = min(start + timedelta(days=rng.randint(1, 8), hours=rng.randint(0, 20)), jobs_seed.STREAM_END)
        dups.append(jobs_seed.make_duplicate(original, f"tmp-dup-{number}", when, rng))
    return dups


def build_eval_set(persona: str, mix: dict, picker: Picker, rng: random.Random, book: jobs_seed.ClientBook,
                   skillsets: dict, prefix: str) -> list[dict]:
    """Jobs (without gold) for one persona and one evaluation set."""
    cov = picker.coverage
    others = [p for p in skillsets if p != persona]

    def pos(i): return cov[i][persona] >= 0.5
    def partial(i): return 0 < cov[i][persona] < 0.5
    def zero_hard(i): return cov[i][persona] == 0 and any(cov[i][o] >= 0.5 for o in others)
    def zero_easy(i): return all(cov[i][p] == 0 for p in skillsets)

    jobs = []
    groups = [(mix["pos"], pos), (mix["partial"], partial), (mix["zero"] // 2, zero_hard),
              (mix["zero"] - mix["zero"] // 2, zero_easy)]
    for count, rule in groups:
        for real in picker.take(count, lambda i, rule=rule: rule(i)):
            when = jobs_seed.random_time(rng, jobs_seed.STREAM_START, jobs_seed.STREAM_END)
            jobs.append(jobs_seed.make_job(real, f"tmp-{len(jobs)}", when, False, rng, book))
    for real in picker.take(mix["injection"], lambda i: pos(i) or partial(i)):
        when = jobs_seed.random_time(rng, jobs_seed.STREAM_START, jobs_seed.STREAM_END)
        jobs.append(jobs_seed.make_injection(real, f"tmp-inj-{len(jobs)}", when, rng, book))
    for number in range(mix["scam"]):
        when = jobs_seed.random_time(rng, jobs_seed.STREAM_START, jobs_seed.STREAM_END)
        jobs.append(jobs_seed.make_scam(f"tmp-scam-{number}", when, rng, book))
    regular = [j for j in jobs if j["kind"] == "regular"]
    jobs += add_duplicates(regular, mix["duplicate"], rng, jobs_seed.STREAM_END)
    renumber(jobs, prefix)
    return jobs


def main() -> None:
    started = time.time()
    rng = random.Random(SEED)
    print("loading real jobs ...")
    jobs = real_jobs.load_kaggle_jobs()
    print(f"  {len(jobs)} clean real jobs in {time.time() - started:.0f}s")

    skillsets = {pid: persona_build.persona_skillset(pdef) for pid, pdef in PERSONAS.items()}
    coverage = []
    for job in jobs:
        core = gold.core_skills(job)
        coverage.append({pid: len([s for s in core if s in sk]) / len(core) for pid, sk in skillsets.items()})
    picker = Picker(jobs, coverage, rng)

    # ---- choose jobs. Order matters: evaluation sets first, then the live stream, then history.
    book = jobs_seed.ClientBook(rng)
    eval_jobs: dict[str, dict[str, list[dict]]] = {"dev": {}, "holdout": {}}
    for persona in PERSONAS:
        short = PERSONAS[persona]["short"]
        eval_jobs["dev"][persona] = build_eval_set(persona, DEV_MIX, picker, rng, book, skillsets, f"dev-{short}")
        eval_jobs["holdout"][persona] = build_eval_set(persona, HOLDOUT_MIX, picker, rng, book, skillsets,
                                                       f"hold-{short}")

    live: list[dict] = []
    for persona in PERSONAS:
        for kind, count in LIVE_PER_PERSONA.items():
            rule = ((lambda i, p=persona: coverage[i][p] >= 0.5) if kind == "pos"
                    else (lambda i, p=persona: 0 < coverage[i][p] < 0.5))
            for real in picker.take(count, rule):
                when = jobs_seed.random_time(rng, jobs_seed.STREAM_START, jobs_seed.STREAM_END)
                live.append(jobs_seed.make_job(real, f"tmp-{len(live)}", when, False, rng, book))
    for real in picker.take(LIVE_UNRELATED, lambda i: all(coverage[i][p] == 0 for p in skillsets)):
        when = jobs_seed.random_time(rng, jobs_seed.STREAM_START, jobs_seed.STREAM_END)
        live.append(jobs_seed.make_job(real, f"tmp-{len(live)}", when, False, rng, book))
    for real in picker.take(LIVE_EXTRA["injection"], lambda i: any(coverage[i][p] > 0 for p in skillsets)):
        when = jobs_seed.random_time(rng, jobs_seed.STREAM_START, jobs_seed.STREAM_END)
        live.append(jobs_seed.make_injection(real, f"tmp-inj-{len(live)}", when, rng, book))
    for number in range(LIVE_EXTRA["scam"]):
        when = jobs_seed.random_time(rng, jobs_seed.STREAM_START, jobs_seed.STREAM_END)
        live.append(jobs_seed.make_scam(f"tmp-scam-{number}", when, rng, book))
    live += add_duplicates(live, LIVE_EXTRA["duplicate"], rng,
                           jobs_seed.STREAM_END - timedelta(days=6))
    renumber(live, "gs")

    history_real: list[dict] = []
    for category, count in HISTORY_QUOTA.items():
        history_real += picker.take(count, lambda i, c=category: jobs[i]["category"] == c)
    history_real += picker.take(HISTORY_OTHER, lambda i: jobs[i]["category"] not in HISTORY_QUOTA)

    # ---- pricing from everything not used above (the historical pool)
    pool = picker.rest() + history_real
    print(f"pricing pool: {len(pool)} real historical jobs")
    pricing = real_jobs.build_pricing(pool, skillsets)
    write_json(GIGSIM_DIR / "pricing.json", pricing)

    history = []
    for real in history_real:
        when = jobs_seed.random_time(rng, jobs_seed.HISTORY_START, jobs_seed.HISTORY_END)
        history.append(jobs_seed.make_job(real, f"tmp-{len(history)}", when, True, rng, book))
    renumber(history, "hist")

    # ---- personas (proposals are written about pool jobs, not about live or evaluation jobs)
    if PERSONA_DIR.exists():
        shutil.rmtree(PERSONA_DIR)
    summaries = []
    for persona, pdef in PERSONAS.items():
        summaries.append(persona_build.build_persona(pdef, pool, pricing["personas"][persona], PERSONA_DIR, SEED))
        print("  persona", summaries[-1])

    # ---- gigsim files
    write_jsonl(GIGSIM_DIR / "jobs.jsonl", live)
    write_jsonl(GIGSIM_DIR / "historical_jobs.jsonl", history)
    write_json(GIGSIM_DIR / "accounts.json", jobs_seed.make_accounts(list(PERSONAS)))

    # ---- evaluation sets with gold labels
    stats: dict = {"personas": summaries, "live": Counter(j["kind"] for j in live),
                   "history": len(history), "pool": len(pool), "eval": {}}
    for persona in PERSONAS:
        registry = gold.load_registry(PERSONA_DIR / persona)
        for split, filename in (("dev", "dev"), ("holdout", "holdout")):
            items = [{"job": j, "gold": gold.make_gold(j, persona, registry, pricing)} for j in eval_jobs[split][persona]]
            write_json(EVAL_DIR / f"{filename}_{persona}.json", items)
            stats["eval"][f"{split}_{persona}"] = {
                "n": len(items), "bid": sum(i["gold"]["bid"] for i in items),
                "scam": sum(i["gold"]["scam"] for i in items), "injection": sum(i["gold"]["injection"] for i in items),
                "duplicate": sum(i["gold"]["duplicate"] for i in items),
                "avg_relevant_evidence": round(sum(len(i["gold"]["relevant_evidence"]) for i in items) / len(items), 1)}
    book.finalize(pricing)
    write_json(GIGSIM_DIR / "clients.json", list(book.clients.values()))
    stats["clients"] = len(book.clients)

    all_ids = [j["job_id"] for j in live + history] + [j["job_id"] for s in eval_jobs.values()
                                                       for v in s.values() for j in v]
    assert len(all_ids) == len(set(all_ids)), "job ids must be unique across live, history and evaluation sets"
    write_json(GIGSIM_DIR / "seed_stats.json", stats)
    print(json.dumps(stats, indent=1))
    print(f"done in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
