import json
import os
import tempfile
import unittest
from pathlib import Path

from muse_mem.gates import PerceptionGate
from muse_mem.llm import DeterministicLLM, LLMResponse
from muse_mem.models import Message
from muse_mem.storage import Database, EpisodicMemory

ROOT = Path(__file__).resolve().parents[1]

class PerceptionProvenanceTests(unittest.TestCase):
    def test_prompt_schema_without_hidden_index_binds_correct_message(self):
        path = tempfile.mktemp(suffix=".db")
        db = Database(path)
        try:
            response = {"signals": [{
                "type": "user_fact",
                "content": "[source_role=user; source_time=2026-01-01T09:00:00+00:00; turn=0; session_context=s1] The user lives in Shanghai.",
                "confidence": "confirmed",
            }]}
            episodic = EpisodicMemory(db)
            gate = PerceptionGate(DeterministicLLM([LLMResponse(json.dumps(response))]), episodic,
                                  str(ROOT / "prompts/perception.txt"))
            messages = [
                Message("user", "I live in Shanghai.", "2026-01-01T09:00:00+00:00", "s1",
                        channel="web"),
                Message("assistant", "Understood.", "2026-01-01T09:01:00+00:00", "s1"),
            ]
            signal_id = gate.process_session("n", messages)[0]
            signal = episodic.existing_signals("n")[0]
            source = episodic.messages_for_signals("n", [signal_id])
            self.assertEqual(signal["source_time"], messages[0].timestamp)
            self.assertEqual(signal["channel"], "web")
            self.assertEqual(source[0]["content"], messages[0].content)
            self.assertEqual(source[0]["channel"], "web")
        finally:
            db.close()
            os.remove(path)

if __name__ == "__main__":
    unittest.main()
