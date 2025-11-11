"""
Main pipeline for Herald article search and ranking system.
"""
import logging
from typing import List, Dict, Optional, Tuple

from src.data_collectors.arxiv_scrape import ArxivScraper
from src.data_processors.metadata_processor import MetadataProcessor
from src.data_processors.text_processor import TextProcessor
from src.ranking_engine.ranker import ArticleRanker
from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


class HeraldPipeline:
    """
    Main pipeline that orchestrates article collection, processing, and ranking.
    """
    
    def __init__(self, config: Optional[ConfigLoader] = None):
        """
        Initialize the Herald pipeline.
        
        Args:
            config: Optional configuration loader. If None, loads default config.
        """
        self.config = config or ConfigLoader()
        
        self.scraper = ArxivScraper()
        self.metadata_processor = MetadataProcessor()
        self.text_processor = TextProcessor()
        self.ranker = ArticleRanker(config=self.config)
        
        logger.info("Herald pipeline initialized")
    
    def search_and_rank(
        self,
        query: str,
        max_results: Optional[int] = None,
        weights: Optional[Dict[str, float]] = None,
        process_metadata: Optional[bool] = None,
        process_text: Optional[bool] = None
    ) -> List[Tuple[Dict, float]]:
        """
        Search for articles and rank them based on query and various criteria.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to fetch (defaults to config)
            weights: Optional custom ranking weights
            process_metadata: Whether to process metadata (defaults to config)
            process_text: Whether to process text (defaults to config)
            
        Returns:
            List of (article, score) tuples, sorted by score (descending)
        """
        logger.info(f"Starting search and rank for query: '{query}'")
        
        max_results = max_results or self.config.get('data_collection.max_results', 100)
        process_metadata = process_metadata if process_metadata is not None else \
            self.config.get('processing.process_metadata', True)
        process_text = process_text if process_text is not None else \
            self.config.get('processing.process_text', True)
        
        logger.info(f"Fetching up to {max_results} articles from arXiv...")
        articles = self.scraper.search_articles(
            query=query,
            max_results=max_results
        )
        
        if not articles:
            logger.warning("No articles found")
            return []
        
        logger.info(f"Fetched {len(articles)} articles")
        
        processed_articles = []
        for i, article in enumerate(articles):
            try:
                if process_metadata:
                    article = self.metadata_processor.process(article)
                
                if process_text and 'abstract' in article:
                    text_result = self.text_processor.process(article['abstract'])
                    article['processed_text'] = text_result
                
                processed_articles.append(article)
                
                if (i + 1) % 10 == 0:
                    logger.debug(f"Processed {i + 1}/{len(articles)} articles")
                    
            except Exception as e:
                logger.error(f"Error processing article {i}: {str(e)}")
                processed_articles.append(article)
        
        logger.info(f"Processed {len(processed_articles)} articles")
        
        logger.info("Ranking articles...")
        ranked_articles = self.ranker.rank_articles(
            articles=processed_articles,
            query=query,
            weights=weights
        )
        
        logger.info(f"Ranked {len(ranked_articles)} articles")
        
        return ranked_articles
    
    def get_article_by_id(self, arxiv_id: str) -> Dict:
        """
        Get a single article by arXiv ID.
        
        Args:
            arxiv_id: arXiv ID of the article
            
        Returns:
            Article dictionary
        """
        logger.info(f"Fetching article: {arxiv_id}")
        article = self.scraper.get_article_by_id(arxiv_id)
        
        if self.config.get('processing.process_metadata', True):
            article = self.metadata_processor.process(article)
        
        if self.config.get('processing.process_text', True) and 'abstract' in article:
            text_result = self.text_processor.process(article['abstract'])
            article['processed_text'] = text_result
        
        return article
    
    def rank_existing_articles(
        self,
        articles: List[Dict],
        query: Optional[str] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> List[Tuple[Dict, float]]:
        """
        Rank a list of existing articles without fetching new ones.
        
        Args:
            articles: List of article dictionaries
            query: Optional search query for relevance scoring
            weights: Optional custom ranking weights
            
        Returns:
            List of (article, score) tuples, sorted by score (descending)
        """
        logger.info(f"Ranking {len(articles)} existing articles")
        return self.ranker.rank_articles(
            articles=articles,
            query=query,
            weights=weights
        )


def main():
    """CLI entry point for Herald pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Herald: Academic Article Search and Ranking System"
    )
    parser.add_argument(
        'query',
        type=str,
        help='Search query string'
    )
    parser.add_argument(
        '--max-results',
        type=int,
        default=None,
        help='Maximum number of results to fetch (default: from config)'
    )
    parser.add_argument(
        '--output',
        type=str,
        choices=['json', 'table', 'simple'],
        default='table',
        help='Output format (default: table)'
    )
    parser.add_argument(
        '--top',
        type=int,
        default=10,
        help='Number of top results to display (default: 10)'
    )
    parser.add_argument(
        '--weights',
        type=str,
        default=None,
        help='Custom weights as comma-separated key:value pairs (e.g., relevance:0.7,recency:0.2,citations:0.1)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    weights = None
    if args.weights:
        weights = {}
        for pair in args.weights.split(','):
            key, value = pair.split(':')
            weights[key.strip()] = float(value.strip())
    
    pipeline = HeraldPipeline()
    
    try:
        results = pipeline.search_and_rank(
            query=args.query,
            max_results=args.max_results,
            weights=weights
        )
        
        top_results = results[:args.top]
        
        if args.output == 'json':
            import json
            output = [
                {
                    'article': article,
                    'score': float(score)
                }
                for article, score in top_results
            ]
            print(json.dumps(output, indent=2, default=str))
        
        elif args.output == 'table':
            print(f"\n{'='*80}")
            print(f"Top {len(top_results)} Results for: '{args.query}'")
            print(f"{'='*80}\n")
            
            for i, (article, score) in enumerate(top_results, 1):
                print(f"{i}. {article.get('title', 'Unknown Title')}")
                print(f"   Score: {score:.4f}")
                print(f"   Authors: {', '.join(article.get('authors', []))}")
                print(f"   Published: {article.get('published', 'Unknown')}")
                if 'citation_count' in article:
                    print(f"   Citations: {article['citation_count']}")
                print(f"   URL: {article.get('pdf_url', 'N/A')}")
                print()
        
        else:
            for i, (article, score) in enumerate(top_results, 1):
                print(f"{i}. [{score:.4f}] {article.get('title', 'Unknown Title')}")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=args.verbose)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

