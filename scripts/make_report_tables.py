"""Write the report's LaTeX tables (docs/report/tables/*.tex) from the same builders as the README tables, so the
report and the README always show the same numbers from evals/results/."""
from __future__ import annotations

from common.config import ROOT
from scripts.make_tables import PENDING, SECTIONS

OUT = ROOT / "docs" / "report" / "tables"


def latex_escape(text: str) -> str:
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_"),
                 ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\^{}")):
        text = text.replace(a, b)
    return text.replace("`", "")


def to_latex(markdown: str) -> str:
    if markdown.strip() == PENDING:
        return r"\emph{Not measured yet.}"
    lines = markdown.strip().splitlines()
    notes = [line for line in lines if not line.startswith("|")]
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines if line.startswith("|")
            and not set(line) <= set("|-: ")]
    if not rows:
        return latex_escape(markdown)
    columns = len(rows[0])
    body = [r"\begin{tabular}{l" + "r" * (columns - 1) + "}", r"\toprule",
            " & ".join(rf"\textbf{{{latex_escape(c)}}}" for c in rows[0]) + r" \\", r"\midrule"]
    body += [" & ".join(latex_escape(c) for c in row) + r" \\" for row in rows[1:]]
    body += [r"\bottomrule", r"\end{tabular}"]
    text = "\n".join(body)
    if notes:
        text += "\n\n{\\footnotesize " + latex_escape(" ".join(n for n in notes if n.strip())) + "}"
    return r"\resizebox{\linewidth}{!}{%" + "\n" + text.split("\n\n")[0] + "}" + (
        "\n" + text.split("\n\n", 1)[1] if "\n\n" in text else "")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, builder in SECTIONS.items():
        (OUT / f"{name}.tex").write_text(to_latex(builder()) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(SECTIONS)} tables to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
