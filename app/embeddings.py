import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

from .config import get_settings


class LocalEmbedder:
    def __init__(self):
        self.settings = get_settings()
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.settings.embedding_model)
        return self._model

    def embed(self, text: str):
        model = self._load()
        return model.encode(text, normalize_embeddings=True).tolist()