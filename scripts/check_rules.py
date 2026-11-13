"""Repository rules enforced in CI:

1. no secrets in tracked files (key patterns, private keys, a tracked .env);
2. nothing under gigsim/ changed (checksums in gigsim/MANIFEST.sha256);
3. every prompt lives in agent/prompts/ (no prompt-like string literals in Python code, and every model call takes
   its system prompt from load_prompt);
4. every number in README.md and docs/RESULTS.md comes from evals/results/ (regenerating the tables changes nothing).

    python -m scripts.check_rules            # all checks
    python -m scripts.check_rules --freeze-gigsim   # write the manifest (only when GigSim is intentionally updated)
"""
from __future__ import annotations

import ast
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "gigsim" / "MANIFEST.sha256"
SECRET_PATTERNS = [
    re.compile(r"ABSK[A-Za-z0-9+/=]{40,}"),                 # Bedrock API keys
    re.compile(r"AKIA[0-9A-Z]{16}"),                        # AWS access key ids
    re.compile(r"\bsk-[A-Za-z0-9]{32,}"),                   # OpenAI-style keys
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}"),            # GitHub tokens
    re.compile(r"\bgsk_[A-Za-z0-9]{40,}"),                  # Groq keys
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),                  # Google API keys
]
PROMPT_PHRASES = re.compile(r"\b(You are (the|a) |You check |You split |Rewrite only|Answer with one JSON|"
                            r"Return only the)", re.I)
PROMPT_DIRS = ["agent", "rag", "apps/api", "worker", "mcp_servers", "common", "evals/runners"]


def tracked_files() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [ROOT / line for line in out.splitlines() if line]


def check_secrets() -> list[str]:
    problems = []
    for path in tracked_files():
        if path.name == ".env":
            problems.append(f"{path.relative_to(ROOT)} must never be committed")
        if path.suffix in {".png", ".pdf", ".db", ".npy", ".pkl", ".ico", ".woff2"} or not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                problems.append(f"possible secret in {path.relative_to(ROOT)} ({pattern.pattern[:20]}...)")
    return problems


def gigsim_hashes() -> dict[str, str]:
    files = sorted(p for p in (ROOT / "gigsim").rglob("*") if p.is_file() and p.name != "MANIFEST.sha256"
                   and "__pycache__" not in p.parts and p.suffix != ".db")
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for p in files}


def check_gigsim() -> list[str]:
    if not MANIFEST.exists():
        return ["gigsim/MANIFEST.sha256 missing (run with --freeze-gigsim once)"]
    expected = dict(line.split("  ", 1)[::-1] for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line)
    actual = gigsim_hashes()
    problems = [f"gigsim changed: {name}" for name in sorted(set(expected) | set(actual))
                if expected.get(name) != actual.get(name)]
    return problems


def check_prompts() -> list[str]:
    problems = []
    for folder in PROMPT_DIRS:
        for path in (ROOT / folder).rglob("*.py"):
            if "tests" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                          if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                          and node.body and isinstance(node.body[0], ast.Expr)
                          and isinstance(node.body[0].value, ast.Constant)}
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings \
                        and PROMPT_PHRASES.search(node.value):
                    problems.append(f"inline prompt text in {path.relative_to(ROOT)}:{node.lineno}; move it to "
                                    f"agent/prompts/")
    return problems


def check_results_in_sync() -> list[str]:
    before = {p: p.read_text(encoding="utf-8") for p in [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]
              if p.exists()}
    subprocess.run([sys.executable, "-m", "scripts.make_tables"], cwd=ROOT, check=True, capture_output=True)
    return [f"{p.relative_to(ROOT)} has numbers not generated from evals/results (run make_tables and commit)"
            for p, text in before.items() if p.read_text(encoding="utf-8") != text]


def check_openapi() -> list[str]:
    from scripts.export_openapi import PATH, current

    if not PATH.exists() or PATH.read_text(encoding="utf-8") != current():
        return ["apps/api/openapi.json is out of date (run python -m scripts.export_openapi, then npm run gen:api)"]
    return []


def main() -> None:
    if "--freeze-gigsim" in sys.argv:
        MANIFEST.write_text("".join(f"{h}  {n}\n" for n, h in gigsim_hashes().items()), encoding="utf-8")
        print(f"wrote {MANIFEST.relative_to(ROOT)}")
        return
    problems = check_secrets() + check_gigsim() + check_prompts() + check_openapi() + check_results_in_sync()
    if problems:
        print("Rule check failed:\n- " + "\n- ".join(problems))
        sys.exit(1)
    print("all repository rules pass")


if __name__ == "__main__":
    main()
