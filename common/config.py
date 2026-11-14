"""Load agent/config.yaml once, with a few environment overrides."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    path = Path(os.environ.get("GIGBID_CONFIG", ROOT / "agent" / "config.yaml"))
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if os.environ.get("MARKETPLACE_MODE"):
        config["marketplace"]["mode"] = os.environ["MARKETPLACE_MODE"]
    if os.environ.get("GIGSIM_BASE_URL"):
        config["marketplace"]["gigsim_base_url"] = os.environ["GIGSIM_BASE_URL"]
    if os.environ.get("MODEL_PROFILE"):
        config["models"]["profile"] = os.environ["MODEL_PROFILE"]
    if os.environ.get("RAG_VARIANT"):
        config["rag"]["variant"] = os.environ["RAG_VARIANT"]
    if os.environ.get("WRITER_STRATEGY"):
        config["writer"]["strategy"] = os.environ["WRITER_STRATEGY"]
    return config


def defences_on() -> bool:
    """Injection defences (delimiting, pattern rules, untrusted-data instructions). Off only for the before/after
    attack measurement in evals/runners/injection_eval.py."""
    return os.environ.get("GIGBID_DEFENCES", "on") != "off"


def model_profile(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """The active model profile, with `inherit` resolved (paid inherits the open profile's nodes)."""
    config = config or load_config()
    profiles = config["models"]["profiles"]
    profile = dict(profiles[config["models"]["profile"]])
    parent = profile.get("inherit")
    if parent:
        base = dict(profiles[parent])
        profile = {**base, **profile, "nodes": {**base["nodes"], **profile.get("nodes", {})}}
    return profile


def load_policy() -> dict[str, Any]:
    path = ROOT / load_config()["platform"]["policy_file"]
    return yaml.safe_load(path.read_text(encoding="utf-8"))
