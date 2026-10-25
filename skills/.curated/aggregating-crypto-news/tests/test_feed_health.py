"""Offline RSS health, filtering, cache and UTC regression cases."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import patch

import feedparser
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from feed_fetcher import FeedFetcher
from feed_parser import FeedParser
from formatters import NewsFormatter
import news_aggregator


GOOD = {"name": "Good", "url": "https://good.example/feed", "quality": 8, "category": "market"}
BAD = {"name": "Bad", "url": "https://bad.example/feed"}
DISABLED = {
    "name": "Disabled",
    "url": "https://disabled.example/feed",
    "enabled": False,
    "disabled_reason": "Recorded unavailable endpoint",
}


def response(content, status=200):
    result = requests.Response()
    result.status_code = status
    result.url = "https://fixture.example/feed"
    result.encoding = "utf-8"
    result._content = content.encode()
    return result


def rss(items=True):
    date = format_datetime(datetime.now(timezone.utc) - timedelta(hours=1))
    entries = (
        (
            f"<item><title>Bitcoin update</title><link>https://news.example/1</link><pubDate>{date}</pubDate></item>"
            "<item><title>Bitcoin undated</title><link>https://news.example/2</link></item>"
        )
        if items
        else ""
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>Fixture</title>{entries}</channel></rss>'


class FeedHealthTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.fetcher = FeedFetcher(cache_dir=self.scratch.name)

    def test_partial_failure_and_disabled_receipts_preserve_configuration_order(self):
        def get(url, **kwargs):
            return response(rss()) if url == GOOD["url"] else response("missing", 404)

        with patch("feed_fetcher.requests.get", side_effect=get) as network:
            feeds = self.fetcher.fetch_all([BAD, GOOD, DISABLED])
        self.assertEqual(list(feeds), ["Good"])
        self.assertEqual([r["source"] for r in self.fetcher.diagnostics], ["Bad", "Good", "Disabled"])
        self.assertEqual([r["status"] for r in self.fetcher.diagnostics], ["failed", "ok", "disabled"])
        self.assertEqual(self.fetcher.diagnostics[0]["reason"], "HTTP 404")
        self.assertEqual(network.call_count, 2)

    def test_timeout_and_tls_failures_remain_visible(self):
        for error, reason in [(requests.Timeout(), "Request timed out"), (requests.exceptions.SSLError(), "SSLError")]:
            with self.subTest(error=type(error).__name__), patch("feed_fetcher.requests.get", side_effect=error):
                self.assertEqual(self.fetcher.fetch_all([GOOD]), {})
                self.assertEqual(self.fetcher.diagnostics[0]["reason"], reason)

    def test_html_200_is_not_cached_as_a_feed(self):
        with patch("feed_fetcher.requests.get", return_value=response("<html>Access denied</html>")):
            self.assertEqual(self.fetcher.fetch_all([GOOD]), {})
        self.assertFalse(self.fetcher._get_cache_path(GOOD["url"]).exists())
        self.assertEqual(self.fetcher.diagnostics[0]["status"], "failed")

    def test_valid_empty_feed_is_not_a_fetch_failure(self):
        with patch("feed_fetcher.requests.get", return_value=response(rss(False))):
            self.assertIn("Good", self.fetcher.fetch_all([GOOD]))
        self.assertEqual(self.fetcher.diagnostics[0]["status"], "ok")

    def test_valid_cache_has_explicit_cache_receipt(self):
        self.fetcher._set_cached(GOOD["url"], rss())
        with patch("feed_fetcher.requests.get", side_effect=AssertionError("network should not run")):
            self.assertIn("Good", self.fetcher.fetch_all([GOOD]))
        self.assertTrue(self.fetcher.diagnostics[0]["cached"])

    def test_invalid_cached_html_is_replaced_by_valid_network_feed(self):
        self.fetcher._set_cached(GOOD["url"], "<html>not RSS</html>")
        with patch("feed_fetcher.requests.get", return_value=response(rss())) as network:
            self.assertIn("Good", self.fetcher.fetch_all([GOOD]))
            network.assert_called_once()
        self.assertFalse(self.fetcher.diagnostics[0]["cached"])

    def test_legacy_utc_cache_and_expiry(self):
        for age, valid in [(timedelta(seconds=10), True), (timedelta(hours=1), False), (timedelta(hours=-1), False)]:
            with self.subTest(age=age):
                stamp = (datetime.now(timezone.utc) - age).replace(tzinfo=None).isoformat()
                self.fetcher._get_cache_path(GOOD["url"]).write_text(json.dumps({"timestamp": stamp, "content": rss()}))
                self.assertEqual(self.fetcher._get_cached(GOOD["url"]) is not None, valid)

    def test_offset_dates_normalize_to_utc_and_symbols_do_not_match_substrings(self):
        parser = FeedParser()
        entry = feedparser.FeedParserDict(published="Sun, 25 Oct 2026 14:00:00 +0200")
        self.assertEqual(parser._parse_date(entry), datetime(2026, 10, 25, 12, tzinfo=timezone.utc))
        self.assertEqual(parser._detect_coins("whether consolidated optional"), [])
        self.assertEqual(parser._detect_coins("Bitcoin and BTC"), ["BTC"])

    def run_cli(self, sources, fetch, fmt="json", extra_args=()):
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.object(news_aggregator, "load_sources", return_value=sources),
            patch.object(
                news_aggregator, "FeedFetcher", side_effect=lambda **kw: FeedFetcher(cache_dir=self.scratch.name, **kw)
            ),
            patch("feed_fetcher.requests.get", side_effect=fetch),
            patch.object(sys, "argv", ["news_aggregator.py", "--coin", "BTC", "--format", fmt, *extra_args]),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
        ):
            try:
                news_aggregator.main()
                code = 0
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def test_cli_json_distinguishes_partial_failure_from_undated_and_coin_matches(self):
        code, output, errors = self.run_cli(
            [GOOD, BAD, DISABLED], lambda url, **kw: response(rss()) if url == GOOD["url"] else response("", 403)
        )
        result = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual([a["title"] for a in result["articles"]], ["Bitcoin update"])
        self.assertEqual(result["meta"]["sources_configured"], 3)
        self.assertEqual(result["meta"]["sources_checked"], 2)
        self.assertEqual(result["meta"]["sources_failed"], 1)
        self.assertIn("Feed failed: Bad: HTTP 403", errors)
        good = result["meta"]["feed_health"][0]
        self.assertEqual(
            (good["articles_parsed"], good["undated_articles"], good["articles_in_window"], good["articles_matched"]),
            (2, 1, 1, 1),
        )
        self.assertEqual(datetime.fromisoformat(result["articles"][0]["published"]).utcoffset(), timedelta(0))
        self.assertNotIn("+00:00Z", output)

    def test_recency_sort_uses_utc_and_future_articles_do_not_enter_window(self):
        future = format_datetime(datetime.now(timezone.utc) + timedelta(days=1))
        content = rss().replace(
            "</channel>",
            f"<item><title>Bitcoin future</title><link>https://news.example/future</link><pubDate>{future}</pubDate></item></channel>",
        )
        code, output, _ = self.run_cli([GOOD], lambda *a, **kw: response(content), extra_args=("--sort-by", "recency"))
        self.assertEqual(code, 0)
        self.assertEqual([a["title"] for a in json.loads(output)["articles"]], ["Bitcoin update"])

    def test_all_failed_exits_nonzero_with_machine_readable_health(self):
        code, output, errors = self.run_cli([BAD], lambda *a, **kw: response("", 404))
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output)["meta"]["sources_succeeded"], 0)
        self.assertIn("No usable feeds fetched", errors)

    def test_empty_valid_feed_exits_successfully_with_zero_matches(self):
        code, output, errors = self.run_cli([GOOD], lambda *a, **kw: response(rss(False)))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["articles"], [])
        self.assertEqual(errors, "")

    def test_csv_diagnostics_stay_off_stdout(self):
        code, output, errors = self.run_cli(
            [GOOD, BAD], lambda url, **kw: response(rss()) if url == GOOD["url"] else response("", 404), "csv"
        )
        self.assertEqual(code, 0)
        self.assertTrue(output.startswith("rank,title,url,"))
        self.assertNotIn("Feed failed", output)
        self.assertIn("Feed failed: Bad", errors)

    def test_configuration_never_silently_falls_back(self):
        with patch.object(news_aggregator, "SCRIPT_DIR", Path(self.scratch.name) / "scripts"):
            with self.assertRaises(OSError):
                news_aggregator.load_sources()
            config = Path(self.scratch.name) / "config"
            config.mkdir()
            path = config / "sources.yaml"
            for text in (
                "sources: [",
                "sources: []",
                "sources: [{name: duplicate, url: https://one}, {name: duplicate, url: https://two}]",
                "sources: [{name: invalid, url: https://one, enabled: yesplease}]",
            ):
                path.write_text(text)
                with self.subTest(text=text), self.assertRaises(ValueError):
                    news_aggregator.load_sources()

    def test_table_includes_failures_and_stale_coverage(self):
        result = {
            "articles": [],
            "meta": {
                "sources_configured": 2,
                "sources_succeeded": 1,
                "sources_failed": 1,
                "feed_health": [
                    {"source": "Bad", "status": "failed", "reason": "HTTP 404"},
                    {
                        "source": "Old",
                        "status": "ok",
                        "articles_in_window": 0,
                        "latest_published": "2025-01-01T00:00:00+00:00",
                    },
                ],
            },
        }
        text = NewsFormatter().format(result)
        self.assertIn("Bad: failed", text)
        self.assertIn("Old: no dated articles in window", text)


if __name__ == "__main__":
    unittest.main()
