import math
import re
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from src.models.article_embedding_model import ArticleEmbeddingModel
from src.utils.citation_fetcher import CitationFetcher
from src.utils.config_loader import ConfigLoader


class ArticleRanker:
    """Engine for ranking articles based on query fit and browse quality."""

    _TOKEN_RE = re.compile(r"[a-z0-9]+")
    _STOPWORDS = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
        "into", "is", "it", "of", "on", "or", "that", "the", "to", "with",
    }

    def __init__(
        self,
        embedding_model: Optional[ArticleEmbeddingModel] = None,
        config: Optional[ConfigLoader] = None,
        citation_fetcher: Optional[CitationFetcher] = None,
    ):
        self.config = config or ConfigLoader()
        self.embedding_model = embedding_model or ArticleEmbeddingModel(
            model_name=self.config.get_embedding_model_name()
        )
        self.citation_fetcher = citation_fetcher
        if self.citation_fetcher is None and self.config.is_citation_enabled():
            self.citation_fetcher = CitationFetcher(
                rate_limit_delay=self.config.get_citation_rate_limit()
            )

    def rank_articles(
        self,
        articles: List[Dict],
        query: Optional[str] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> List[Tuple[Dict, float]]:
        """
        Rank articles and annotate them with feature-level ranking metadata.

        Returns:
            List of (article, score) tuples sorted by score descending.
        """
        if not articles:
            return []

        query = (query or "").strip()
        query_context = self._build_query_context(query) if query else None
        normalized_weights = self._normalize_weights(weights or self.config.get_ranking_weights())

        article_embeddings: Optional[List[Optional[np.ndarray]]] = None
        if query_context is not None and query_context["embedding"] is not None:
            article_embeddings = self._predict_embeddings(articles)

        scored_articles: List[Tuple[Dict, float]] = []
        for index, article in enumerate(articles):
            article_embedding = article_embeddings[index] if article_embeddings is not None else None
            feature_scores = self._collect_feature_scores(article, query_context, article_embedding)
            score = self._combine_feature_scores(feature_scores, normalized_weights)
            article["ranking_features"] = feature_scores
            article["ranking_explanation"] = self._build_explanation(feature_scores, query_context is not None)
            article["ranking_score"] = score
            scored_articles.append((article, score))

        return sorted(
            scored_articles,
            key=lambda item: (
                item[1],
                item[0].get("ranking_features", {}).get("relevance", 0.0),
                item[0].get("ranking_features", {}).get("title_overlap", 0.0),
                item[0].get("ranking_features", {}).get("recency", 0.0),
            ),
            reverse=True,
        )

    def _build_query_context(self, query: str) -> Dict[str, object]:
        return {
            "raw": query,
            "normalized": self._normalize_text(query),
            "tokens": self._tokenize(query),
            "embedding": self._predict_query_embedding(query),
        }

    def _predict_query_embedding(self, query: str) -> Optional[np.ndarray]:
        try:
            return self.embedding_model.predict({"title": query, "abstract": ""})
        except Exception:
            return None

    def _predict_embeddings(self, articles: List[Dict]) -> List[Optional[np.ndarray]]:
        try:
            embeddings = self.embedding_model.predict(articles)
            return [embedding for embedding in embeddings]
        except Exception:
            return [None] * len(articles)

    def _collect_feature_scores(
        self,
        article: Dict,
        query_context: Optional[Dict[str, object]],
        article_embedding: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        title = article.get("title", "") or ""
        abstract = article.get("abstract", "") or article.get("summary", "") or ""
        title_norm = self._normalize_text(title)
        abstract_norm = self._normalize_text(abstract)
        title_tokens = self._tokenize(title)
        abstract_tokens = self._tokenize(abstract)
        all_tokens = title_tokens + abstract_tokens

        scores: Dict[str, float] = {
            "relevance": 0.0,
            "semantic_similarity": 0.0,
            "lexical_overlap": 0.0,
            "title_overlap": 0.0,
            "phrase_match": 0.0,
            "quality": self._calculate_quality_score(abstract),
            "recency": self._calculate_recency_score(article),
            "citations": self._calculate_citation_score(article),
        }

        if query_context is None:
            return scores

        query_tokens = query_context["tokens"]
        query_norm = query_context["normalized"]
        query_embedding = query_context["embedding"]

        lexical_overlap = self._token_overlap_score(query_tokens, all_tokens)
        title_overlap = self._token_overlap_score(query_tokens, title_tokens)
        phrase_match = self._phrase_match_score(query_norm, title_norm, abstract_norm)
        semantic_similarity = self._calculate_semantic_similarity(query_embedding, article_embedding)

        scores["lexical_overlap"] = lexical_overlap
        scores["title_overlap"] = title_overlap
        scores["phrase_match"] = phrase_match
        scores["semantic_similarity"] = semantic_similarity
        scores["relevance"] = self._combine_relevance_components(
            semantic_similarity=semantic_similarity,
            lexical_overlap=lexical_overlap,
            title_overlap=title_overlap,
            phrase_match=phrase_match,
        )
        return scores

    def _combine_feature_scores(self, feature_scores: Dict[str, float], weights: Dict[str, float]) -> float:
        active_weights: Dict[str, float] = {}
        for feature, weight in weights.items():
            score = feature_scores.get(feature)
            if score is None:
                continue
            if feature == "relevance" and score <= 0.0:
                continue
            active_weights[feature] = weight

        if not active_weights:
            return 0.0

        normalized = self._normalize_weights(active_weights)
        total_score = sum(feature_scores[feature] * weight for feature, weight in normalized.items())
        return float(min(1.0, max(0.0, total_score)))

    def _combine_relevance_components(
        self,
        semantic_similarity: float,
        lexical_overlap: float,
        title_overlap: float,
        phrase_match: float,
    ) -> float:
        component_weights = self.config.get(
            "ranking.relevance_components",
            {
                "semantic_similarity": 0.55,
                "lexical_overlap": 0.2,
                "title_overlap": 0.2,
                "phrase_match": 0.05,
            },
        )

        components = {
            "semantic_similarity": semantic_similarity,
            "lexical_overlap": lexical_overlap,
            "title_overlap": title_overlap,
            "phrase_match": phrase_match,
        }
        normalized = self._normalize_weights(component_weights)
        return float(sum(components[name] * normalized.get(name, 0.0) for name in components))

    def _calculate_semantic_similarity(
        self,
        query_embedding: Optional[np.ndarray],
        article_embedding: Optional[np.ndarray],
    ) -> float:
        if query_embedding is None or article_embedding is None:
            return 0.0

        similarity = cosine_similarity(
            query_embedding.reshape(1, -1),
            article_embedding.reshape(1, -1),
        )[0][0]
        return float(min(1.0, max(0.0, (similarity + 1.0) / 2.0)))

    def _calculate_recency_score(self, article: Dict) -> float:
        published = article.get("published")
        if published is None:
            return 0.0

        try:
            if isinstance(published, datetime):
                pub_date = published
            elif isinstance(published, str):
                pub_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
            else:
                return 0.0

            now = datetime.now(timezone.utc) if pub_date.tzinfo is not None else datetime.now()
            days_old = max(0.0, (now - pub_date).total_seconds() / 86400)
            decay_days = max(float(self.config.get("ranking.recency_decay_days", 365)), 1.0)
            score = np.exp(-days_old / decay_days)
            return float(min(1.0, max(0.0, score)))
        except (ValueError, TypeError):
            return 0.0

    def _calculate_citation_score(self, article: Dict) -> float:
        if not self.config.is_citation_enabled() or self.citation_fetcher is None:
            return 0.0

        citation_count = article.get("citation_count")
        if citation_count is None:
            citation_count = self.citation_fetcher.get_citation_count(article)
            if citation_count is not None:
                article["citation_count"] = citation_count

        if citation_count is None or citation_count <= 0:
            return 0.0

        max_citations = max(self.config.get_max_citations_for_normalization(), 1)
        normalized = math.log1p(citation_count) / math.log1p(max_citations)
        return float(min(1.0, max(0.0, normalized)))

    def _calculate_quality_score(self, abstract: str) -> float:
        abstract = (abstract or "").strip()
        if not abstract:
            return 0.0

        word_count = len(abstract.split())
        saturation = max(float(self.config.get("ranking.abstract_length_saturation", 180)), 1.0)
        score = min(word_count / saturation, 1.0)
        return float(score)

    def _phrase_match_score(self, query_norm: str, title_norm: str, abstract_norm: str) -> float:
        if not query_norm:
            return 0.0
        if query_norm in title_norm:
            return 1.0
        if query_norm in abstract_norm:
            return 0.7
        return 0.0

    def _token_overlap_score(self, query_tokens: List[str], article_tokens: Iterable[str]) -> float:
        if not query_tokens:
            return 0.0
        article_set = set(article_tokens)
        overlap = sum(1 for token in query_tokens if token in article_set)
        return overlap / len(query_tokens)

    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        cleaned = {key: max(float(value), 0.0) for key, value in weights.items()}
        total = sum(cleaned.values())
        if total <= 0.0:
            return {key: 0.0 for key in cleaned}
        return {key: value / total for key, value in cleaned.items()}

    def _build_explanation(self, feature_scores: Dict[str, float], has_query: bool) -> List[str]:
        explanations: List[str] = []
        if has_query:
            if feature_scores["phrase_match"] >= 1.0:
                explanations.append("Exact query phrase appears in the title.")
            elif feature_scores["phrase_match"] > 0.0:
                explanations.append("Exact query phrase appears in the abstract.")

            if feature_scores["title_overlap"] >= 0.75:
                explanations.append("Most query terms appear in the title.")
            elif feature_scores["lexical_overlap"] >= 0.6:
                explanations.append("Strong keyword overlap with the query.")

            if feature_scores["semantic_similarity"] >= 0.75:
                explanations.append("High semantic similarity to the query.")

        if feature_scores["recency"] >= 0.8:
            explanations.append("Recently published.")
        if feature_scores["citations"] >= 0.65:
            explanations.append("Strong citation signal.")
        if feature_scores["quality"] >= 0.75:
            explanations.append("Abstract has enough detail for robust matching.")
        return explanations[:4]

    def _normalize_text(self, text: str) -> str:
        return " ".join(self._TOKEN_RE.findall((text or "").lower()))

    def _tokenize(self, text: str) -> List[str]:
        tokens = self._TOKEN_RE.findall((text or "").lower())
        filtered = [token for token in tokens if token not in self._STOPWORDS]
        return filtered or tokens
