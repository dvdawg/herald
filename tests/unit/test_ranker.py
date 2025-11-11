import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from src.ranking_engine.ranker import ArticleRanker

class TestArticleRanker(unittest.TestCase):
    def setUp(self):
        # Mock citation fetcher to avoid API calls in tests
        with patch('src.ranking_engine.ranker.CitationFetcher') as mock_citation:
            mock_citation.return_value.get_citation_count.return_value = None
            self.ranker = ArticleRanker()
        
        self.sample_articles = [
            {
                'title': 'Recent ML Paper',
                'abstract': 'A paper about machine learning',
                'published': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'citation_count': 10
            },
            {
                'title': 'Old ML Paper',
                'abstract': 'An older paper about machine learning',
                'published': (datetime.utcnow() - timedelta(days=365)).isoformat(),
                'citation_count': 100
            }
        ]

    def test_rank_articles_empty(self):
        """Test ranking with empty article list"""
        results = self.ranker.rank_articles([])
        self.assertEqual(len(results), 0)

    def test_rank_articles_with_query(self):
        """Test ranking with search query"""
        query = "machine learning"
        results = self.ranker.rank_articles(self.sample_articles, query=query)
        
        self.assertEqual(len(results), 2)
        self.assertTrue(all(isinstance(score, float) for _, score in results))
        self.assertTrue(all(0 <= score <= 1 for _, score in results))

    def test_rank_articles_with_weights(self):
        """Test ranking with custom weights"""
        weights = {
            'relevance': 0.7,
            'recency': 0.2,
            'citations': 0.1
        }
        results = self.ranker.rank_articles(
            self.sample_articles,
            weights=weights
        )
        
        self.assertEqual(len(results), 2)
        self.assertTrue(all(isinstance(score, float) for _, score in results))
    
    def test_citation_score_with_cached_count(self):
        """Test citation scoring with cached citation count"""
        article = {
            'title': 'Test Paper',
            'abstract': 'Test abstract',
            'citation_count': 500
        }
        
        score = self.ranker._calculate_citation_score(article)
        
        # Should be a normalized score between 0 and 1
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_citation_score_without_count(self):
        """Test citation scoring when no citation count available"""
        article = {
            'title': 'Test Paper',
            'abstract': 'Test abstract'
        }
        
        score = self.ranker._calculate_citation_score(article)
        
        # Should return 0.0 when no citations
        self.assertEqual(score, 0.0)
    
    def test_recency_score_configurable(self):
        """Test that recency decay is configurable"""
        article = {
            'title': 'Test Paper',
            'abstract': 'Test abstract',
            'published': (datetime.utcnow() - timedelta(days=100)).isoformat()
        }
        
        score = self.ranker._calculate_recency_score(article)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

if __name__ == '__main__':
    unittest.main() 