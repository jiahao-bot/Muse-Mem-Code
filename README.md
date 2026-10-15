# MUSE-Mem

**Official implementation of MUSE-Mem.**

MUSE-Mem is a persistent memory system for lifelong agents. It organizes memory as an externalized gated recurrence over paired Semantic and Episodic Memory:

- **Perception Gate** performs instruction-conditioned Contextual Perception and appends traceable Perception Signals and Raw Messages to Episodic Memory.
- **Governance Gate** is the sole writer of Semantic Memory and maintains the Core, Routing Index, and Topic Entries through `add`, `update`, `delete`, `link`, and `unlink` actions.
- **Retrieval Gate** is read-only and progressively moves from semantic guidance to Perception Signals and Raw Messages while an information residual remains.

The repository contains the complete core runtime: persistent storage, Gate instruction templates, executable tool contracts, memory construction, provenance-guided retrieval, evaluation primitives, and architectural tests. Model serving is connected through an OpenAI-compatible interface and remains independent of the memory runtime.

## Installation

```bash
git clone <repository-url>
cd muse-code
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

The core package has no third-party runtime dependencies.

## Quick start

```bash
bash scripts/run_example.sh
```

This command runs an end-to-end MUSE-Mem workflow:

1. retain only completed sessions visible at question time;
2. persist Raw Messages and run Contextual Perception per session;
3. restore signal chronology and perform one case-level Governance finalization;
4. freeze the memory state;
5. answer questions through independent read-only Retrieval procedures.

Inspect the persistent state:

```bash
muse-mem inspect --config configs/example.json --namespace example
```

## Model configuration

For model-backed execution, configure an OpenAI-compatible endpoint:

```bash
export MUSE_LLM_BASE_URL=https://your-endpoint/v1
export MUSE_LLM_API_KEY=...
export MUSE_LLM_MODEL=gemini-3.1-flash-lite
```

Then use `configs/benchmark.json`. API credentials are read only from the environment and are never stored in experiment outputs.

## Repository structure

```text
prompts/                 Runtime Gate instruction templates
src/muse_mem/gates/      Perception, Governance, and Retrieval Gates
src/muse_mem/storage/    Episodic and Semantic Memory persistence
src/muse_mem/runtime/    Completed-session construction protocol
src/muse_mem/benchmarks/ Runner primitives and evaluators
examples/                Executable input examples
configs/                 Protocol and model configurations
tests/                   Executable architectural invariants
docs/                    Architecture and model-backed execution
```

## Run tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Architecture and execution

See [`docs/architecture.md`](docs/architecture.md) for the system components and enforced guarantees, and [`docs/model_execution.md`](docs/model_execution.md) for model-backed execution and configuration.

## License

MIT License. See [`LICENSE`](LICENSE).
