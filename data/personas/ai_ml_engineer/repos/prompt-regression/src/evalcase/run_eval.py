import json
import statistics
from pathlib import Path

from .client import ask


def load_cases(path: str) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def judge(question: str, answer: str, reference: str) -> int:
    verdict = ask(
        system="Grade the answer against the reference. Reply with 1 if correct and 0 if not.",
        user=f"Question: {question}\nReference: {reference}\nAnswer: {answer}",
        temperature=0,
    )
    return 1 if verdict.strip().startswith("1") else 0


def run(path: str, prompt_template: str) -> dict:
    scores = []
    for case in load_cases(path):
        answer = ask(system=prompt_template, user=case["question"], temperature=0)
        scores.append(judge(case["question"], answer, case["reference"]))
    return {"n": len(scores), "accuracy": statistics.mean(scores)}
