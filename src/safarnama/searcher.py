import httpx
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Any
from loguru import logger

from safarnama.db import DBHandler


class SearxNGSearcher:
    """
    High-level searcher that queries available SearxNG instances stored in the DB,
    selects a healthy instance, and returns search results.
    """

    def __init__(self, db: DBHandler, timeout: int = 10, retries: int = 1):
        self.db = db
        self.timeout = timeout
        self.retries = retries
        self.instances = self.load_instances()

    def load_instances(self) -> List:
        return self.db.get_available_instances()

    def update_instances(self):
        self.db.update_all_priorities()
        self.instances = self.load_instances()

    def search(self, query: str) -> Optional[Tuple[str, Any]]:
        attempt = 0
        while attempt <= self.retries:
            self.update_instances()
            for record in self.instances:
                instance_url = record.url.rstrip("/")
                logger.info(
                    f"Trying instance: {instance_url} (priority: {record.priority})"
                )
                healthy, message = self.check_instance_health(instance_url)
                if not healthy:
                    logger.info(f"Instance {instance_url} not healthy: {message}")
                    continue
                result = self.perform_search(instance_url, query)
                if result is not None:
                    logger.info(f"Success using instance: {instance_url}")
                    return instance_url, result
            logger.info("No healthy instance found. Retrying...")
            attempt += 1
        return None

    def check_instance_health(
        self, instance_url: str, test_query: str = "test"
    ) -> Tuple[bool, str]:
        params = {"q": test_query, "format": "json"}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(instance_url, params=params)
                if response.status_code == 429:
                    self.db.update_sleep(instance_url, 60)
                    return False, "rate_limited"
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Unexpected JSON structure")
                self.db.clear_sleep(instance_url)
                return True, "healthy"
        except Exception as e:
            self.db.update_sleep(instance_url, 24 * 3600)
            return False, f"error: {e}"

    def perform_search(self, instance_url: str, query: str) -> Optional[Any]:
        params = {"q": query, "format": "json"}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(instance_url, params=params)
                if response.status_code == 429:
                    self.db.update_sleep(instance_url, 60)
                    logger.info(f"Instance {instance_url} rate limited.")
                    return None
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error with instance {instance_url}: {e}")
            return None
