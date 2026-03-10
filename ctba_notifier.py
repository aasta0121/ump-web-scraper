#!/usr/bin/env python3
"""Monitor CTBA announcements and notify LINE when new umpire-training posts appear."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

DEFAULT_URL = "http://www.ctba.org.tw/news.php?cate=works&type=16"
DEFAULT_KEYWORD = "裁判講習"
DEFAULT_STATE_FILE = "state/ctba_seen.json"
LINE_PUSH_API = "https://api.line.me/v2/bot/message/push"


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str

    @property
    def item_id(self) -> str:
        raw = f"{self.title}\n{self.url}".encode("utf-8")
        return hashlib.sha1(raw).hexdigest()


class AnchorParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self._current_href: str | None = None
        self._text_chunks: list[str] = []
        self.anchors: list[NewsItem] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        href = attr_map.get("href", "").strip()
        self._current_href = href or None
        self._text_chunks = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._text_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return
        title = " ".join("".join(self._text_chunks).split())
        if title:
            self.anchors.append(
                NewsItem(title=title, url=urljoin(self.base_url, self._current_href))
            )
        self._current_href = None
        self._text_chunks = []


def fetch_html(url: str, timeout: int = 20) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ctba-ump-notifier/1.0)",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        encoding = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(encoding, errors="replace")


def parse_matching_news(html: str, base_url: str, keyword: str) -> list[NewsItem]:
    parser = AnchorParser(base_url=base_url)
    parser.feed(html)

    matched: list[NewsItem] = []
    seen: set[str] = set()
    for item in parser.anchors:
        if keyword not in item.title:
            continue
        if item.item_id in seen:
            continue
        seen.add(item.item_id)
        matched.append(item)
    return matched


def load_seen_ids(state_file: Path) -> set[str]:
    if not state_file.exists():
        return set()
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    if not isinstance(data, list):
        return set()
    return {str(x) for x in data}


def save_seen_ids(state_file: Path, ids: Iterable[str]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(set(ids))
    state_file.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")


def build_message(new_items: list[NewsItem]) -> str:
    lines = ["【CTBA 新的裁判講習公告】"]
    for idx, item in enumerate(new_items, start=1):
        lines.append(f"{idx}. {item.title}")
        lines.append(item.url)
    return "\n".join(lines)


def push_line_message(channel_access_token: str, to: str, message: str, timeout: int = 20) -> None:
    payload = {"to": to, "messages": [{"type": "text", "text": message[:5000]}]}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        LINE_PUSH_API,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {channel_access_token}",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"LINE push failed with status {resp.status}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("CTBA_URL", DEFAULT_URL))
    parser.add_argument("--keyword", default=os.getenv("CTBA_KEYWORD", DEFAULT_KEYWORD))
    parser.add_argument("--state-file", default=os.getenv("STATE_FILE", DEFAULT_STATE_FILE))
    parser.add_argument("--line-token", default=os.getenv("LINE_CHANNEL_ACCESS_TOKEN", ""))
    parser.add_argument("--line-to", default=os.getenv("LINE_TO", ""))
    parser.add_argument("--dry-run", action="store_true", help="Do not send LINE message")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_file = Path(args.state_file)

    try:
        html = fetch_html(args.url)
        matched = parse_matching_news(html, base_url=args.url, keyword=args.keyword)
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"[ERROR] Failed to fetch or parse page: {exc}", file=sys.stderr)
        return 1

    if not matched:
        print(f"No announcements matched keyword: {args.keyword}")
        return 0

    seen_ids = load_seen_ids(state_file)
    new_items = [item for item in matched if item.item_id not in seen_ids]

    if not new_items:
        print("No new matched announcements.")
        return 0

    message = build_message(new_items)
    print(message)

    if args.dry_run:
        print("Dry run enabled; LINE notification skipped.")
    else:
        if not args.line_token or not args.line_to:
            print(
                "[ERROR] LINE_CHANNEL_ACCESS_TOKEN and LINE_TO are required unless --dry-run is used.",
                file=sys.stderr,
            )
            return 1
        try:
            push_line_message(args.line_token, args.line_to, message)
            print("LINE notification sent.")
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            print(f"[ERROR] Failed to send LINE notification: {exc}", file=sys.stderr)
            return 1

    updated_ids = seen_ids | {item.item_id for item in matched}
    save_seen_ids(state_file, updated_ids)
    print(f"State updated at {state_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
