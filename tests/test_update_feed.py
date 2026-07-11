from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.update_feed import build_rss, ensure_schema, extract_articles, load_feed_items, upsert_articles, write_if_changed


SAMPLE_ATOM = b'''<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Golem.de</title>
  <entry><title>Erster Artikel</title><link href="https://www.golem.de/news/first-123.html"/><summary>Eine Zusammenfassung.</summary><published>2026-07-10T12:00:00Z</published></entry>
  <entry><title>Zweiter Artikel</title><link href="https://www.golem.de/news/second-456.html"/><content>Weitere Details.</content><updated>2026-07-09T12:00:00+00:00</updated></entry>
</feed>'''


class UpdateFeedTests(unittest.TestCase):
    def test_extracts_atom_entries(self) -> None:
        articles = extract_articles(SAMPLE_ATOM)
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].url, "https://www.golem.de/news/first-123.html")
        self.assertEqual(articles[1].summary, "Weitere Details.")
        self.assertEqual(articles[0].published_at, "2026-07-10T12:00:00+00:00")

    def test_upsert_is_stable_and_rss_uses_golem_metadata(self) -> None:
        articles = extract_articles(SAMPLE_ATOM)
        with sqlite3.connect(":memory:") as connection:
            ensure_schema(connection)
            self.assertEqual(upsert_articles(connection, articles, "2026-07-11T10:00:00+00:00"), 2)
            self.assertEqual(upsert_articles(connection, articles, "2026-07-11T10:15:00+00:00"), 0)
            rss = ET.fromstring(build_rss(load_feed_items(connection, 1000)))
        channel = rss.find("channel")
        self.assertEqual(channel.findtext("title"), "Golem.de")
        self.assertEqual(len(channel.findall("item")), 2)

    def test_write_paths_can_be_created_in_temp_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out_path = Path(directory) / "public" / "rss.xml"
            self.assertTrue(write_if_changed(out_path, b"feed"))
            self.assertFalse(write_if_changed(out_path, b"feed"))


if __name__ == "__main__":
    unittest.main()
