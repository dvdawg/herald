import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from src.models.article_embedding_model import ArticleEmbeddingModel


class _FakeSentenceTransformer:
    def __init__(self, model_name):
        self.model_name = model_name
        self.device = None

    def to(self, device):
        self.device = device

    def encode(self, texts, convert_to_numpy=True, show_progress_bar=True):
        vectors = []
        for text in texts:
            text = text.lower()
            vectors.append(
                np.array(
                    [
                        float(len(text)),
                        float(text.count("test")),
                        float(text.count("machine")),
                    ],
                    dtype=float,
                )
            )
        return np.vstack(vectors)

    def save(self, path):
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "fake-model.txt"), "w", encoding="utf-8") as handle:
            handle.write(self.model_name)


class TestArticleEmbeddingModel(unittest.TestCase):
    def setUp(self):
        sentence_transformer_patch = patch(
            "src.models.article_embedding_model.SentenceTransformer",
            side_effect=lambda model_name: _FakeSentenceTransformer(model_name),
        )
        cuda_patch = patch("src.models.article_embedding_model.torch.cuda.is_available", return_value=False)
        self.addCleanup(sentence_transformer_patch.stop)
        self.addCleanup(cuda_patch.stop)
        sentence_transformer_patch.start()
        cuda_patch.start()

        self.model = ArticleEmbeddingModel()
        self.sample_article = {
            "title": "Test Article",
            "abstract": "This is a test article about machine learning.",
        }

    def test_predict_single_article(self):
        embedding = self.model.predict(self.sample_article)

        self.assertIsInstance(embedding, np.ndarray)
        self.assertEqual(embedding.ndim, 1)
        self.assertTrue(np.all(np.isfinite(embedding)))

    def test_predict_multiple_articles(self):
        articles = [
            self.sample_article,
            {
                "title": "Another Article",
                "abstract": "This is another test article.",
            },
        ]

        embeddings = self.model.predict(articles)

        self.assertIsInstance(embeddings, np.ndarray)
        self.assertEqual(embeddings.ndim, 2)
        self.assertEqual(embeddings.shape[0], 2)
        self.assertTrue(np.all(np.isfinite(embeddings)))

    def test_save_load(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, "test_model")

            self.model.save(save_path)
            self.assertTrue(os.path.exists(save_path))

            new_model = ArticleEmbeddingModel()
            new_model.load(save_path)

            embedding1 = self.model.predict(self.sample_article)
            embedding2 = new_model.predict(self.sample_article)
            np.testing.assert_array_almost_equal(embedding1, embedding2)


if __name__ == "__main__":
    unittest.main()
