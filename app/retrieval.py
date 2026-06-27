import json
import hashlib
from pathlib import Path
from typing import List, Optional, Tuple

from .config import get_settings
from .models import ReferenceQA


def _cosine(a: List[float], b: List[float]) -> float:
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


class ReferenceStore:
    def __init__(self, embedder):
        self.settings = get_settings()
        self.embedder = embedder
        self.questions: List[ReferenceQA] = []
        self.embeddings: List[List[float]] = []
        self.domain: str = ""
        self.title: str = ""
        self._load_questions()
        self._build_index()

    def _load_questions(self) -> None:
        raw = json.loads(Path(self.settings.questions_path).read_text(encoding="utf-8"))
        self.domain = raw.get("domain", "")
        self.title = raw.get("title", "")
        self.questions = [ReferenceQA(**q) for q in raw["questions"]]

    def _source_hash(self) -> str:
        payload = json.dumps(
            [(q.id, q.question, q.ideal_answer) for q in self.questions],
            sort_keys=True,
        )
        key = payload + self.settings.embedding_model
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _build_index(self) -> None:
        cache_path = Path(self.settings.embeddings_cache_path)
        current_hash = self._source_hash()
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("hash") == current_hash:
                self.embeddings = cached["embeddings"]
                return
        self.embeddings = [self.embedder.embed(self._index_text(q)) for q in self.questions]
        cache_path.write_text(
            json.dumps({"hash": current_hash, "embeddings": self.embeddings}),
            encoding="utf-8",
        )

    @staticmethod
    def _index_text(q: ReferenceQA) -> str:
        return f"{q.topic}. {q.question} {q.ideal_answer}"

    def all(self) -> List[ReferenceQA]:
        return self.questions

    def count(self) -> int:
        return len(self.questions)

    def get_by_index(self, index: int) -> ReferenceQA:
        return self.questions[index]

    def get_by_id(self, qid: str) -> Optional[ReferenceQA]:
        for q in self.questions:
            if q.id == qid:
                return q
        return None

    def retrieve(self, query: str, k: int = 1) -> List[Tuple[ReferenceQA, float]]:
        query_vec = self.embedder.embed(query)
        scored = [
            (self.questions[i], _cosine(query_vec, self.embeddings[i]))
            for i in range(len(self.questions))
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]
