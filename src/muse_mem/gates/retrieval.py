"""Retrieval Gate: residual-driven progressive recall."""
from __future__ import annotations

import json
from pathlib import Path
from ..llm import LLM
from ..models import RetrievalResult
from ..storage import EpisodicMemory, SemanticMemory
from .retrieval_tools import RetrievalTools

RETRIEVAL_TOOL_SCHEMA = [
    {"type": "function", "function": {"name": "read_memory_topic", "description": "Read a topic listed in the Routing Index", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "bash", "description": "Execute a scoped SELECT query over muse_perceive_signals and musa_messages", "parameters": {"type": "object", "properties": {"sql": {"type": "string", "description": "One read-only SELECT statement"}}, "required": ["sql"]}}},
]

class RetrievalGate:
    def __init__(self, llm: LLM, semantic: SemanticMemory, episodic: EpisodicMemory,
                 prompt_path: str, max_rounds: int = 10):
        self.llm, self.semantic, self.episodic = llm, semantic, episodic
        self.prompt = Path(prompt_path).read_text(encoding="utf-8")
        self.max_rounds = max_rounds

    def answer(self, namespace: str, question: str, question_date: str = "") -> RetrievalResult:
        tools = RetrievalTools(namespace, self.semantic, self.episodic)
        context = {"question_date": question_date, "core": self.semantic.core(namespace),
                   "routing_index": self.semantic.routing_index(namespace)}
        messages = [{"role": "user", "content": question},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
        evidence = []
        for round_number in range(1, self.max_rounds + 1):
            response = self.llm.complete(system=self.prompt, messages=messages, tools=RETRIEVAL_TOOL_SCHEMA)
            if not response.tool_calls:
                return RetrievalResult(response.content, round_number, evidence, [])
            if response.assistant_message:
                messages.append(response.assistant_message)
            for call in response.tool_calls:
                result = getattr(tools, call.name)(**call.arguments)
                evidence.append({"tool": call.name, "arguments": call.arguments, "result": result})
                if call.call_id:
                    messages.append({"role": "tool", "tool_call_id": call.call_id,
                                     "name": call.name, "content": json.dumps(result, ensure_ascii=False)})
                else:
                    messages.append({"role": "assistant", "content": json.dumps(
                        {"name": call.name, "result": result}, ensure_ascii=False)})
        messages.append({"role": "system", "content": "The retrieval tool budget is exhausted. Produce the final answer from the current evidence view without requesting tools. If evidence is insufficient, state that the answer cannot be determined from memory."})
        final = self.llm.complete(system=self.prompt, messages=messages, tools=None, tool_choice="none")
        if final.tool_calls:
            return RetrievalResult("retrieval-round-limit error", self.max_rounds, evidence,
                                   ["tool budget exhausted"], True)
        return RetrievalResult(final.content, self.max_rounds, evidence, [], True)
