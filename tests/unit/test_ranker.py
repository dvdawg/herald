import unittest
from datetime import datetime, timedelta, timezone

import numpy as np

from src.ranking_engine.ranker import ArticleRanker
from src.utils.config_loader import ConfigLoader


class _FakeEmbeddingModel:
    _DIMENSIONS = [
        "graph",
        "neural",
        "networks",
        "language",
        "model",
        "vision",
        "diffusion",
    ]

    def predict(self, articles):
        single = isinstance(articles, dict)
        items = [articles] if single else articles
        embeddings = [self._encode(article) for article in items]
        return embeddings[0] if single else embeddings

    def _encode(self, article):
        text = f"{article.get('title', '')} {article.get('abstract', '')}".lower()
        return np.array([float(text.count(token)) for token in self._DIMENSIONS], dtype=float)


class _FailingEmbeddingModel:
    def predict(self, articles):
        raise RuntimeError("embedding backend unavailable")


class _FakeCitationFetcher:
    def get_citation_count(self, article):
        return article.get("citation_count")


class TestArticleRanker(unittest.TestCase):
    def setUp(self):
        self.config = ConfigLoader(config_path="/definitely/missing.yaml")
        self.config.config["citation"]["enabled"] = True
        self.config.config["ranking"]["weights"] = {
            "relevance": 0.65,
            "recency": 0.2,
            "citations": 0.1,
            "quality": 0.05,
        }

    def _build_ranker(self, embedding_model=None):
        return ArticleRanker(
            embedding_model=embedding_model or _FakeEmbeddingModel(),
            config=self.config,
            citation_fetcher=_FakeCitationFetcher(),
        )

    def test_rank_articles_empty(self):
        ranker = self._build_ranker()
        self.assertEqual(ranker.rank_articles([]), [])

    def test_exact_title_phrase_beats_loose_semantic_match(self):
        ranker = self._build_ranker()
        now = datetime.now(timezone.utc)
        articles = [
            {
                "title": "Graph Neural Networks for Molecular Property Prediction",
                "abstract": "Graph neural networks improve molecular reasoning with graph structure.",
                "published": (now - timedelta(days=7)).isoformat(),
                "citation_count": 15,
            },
            {
                "title": "Neural Networks for Molecular Property Prediction",
                "abstract": "A broad neural architecture without graph-specific modeling.",
                "published": (now - timedelta(days=1)).isoformat(),
                "citation_count": 25,
            },
        ]

        ranked = ranker.rank_articles(articles, query="graph neural networks")

        self.assertEqual(ranked[0][0]["title"], articles[0]["title"])
        self.assertGreater(
            ranked[0][0]["ranking_features"]["title_overlap"],
            ranked[1][0]["ranking_features"]["title_overlap"],
        )
        self.assertIn("Exact query phrase appears in the title.", ranked[0][0]["ranking_explanation"])

    def test_lexical_fallback_still_ranks_when_embeddings_fail(self):
        ranker = self._build_ranker(embedding_model=_FailingEmbeddingModel())
        now = datetime.now(timezone.utc)
        articles = [
            {
                "title": "Scaling Laws for Diffusion Models",
                "abstract": "Diffusion models exhibit predictable scaling behavior.",
                "published": (now - timedelta(days=14)).isoformat(),
                "citation_count": 2,
            },
            {
                "title": "Vision Transformers for Medical Imaging",
                "abstract": "A recent paper with little relation to diffusion.",
                "published": (now - timedelta(days=1)).isoformat(),
                "citation_count": 90,
            },
        ]

        ranked = ranker.rank_articles(articles, query="diffusion scaling laws")

        self.assertEqual(ranked[0][0]["title"], articles[0]["title"])
        self.assertGreater(ranked[0][0]["ranking_features"]["lexical_overlap"], 0.9)
        self.assertEqual(ranked[0][0]["ranking_features"]["semantic_similarity"], 0.0)

    def test_no_query_rebalances_to_browse_features(self):
        ranker = self._build_ranker()
        now = datetime.now(timezone.utc)
        articles = [
            {
                "title": "Fresh Paper",
                "abstract": "This abstract is fairly detailed and recent." * 10,
                "published": (now - timedelta(days=3)).isoformat(),
                "citation_count": 20,
            },
            {
                "title": "Old Paper",
                "abstract": "Short abstract.",
                "published": (now - timedelta(days=900)).isoformat(),
                "citation_count": 20,
            },
        ]

        ranked = ranker.rank_articles(articles, query=None)

        self.assertEqual(ranked[0][0]["title"], "Fresh Paper")
        self.assertGreater(ranked[0][1], 0.0)
        self.assertEqual(ranked[0][0]["ranking_features"]["relevance"], 0.0)

    def test_scores_are_normalized_even_with_overspecified_weights(self):
        ranker = self._build_ranker()
        article = {
            "title": "Graph Neural Networks",
            "abstract": "Graph neural networks are useful for relational learning." * 8,
            "published": datetime.now(timezone.utc).isoformat(),
            "citation_count": 500,
        }

        ranked = ranker.rank_articles(
            [article],
            query="graph neural networks",
            weights={"relevance": 7, "recency": 3, "citations": 2, "quality": 1},
        )

        self.assertGreaterEqual(ranked[0][1], 0.0)
        self.assertLessEqual(ranked[0][1], 1.0)

    def test_cached_citations_are_normalized(self):
        ranker = self._build_ranker()
        score = ranker._calculate_citation_score({"citation_count": 500})
        self.assertIsInstance(score, float)
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_recency_score_supports_datetime_input(self):
        ranker = self._build_ranker()
        score = ranker._calculate_recency_score(
            {"published": datetime.now(timezone.utc) - timedelta(days=30)}
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


if __name__ == "__main__":
    unittest.main()
