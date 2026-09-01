#!/usr/bin/env python3
"""Fetch Golem's Atom feed, persist articles in SQLite, and emit RSS 2.0."""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

import requests


SOURCE_URL = "https://rss.golem.de/rss.php?feed=ATOM1.0"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0"
ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
ATOM = f"{{{ATOM_NAMESPACE}}}"
RSS_URL = "https://seraangel.github.io/feed-golem/rss.xml"
GOLEM_ICON_URL = "https://www.golem.de/staticrl/images/Golem-Logo-black-small.png"
RETRY_DELAYS = {503: 10, 429: 15}
RETRY_WINDOW_SECONDS = 60
ET.register_namespace("atom", ATOM_NAMESPACE)


@dataclass(frozen=True)
class Article:
    url: str
    title: str
    summary: str
    published_at: str | None


class PlainTextExtractor(HTMLParser):
    """Extract readable text from the HTML fragments embedded in Atom summaries."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "div", "li", "p"}:
            self.parts.append(" ")

    def text(self) -> str:
        return "".join(self.parts)


def clean_text(value: str | None) -> str:
    parser = PlainTextExtractor()
    parser.feed(value or "")
    parser.close()
    return " ".join(parser.text().split())


def parse_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def extract_articles(document: bytes) -> list[Article]:
    root = ET.fromstring(document)
    if root.tag != f"{ATOM}feed":
        raise RuntimeError("Expected an Atom 1.0 feed from Golem.")

    articles: list[Article] = []
    seen: set[str] = set()
    for entry in root.findall(f"{ATOM}entry"):
        link = next(
            (
                element.get("href")
                for element in entry.findall(f"{ATOM}link")
                if element.get("href") and element.get("rel", "alternate") == "alternate"
            ),
            None,
        )
        title = clean_text(entry.findtext(f"{ATOM}title"))
        summary = clean_text(entry.findtext(f"{ATOM}summary") or entry.findtext(f"{ATOM}content"))
        published_at = parse_datetime(entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated"))
        if not link or not title or link in seen:
            continue
        articles.append(Article(link, title, summary, published_at))
        seen.add(link)

    if not articles:
        raise RuntimeError("No Golem articles found in the Atom feed.")
    return articles


def fetch_feed(timeout: int) -> bytes:
    """Fetch the source feed, retrying temporary overload and rate-limit responses.

    The retry window contains the pauses between attempts: 503 is retried every
    10 seconds and 429 every 15 seconds, for no more than 60 seconds total.
    """
    elapsed_wait = 0
    while True:
        response = requests.get(
            SOURCE_URL,
            headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml, application/xml;q=0.9, */*;q=0.8"},
            timeout=timeout,
        )
        delay = RETRY_DELAYS.get(response.status_code)
        if delay is None:
            response.raise_for_status()
            return response.content

        if elapsed_wait >= RETRY_WINDOW_SECONDS:
            response.raise_for_status()

        sleep_for = min(delay, RETRY_WINDOW_SECONDS - elapsed_wait)
        print(
            f"Golem feed returned HTTP {response.status_code}; retrying in {sleep_for} seconds "
            f"({elapsed_wait + sleep_for}/{RETRY_WINDOW_SECONDS} seconds).",
            file=sys.stderr,
        )
        time.sleep(sleep_for)
        elapsed_wait += sleep_for


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            url TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            published_at TEXT,
            first_seen_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_articles_sort ON articles(published_at DESC, first_seen_at DESC)"
    )


def upsert_articles(connection: sqlite3.Connection, articles: Iterable[Article], now: str) -> int:
    changed = 0
    for article in articles:
        existing = connection.execute(
            "SELECT title, summary, published_at FROM articles WHERE url = ?", (article.url,)
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO articles (url, title, summary, published_at, first_seen_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (article.url, article.title, article.summary, article.published_at, now, now),
            )
            changed += 1
        elif tuple(existing) != (article.title, article.summary, article.published_at):
            connection.execute(
                "UPDATE articles SET title = ?, summary = ?, published_at = ?, updated_at = ? WHERE url = ?",
                (article.title, article.summary, article.published_at, now, article.url),
            )
            changed += 1
    return changed


def load_feed_items(connection: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    return list(connection.execute("""
        SELECT url, title, summary, published_at, first_seen_at, updated_at
        FROM articles
        ORDER BY COALESCE(published_at, first_seen_at) DESC, first_seen_at DESC, url ASC
        LIMIT ?
    """, (limit,)))


def iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def add_text(parent: ET.Element, name: str, text: str) -> None:
    ET.SubElement(parent, name).text = text


def build_rss(items: list[sqlite3.Row]) -> bytes:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    add_text(channel, "title", "Golem.de")
    add_text(channel, "link", "https://www.golem.de/")
    add_text(channel, "description", "Aktuelle Artikel von Golem.de.")
    add_text(channel, "language", "de-DE")
    ET.SubElement(
        channel,
        f"{ATOM}link",
        {"href": RSS_URL, "rel": "self", "type": "application/rss+xml"},
    )
    image = ET.SubElement(channel, "image")
    add_text(image, "url", GOLEM_ICON_URL)
    add_text(image, "title", "Golem.de")
    add_text(image, "link", "https://www.golem.de/")
    if items:
        add_text(channel, "lastBuildDate", format_datetime(max(iso_datetime(row["updated_at"]) for row in items), usegmt=True))
    for row in items:
        item = ET.SubElement(channel, "item")
        add_text(item, "title", row["title"])
        add_text(item, "link", row["url"])
        guid = ET.SubElement(item, "guid", {"isPermaLink": "true"})
        guid.text = row["url"]
        if row["summary"]:
            add_text(item, "description", row["summary"])
        add_text(item, "pubDate", format_datetime(iso_datetime(row["published_at"] or row["first_seen_at"]), usegmt=True))
    ET.indent(rss, space="  ")
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def write_if_changed(path: Path, content: bytes) -> bool:
    if path.exists() and path.read_bytes() == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return True


def update_feed(db_path: Path, out_path: Path, limit: int, timeout: int) -> tuple[int, int, bool]:
    articles = extract_articles(fetch_feed(timeout))
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        ensure_schema(connection)
        changed_rows = upsert_articles(connection, articles, now)
        rss_changed = write_if_changed(out_path, build_rss(load_feed_items(connection, limit)))
    return len(articles), changed_rows, rss_changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/articles.sqlite"))
    parser.add_argument("--out", type=Path, default=Path("public/rss.xml"))
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit < 1 or args.limit > 200:
        print("--limit must be between 1 and 200.", file=sys.stderr)
        return 2
    try:
        found, changed_rows, rss_changed = update_feed(args.db, args.out, args.limit, args.timeout)
    except Exception as exc:
        print(f"Failed to update feed: {exc}", file=sys.stderr)
        return 1
    print(f"Found {found} articles; changed {changed_rows} database rows; rss.xml {'updated' if rss_changed else 'unchanged'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
