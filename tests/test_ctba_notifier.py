import tempfile
import unittest
from datetime import date
from pathlib import Path

from ctba_notifier import (
    NewsItem,
    build_message,
    extract_news_date,
    filter_recent_news,
    parse_line_targets,
    parse_matching_news,
    read_secret_from_file,
)


class CtbaNotifierTests(unittest.TestCase):
    def test_parse_matching_news_filters_keyword_and_dedup(self):
        html = """
        <html><body>
          <a href='news_detail.php?id=1'>2026/01/05 裁判講習課程</a>
          <a href='news_detail.php?id=1'>2026/01/05 裁判講習課程</a>
          <a href='news_detail.php?id=2'>其他公告</a>
        </body></html>
        """
        items = parse_matching_news(
            html=html,
            base_url="http://www.ctba.org.tw/news.php?cate=works&type=16",
            keyword="裁判講習",
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "2026/01/05 裁判講習課程")
        self.assertEqual(items[0].url, "http://www.ctba.org.tw/news_detail.php?id=1")

    def test_build_message_formats_links(self):
        html = "<a href='x.php'>2026/01/05 A 裁判講習</a><a href='y.php'>2026/01/06 B 裁判講習</a>"
        items = parse_matching_news(html, "https://example.com/list", "裁判講習")
        message = build_message(items)
        self.assertIn("【CTBA 新的裁判講習公告】", message)
        self.assertIn("1. 2026/01/05 A 裁判講習", message)
        self.assertIn("https://example.com/x.php", message)
        self.assertIn("2. 2026/01/06 B 裁判講習", message)

    def test_extract_news_date_supports_multiple_formats(self):
        self.assertEqual(extract_news_date("2026-01-05 裁判講習"), date(2026, 1, 5))
        self.assertEqual(extract_news_date("民國 115 年 1 月 5 日 裁判講習"), date(2026, 1, 5))

    def test_filter_recent_news_only_today_or_yesterday(self):
        today = date(2026, 1, 6)
        items = [
            NewsItem("2026/01/06 裁判講習 A", "https://example.com/a"),
            NewsItem("2026/01/05 裁判講習 B", "https://example.com/b"),
            NewsItem("2026/01/04 裁判講習 C", "https://example.com/c"),
            NewsItem("無日期 裁判講習 D", "https://example.com/d"),
        ]
        filtered = filter_recent_news(items, today=today)
        self.assertEqual([item.url for item in filtered], ["https://example.com/a", "https://example.com/b"])

    def test_parse_line_targets_supports_comma_newline_and_dedup(self):
        targets = parse_line_targets("U111, C222\nU111\n C333 ", "")
        self.assertEqual(targets, ["U111", "C222", "C333"])

    def test_read_secret_and_targets_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "line_token.txt"
            to_file = Path(tmp) / "line_to.txt"
            token_file.write_text("abc123\n", encoding="utf-8")
            to_file.write_text("U111\nC222\n", encoding="utf-8")

            self.assertEqual(read_secret_from_file(str(token_file)), "abc123")
            self.assertEqual(parse_line_targets("", str(to_file)), ["U111", "C222"])


if __name__ == "__main__":
    unittest.main()
