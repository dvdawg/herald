from typing import Dict, List, Union
import numpy as np
from sentence_transformers import SentenceTransformer
import torch
import pickle

from .base_model import BaseModel

class ArticleEmbeddingModel(BaseModel):
    """Model for generating article embeddings."""
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize the article embedding model.
        
        Args:
            model_name: Name of the sentence transformer model to use
        """
        super().__init__()
        self.model = SentenceTransformer(model_name)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)

    def train(self, data: List[Dict]) -> None:
        """
        Train the model on article data.
        
        Args:
            data: List of article dictionaries
        """
        # For sentence transformers, we don't need explicit training as it uses pre-trained models
        self.logger.info("Using pre-trained sentence transformer model")

    def predict(self, articles: Union[Dict, List[Dict]]) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Generate embeddings for articles.
        
        Args:
            articles: Single article dict or list of article dicts
            
        Returns:
            Embeddings for the articles
        """
        if isinstance(articles, dict):
            articles = [articles]
            
        texts = []
        for article in articles:
            text = f"{article.get('title', '')} {article.get('abstract', '')}"
            texts.append(text)
            
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=True
        )
        
        self.log_prediction(articles, embeddings)
        return embeddings[0] if len(articles) == 1 else embeddings

    def save(self, path: str) -> None:
        """
        Save the model to disk.
        
        Args:
            path: Path to save the model
        """
        self.model.save(path)

    def load(self, path: str) -> None:
        """
        Load the model from disk.
        
        Args:
            path: Path to load the model from
        """
        self.model = SentenceTransformer(path)
        self.model.to(self.device) 