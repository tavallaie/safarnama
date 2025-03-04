import os
import re
import time
import json
import httpx
import urllib.robotparser
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from loguru import logger
from bs4 import BeautifulSoup

from safarnama.html_cleaner import HTMLCleaner
from safarnama.db import DBHandler


class SiteCrawler:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.base_url = config.get("base_url")
        self.max_depth = config.get("max_depth", 2)
        self.delay = config.get("delay", 1)
        self.llm_config = config.get("llm", {})
        self.accepted_content_types = config.get("accepted_content_types")
        self.binary_extensions = config.get("binary_extensions", [])
        self.download_binaries = config.get("download_binaries", False)
        self.download_specific_binaries = config.get("download_specific_binaries", [])
        self.find_images = config.get("find_images", False)
        self.respect_robots = config.get("respect_robots", True)
        self.exclude_url_patterns = config.get("exclude_url_patterns", [])
        self.exclude_content_patterns = config.get("exclude_content_patterns", [])
        self.depth_settings = config.get("depth_settings", {})
        self.url_settings = config.get("url_settings", {})

        connection_string = config.get("connection_string", "sqlite:///python.db")
        self.db = DBHandler(connection_string)
        self.rp = None
        if self.respect_robots:
            self.rp = self.get_robots_parser(self.base_url)
        self.html_cleaner = HTMLCleaner

    def get_robots_parser(self, base_url: str) -> urllib.robotparser.RobotFileParser:
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
        except Exception as e:
            logger.error(f"Error reading robots.txt from {robots_url}: {e}")
        return rp

    def is_allowed(self, url: str, user_agent: str = "*") -> bool:
        if not self.respect_robots:
            return True
        return self.rp.can_fetch(user_agent, url)

    def is_binary_url(self, url: str) -> bool:
        for ext in self.binary_extensions:
            if url.lower().endswith(ext):
                return True
        return False

    def should_exclude_url(self, url: str, exclude_patterns: list = None) -> bool:
        patterns = (
            exclude_patterns
            if exclude_patterns is not None
            else self.exclude_url_patterns
        )
        for pattern in patterns:
            if re.search(pattern, url):
                logger.info(f"Excluding URL {url} due to pattern match: {pattern}")
                return True
        return False

    def get_url_specific_settings(self, url: str) -> dict:
        if url in self.url_settings:
            return self.url_settings[url]
        for pattern, settings in self.url_settings.items():
            if re.search(pattern, url):
                return settings
        return {}

    def merge_settings(self, url: str, depth: int) -> dict:
        effective = {
            "download_binaries": self.download_binaries,
            "download_specific_binaries": self.download_specific_binaries,
            "find_images": self.find_images,
            "exclude_url_patterns": self.exclude_url_patterns,
            "exclude_content_patterns": self.exclude_content_patterns,
        }
        effective.update(self.depth_settings.get(depth, {}))
        effective.update(self.get_url_specific_settings(url))
        return effective

    def download_file(self, url: str, dest_folder: str = "downloads") -> None:
        try:
            os.makedirs(dest_folder, exist_ok=True)
            local_filename = os.path.join(
                dest_folder, os.path.basename(urlparse(url).path)
            )
            with httpx.stream("GET", url) as r:
                with open(local_filename, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
            logger.info(f"Downloaded file from {url} to {local_filename}")
        except Exception as e:
            logger.error(f"Failed to download file {url}: {e}")

    def add_url(
        self, url: str, depth: int, status: str = "to_visit", content_type: str = None
    ) -> None:
        effective_settings = self.merge_settings(url, depth)
        if self.should_exclude_url(
            url, effective_settings.get("exclude_url_patterns", [])
        ):
            return

        if self.is_binary_url(url):
            ext = os.path.splitext(urlparse(url).path)[1].lower()
            if effective_settings.get("download_binaries") or (
                effective_settings.get("download_specific_binaries")
                and ext in effective_settings.get("download_specific_binaries")
            ):
                self.download_file(url)
                self.update_url_status(url, "downloaded", "binary")
            else:
                logger.info(f"Skipping binary URL (pre-request): {url}")
                self.update_url_status(url, "ignored", "binary")
            return

        self.db.insert_url(url, depth, status, content_type)

    def update_url_status(
        self, url: str, status: str, content_type: str = None
    ) -> None:
        self.db.update_url_status(url, status, content_type)

    def update_page_info(self, url: str, summary: str, tags: str) -> None:
        self.db.update_page_info(url, summary, tags)

    def get_next_url(self) -> tuple:
        return self.db.get_next_url(self.max_depth)

    def get_summary_and_tags(self, text: str, effective_settings: dict = None) -> tuple:
        exclude_patterns = (
            effective_settings.get(
                "exclude_content_patterns", self.exclude_content_patterns
            )
            if effective_settings
            else self.exclude_content_patterns
        )
        cleaned_text = self.html_cleaner.clean_html(
            text, clean_svg=True, clean_base64=True, exclude_patterns=exclude_patterns
        )
        prompt_template = self.llm_config.get("llm_prompt_template", "")
        system_prompt = self.llm_config.get(
            "system_prompt",
            "You are a helpful assistant that summarizes webpages and extracts tags.",
        )
        prompt = f"{prompt_template}\n\n{cleaned_text}"
        payload = {
            "model": self.llm_config.get("model", ""),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.llm_config.get("max_tokens", 200000),
            "temperature": self.llm_config.get("temperature", 0.7),
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.llm_config.get('api_key', '')}",
        }
        timeout_config = httpx.Timeout(
            120.0, connect=120.0, read=120.0, write=120.0, pool=120.0
        )
        retries = 3
        for attempt in range(retries):
            try:
                endpoint = self.llm_config.get("endpoint", "")
                logger.info(f"Sending request to LLM endpoint: {endpoint}")
                response = httpx.post(
                    endpoint, json=payload, headers=headers, timeout=timeout_config
                )
                response.raise_for_status()
                response_json = response.json()
                if "error" in response_json:
                    logger.error(f"LLM returned error: {response_json['error']}")
                    return "", []
                choices = response_json.get("choices")
                if not choices:
                    logger.error(f"LLM response missing 'choices': {response_json}")
                    return "", []
                content = choices[0]["message"]["content"]
                if content.startswith("```json"):
                    content = content[len("```json") :].strip()
                if content.endswith("```"):
                    content = content[:-3].strip()
                result = json.loads(content)
                summary = result.get("summary", "")
                tags = result.get("tags", [])
                return summary, tags
            except httpx.TimeoutException as e:
                logger.error(f"LLM request timeout on attempt {attempt+1}: {e}")
                time.sleep(2)
            except Exception as e:
                logger.error(f"LLM request error on attempt {attempt+1}: {e}")
                break
        return "", []

    def generate_sitemap(self, urls: set) -> ET.ElementTree:
        urlset = ET.Element(
            "urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        )
        for url in urls:
            url_elem = ET.SubElement(urlset, "url")
            loc = ET.SubElement(url_elem, "loc")
            loc.text = url
        return ET.ElementTree(urlset)

    def crawl(self) -> set:
        self.add_url(self.base_url, 0)
        visited_urls = set()
        with httpx.Client(timeout=10) as client:
            while True:
                current_url, depth = self.get_next_url()
                if not current_url:
                    break
                effective_settings = self.merge_settings(current_url, depth)
                if self.should_exclude_url(
                    current_url, effective_settings.get("exclude_url_patterns", [])
                ):
                    self.update_url_status(current_url, "ignored")
                    continue
                if self.is_binary_url(current_url):
                    continue
                logger.info(f"Processing {current_url} at depth {depth}")
                if not self.is_allowed(current_url):
                    logger.info(f"Skipping disallowed URL: {current_url}")
                    self.update_url_status(current_url, "ignored")
                    continue
                try:
                    response = client.get(current_url)
                except Exception as e:
                    logger.error(f"Error fetching {current_url}: {e}")
                    self.update_url_status(current_url, "ignored")
                    continue
                content_type = (
                    response.headers.get("Content-Type", "").split(";")[0].strip()
                )
                if content_type not in self.accepted_content_types:
                    logger.info(
                        f"Ignoring {current_url}: unsupported content type '{content_type}'"
                    )
                    self.update_url_status(current_url, "ignored", content_type)
                    continue
                self.update_url_status(current_url, "visited", content_type)
                visited_urls.add(current_url)
                if "html" in content_type.lower():
                    summary, tags = self.get_summary_and_tags(
                        response.text, effective_settings
                    )
                    logger.info(f"Summary for {current_url}: {summary}")
                    logger.info(f"Tags for {current_url}: {tags}")
                    tags_str = ", ".join(
                        (tag.get("name", "") if isinstance(tag, dict) else tag).replace(
                            "/", ""
                        )
                        for tag in tags
                    )
                    self.update_page_info(current_url, summary, tags_str)
                    if effective_settings.get("find_images", self.find_images):
                        soup = BeautifulSoup(response.text, "html.parser")
                        for img in soup.find_all("img", src=True):
                            img_url = urljoin(current_url, img.get("src"))
                            logger.info(f"Found image: {img_url}")
                            if effective_settings.get(
                                "download_binaries", self.download_binaries
                            ):
                                self.download_file(img_url, dest_folder="images")
                    if self.config.get("recursive_crawl", True):
                        soup = BeautifulSoup(response.text, "html.parser")
                        for link in soup.find_all("a", href=True):
                            href = link.get("href")
                            if href.startswith("#") or not href.strip():
                                continue
                            absolute_url = urljoin(current_url, href)
                            if (
                                urlparse(absolute_url).netloc
                                == urlparse(self.base_url).netloc
                            ):
                                next_depth = depth + 1
                                self.add_url(absolute_url, next_depth)
                time.sleep(self.delay)
        return visited_urls

    def close(self) -> None:
        self.db.close()
