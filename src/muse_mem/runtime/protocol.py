"""MUSE-Mem construction and retrieval runtime."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from ..models import Message, RetrievalResult
from ..gates.perception import PerceptionGate
from ..gates.governance import GovernanceGate
from ..gates.retrieval import RetrievalGate

class MuseRuntime:
    def __init__(self, perception: PerceptionGate, governance: GovernanceGate,
                 retrieval: RetrievalGate, build_concurrency: int = 1):
        self.perception = perception
        self.governance = governance
        self.retrieval = retrieval
        self.build_concurrency = max(1, build_concurrency)

    @staticmethod
    def visible_sessions(sessions: list[list[Message]], question_date: str) -> list[list[Message]]:
        cutoff = datetime.fromisoformat(question_date.replace("Z", "+00:00"))
        visible = []
        for session in sessions:
            if not session:
                continue
            latest = max(datetime.fromisoformat(m.timestamp.replace("Z", "+00:00")) for m in session)
            if latest <= cutoff:
                visible.append(session)
        return sorted(visible, key=lambda s: min(m.timestamp for m in s))

    def construct(self, namespace: str, sessions: list[list[Message]], question_date: str) -> str | None:
        visible = self.visible_sessions(sessions, question_date)
        if self.build_concurrency == 1:
            for session in visible:
                self.perception.process_session(namespace, session, question_date[:10])
        else:
            with ThreadPoolExecutor(max_workers=self.build_concurrency) as pool:
                futures = [pool.submit(self.perception.process_session, namespace, session, question_date[:10]) for session in visible]
                for future in futures:
                    future.result()
        return self.governance.finalize(namespace)

    def answer(self, namespace: str, question: str, question_date: str) -> RetrievalResult:
        return self.retrieval.answer(namespace, question, question_date)
