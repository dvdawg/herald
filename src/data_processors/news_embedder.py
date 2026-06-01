"""Compute and persist embeddings for stored news articles."""
from __future__ import annotations

import logging
import threading
from typing import List, Optional

import numpy as np

from src.storage.article_store import ArticleStore, StoredArticle
from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


def normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


class NewsEmbedder:
    """Wraps a sentence-transformer model with lazy loading + caching."""

    _model_cache = {}
    _cache_lock = threading.Lock()

    def __init__(
        self,
        config: Optional[ConfigLoader] = None,
        store: Optional[ArticleStore] = None,
        model_name: Optional[str] = None,
    ):
        self.config = config or ConfigLoader()
        self.store = store or ArticleStore()
        self.model_name = model_name or self.config.get_embedding_model_name()
        self._model = None

    @property
    def model(self):
        if self._model is None:
            with self._cache_lock:
                cached = self._model_cache.get(self.model_name)
                if cached is None:
                    from sentence_transformers import SentenceTransformer
                    cached = SentenceTransformer(self.model_name)
                    self._model_cache[self.model_name] = cached
                self._model = cached
        return self._model

    def _encode(self, texts: List[str]) -> np.ndarray:
        vectors = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return np.asarray(vectors, dtype=np.float32)

    def _article_text(self, article: StoredArticle) -> str:
        parts = [article.title]
        if article.summary:
            parts.append(article.summary[:1000])
        return " ".join(parts).strip()

    def embed_pending(self, batch_size: int = 64, max_articles: int = 512) -> int:
        embedded = 0
        while embedded < max_articles:
            batch = self.store.articles_missing_embedding(limit=min(batch_size, max_articles - embedded))
            if not batch:
                break
            texts = [self._article_text(a) for a in batch]
            vectors = self._encode(texts)
            for article, vector in zip(batch, vectors):
                self.store.save_embedding(article.id, normalize(vector), self.model_name)
            embedded += len(batch)
        if embedded:
            logger.info("Embedded %d new articles", embedded)
        return embedded

    def encode_query(self, query: str) -> np.ndarray:
        vec = self._encode([query])[0]
        return normalize(vec)
