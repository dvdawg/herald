"""
Utility for fetching citation data from external APIs.
"""
import logging
from typing import Dict, Optional
import requests
import time

logger = logging.getLogger(__name__)


class CitationFetcher:
    """Fetches citation counts from Semantic Scholar API."""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper"
    
    def __init__(self, rate_limit_delay: float = 0.1):
        """
        Initialize the citation fetcher.
        
        Args:
            rate_limit_delay: Delay between API calls in seconds (default 0.1)
        """
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
    
    def _rate_limit(self):
        """Enforce rate limiting between API calls."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()
    
    def get_citation_count(self, article: Dict) -> Optional[int]:
        """
        Get citation count for an article.
        
        Args:
            article: Article dictionary with metadata
            
        Returns:
            Citation count if found, None otherwise
        """
        # Check if citation count is already cached in the article
        if 'citation_count' in article and article['citation_count'] is not None:
            return article['citation_count']
        
        # Try multiple methods to find the paper
        paper_id = None
        
        # Method 1: Try DOI
        if 'doi' in article and article['doi']:
            paper_id = article['doi']
            citation_count = self._fetch_by_doi(paper_id)
            if citation_count is not None:
                return citation_count
        
        # Method 2: Try arXiv ID
        if 'arxiv_id' in article and article['arxiv_id']:
            paper_id = f"arXiv:{article['arxiv_id']}"
            citation_count = self._fetch_by_arxiv_id(article['arxiv_id'])
            if citation_count is not None:
                return citation_count
        
        # Method 3: Try searching by title
        if 'title' in article and article['title']:
            citation_count = self._fetch_by_title(article['title'])
            if citation_count is not None:
                return citation_count
        
        logger.debug(f"Could not find citation count for article: {article.get('title', 'Unknown')}")
        return None
    
    def _fetch_by_doi(self, doi: str) -> Optional[int]:
        """Fetch citation count by DOI."""
        try:
            self._rate_limit()
            url = f"{self.BASE_URL}/DOI:{doi}"
            params = {"fields": "citationCount"}
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('citationCount', 0)
            elif response.status_code == 404:
                return None
            else:
                logger.warning(f"Semantic Scholar API returned status {response.status_code} for DOI {doi}")
                return None
        except Exception as e:
            logger.error(f"Error fetching citation by DOI {doi}: {str(e)}")
            return None
    
    def _fetch_by_arxiv_id(self, arxiv_id: str) -> Optional[int]:
        """Fetch citation count by arXiv ID."""
        try:
            self._rate_limit()
            url = f"{self.BASE_URL}/arXiv:{arxiv_id}"
            params = {"fields": "citationCount"}
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('citationCount', 0)
            elif response.status_code == 404:
                return None
            else:
                logger.warning(f"Semantic Scholar API returned status {response.status_code} for arXiv ID {arxiv_id}")
                return None
        except Exception as e:
            logger.error(f"Error fetching citation by arXiv ID {arxiv_id}: {str(e)}")
            return None
    
    def _fetch_by_title(self, title: str) -> Optional[int]:
        """Fetch citation count by searching title."""
        try:
            self._rate_limit()
            url = f"{self.BASE_URL}/search"
            params = {
                "query": title,
                "limit": 1,
                "fields": "citationCount,title"
            }
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                papers = data.get('data', [])
                if papers:
                    # Check if title matches closely
                    first_paper = papers[0]
                    if first_paper.get('title', '').lower() == title.lower():
                        return first_paper.get('citationCount', 0)
            return None
        except Exception as e:
            logger.error(f"Error fetching citation by title {title}: {str(e)}")
            return None

