"""
Configuration loader for Herald application.
"""
import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Loads and manages application configuration."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the config loader.
        
        Args:
            config_path: Path to config file. If None, looks for config/config.yaml
        """
        if config_path is None:
            # Default to config/config.yaml relative to project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "config.yaml"
        
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.load()
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary (defaults)
            override: Override dictionary (user config)
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = self._deep_merge(result[key], value)
            else:
                # Override with new value
                result[key] = value
        
        return result
    
    def load(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found at {self.config_path}, using defaults")
            self.config = self._get_default_config()
            return
        
        try:
            with open(self.config_path, 'r') as f:
                user_config = yaml.safe_load(f) or {}
            
            # Deep merge with defaults to ensure all keys exist
            defaults = self._get_default_config()
            self.config = self._deep_merge(defaults, user_config)
            
            logger.info(f"Loaded configuration from {self.config_path}")
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}, using defaults")
            self.config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'ranking': {
                'weights': {
                    'relevance': 0.5,
                    'recency': 0.3,
                    'citations': 0.2
                },
                'recency_decay_days': 730  # 2 years
            },
            'models': {
                'embedding_model': 'all-MiniLM-L6-v2'
            },
            'citation': {
                'enabled': True,
                'rate_limit_delay': 0.1,
                'normalization_max_citations': 1000
            },
            'data_collection': {
                'max_results': 100,
                'default_sort': 'submitted_date',
                'default_sort_order': 'descending'
            },
            'processing': {
                'process_metadata': True,
                'process_text': True
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key (supports dot notation).
        
        Args:
            key: Configuration key (e.g., 'ranking.weights.relevance')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_ranking_weights(self) -> Dict[str, float]:
        """Get ranking weights configuration."""
        return self.get('ranking.weights', {
            'relevance': 0.5,
            'recency': 0.3,
            'citations': 0.2
        })
    
    def get_embedding_model_name(self) -> str:
        """Get embedding model name."""
        return self.get('models.embedding_model', 'all-MiniLM-L6-v2')
    
    def is_citation_enabled(self) -> bool:
        """Check if citation fetching is enabled."""
        return self.get('citation.enabled', True)
    
    def get_citation_rate_limit(self) -> float:
        """Get citation API rate limit delay."""
        return self.get('citation.rate_limit_delay', 0.1)
    
    def get_max_citations_for_normalization(self) -> int:
        """Get max citations for normalization."""
        return self.get('citation.normalization_max_citations', 1000)

