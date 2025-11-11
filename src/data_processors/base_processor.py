from abc import ABC, abstractmethod
from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)

class BaseProcessor(ABC):
    """Base class for all data processors."""
    
    def __init__(self):
        """Initialize the processor."""
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def process(self, data: Any) -> Any:
        """
        Process the input data.
        
        Args:
            data: Input data to process
            
        Returns:
            Processed data
        """
        pass

    def validate_input(self, data: Any) -> bool:
        """
        Validate the input data.
        
        Args:
            data: Input data to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        return True

    def log_processing(self, data: Any, result: Any) -> None:
        """
        Log processing information.
        
        Args:
            data: Input data
            result: Processing result
        """
        self.logger.info(f"Processed data: {type(data)} -> {type(result)}") 