import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock

import sqlalchemy
from sqlalchemy.exc import SQLAlchemyError

from safarnama.config import load_config
from safarnama.html_cleaner import HTMLCleaner
from safarnama.db import DBHandler
from safarnama.crawler import SiteCrawler


# -------------------------------
# Tests for HTMLCleaner
# -------------------------------
class TestHTMLCleaner(unittest.TestCase):
    def test_clean_html_removes_scripts_and_styles(self):
        html = "<script>alert('hi');</script><style>body{}</style><p>Content</p>"
        cleaned = HTMLCleaner.clean_html(html)
        self.assertNotIn("script", cleaned.lower())
        self.assertNotIn("style", cleaned.lower())
        self.assertIn("Content", cleaned)

    def test_clean_html_excludes_patterns(self):
        html = "<p>This text contains unwantedtext and should be cleaned.</p>"
        cleaned = HTMLCleaner.clean_html(html, exclude_patterns=["unwantedtext"])
        self.assertNotIn("unwantedtext", cleaned)


# -------------------------------
# Tests for Config Loader
# -------------------------------
class TestConfig(unittest.TestCase):
    def test_default_config(self):
        # Using a non-existent config file so defaults are applied.
        config = load_config("non_existing_config.yaml")
        self.assertIn("base_url", config)
        self.assertEqual(config["base_url"], "https://www.techbend.io")
        # Ensure connection_string is set (from env or fallback).
        self.assertIn("connection_string", config)
        self.assertTrue(
            config["connection_string"].startswith("sqlite")
            or config["connection_string"].startswith("postgresql")
        )


# -------------------------------
# Tests for DBHandler
# -------------------------------
class TestDBHandler(unittest.TestCase):
    def setUp(self):
        # Use an in-memory SQLite database for tests.
        self.db = DBHandler("sqlite:///:memory:")

    def test_insert_and_get_url(self):
        try:
            self.db.insert_url("https://example.com", 0, "to_visit")
        except SQLAlchemyError as e:
            self.fail(f"insert_url raised an exception: {e}")
        url, depth = self.db.get_next_url(1)
        self.assertEqual(url, "https://example.com")
        self.assertEqual(depth, 0)

    def test_update_url_status(self):
        self.db.insert_url("https://example.com", 0, "to_visit")
        self.db.update_url_status("https://example.com", "visited", "text/html")
        # After updating, the URL should not be returned as 'to_visit'
        url, depth = self.db.get_next_url(1)
        self.assertIsNone(url)


# -------------------------------
# Tests for LLM Integration in SiteCrawler
# -------------------------------
class TestLLMIntegration(unittest.TestCase):
    def setUp(self):
        # Dummy configuration for testing LLM integration.
        self.config = {
            "base_url": "https://example.com",
            "max_depth": 1,
            "delay": 0,
            "llm": {
                "endpoint": "http://fake-llm",
                "model": "dummy",
                "max_tokens": 100,
                "temperature": 0.5,
                "llm_prompt_template": "Dummy prompt:",
                "system_prompt": "Dummy system prompt:",
                "api_key": "dummy",
            },
            "download_binaries": False,
            "download_specific_binaries": [],
            "find_images": False,
            "respect_robots": False,
            "exclude_url_patterns": [],
            "exclude_content_patterns": [],
            "binary_extensions": [],
            "accepted_content_types": ["text/html"],
            "depth_settings": {},
            "url_settings": {},
            "connection_string": "sqlite:///:memory:",
        }
        self.crawler = SiteCrawler(self.config)

    @patch("httpx.post")
    def test_get_summary_and_tags_success(self, mock_post):
        # Simulate a successful LLM response.
        fake_response = MagicMock()
        fake_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"summary": "Test summary", "tags": ["tag1", "tag2"]}'
                    }
                }
            ]
        }
        fake_response.raise_for_status = lambda: None
        mock_post.return_value = fake_response

        summary, tags = self.crawler.get_summary_and_tags("<p>Test content</p>")
        self.assertEqual(summary, "Test summary")
        self.assertEqual(tags, ["tag1", "tag2"])

    @patch("httpx.post")
    def test_get_summary_and_tags_error(self, mock_post):
        # Simulate an LLM error response.
        fake_response = MagicMock()
        fake_response.json.return_value = {"error": "Some error"}
        fake_response.raise_for_status = lambda: None
        mock_post.return_value = fake_response

        summary, tags = self.crawler.get_summary_and_tags("<p>Test content</p>")
        self.assertEqual(summary, "")
        self.assertEqual(tags, [])


# -------------------------------
# Tests for Sitemap Generation
# -------------------------------
class TestSitemapGeneration(unittest.TestCase):
    def test_generate_sitemap(self):
        dummy_urls = {"https://example.com", "https://example.com/about"}
        config = {
            "base_url": "https://example.com",
            "max_depth": 1,
            "delay": 0,
            "llm": {},
            "download_binaries": False,
            "download_specific_binaries": [],
            "find_images": False,
            "respect_robots": False,
            "exclude_url_patterns": [],
            "exclude_content_patterns": [],
            "binary_extensions": [],
            "accepted_content_types": ["text/html"],
            "depth_settings": {},
            "url_settings": {},
            "connection_string": "sqlite:///:memory:",
        }
        crawler = SiteCrawler(config)
        sitemap_tree = crawler.generate_sitemap(dummy_urls)
        sitemap_str = ET.tostring(sitemap_tree.getroot(), encoding="unicode")
        self.assertIn("https://example.com", sitemap_str)
        self.assertIn("https://example.com/about", sitemap_str)


# -------------------------------
# Tests for URL Exclusion Logic
# -------------------------------
class TestShouldExcludeUrl(unittest.TestCase):
    def test_should_exclude(self):
        config = {
            "exclude_url_patterns": ["forbidden"],
            "depth_settings": {},
            "url_settings": {},
            "connection_string": "sqlite:///:memory:",
        }
        crawler = SiteCrawler(config)
        self.assertTrue(
            crawler.should_exclude_url("https://example.com/forbidden", ["forbidden"])
        )
        self.assertFalse(
            crawler.should_exclude_url("https://example.com/allowed", ["forbidden"])
        )


if __name__ == "__main__":
    unittest.main()
