# Architecture and Guarantees

MUSE-Mem separates memory selection, semantic maintenance, and evidence retrieval into three Gates over persistent Semantic and Episodic Memory. The following guarantees are enforced by the runtime and its tests.

| System guarantee | Implementation |
|---|---|
| Persistent state `M = (T, D)` | `SemanticMemory` and `EpisodicMemory` |
| Episodic Memory is append-only | `storage/episodic.py`; no update/delete API; tested in `test_episodic_memory_is_append_only` |
| Semantic Memory = Core + Routing Index + Topic Entries | `storage/schema.sql`, `storage/semantic.py` |
| Contextual Perception over completed visible sessions | `gates/perception.py`, `runtime/protocol.py` |
| Existing signals are supplied to the extractor | `PerceptionGate.process_session` |
| Source, channel, session, and timestamp metadata | `Message`, `Signal`, and Episodic Memory tables |
| Governance is the sole Semantic Memory writer | `GovernanceTools`; Retrieval exposes no write tool |
| Governance actions are add/update/delete/link/unlink | `GovernanceTools.ACTIONS` and `GOVERNANCE_TOOL_SCHEMA` |
| Merge/Revise/Qualify/etc. are semantic effects | Implemented by Governance through the executable action set, not exposed as synthetic actions |
| Topic must be read before modification | `GovernanceTools.memory_entry` enforces read-before-write |
| Failed finalization leaves signals unprocessed | Transaction rollback in `GovernanceGate.finalize`; covered by tests |
| Retrieval is read-only | `RetrievalTools` exposes topic and episodic evidence reads only |
| Core/Index → Topic Entries → Signals → Raw Messages | Retrieval prompt and tool schemas in `gates/retrieval.py` |
| Information residual controls further retrieval | Retrieval model instruction in `prompts/retrieval.txt` |
| Maximum ten retrieval rounds | `RetrievalGate.max_rounds=10` |
| Final model call has tools disabled | Final branch of `RetrievalGate.answer` |
| Case-level namespace isolation | Every persistent table is keyed by `namespace` |
| Later interactions are excluded | `MuseRuntime.visible_sessions` |
| Batched Governance within one case-level finalize | `GovernanceGate.finalize` processes ordered batches in one transaction and creates one snapshot |
| Memory construction and answering are separate | `MuseRuntime.construct` and `MuseRuntime.answer` |
| PersonaMem option-label exact match primitive | `benchmarks/evaluators.py` |
| w/o Governance Gate restricted append-only writer | `gates/append_only_writer.py` |

Model serving is accessed through a provider interface, while memory state transitions and evidence access remain part of the MUSE-Mem runtime. This separation keeps the core system portable across OpenAI-compatible endpoints without changing its storage or Gate semantics.
