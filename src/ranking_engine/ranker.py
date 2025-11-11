from typing import Dict, List, Optional, Tuple
import numpy as np
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity
import math

from src.models.article_embedding_model import ArticleEmbeddingModel
from src.utils.citation_fetcher import CitationFetcher
from src.utils.config_loader import ConfigLoader

class ArticleRanker:
    """Engine for ranking articles based on various criteria."""
    
    def __init__(
        self,
        embedding_model: Optional[ArticleEmbeddingModel] = None,
        config: Optional[ConfigLoader] = None,
        citation_fetcher: Optional[CitationFetcher] = None
    ):
        """
        Initialize the article ranker.
        
        Args:
            embedding_model: Optional pre-initialized embedding model
            config: Optional configuration loader
            citation_fetcher: Optional citation fetcher (created if not provided)
        """
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
        weights: Optional[Dict[str, float]] = None
    ) -> List[Tuple[Dict, float]]:
        """
        Rank articles based on query and various criteria.
        
        Args:
            articles: List of articles to rank
            query: Optional search query
            weights: Optional weights for different ranking factors
                    (relevance, recency, citations, etc.)
            
        Returns:
            List of (article, score) tuples, sorted by score
        """
        if not articles:
            return []
            
        weights = weights or self.config.get_ranking_weights()
        
        scored_articles = []
        for article in articles:
            score = self._calculate_score(article, query, weights)
            scored_articles.append((article, score))
            
        return sorted(scored_articles, key=lambda x: x[1], reverse=True)
    
    def _calculate_score(
        self,
        article: Dict,
        query: Optional[str],
        weights: Dict[str, float]
    ) -> float:
        """
        Calculate the overall score for an article.
        
        Args:
            article: Article to score
            query: Optional search query
            weights: Weights for different scoring factors
            
        Returns:
            Overall score for the article
        """
        scores = {}
        
        if query:
            scores['relevance'] = self._calculate_relevance_score(article, query)
        else:
            scores['relevance'] = 0.0
            
        scores['recency'] = self._calculate_recency_score(article)
        
        scores['citations'] = self._calculate_citation_score(article)
        
        total_score = sum(
            scores[factor] * weight
            for factor, weight in weights.items()
        )
        
        return total_score
    
    def _calculate_relevance_score(self, article: Dict, query: str) -> float:
        """
        Calculate relevance score based on query similarity.
        
        Args:
            article: Article to score
            query: Search query
            
        Returns:
            Relevance score between 0 and 1
        """
        query_embedding = self.embedding_model.predict({'title': query, 'abstract': ''})
        article_embedding = self.embedding_model.predict(article)
        
        similarity = cosine_similarity(
            query_embedding.reshape(1, -1),
            article_embedding.reshape(1, -1)
        )[0][0]
        
        return float(similarity)
    
    def _calculate_recency_score(self, article: Dict) -> float:
        """
        Calculate recency score based on publication date.
        
        Args:
            article: Article to score
            
        Returns:
            Recency score between 0 and 1
        """
        if 'published' not in article:
            return 0.0
            
        try:
            pub_date = datetime.fromisoformat(article['published'].replace('Z', '+00:00'))
            now = datetime.utcnow()
            
            days_old = (now - pub_date).days
            
            decay_days = self.config.get('ranking.recency_decay_days', 730)
            score = np.exp(-days_old / decay_days)
            return float(score)
            
        except (ValueError, TypeError):
            return 0.0
    
    def _calculate_citation_score(self, article: Dict) -> float:
        """
        Calculate citation score based on citation count.
        
        Args:
            article: Article to score
            
        Returns:
            Citation score between 0 and 1
        """
        if not self.config.is_citation_enabled() or self.citation_fetcher is None:
            return 0.0
        
        citation_count = article.get('citation_count')
        
        if citation_count is None:
            citation_count = self.citation_fetcher.get_citation_count(article)
            if citation_count is not None:
                article['citation_count'] = citation_count
        
        if citation_count is None or citation_count == 0:
            return 0.0
        
        # prevents few highly cited papers from dominating
        max_citations = self.config.get_max_citations_for_normalization()
        normalized = math.log(1 + citation_count) / math.log(1 + max_citations)
        
        return float(min(1.0, max(0.0, normalized))) 