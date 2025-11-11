import unittest
import numpy as np
from src.models.article_embedding_model import ArticleEmbeddingModel

class TestArticleEmbeddingModel(unittest.TestCase):
    def setUp(self):
        self.model = ArticleEmbeddingModel()
        self.sample_article = {
            'title': 'Test Article',
            'abstract': 'This is a test article about machine learning.'
        }

    def test_predict_single_article(self):
        """Test embedding generation for a single article"""
        embedding = self.model.predict(self.sample_article)
        
        self.assertIsInstance(embedding, np.ndarray)
        self.assertEqual(embedding.ndim, 1)
        self.assertTrue(np.all(np.isfinite(embedding)))

    def test_predict_multiple_articles(self):
        """Test embedding generation for multiple articles"""
        articles = [
            self.sample_article,
            {
                'title': 'Another Article',
                'abstract': 'This is another test article.'
            }
        ]
        
        embeddings = self.model.predict(articles)
        
        self.assertIsInstance(embeddings, np.ndarray)
        self.assertEqual(embeddings.ndim, 2)
        self.assertEqual(embeddings.shape[0], 2)  # Two articles
        self.assertTrue(np.all(np.isfinite(embeddings)))

    def test_save_load(self):
        """Test model saving and loading"""
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, 'test_model')
            
            # Save model
            self.model.save(save_path)
            self.assertTrue(os.path.exists(save_path))
            
            # Load model
            new_model = ArticleEmbeddingModel()
            new_model.load(save_path)
            
            # Test loaded model
            embedding1 = self.model.predict(self.sample_article)
            embedding2 = new_model.predict(self.sample_article)
            
            np.testing.assert_array_almost_equal(embedding1, embedding2)

if __name__ == '__main__':
    unittest.main() 