"""Deterministic research provider used for smoke tests and protocol verification."""
from __future__ import annotations

import json
import re
import uuid
from .base import LLM, LLMResponse, ToolCall

class RuleBasedLLM(LLM):
    def complete(self, *, system: str, messages: list[dict], tools: list[dict] | None = None,
                 tool_choice: str | None = None) -> LLMResponse:
        names = {t["function"]["name"] for t in tools or []}
        if "signals" in system and "memory evidence extractor" in system:
            transcript = json.loads(messages[-1]["content"])
            signals = []
            for index, item in enumerate(transcript):
                content = item["content"].strip()
                if not content:
                    continue
                lower = content.lower()
                signal_type = "assistant_fact" if item["role"] == "assistant" else "user_fact"
                if any(x in lower for x in ["prefer", "like", "quiet"]): signal_type = "user_preference"
                elif any(x in lower for x in ["plan", "would like", "trip"]): signal_type = "user_plan"
                signals.append({"type": signal_type, "content": f"[source_role={item['role']}; source_time={item['timestamp']}; session_context={item['session_id']}] {content}", "confidence": "confirmed", "source_message_index": index})
            return LLMResponse(json.dumps({"signals": signals}, ensure_ascii=False))
        if "memory_entry" in names:
            first_payload = json.loads(messages[0]["content"])
            signals = first_payload["perception_signals"]
            prior = [json.loads(m["content"]) for m in messages[1:] if m["role"] == "assistant"]
            flat = []
            for item in prior:
                flat.extend(item if isinstance(item, list) else [item])
            read = any(x["name"] == "read_file" for x in flat)
            added = sum(x["name"] == "memory_entry" for x in flat)
            edited = any(x["name"] == "edit_file" for x in flat)
            path = "user/interaction-memory.md"
            if not read:
                return LLMResponse(tool_calls=[ToolCall("read_file", {"path": path})])
            if not any(x["name"] == "add_file" for x in flat) and flat[-1]["result"].get("exists") is False:
                return LLMResponse(tool_calls=[ToolCall("add_file", {"path": path, "content": "Interaction evidence"})])
            if added < len(signals):
                signal = signals[added]
                words = re.findall(r"[A-Za-z0-9_-]+", signal["content"])
                return LLMResponse(tool_calls=[ToolCall("memory_entry", {
                    "action": "add", "file": path, "entry_id": uuid.uuid5(uuid.NAMESPACE_URL, signal["signal_id"]).hex,
                    "title": " ".join(words[-6:]) or "Interaction evidence", "content": signal["content"],
                    "category": "context", "confidence": signal["confidence"],
                    "source_context": f"session_id={signal['session_id']}; signal_id={signal['signal_id']}",
                })])
            if not edited:
                keywords = sorted({w.lower() for s in signals for w in re.findall(r"[A-Za-z]{4,}", s["content"])})[:30]
                return LLMResponse(tool_calls=[ToolCall("edit_file", {"path": path, "description": "Traceable interaction evidence", "keywords": keywords})])
            return LLMResponse("Governance finalization complete.")
        if "read_memory_topic" in names:
            question = messages[0]["content"]
            tool_results = [json.loads(m["content"]) for m in messages[2:] if m["role"] == "assistant"]
            if not tool_results:
                context = json.loads(messages[1]["content"])
                index = context.get("routing_index", [])
                if index:
                    return LLMResponse(tool_calls=[ToolCall("read_memory_topic", {"path": index[0]["path"]})])
                query = "SELECT * FROM muse_perceive_signals ORDER BY source_time LIMIT 20"
                return LLMResponse(tool_calls=[ToolCall("bash", {"sql": query})])
            last = tool_results[-1]
            if last.get("name") == "read_memory_topic":
                signal_ids = [signal_id for entry in last["result"].get("entries", [])
                              for signal_id in entry.get("source_signal_ids", [])]
                values = ",".join("'" + signal_id.replace("'", "''") + "'" for signal_id in signal_ids)
                query = "SELECT * FROM muse_perceive_signals" + (f" WHERE signal_id IN ({values})" if values else "") + " ORDER BY source_time LIMIT 50"
                return LLMResponse(tool_calls=[ToolCall("bash", {"sql": query})])
            if last.get("name") == "bash" and last["result"] and "signal_id" in last["result"][0]:
                message_ids = [message_id for signal in last["result"]
                               for message_id in (signal.get("source_message_ids") or "").split(",") if message_id]
                where = ",".join("'" + message_id.replace("'", "''") + "'" for message_id in message_ids)
                query = "SELECT * FROM musa_messages" + (f" WHERE message_id IN ({where})" if where else "") + " ORDER BY timestamp LIMIT 50"
                return LLMResponse(tool_calls=[ToolCall("bash", {"sql": query})])
            evidence_text = json.dumps(tool_results, ensure_ascii=False)
            return LLMResponse(f"<mem_thinking>Answer grounded in the retrieved memory.</mem_thinking>\n<final_answer>{evidence_text}</final_answer>")
        return LLMResponse("I cannot determine the answer from memory.")
