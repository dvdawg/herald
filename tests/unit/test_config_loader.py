"""
Tests for configuration loader.
"""
import unittest
import tempfile
import os
import yaml
from src.utils.config_loader import ConfigLoader


class TestConfigLoader(unittest.TestCase):
    def setUp(self):
        self.default_config = ConfigLoader._get_default_config(ConfigLoader())
    
    def test_default_config(self):
        """Test that default config is loaded when file doesn't exist"""
        # Use a non-existent path
        config = ConfigLoader(config_path='/nonexistent/path/config.yaml')
        
        self.assertIsNotNone(config.config)
        self.assertIn('ranking', config.config)
        self.assertIn('models', config.config)
    
    def test_load_from_file(self):
        """Test loading config from YAML file"""
        test_config = {
            'ranking': {
                'weights': {
                    'relevance': 0.7,
                    'recency': 0.2,
                    'citations': 0.1
                }
            },
            'models': {
                'embedding_model': 'test-model'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_path = f.name
        
        try:
            config = ConfigLoader(config_path=temp_path)
            
            self.assertEqual(config.get('ranking.weights.relevance'), 0.7)
            self.assertEqual(config.get('models.embedding_model'), 'test-model')
        finally:
            os.unlink(temp_path)
    
    def test_get_ranking_weights(self):
        """Test getting ranking weights"""
        config = ConfigLoader()
        weights = config.get_ranking_weights()
        
        self.assertIn('relevance', weights)
        self.assertIn('recency', weights)
        self.assertIn('citations', weights)
        self.assertIsInstance(weights['relevance'], float)
    
    def test_get_embedding_model_name(self):
        """Test getting embedding model name"""
        config = ConfigLoader()
        model_name = config.get_embedding_model_name()
        
        self.assertIsInstance(model_name, str)
        self.assertEqual(model_name, 'all-MiniLM-L6-v2')
    
    def test_is_citation_enabled(self):
        """Test citation enabled check"""
        config = ConfigLoader()
        enabled = config.is_citation_enabled()
        
        self.assertIsInstance(enabled, bool)
    
    def test_get_with_dot_notation(self):
        """Test getting config values with dot notation"""
        config = ConfigLoader()
        
        value = config.get('ranking.weights.relevance')
        self.assertIsNotNone(value)
        self.assertIsInstance(value, float)
    
    def test_get_with_default(self):
        """Test getting config value with default"""
        config = ConfigLoader()
        
        value = config.get('nonexistent.key', 'default_value')
        self.assertEqual(value, 'default_value')
    
    def test_partial_config_merges_with_defaults(self):
        """Test that partial config merges with defaults"""
        partial_config = {
            'ranking': {
                'weights': {
                    'relevance': 0.8
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(partial_config, f)
            temp_path = f.name
        
        try:
            config = ConfigLoader(config_path=temp_path)
            
            # Should have custom relevance
            self.assertEqual(config.get('ranking.weights.relevance'), 0.8)
            # Should have default recency
            self.assertIsNotNone(config.get('ranking.weights.recency'))
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    unittest.main()

