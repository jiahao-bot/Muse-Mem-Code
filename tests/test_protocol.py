"""Core protocol tests for the official MUSE-Mem implementation."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from muse_mem.gates import GovernanceGate, GovernanceTools, RetrievalGate, RetrievalTools, AppendOnlyWriter
from muse_mem.llm import DeterministicLLM, LLMResponse, ToolCall, RuleBasedLLM
from muse_mem.models import Message, Signal
from muse_mem.storage import Database, EpisodicMemory, SemanticMemory
from muse_mem.runtime import MuseRuntime

ROOT = Path(__file__).resolve().parents[1]

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp(suffix=".db")
        self.db = Database(self.path)
        self.episodic = EpisodicMemory(self.db)
        self.semantic = SemanticMemory(self.db)

    def tearDown(self):
        self.db.close()
        os.remove(self.path)

    def add_signal(self):
        mid = self.episodic.append_message("n", Message("user", "I live in Shanghai", "2026-01-01T00:00:00+00:00", "s1"))
        signal_id = self.episodic.append_signal("n", Signal("user_fact", "The user lives in Shanghai", "confirmed", "user", "2026-01-01T00:00:00+00:00", "s1", mid))
        self.episodic.link_signal_messages("n", signal_id, [mid])
        return signal_id

    def test_episodic_memory_is_append_only(self):
        self.add_signal()
        self.assertFalse(hasattr(self.episodic, "update_signal"))
        self.assertFalse(hasattr(self.episodic, "delete_message"))

    def test_governance_is_only_semantic_writer(self):
        tools = GovernanceTools(self.db, self.semantic, "n")
        tools.add_file("user/profile.md")
        with self.assertRaises(RuntimeError):
            tools.memory_entry(action="add", file="user/profile.md", entry_id="e1", content="x")
        tools.read_file("user/profile.md")
        tools.memory_entry(action="add", file="user/profile.md", entry_id="e1", content="x")
        self.assertEqual(len(self.semantic.all_entries("n")), 1)

    def test_governance_writes_core_through_memory_entry(self):
        signal_id = self.add_signal()
        tools = GovernanceTools(self.db, self.semantic, "n", self.episodic.existing_signals("n"))
        tools.memory_entry(action="add", file="OWNER.md", entry_id="core-1",
                           content="The user lives in Shanghai", category="identity",
                           source_context=f"signal_id={signal_id}")
        self.assertEqual(self.semantic.core("n"), "The user lives in Shanghai")

    def test_retrieval_tools_are_read_only(self):
        tools = RetrievalTools("n", self.semantic, self.episodic)
        self.assertFalse(hasattr(tools, "memory_entry"))
        self.assertFalse(hasattr(tools, "edit_file"))

    def test_failed_governance_does_not_mark_signals(self):
        self.add_signal()
        llm = DeterministicLLM([LLMResponse(tool_calls=[ToolCall("memory_entry", {"action": "add", "file": "user/x.md", "entry_id": "e1"})])])
        gate = GovernanceGate(llm, self.db, self.episodic, self.semantic, str(ROOT / "prompts/governance.txt"))
        with self.assertRaises(RuntimeError):
            gate.finalize("n")
        self.assertEqual(len(self.episodic.unprocessed_signals("n")), 1)

    def test_merged_entry_retains_multiple_signal_sources(self):
        first = self.add_signal()
        mid = self.episodic.append_message("n", Message("user", "I start trips from Shanghai", "2026-01-02", "s1"))
        second = self.episodic.append_signal("n", Signal("user_fact", "The user starts trips from Shanghai", "confirmed", "user", "2026-01-02", "s1", mid))
        self.episodic.link_signal_messages("n", second, [mid])
        signals = self.episodic.existing_signals("n")
        tools = GovernanceTools(self.db, self.semantic, "n", signals)
        tools.add_file("user/profile.md"); tools.read_file("user/profile.md")
        tools.memory_entry(action="add", file="user/profile.md", entry_id="merged",
                           content="The user lives in Shanghai and starts trips from Shanghai.",
                           source_context="session_context=s1")
        self.assertEqual(set(self.semantic.entry_signal_ids("n", "merged")), {first, second})

    def test_governance_requires_signal_coverage(self):
        self.add_signal()
        gate = GovernanceGate(DeterministicLLM([LLMResponse("done")]), self.db,
                              self.episodic, self.semantic, str(ROOT / "prompts/governance.txt"))
        with self.assertRaisesRegex(RuntimeError, "unrepresented signals"):
            gate.finalize("n")
        self.assertEqual(len(self.episodic.unprocessed_signals("n")), 1)

    def test_archive_preserves_episodic_evidence(self):
        signal_id = self.add_signal()
        tools = GovernanceTools(self.db, self.semantic, "n", self.episodic.existing_signals("n"))
        tools.add_file("user/profile.md"); tools.read_file("user/profile.md")
        tools.memory_entry(action="add", file="user/profile.md", entry_id="e1",
                           content="The user lives in Shanghai", source_context=f"signal_id={signal_id}")
        tools.memory_entry(action="delete", file="user/profile.md", entry_id="e1")
        self.db.connection.commit()
        self.assertEqual(self.semantic.all_entries("n"), [])
        self.assertEqual(len(self.episodic.existing_signals("n")), 1)

    def test_future_sessions_are_excluded(self):
        before = [[Message("user", "before", "2026-01-01T00:00:00+00:00", "s1")]]
        after = [Message("user", "after", "2027-01-01T00:00:00+00:00", "s2")]
        visible = MuseRuntime.visible_sessions([*before, after], "2026-06-01T00:00:00+00:00")
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0][0].content, "before")

    def test_ten_round_budget_forces_final_call_without_tools(self):
        query = "SELECT * FROM musa_messages WHERE content LIKE '%x%'"
        responses = [LLMResponse(tool_calls=[ToolCall("bash", {"sql": query})]) for _ in range(10)]
        responses.append(LLMResponse("cannot determine from memory"))
        llm = DeterministicLLM(responses)
        gate = RetrievalGate(llm, self.semantic, self.episodic, str(ROOT / "prompts/retrieval.txt"), 10)
        result = gate.answer("n", "x")
        self.assertTrue(result.limit_reached)
        self.assertEqual(len(result.evidence), 10)
        self.assertIsNone(llm.calls[-1]["tools"])

    def test_provenance_guided_evidence_reads(self):
        signal_id = self.add_signal()
        tools = GovernanceTools(self.db, self.semantic, "n", self.episodic.existing_signals("n"))
        tools.add_file("user/profile.md"); tools.read_file("user/profile.md")
        tools.memory_entry(action="add", file="user/profile.md", entry_id="e1",
                           content="The user lives in Shanghai", source_context=f"signal_id={signal_id}")
        self.db.connection.commit()
        retrieval = RetrievalTools("n", self.semantic, self.episodic)
        signals = retrieval.bash(f"SELECT * FROM muse_perceive_signals WHERE signal_id='{signal_id}'")
        messages = retrieval.bash("SELECT * FROM musa_messages WHERE content LIKE '%Shanghai%'")
        self.assertEqual(signals[0]["signal_id"], signal_id)
        self.assertEqual(messages[0]["content"], "I live in Shanghai")

    def test_bash_rejects_non_select_and_unscoped_tables(self):
        retrieval = RetrievalTools("n", self.semantic, self.episodic)
        with self.assertRaises(ValueError):
            retrieval.bash("DELETE FROM musa_messages")
        with self.assertRaises(ValueError):
            retrieval.bash("SELECT * FROM topic_entries")

    def test_without_governance_gate_is_restricted_append_only(self):
        self.add_signal()
        writer = AppendOnlyWriter(self.db, self.episodic)
        self.assertTrue(writer.finalize("n"))
        entries = self.semantic.all_entries("n")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].file, "user/append-only-signals.md")
        self.assertEqual(len(self.episodic.unprocessed_signals("n")), 0)

    def test_end_to_end_protocol(self):
        llm = RuleBasedLLM()
        from muse_mem.gates import PerceptionGate
        perception = PerceptionGate(llm, self.episodic, str(ROOT / "prompts/perception.txt"))
        governance = GovernanceGate(llm, self.db, self.episodic, self.semantic, str(ROOT / "prompts/governance.txt"))
        retrieval = RetrievalGate(llm, self.semantic, self.episodic, str(ROOT / "prompts/retrieval.txt"))
        runtime = MuseRuntime(perception, governance, retrieval)
        sessions = [[Message("user", "I prefer quiet hotels", "2026-01-01T00:00:00+00:00", "s1")]]
        snapshot = runtime.construct("n", sessions, "2026-02-01T00:00:00+00:00")
        result = runtime.answer("n", "What hotels do I prefer?", "2026-02-01T00:00:00+00:00")
        self.assertTrue(snapshot)
        self.assertTrue(self.semantic.routing_index("n"))
        self.assertTrue(result.evidence)

    def test_governance_processes_batches_before_one_snapshot(self):
        for index in range(3):
            mid = self.episodic.append_message(
                "n", Message("user", f"fact {index}", f"2026-01-0{index + 1}", "s1")
            )
            signal_id = self.episodic.append_signal(
                "n", Signal("user_fact", f"fact {index}", "confirmed", "user",
                            f"2026-01-0{index + 1}", "s1", mid)
            )
            self.episodic.link_signal_messages("n", signal_id, [mid])
        gate = GovernanceGate(RuleBasedLLM(), self.db, self.episodic, self.semantic,
                              str(ROOT / "prompts/governance.txt"), batch_size=2)
        self.assertTrue(gate.finalize("n"))
        count = self.db.connection.execute(
            "SELECT COUNT(*) FROM snapshots WHERE namespace='n'"
        ).fetchone()[0]
        self.assertEqual(count, 1)
        self.assertEqual(len(self.episodic.unprocessed_signals("n")), 0)
        self.assertEqual(len(self.semantic.all_entries("n")), 3)

    def test_repeated_construction_is_idempotent(self):
        llm = RuleBasedLLM()
        from muse_mem.gates import PerceptionGate
        runtime = MuseRuntime(
            PerceptionGate(llm, self.episodic, str(ROOT / "prompts/perception.txt")),
            GovernanceGate(llm, self.db, self.episodic, self.semantic,
                           str(ROOT / "prompts/governance.txt")),
            RetrievalGate(llm, self.semantic, self.episodic,
                          str(ROOT / "prompts/retrieval.txt")),
        )
        sessions = [[Message("user", "I prefer quiet hotels", "2026-01-01", "s1")]]
        self.assertTrue(runtime.construct("n", sessions, "2026-02-01"))
        before = (len(self.episodic.existing_signals("n")), len(self.semantic.all_entries("n")))
        self.assertIsNone(runtime.construct("n", sessions, "2026-02-01"))
        after = (len(self.episodic.existing_signals("n")), len(self.semantic.all_entries("n")))
        self.assertEqual(before, after)

    def test_session_extraction_can_run_concurrently(self):
        class RecordingPerception:
            def __init__(self):
                self.barrier = threading.Barrier(2)
                self.sessions = []
                self.lock = threading.Lock()
            def process_session(self, namespace, messages, current_date):
                self.barrier.wait(timeout=2)
                with self.lock:
                    self.sessions.append(messages[0].session_id)
        class RecordingGovernance:
            def finalize(self, namespace):
                return "snapshot"
        perception = RecordingPerception()
        runtime = MuseRuntime(perception, RecordingGovernance(), object(), build_concurrency=2)
        sessions = [
            [Message("user", "one", "2026-01-01", "s1")],
            [Message("user", "two", "2026-01-02", "s2")],
        ]
        self.assertEqual(runtime.construct("n", sessions, "2026-02-01"), "snapshot")
        self.assertEqual(set(perception.sessions), {"s1", "s2"})

if __name__ == "__main__":
    unittest.main()
