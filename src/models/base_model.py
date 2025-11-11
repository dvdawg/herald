from abc import ABC, abstractmethod
from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)

class BaseModel(ABC):
    """Base class for all models."""
    
    def __init__(self):
        """Initialize the model."""
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def train(self, data: Any) -> None:
        """
        Train the model on the given data.
        
        Args:
            data: Training data
        """
        pass

    @abstractmethod
    def predict(self, data: Any) -> Any:
        """
        Make predictions using the model.
        
        Args:
            data: Input data for prediction
            
        Returns:
            Model predictions
        """
        pass

    @abstractmethod
    def save(self, path: str) -> None:
        """
        Save the model to disk.
        
        Args:
            path: Path to save the model
        """
        pass

    @abstractmethod
    def load(self, path: str) -> None:
        """
        Load the model from disk.
        
        Args:
            path: Path to load the model from
        """
        pass

    def log_prediction(self, input_data: Any, prediction: Any) -> None:
        """
        Log prediction information.
        
        Args:
            input_data: Input data
            prediction: Model prediction
        """
        self.logger.info(f"Made prediction for input type: {type(input_data)}") 