"""
Tests for Herald pipeline.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from src.pipeline import HeraldPipeline


class TestHeraldPipeline(unittest.TestCase):
    def setUp(self):
        # Mock the components to avoid actual API calls and model loading
        with patch('src.pipeline.ArxivScraper'), \
             patch('src.pipeline.MetadataProcessor'), \
             patch('src.pipeline.TextProcessor'), \
             patch('src.pipeline.ArticleRanker'):
            self.pipeline = HeraldPipeline()
    
    @patch('src.pipeline.ArxivScraper')
    @patch('src.pipeline.MetadataProcessor')
    @patch('src.pipeline.TextProcessor')
    @patch('src.pipeline.ArticleRanker')
    def test_pipeline_initialization(self, mock_ranker, mock_text, mock_meta, mock_scraper):
        """Test pipeline initializes all components"""
        pipeline = HeraldPipeline()
        
        mock_scraper.assert_called_once()
        mock_meta.assert_called_once()
        mock_text.assert_called_once()
        mock_ranker.assert_called_once()
    
    @patch('src.pipeline.ArxivScraper')
    @patch('src.pipeline.MetadataProcessor')
    @patch('src.pipeline.TextProcessor')
    @patch('src.pipeline.ArticleRanker')
    def test_search_and_rank_integration(self, mock_ranker_class, mock_text_class, 
                                         mock_meta_class, mock_scraper_class):
        """Test full search and rank pipeline"""
        # Setup mocks
        mock_scraper = Mock()
        mock_scraper.search_articles.return_value = [
            {
                'title': 'Test Paper 1',
                'abstract': 'This is about machine learning',
                'published': datetime.utcnow().isoformat(),
                'authors': ['Author 1']
            },
            {
                'title': 'Test Paper 2',
                'abstract': 'This is about deep learning',
                'published': (datetime.utcnow() - timedelta(days=100)).isoformat(),
                'authors': ['Author 2']
            }
        ]
        mock_scraper_class.return_value = mock_scraper
        
        mock_meta_processor = Mock()
        mock_meta_processor.process.side_effect = lambda x: x  # Pass through
        mock_meta_class.return_value = mock_meta_processor
        
        mock_text_processor = Mock()
        mock_text_processor.process.return_value = {'processed_words': ['test']}
        mock_text_class.return_value = mock_text_processor
        
        mock_ranker = Mock()
        mock_ranker.rank_articles.return_value = [
            ({'title': 'Test Paper 1'}, 0.9),
            ({'title': 'Test Paper 2'}, 0.7)
        ]
        mock_ranker_class.return_value = mock_ranker
        
        # Create pipeline and test
        pipeline = HeraldPipeline()
        results = pipeline.search_and_rank("machine learning", max_results=10)
        
        # Verify calls
        mock_scraper.search_articles.assert_called_once_with(
            query="machine learning",
            max_results=10
        )
        mock_ranker.rank_articles.assert_called_once()
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][1], 0.9)
    
    @patch('src.pipeline.ArxivScraper')
    @patch('src.pipeline.MetadataProcessor')
    @patch('src.pipeline.TextProcessor')
    @patch('src.pipeline.ArticleRanker')
    def test_get_article_by_id(self, mock_ranker_class, mock_text_class,
                               mock_meta_class, mock_scraper_class):
        """Test getting article by ID"""
        mock_scraper = Mock()
        mock_scraper.get_article_by_id.return_value = {
            'title': 'Test Paper',
            'abstract': 'Test abstract',
            'arxiv_id': '1234.5678'
        }
        mock_scraper_class.return_value = mock_scraper
        
        mock_meta_processor = Mock()
        mock_meta_processor.process.side_effect = lambda x: x
        mock_meta_class.return_value = mock_meta_processor
        
        mock_text_processor = Mock()
        mock_text_processor.process.return_value = {'processed_words': ['test']}
        mock_text_class.return_value = mock_text_processor
        
        mock_ranker_class.return_value = Mock()
        
        pipeline = HeraldPipeline()
        article = pipeline.get_article_by_id('1234.5678')
        
        mock_scraper.get_article_by_id.assert_called_once_with('1234.5678')
        self.assertEqual(article['title'], 'Test Paper')
    
    @patch('src.pipeline.ArxivScraper')
    @patch('src.pipeline.MetadataProcessor')
    @patch('src.pipeline.TextProcessor')
    @patch('src.pipeline.ArticleRanker')
    def test_rank_existing_articles(self, mock_ranker_class, mock_text_class,
                                    mock_meta_class, mock_scraper_class):
        """Test ranking existing articles without fetching"""
        mock_ranker = Mock()
        mock_ranker.rank_articles.return_value = [
            ({'title': 'Paper 1'}, 0.8),
            ({'title': 'Paper 2'}, 0.6)
        ]
        mock_ranker_class.return_value = mock_ranker
        
        mock_scraper_class.return_value = Mock()
        mock_meta_class.return_value = Mock()
        mock_text_class.return_value = Mock()
        
        pipeline = HeraldPipeline()
        articles = [
            {'title': 'Paper 1', 'abstract': 'Abstract 1'},
            {'title': 'Paper 2', 'abstract': 'Abstract 2'}
        ]
        
        results = pipeline.rank_existing_articles(articles, query="test")
        
        mock_ranker.rank_articles.assert_called_once_with(
            articles=articles,
            query="test",
            weights=None
        )
        self.assertEqual(len(results), 2)


if __name__ == '__main__':
    unittest.main()

