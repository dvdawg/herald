import arxiv
import datetime
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArxivScraper:
    def __init__(self):
        """Initialize the ArxivScraper."""
        self.client = arxiv.Client()

    def search_articles(
        self,
        query: str,
        max_results: int = 100,
        sort_by: arxiv.SortCriterion = arxiv.SortCriterion.SubmittedDate,
        sort_order: arxiv.SortOrder = arxiv.SortOrder.Descending
    ) -> List[Dict]:
        """
        Search for articles on arXiv based on given criteria.

        Args:
            query (str): Search query string
            max_results (int): Maximum number of results to return
            sort_by (arxiv.SortCriterion): Criterion to sort results by
            sort_order (arxiv.SortOrder): Order to sort results in

        Returns:
            List[Dict]: List of article metadata dictionaries
        """
        try:
            # Construct the search query
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=sort_by,
                sort_order=sort_order
            )

            # Execute the search
            results = list(self.client.results(search))
            
            # Convert results to dictionaries
            articles = []
            for result in results:
                article = {
                    'title': result.title,
                    'authors': [author.name for author in result.authors],
                    'abstract': result.summary,
                    'pdf_url': result.pdf_url,
                    'published': result.published,
                    'updated': result.updated,
                    'arxiv_id': result.entry_id.split('/')[-1],
                    'categories': result.categories,
                    'doi': result.doi,
                    'comment': result.comment
                }
                articles.append(article)

            logger.info(f"Successfully retrieved {len(articles)} articles")
            return articles

        except Exception as e:
            logger.error(f"Error searching arXiv: {str(e)}")
            raise

    def get_article_by_id(self, arxiv_id: str) -> Dict:
        """
        Get a specific article by its arXiv ID.

        Args:
            arxiv_id (str): The arXiv ID of the article

        Returns:
            Dict: Article metadata dictionary
        """
        try:
            search = arxiv.Search(id_list=[arxiv_id])
            result = next(self.client.results(search))
            
            article = {
                'title': result.title,
                'authors': [author.name for author in result.authors],
                'abstract': result.summary,
                'pdf_url': result.pdf_url,
                'published': result.published,
                'updated': result.updated,
                'arxiv_id': result.entry_id.split('/')[-1],
                'categories': result.categories,
                'doi': result.doi,
                'comment': result.comment
            }
            
            logger.info(f"Successfully retrieved article {arxiv_id}")
            return article

        except Exception as e:
            logger.error(f"Error retrieving article {arxiv_id}: {str(e)}")
            raise

def main():
    """Example usage of the ArxivScraper."""
    scraper = ArxivScraper()
    
    # Example: Search for recent machine learning papers
    query = "machine learning"
    articles = scraper.search_articles(
        query=query,
        max_results=10
    )
    
    # Print results
    for article in articles:
        print(f"\nTitle: {article['title']}")
        print(f"Authors: {', '.join(article['authors'])}")
        print(f"Published: {article['published']}")
        print(f"PDF URL: {article['pdf_url']}")
        print("-" * 80)

if __name__ == "__main__":
    main()
