#!/usr/bin/env python3
"""Monitor CTBA announcements and notify LINE when new umpire-training posts appear."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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


def extract_news_date(title: str, today: date | None = None) -> date | None:
    today = today or datetime.now().date()

    ymd = re.search(r"(?P<y>\d{4})[./-](?P<m>\d{1,2})[./-](?P<d>\d{1,2})", title)
    if ymd:
        try:
            return date(int(ymd.group("y")), int(ymd.group("m")), int(ymd.group("d")))
        except ValueError:
            return None

    roc = re.search(r"民國\s*(?P<y>\d{2,3})\s*年\s*(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*日", title)
    if roc:
        try:
            return date(int(roc.group("y")) + 1911, int(roc.group("m")), int(roc.group("d")))
        except ValueError:
            return None

    md = re.search(r"(?P<m>\d{1,2})[./-](?P<d>\d{1,2})", title)
    if md:
        m = int(md.group("m"))
        d = int(md.group("d"))
        for year in (today.year, today.year - 1, today.year + 1):
            try:
                candidate = date(year, m, d)
            except ValueError:
                continue
            if abs((candidate - today).days) <= 1:
                return candidate

    return None


def filter_recent_news(items: list[NewsItem], today: date | None = None) -> list[NewsItem]:
    today = today or datetime.now().date()
    accepted_dates = {today, today - timedelta(days=1)}

    filtered: list[NewsItem] = []
    for item in items:
        news_date = extract_news_date(item.title, today=today)
        if news_date in accepted_dates:
            filtered.append(item)
    return filtered


def read_secret_from_file(path: str) -> str:
    file_path = Path(path)
    return file_path.read_text(encoding="utf-8").strip()


def resolve_line_token(cli_token: str, token_file: str) -> str:
    if cli_token:
        return cli_token
    if token_file:
        return read_secret_from_file(token_file)
    return ""


def parse_line_targets(cli_to: str, to_file: str) -> list[str]:
    raw = cli_to
    if not raw and to_file:
        raw = read_secret_from_file(to_file)
    if not raw:
        return []
    targets = [target.strip() for target in re.split(r"[\n,]+", raw) if target.strip()]
    unique_targets = list(dict.fromkeys(targets))
    return unique_targets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("CTBA_URL", DEFAULT_URL))
    parser.add_argument("--keyword", default=os.getenv("CTBA_KEYWORD", DEFAULT_KEYWORD))
    parser.add_argument("--state-file", default=os.getenv("STATE_FILE", DEFAULT_STATE_FILE))
    parser.add_argument("--line-token", default=os.getenv("LINE_CHANNEL_ACCESS_TOKEN", ""))
    parser.add_argument("--line-token-file", default=os.getenv("LINE_CHANNEL_ACCESS_TOKEN_FILE", ""))
    parser.add_argument("--line-to", default=os.getenv("LINE_TO", ""))
    parser.add_argument("--line-to-file", default=os.getenv("LINE_TO_FILE", ""))
    parser.add_argument(
        "--disable-date-filter",
        action="store_true",
        help="Disable today/yesterday filter and notify all unseen matched posts.",
    )
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
    unseen_items = [item for item in matched if item.item_id not in seen_ids]

    if args.disable_date_filter:
        new_items = unseen_items
    else:
        new_items = filter_recent_news(unseen_items)

    if not new_items:
        if args.disable_date_filter:
            print("No new matched announcements.")
        else:
            print("No new matched announcements from today/yesterday.")
        return 0

    message = build_message(new_items)
    print(message)

    if args.dry_run:
        print("Dry run enabled; LINE notification skipped.")
    else:
        token = resolve_line_token(args.line_token, args.line_token_file)
        targets = parse_line_targets(args.line_to, args.line_to_file)
        if not token or not targets:
            print(
                "[ERROR] LINE token and target(s) are required unless --dry-run is used.",
                file=sys.stderr,
            )
            return 1

        try:
            for target in targets:
                push_line_message(token, target, message)
            print(f"LINE notification sent to {len(targets)} target(s).")
        except (HTTPError, URLError, TimeoutError, RuntimeError, OSError) as exc:
            print(f"[ERROR] Failed to send LINE notification: {exc}", file=sys.stderr)
            return 1

    updated_ids = seen_ids | {item.item_id for item in new_items}
    save_seen_ids(state_file, updated_ids)
    print(f"State updated at {state_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
