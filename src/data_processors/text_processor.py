import re
from typing import Dict, List, Optional
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

from .base_processor import BaseProcessor

class TextProcessor(BaseProcessor):
    """Processor for handling article text processing."""
    
    def __init__(self):
        """Initialize the text processor."""
        super().__init__()
        try:
            nltk.data.find('tokenizers/punkt')
            nltk.data.find('corpora/stopwords')
            nltk.data.find('corpora/wordnet')
        except LookupError:
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
            nltk.download('wordnet', quiet=True)
        
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            try:
                nltk.download('punkt_tab', quiet=True)
            except Exception:
                pass
        
        self.stop_words = set(stopwords.words('english'))
        self.lemmatizer = WordNetLemmatizer()

    def process(self, text: str) -> Dict[str, any]:
        """
        Process the input text.
        
        Args:
            text: Input text to process
            
        Returns:
            Dict containing processed text components
        """
        if not self.validate_input(text):
            raise ValueError("Invalid input text")

        cleaned_text = self._clean_text(text)
        
        sentences = sent_tokenize(cleaned_text)
        words = word_tokenize(cleaned_text.lower())
        
        processed_words = [
            self.lemmatizer.lemmatize(word)
            for word in words
            if word.isalnum() and word not in self.stop_words
        ]
        
        key_phrases = self._extract_key_phrases(sentences)
        
        result = {
            'cleaned_text': cleaned_text,
            'sentences': sentences,
            'processed_words': processed_words,
            'key_phrases': key_phrases,
            'word_count': len(processed_words),
            'sentence_count': len(sentences)
        }
        
        self.log_processing(text, result)
        return result

    def validate_input(self, text: str) -> bool:
        """
        Validate the input text.
        
        Args:
            text: Input text to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        return isinstance(text, str) and len(text.strip()) > 0

    def _clean_text(self, text: str) -> str:
        """
        Clean the input text.
        
        Args:
            text: Input text to clean
            
        Returns:
            Cleaned text
        """
        text = re.sub(r'[^\w\s.]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_key_phrases(self, sentences: List[str], max_phrases: int = 5) -> List[str]:
        """
        Extract key phrases from sentences.
        
        Args:
            sentences: List of sentences
            max_phrases: Maximum number of phrases to extract
            
        Returns:
            List of key phrases
        """
        return sentences[:max_phrases] 