from typing import Dict, List, Optional
from datetime import datetime
import re

from .base_processor import BaseProcessor

class MetadataProcessor(BaseProcessor):
    """Processor for handling article metadata processing."""
    
    def __init__(self):
        """Initialize the metadata processor."""
        super().__init__()

    def process(self, metadata: Dict) -> Dict:
        """
        Process the article metadata.
        
        Args:
            metadata: Dictionary containing article metadata
            
        Returns:
            Processed metadata dictionary
        """
        if not self.validate_input(metadata):
            raise ValueError("Invalid metadata input")

        processed = metadata.copy()
        
        # Process authors
        if 'authors' in processed:
            processed['authors'] = self._process_authors(processed['authors'])
        
        # Process dates
        if 'published' in processed:
            processed['published'] = self._process_date(processed['published'])
        if 'updated' in processed:
            processed['updated'] = self._process_date(processed['updated'])
        
        # Process categories
        if 'categories' in processed:
            processed['categories'] = self._process_categories(processed['categories'])
        
        # Add processing timestamp
        processed['processed_at'] = datetime.utcnow().isoformat()
        
        self.log_processing(metadata, processed)
        return processed

    def validate_input(self, metadata: Dict) -> bool:
        """
        Validate the input metadata.
        
        Args:
            metadata: Input metadata to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        return isinstance(metadata, dict) and len(metadata) > 0

    def _process_authors(self, authors: List[str]) -> List[Dict]:
        """
        Process author information.
        
        Args:
            authors: List of author names
            
        Returns:
            List of processed author dictionaries
        """
        processed_authors = []
        for author in authors:
            parts = author.split()
            processed_author = {
                'full_name': author,
                'first_name': parts[0] if parts else '',
                'last_name': parts[-1] if len(parts) > 1 else '',
                'middle_names': ' '.join(parts[1:-1]) if len(parts) > 2 else ''
            }
            processed_authors.append(processed_author)
        return processed_authors

    def _process_date(self, date_str: str) -> str:
        """
        Process date string into ISO format.
        
        Args:
            date_str: Date string to process
            
        Returns:
            ISO formatted date string
        """
        try:
            if isinstance(date_str, str):
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.isoformat()
            return date_str
        except ValueError:
            return date_str

    def _process_categories(self, categories: List[str]) -> List[str]:
        """
        Process and clean category names.
        
        Args:
            categories: List of category names
            
        Returns:
            List of processed category names
        """
        return [cat.strip().lower() for cat in categories] 