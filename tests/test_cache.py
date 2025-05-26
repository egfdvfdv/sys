import unittest
from unittest.mock import MagicMock, patch
import json
import datetime # For non-serializable test

# Adjust the import path based on your project structure.
# If 'cache.py' is in the root 'agi_prompt_system' directory alongside 'tests',
# and 'tests' is run as a module, this might be:
# from ..cache import CacheManager
# For simplicity, assuming cache.py is discoverable in PYTHONPATH or tests are run from root.
# If cache.py is in a sub-package like 'utils', it would be 'from ..utils.cache import CacheManager'
# Given the previous `ls()` output, `cache.py` is in the root.
# However, to run tests correctly, it's better to assume a package structure.
# Let's assume 'agi_prompt_system' is the top-level package.
from agi_prompt_system.cache import CacheManager, settings as cache_settings

class TestCacheManager(unittest.TestCase):

    def setUp(self):
        """Set up for each test."""
        # Mock the Redis client instance within CacheManager
        self.mock_redis_client = MagicMock()
        
        # Patch 'redis.Redis' in the 'agi_prompt_system.cache' module
        # where CacheManager tries to create it.
        self.redis_patcher = patch('agi_prompt_system.cache.redis.Redis', return_value=self.mock_redis_client)
        self.mock_redis_constructor = self.redis_patcher.start()

        # Mock settings used by CacheManager if they affect Redis connection
        # (e.g., REDIS_HOST, REDIS_PORT). For _serialize/_deserialize, this isn't
        # strictly necessary, but good for set/get tests.
        # cache_settings is imported from agi_prompt_system.cache module.
        # We can patch specific attributes of this imported settings object.
        self.settings_patcher_host = patch.object(cache_settings, 'REDIS_HOST', 'mock_host')
        self.settings_patcher_port = patch.object(cache_settings, 'REDIS_PORT', 6379)
        self.settings_patcher_db = patch.object(cache_settings, 'REDIS_DB', 0)
        self.settings_patcher_password = patch.object(cache_settings, 'REDIS_PASSWORD', None, create=True) # create if not exists
        self.settings_patcher_prefix = patch.object(cache_settings, 'CACHE_PREFIX', 'test_cache', create=True)
        self.settings_patcher_ttl = patch.object(cache_settings, 'CACHE_TTL', 300, create=True)


        self.mock_settings_host = self.settings_patcher_host.start()
        self.mock_settings_port = self.settings_patcher_port.start()
        self.mock_settings_db = self.settings_patcher_db.start()
        self.mock_settings_password = self.settings_patcher_password.start()
        self.mock_settings_prefix = self.settings_patcher_prefix.start()
        self.mock_settings_ttl = self.settings_patcher_ttl.start()

        self.cache_manager = CacheManager(redis_client=self.mock_redis_client)
        # Ensure the client used by cache_manager is our mock
        self.assertEqual(self.cache_manager.redis, self.mock_redis_client)


    def tearDown(self):
        """Clean up after each test."""
        self.redis_patcher.stop()
        self.settings_patcher_host.stop()
        self.settings_patcher_port.stop()
        self.settings_patcher_db.stop()
        self.settings_patcher_password.stop()
        self.settings_patcher_prefix.stop()
        self.settings_patcher_ttl.stop()

    def test_serialization_to_json(self):
        """Test that a dictionary is serialized to JSON bytes."""
        data = {"key": "value", "number": 123}
        serialized_data = self.cache_manager._serialize(data)
        self.assertIsInstance(serialized_data, bytes)
        self.assertEqual(json.loads(serialized_data.decode('utf-8')), data)

    def test_serialization_non_json_serializable(self):
        """Test serializing a non-JSON-serializable object raises ValueError."""
        # datetime objects are not directly JSON serializable without a custom handler
        non_serializable_data = datetime.datetime.now()
        with self.assertRaises(ValueError) as context: # As per CacheManager's _serialize
            self.cache_manager._serialize(non_serializable_data)
        self.assertIn("Could not serialize value to JSON", str(context.exception))


    def test_deserialization_from_json(self):
        """Test that valid JSON bytes are deserialized correctly."""
        data = {"key": "value", "number": 123}
        json_bytes = json.dumps(data).encode('utf-8')
        deserialized_data = self.cache_manager._deserialize(json_bytes)
        self.assertEqual(deserialized_data, data)

    def test_deserialization_malformed_json(self):
        """Test deserializing malformed JSON bytes returns None."""
        malformed_json_bytes = b"{'key': 'value'," # Missing closing brace
        # _deserialize is expected to log an error and return None
        deserialized_data = self.cache_manager._deserialize(malformed_json_bytes)
        self.assertIsNone(deserialized_data)

    def test_deserialization_none_input(self):
        """Test deserializing None returns None."""
        deserialized_data = self.cache_manager._deserialize(None)
        self.assertIsNone(deserialized_data)

    def test_set_with_json(self):
        """Test cache.set() calls Redis client's setex with JSON bytes."""
        key = "test_key"
        value = {"data": "sample", "count": 1}
        ttl = 3600
        
        self.cache_manager.set(key, value, ttl=ttl)
        
        expected_cache_key = f"{self.cache_manager._key_prefix}{key}"
        expected_json_bytes = json.dumps(value).encode('utf-8')
        
        self.mock_redis_client.setex.assert_called_once_with(
            name=expected_cache_key,
            time=ttl,
            value=expected_json_bytes
        )

    def test_set_with_default_ttl(self):
        """Test cache.set() uses default TTL if none provided."""
        key = "test_key_default_ttl"
        value = {"data": "sample"}
        
        self.cache_manager.set(key, value) # No TTL provided
        
        expected_cache_key = f"{self.cache_manager._key_prefix}{key}"
        expected_json_bytes = json.dumps(value).encode('utf-8')
        default_ttl = cache_settings.CACHE_TTL # From patched settings
        
        self.mock_redis_client.setex.assert_called_once_with(
            name=expected_cache_key,
            time=default_ttl,
            value=expected_json_bytes
        )

    def test_get_existing_with_json(self):
        """Test cache.get() returns deserialized object when key exists."""
        key = "test_key_get"
        original_value = {"data": "retrieved", "id": 42}
        json_bytes = json.dumps(original_value).encode('utf-8')
        
        expected_cache_key = f"{self.cache_manager._key_prefix}{key}"
        self.mock_redis_client.get.return_value = json_bytes
        
        retrieved_value = self.cache_manager.get(key)
        
        self.mock_redis_client.get.assert_called_once_with(expected_cache_key)
        self.assertEqual(retrieved_value, original_value)
        self.assertEqual(self.cache_manager.stats['hits'], 1)


    def test_get_non_existing(self):
        """Test cache.get() returns default value when key does not exist."""
        key = "test_key_non_existing"
        default_value = "NOT_FOUND"
        
        expected_cache_key = f"{self.cache_manager._key_prefix}{key}"
        self.mock_redis_client.get.return_value = None
        
        retrieved_value = self.cache_manager.get(key, default=default_value)
        
        self.mock_redis_client.get.assert_called_once_with(expected_cache_key)
        self.assertEqual(retrieved_value, default_value)
        self.assertEqual(self.cache_manager.stats['misses'], 1)


    def test_delete(self):
        """Test cache.delete() calls Redis client's delete."""
        key = "test_key_delete"
        expected_cache_key = f"{self.cache_manager._key_prefix}{key}"
        self.mock_redis_client.delete.return_value = 1 # Simulate one key deleted
        
        result = self.cache_manager.delete(key)
        
        self.mock_redis_client.delete.assert_called_once_with(expected_cache_key)
        self.assertTrue(result)
        self.assertEqual(self.cache_manager.stats['deletes'], 1)

    def test_delete_non_existing(self):
        """Test cache.delete() returns False if key doesn't exist."""
        key = "test_key_delete_non_existing"
        expected_cache_key = f"{self.cache_manager._key_prefix}{key}"
        self.mock_redis_client.delete.return_value = 0 # Simulate no key deleted

        result = self.cache_manager.delete(key)

        self.mock_redis_client.delete.assert_called_once_with(expected_cache_key)
        self.assertFalse(result)
        self.assertEqual(self.cache_manager.stats['deletes'], 0) # Deletes stat increments on successful deletion count

if __name__ == '__main__':
    unittest.main()
