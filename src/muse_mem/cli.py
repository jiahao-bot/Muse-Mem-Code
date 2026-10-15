"""Command-line entry point for MUSE-Mem."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from .config import Config
from .models import Message
from .llm import RuleBasedLLM, OpenAICompatibleLLM
from .storage import Database, EpisodicMemory, SemanticMemory
from .gates import PerceptionGate, GovernanceGate, RetrievalGate, AppendOnlyWriter
from .runtime import MuseRuntime

def build_runtime(config: Config) -> tuple[MuseRuntime, Database, EpisodicMemory, SemanticMemory]:
    prompt_root = Path(__file__).with_name("prompts")
    if config.provider == "rule_based":
        llm = RuleBasedLLM()
    elif config.provider == "openai_compatible":
        llm = OpenAICompatibleLLM(config.base_url, config.api_key, config.model,
                                  temperature=config.temperature, max_tokens=config.max_tokens)
    else:
        raise ValueError(f"unsupported provider: {config.provider}")
    db = Database(config.database)
    episodic, semantic = EpisodicMemory(db), SemanticMemory(db)
    perception = PerceptionGate(llm, episodic, str(prompt_root / "perception.txt"))
    if config.governance_mode == "append_only":
        governance = AppendOnlyWriter(db, episodic)
    elif config.governance_mode == "full":
        governance = GovernanceGate(llm, db, episodic, semantic,
                                    str(prompt_root / "governance.txt"),
                                    batch_size=config.governance_batch_size)
    else:
        raise ValueError(f"unsupported governance_mode: {config.governance_mode}")
    retrieval = RetrievalGate(llm, semantic, episodic, str(prompt_root / "retrieval.txt"), config.retrieval_rounds)
    return MuseRuntime(perception, governance, retrieval, config.build_concurrency), db, episodic, semantic

def load_case(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def sessions_from_case(case: dict) -> list[list[Message]]:
    return [[Message(**message) for message in session] for session in case["sessions"]]

def run_command(args: argparse.Namespace) -> None:
    config = Config.load(args.config)
    runtime, db, episodic, semantic = build_runtime(config)
    try:
        case = load_case(args.input)
        snapshot = runtime.construct(case["namespace"], sessions_from_case(case), case["question_date"])
        answers = []
        for question in case.get("questions", []):
            result = runtime.answer(case["namespace"], question["question"], case["question_date"])
            answers.append({"question_id": question["question_id"], "question": question["question"], **result.__dict__})
        output = {"namespace": case["namespace"], "snapshot_id": snapshot,
                  "routing_index": semantic.routing_index(case["namespace"]), "answers": answers}
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "ok", "output": args.output, "answers": len(answers)}))
    finally:
        db.close()

def inspect_command(args: argparse.Namespace) -> None:
    config = Config.load(args.config)
    _, db, episodic, semantic = build_runtime(config)
    try:
        result = {"namespace": args.namespace, "core": semantic.core(args.namespace),
                  "routing_index": semantic.routing_index(args.namespace),
                  "entries": [entry.__dict__ for entry in semantic.all_entries(args.namespace)],
                  "signals": episodic.existing_signals(args.namespace)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()

def main() -> None:
    parser = argparse.ArgumentParser(prog="muse-mem", description="Official MUSE-Mem research implementation")
    sub = parser.add_subparsers(required=True)
    run = sub.add_parser("run", help="construct memory and answer questions")
    run.add_argument("--config", default="configs/example.json")
    run.add_argument("--input", default="examples/example.json")
    run.add_argument("--output", default="runs/example/output.json")
    run.set_defaults(func=run_command)
    inspect = sub.add_parser("inspect", help="inspect the persistent memory state")
    inspect.add_argument("--config", default="configs/example.json")
    inspect.add_argument("--namespace", required=True)
    inspect.set_defaults(func=inspect_command)
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
