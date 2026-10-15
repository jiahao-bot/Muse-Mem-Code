"""Runtime configuration."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    database: str = "runs/muse_mem.db"
    provider: str = "deterministic"
    model: str = "deterministic"
    base_url: str = ""
    api_key: str = ""
    temperature: float = 1.0
    max_tokens: int | None = None
    governance_mode: str = "full"
    governance_batch_size: int = 50
    retrieval_rounds: int = 10
    build_concurrency: int = 1
    answer_concurrency: int = 4

    @classmethod
    def load(cls, path: str | None = None) -> "Config":
        values = {}
        if path:
            values = json.loads(Path(path).read_text(encoding="utf-8"))
        values.setdefault("base_url", os.getenv("MUSE_LLM_BASE_URL", ""))
        values.setdefault("api_key", os.getenv("MUSE_LLM_API_KEY", ""))
        if model := os.getenv("MUSE_LLM_MODEL"):
            values["model"] = model
        else:
            values.setdefault("model", "deterministic")
        return cls(**values)
