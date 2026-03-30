"""
Quick test script to search and list articles.
"""
from src.pipeline import HeraldPipeline

def main():
    # Initialize pipeline
    print("Initializing Herald pipeline...")
    pipeline = HeraldPipeline()
    
    # Quick search with small number of results
    query = "quantum computing"
    max_results = 20
    
    print(f"\nSearching for: '{query}' (max {max_results} results)")
    print("=" * 80)
    
    try:
        results = pipeline.search_and_rank(
            query=query,
            max_results=max_results
        )
        
        if not results:
            print("No results found.")
            return
        
        print(f"\nFound {len(results)} articles:\n")
        
        for i, (article, score) in enumerate(results, 1):
            print(f"{i}. {article.get('title', 'No title')[:70]}")
            print(f"   Score: {score:.4f}")
            print(f"   Published: {article.get('published', 'Unknown')}")
            
            # Handle authors - can be list of strings or list of dicts (after processing)
            authors = article.get('authors', [])[:3]
            if authors and isinstance(authors[0], dict):
                # Processed format: extract full_name from dicts
                author_names = [author.get('full_name', str(author)) for author in authors]
            else:
                # Original format: list of strings
                author_names = [str(author) for author in authors]
            print(f"   Authors: {', '.join(author_names)}")
            
            if 'citation_count' in article:
                print(f"   Citations: {article['citation_count']}")
            print(f"   URL: {article.get('pdf_url', 'N/A')}")
            print()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()