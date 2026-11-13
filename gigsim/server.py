"""Run GigSim:  python -m gigsim.server   (port from GIGSIM_PORT, default 8081)"""
from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run("gigsim.app:create_app", factory=True, host=os.environ.get("GIGSIM_HOST", "0.0.0.0"),
                port=int(os.environ.get("GIGSIM_PORT", "8081")))


if __name__ == "__main__":
    main()
