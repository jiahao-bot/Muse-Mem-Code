# Model-backed Execution

MUSE-Mem can run with any compatible chat-completions endpoint that supports multi-turn tool calling. The runtime combines persistent Semantic and Episodic Memory, three Gate responsibilities, executable tool contracts, completed-session construction, and provenance-guided retrieval.

## Environment

- Python 3.11 or newer
- An OpenAI-compatible model endpoint

Configure the provider through environment variables:

```bash
export MUSE_LLM_BASE_URL=https://your-endpoint/v1
export MUSE_LLM_API_KEY=...
export MUSE_LLM_MODEL=gemini-3.1-flash-lite
```

The default model-backed configuration is `configs/benchmark.json`. It records the model name, temperature, retrieval-round budget, and concurrency settings used by the core runtime.

## Core protocol

For every case, the runtime:

1. keeps only completed sessions visible at question time;
2. persists Raw Messages and performs Contextual Perception per session;
3. restores Perception Signal chronology;
4. processes ordered Perception Signal batches within one case-level Governance finalization;
5. verifies that every processed signal is represented in Semantic Memory with provenance;
6. freezes the resulting memory state;
7. answers each question through an independent read-only Retrieval procedure;
8. follows Topic Entry provenance to supporting Perception Signals and Raw Messages while information requirements remain unresolved.

Raw Messages and Perception Signals retain source channel, role, session, and timestamp metadata. The Governance batch size is configurable, while coverage validation, processed-signal marking, and snapshot creation remain case-level atomic operations.

The `rule_based` provider is a deterministic backend for end-to-end validation. Model-backed execution uses the `openai_compatible` provider and the Gate instruction templates under `prompts/`.

## Governance modes

- `governance_mode: "full"` executes the Governance agent loop.
- `governance_mode: "append_only"` executes a restricted writer without semantic governance. It converts each Perception Signal into an independent Topic Entry and cannot revise, merge, delete, link, or refresh existing memory.

## Verification

Run the architectural invariant suite:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Run the deterministic end-to-end protocol check:

```bash
bash scripts/run_example.sh
```
