#!/usr/bin/env python3
"""Fetch RSS feeds concurrently with a per-source health receipt and UTC cache."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import feedparser
import requests


class FeedFetcher:
    """Fetch enabled sources, retaining failures rather than hiding partial coverage."""

    def __init__(self, timeout=10, max_workers=10, cache_ttl=300, verbose=False, cache_dir=None):
        self.timeout = timeout
        self.max_workers = max_workers
        self.cache_ttl = cache_ttl
        self.verbose = verbose
        self.cache_dir = Path(cache_dir) if cache_dir is not None else Path(__file__).parent.parent / "data" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.diagnostics = []

    def fetch_all(self, sources: List[Dict[str, Any]]) -> Dict[str, str]:
        """Return successful content by name; diagnostics cover every configured source."""
        results = {}
        receipts = {}
        self.diagnostics = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            pending = {}
            for index, source in enumerate(sources):
                if source.get("enabled", True) is False:
                    receipts[index] = {
                        "source": source["name"],
                        "url": source["url"],
                        "status": "disabled",
                        "reason": source.get("disabled_reason", "Disabled in configuration"),
                    }
                else:
                    pending[executor.submit(self._fetch_one, source)] = (index, source)
            for future in as_completed(pending):
                index, source = pending[future]
                try:
                    content, receipt = future.result()
                except Exception as error:
                    content, receipt = None, {"status": "failed", "reason": type(error).__name__}
                receipts[index] = {"source": source["name"], "url": source["url"], **receipt}
                if content is not None:
                    results[source["name"]] = content
        self.diagnostics = [receipts[index] for index in range(len(sources))]
        return results

    @staticmethod
    def _is_feed(content: str) -> bool:
        """A 200 HTML error page is not a successful feed, including when cached."""
        feed = feedparser.parse(content)
        return bool(feed.version and (not feed.bozo or feed.entries))

    def _fetch_one(self, source):
        url = source.get("url", "")
        if not url:
            return None, {"status": "failed", "reason": "Missing feed URL"}
        cached = self._get_cached(url)
        if cached is not None and self._is_feed(cached):
            return cached, {"status": "ok", "cached": True}
        try:
            response = requests.get(
                url,
                timeout=self.timeout,
                headers={
                    "User-Agent": "CryptoNewsAggregator/2.0 (RSS Feed Reader)",
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
                },
            )
            response.raise_for_status()
            content = response.text
            if not self._is_feed(content):
                return None, {
                    "status": "failed",
                    "http_status": response.status_code,
                    "reason": "Response is not a recognized RSS/Atom feed",
                }
            self._set_cached(url, content)
            return content, {"status": "ok", "cached": False, "http_status": response.status_code}
        except requests.exceptions.Timeout:
            return None, {"status": "failed", "reason": "Request timed out"}
        except requests.exceptions.HTTPError as error:
            code = error.response.status_code if error.response is not None else None
            return None, {"status": "failed", "http_status": code, "reason": f"HTTP {code}"}
        except requests.exceptions.RequestException as error:
            return None, {"status": "failed", "reason": type(error).__name__}

    def _get_cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.md5(url.encode()).hexdigest()}.json"

    def _get_cached(self, url: str) -> Optional[str]:
        try:
            cached = json.loads(self._get_cache_path(url).read_text())
            cached_time = datetime.fromisoformat(cached["timestamp"])
            if cached_time.tzinfo is None:
                cached_time = cached_time.replace(tzinfo=timezone.utc)  # Legacy cache timestamps were UTC.
            age = datetime.now(timezone.utc) - cached_time
            if not timedelta(0) <= age <= timedelta(seconds=self.cache_ttl):
                return None
            content = cached.get("content")
            return content if isinstance(content, str) else None
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _set_cached(self, url: str, content: str) -> None:
        try:
            self._get_cache_path(url).write_text(
                json.dumps(
                    {
                        "url": url,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "content": content,
                    }
                )
            )
        except OSError:
            pass  # A cache-write failure does not invalidate a successful feed response.

    def clear_cache(self) -> int:
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except OSError:
                pass
        return count
