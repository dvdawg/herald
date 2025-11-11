"""
Tests for citation fetcher.
"""
import unittest
from unittest.mock import patch, Mock
from src.utils.citation_fetcher import CitationFetcher


class TestCitationFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = CitationFetcher(rate_limit_delay=0.01)
        self.sample_article = {
            'title': 'Attention Is All You Need',
            'arxiv_id': '1706.03762',
            'doi': '10.48550/arXiv.1706.03762'
        }
    
    @patch('src.utils.citation_fetcher.requests.get')
    def test_fetch_by_arxiv_id_success(self, mock_get):
        """Test successful citation fetch by arXiv ID"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'citationCount': 50000}
        mock_get.return_value = mock_response
        
        result = self.fetcher._fetch_by_arxiv_id('1706.03762')
        
        self.assertEqual(result, 50000)
        mock_get.assert_called_once()
    
    @patch('src.utils.citation_fetcher.requests.get')
    def test_fetch_by_arxiv_id_not_found(self, mock_get):
        """Test citation fetch when paper not found"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = self.fetcher._fetch_by_arxiv_id('9999.99999')
        
        self.assertIsNone(result)
    
    @patch('src.utils.citation_fetcher.requests.get')
    def test_fetch_by_doi_success(self, mock_get):
        """Test successful citation fetch by DOI"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'citationCount': 1000}
        mock_get.return_value = mock_response
        
        result = self.fetcher._fetch_by_doi('10.48550/arXiv.1706.03762')
        
        self.assertEqual(result, 1000)
    
    @patch('src.utils.citation_fetcher.requests.get')
    def test_get_citation_count_with_arxiv_id(self, mock_get):
        """Test getting citation count using arXiv ID"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'citationCount': 50000}
        mock_get.return_value = mock_response
        
        article = {'arxiv_id': '1706.03762'}
        result = self.fetcher.get_citation_count(article)
        
        self.assertEqual(result, 50000)
    
    @patch('src.utils.citation_fetcher.requests.get')
    def test_get_citation_count_with_doi(self, mock_get):
        """Test getting citation count using DOI"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'citationCount': 1000}
        mock_get.return_value = mock_response
        
        article = {'doi': '10.48550/arXiv.1706.03762'}
        result = self.fetcher.get_citation_count(article)
        
        self.assertEqual(result, 1000)
    
    @patch('src.utils.citation_fetcher.requests.get')
    def test_get_citation_count_not_found(self, mock_get):
        """Test when citation count cannot be found"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        article = {'title': 'Unknown Paper'}
        result = self.fetcher.get_citation_count(article)
        
        self.assertIsNone(result)
    
    def test_get_citation_count_with_cached_value(self):
        """Test that cached citation count is used"""
        article = {'citation_count': 100}
        result = self.fetcher.get_citation_count(article)
        
        # Should return cached value without API call
        self.assertEqual(result, 100)


if __name__ == '__main__':
    unittest.main()

