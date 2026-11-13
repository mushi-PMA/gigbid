"""Render both graphs from code (Mermaid source and PNG when the renderer is reachable) into docs/images."""
from __future__ import annotations

from agent.graphs.bid_graph import compile_bid_graph
from agent.graphs.conversation_graph import compile_conversation_graph
from common.config import ROOT

OUT = ROOT / "docs" / "images"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, graph in (("bid_graph", compile_bid_graph()), ("conversation_graph", compile_conversation_graph())):
        drawable = graph.get_graph()
        (OUT / f"{name}.mmd").write_text(drawable.draw_mermaid(), encoding="utf-8")
        try:
            (OUT / f"{name}.png").write_bytes(drawable.draw_mermaid_png())
            print(f"wrote docs/images/{name}.png")
        except Exception as error:  # the PNG renderer needs network access; the .mmd file always works
            print(f"wrote docs/images/{name}.mmd (PNG skipped: {type(error).__name__})")


if __name__ == "__main__":
    main()
