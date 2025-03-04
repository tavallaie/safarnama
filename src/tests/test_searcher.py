import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import httpx

from safarnama.searcher import SearxNGSearcher


# Dummy DBHandler to simulate instance records for searcher tests.
class DummyDBHandler:
    class DummyInstance:
        def __init__(self, url, priority):
            self.url = url
            self.priority = priority

    def get_available_instances(self):
        # Return a single dummy instance record.
        return [self.DummyInstance("http://fake-instance", 10)]

    def update_all_priorities(self):
        pass

    def update_sleep(self, url, sleep_seconds):
        pass

    def clear_sleep(self, url):
        pass

    def close(self):
        pass


class TestSearxNGSearcher(unittest.TestCase):
    def setUp(self):
        self.db = DummyDBHandler()
        # Set timeout low and retries 0 for tests.
        self.searcher = SearxNGSearcher(self.db, timeout=5, retries=0)

    @patch("httpx.Client.get")
    def test_check_instance_health_success(self, mock_get):
        # Fake healthy response.
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"dummy": "data"}
        fake_response.raise_for_status = lambda: None
        mock_get.return_value = fake_response

        healthy, message = self.searcher.check_instance_health(
            "http://fake-instance", "test"
        )
        self.assertTrue(healthy)
        self.assertEqual(message, "healthy")

    @patch("httpx.Client.get")
    def test_perform_search_success(self, mock_get):
        # Fake successful search response with JSON.
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "results": [{"url": "http://link1"}, {"url": "http://link2"}]
        }
        fake_response.raise_for_status = lambda: None
        mock_get.return_value = fake_response

        result = self.searcher.perform_search("http://fake-instance", "query")
        self.assertIsNotNone(result)
        self.assertIn("results", result)
        self.assertEqual(len(result["results"]), 2)

    @patch("safarnama.searcher.SearxNGSearcher.check_instance_health")
    @patch("safarnama.searcher.SearxNGSearcher.perform_search")
    def test_search_overall_success(self, mock_search, mock_health):
        # Setup dummy health and search responses.
        mock_health.return_value = (True, "healthy")
        mock_search.return_value = {
            "results": [{"url": "http://link1"}, {"url": "http://link2"}]
        }

        result = self.searcher.search("query")
        self.assertIsNotNone(result)
        instance_used, data = result
        self.assertEqual(instance_used, "http://fake-instance")
        self.assertEqual(len(data["results"]), 2)


if __name__ == "__main__":
    unittest.main()
