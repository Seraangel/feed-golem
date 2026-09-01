from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from xml.etree import ElementTree as ET

import requests

from scripts.update_feed import ATOM, GOLEM_ICON_URL, RSS_URL, build_rss, ensure_schema, extract_articles, fetch_feed, load_feed_items, upsert_articles, write_if_changed


SAMPLE_ATOM = b'''<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Golem.de</title>
  <entry><title>Erster Artikel</title><link href="https://www.golem.de/news/first-123.html"/><summary>Eine &lt;b&gt;Zusammenfassung&lt;/b&gt;.</summary><published>2026-07-10T12:00:00Z</published></entry>
  <entry><title>Zweiter Artikel</title><link href="https://www.golem.de/news/second-456.html"/><content>Weitere Details.</content><updated>2026-07-09T12:00:00+00:00</updated></entry>
</feed>'''


class UpdateFeedTests(unittest.TestCase):
    def test_extracts_atom_entries(self) -> None:
        articles = extract_articles(SAMPLE_ATOM)
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].url, "https://www.golem.de/news/first-123.html")
        self.assertEqual(articles[1].summary, "Weitere Details.")
        self.assertEqual(articles[0].published_at, "2026-07-10T12:00:00+00:00")

    def test_upsert_is_stable_and_rss_uses_standard_metadata(self) -> None:
        articles = extract_articles(SAMPLE_ATOM)
        with sqlite3.connect(":memory:") as connection:
            ensure_schema(connection)
            self.assertEqual(upsert_articles(connection, articles, "2026-07-11T10:00:00+00:00"), 2)
            self.assertEqual(upsert_articles(connection, articles, "2026-07-11T10:15:00+00:00"), 0)
            rss = ET.fromstring(build_rss(load_feed_items(connection, 200)))
        channel = rss.find("channel")
        self.assertEqual(channel.findtext("title"), "Golem.de")
        self.assertEqual(len(channel.findall("item")), 2)
        self.assertEqual(
            channel.find(f"{ATOM}link").attrib,
            {"href": RSS_URL, "rel": "self", "type": "application/rss+xml"},
        )
        self.assertEqual(channel.findtext("image/url"), GOLEM_ICON_URL)
        self.assertEqual(channel.findtext("image/title"), "Golem.de")
        self.assertEqual(channel.findtext("item/description"), "Eine Zusammenfassung.")

    def test_write_paths_can_be_created_in_temp_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out_path = Path(directory) / "public" / "rss.xml"
            self.assertTrue(write_if_changed(out_path, b"feed"))
            self.assertFalse(write_if_changed(out_path, b"feed"))

    @patch("scripts.update_feed.time.sleep")
    @patch("scripts.update_feed.requests.get")
    def test_fetch_feed_retries_503_every_ten_seconds(self, get: Mock, sleep: Mock) -> None:
        unavailable = Mock(status_code=503)
        successful = Mock(status_code=200, content=SAMPLE_ATOM)
        get.side_effect = [unavailable, unavailable, successful]

        self.assertEqual(fetch_feed(30), SAMPLE_ATOM)
        self.assertEqual(get.call_count, 3)
        self.assertEqual(sleep.call_args_list, [((10,),), ((10,),)])

    @patch("scripts.update_feed.time.sleep")
    @patch("scripts.update_feed.requests.get")
    def test_fetch_feed_stops_429_retries_after_one_minute(self, get: Mock, sleep: Mock) -> None:
        rate_limited = Mock(status_code=429)
        rate_limited.raise_for_status.side_effect = requests.HTTPError("429 Client Error")
        get.return_value = rate_limited

        with self.assertRaises(requests.HTTPError):
            fetch_feed(30)

        self.assertEqual(get.call_count, 5)
        self.assertEqual(sleep.call_args_list, [((15,),), ((15,),), ((15,),), ((15,),)])


if __name__ == "__main__":
    unittest.main()
