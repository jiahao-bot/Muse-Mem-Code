"""Cached, resumable benchmark runner for MUSE-Mem datasets."""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

class BenchmarkRunner:
    def __init__(self, output_dir: str, answer_concurrency: int = 4):
        self.root = Path(output_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.answer_concurrency = max(1, answer_concurrency)

    @staticmethod
    def cache_key(case: dict, method_config: dict) -> str:
        payload = json.dumps({"case": case, "config": method_config}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()[:24]

    def run(self, cases: list[dict], method_config: dict,
            build: Callable[[dict], str | None], answer: Callable[[dict], dict]) -> dict:
        build_dir = self.root / "build"
        build_dir.mkdir(exist_ok=True)
        for case in cases:
            key = self.cache_key(case, method_config)
            marker = build_dir / f"{key}.json"
            if not marker.exists():
                snapshot = build(case)
                marker.write_text(json.dumps({"case_id": case["case_id"], "snapshot_id": snapshot}), encoding="utf-8")
        rows_path = self.root / "output.json"
        existing = {}
        if rows_path.exists():
            existing = {row["case_id"]: row for row in json.loads(rows_path.read_text(encoding="utf-8"))}
        pending = [case for case in cases if case["case_id"] not in existing or existing[case["case_id"]].get("error")]
        with ThreadPoolExecutor(max_workers=self.answer_concurrency) as pool:
            futures = {pool.submit(answer, case): case for case in pending}
            for future in as_completed(futures):
                case = futures[future]
                try:
                    existing[case["case_id"]] = {"case_id": case["case_id"], **future.result()}
                except Exception as exc:
                    existing[case["case_id"]] = {"case_id": case["case_id"], "error": str(exc)}
                rows_path.write_text(json.dumps(list(existing.values()), ensure_ascii=False, indent=2), encoding="utf-8")
        failures = sum(bool(row.get("error")) for row in existing.values())
        summary = {"method": "MUSE-Mem", "cases": len(cases), "completed": len(existing) - failures,
                   "failures": failures, "answer_concurrency": self.answer_concurrency,
                   "output": str(rows_path)}
        (self.root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary
