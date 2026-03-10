import unittest

from ctba_notifier import build_message, parse_matching_news


class CtbaNotifierTests(unittest.TestCase):
    def test_parse_matching_news_filters_keyword_and_dedup(self):
        html = """
        <html><body>
          <a href='news_detail.php?id=1'>2026 年裁判講習課程</a>
          <a href='news_detail.php?id=1'>2026 年裁判講習課程</a>
          <a href='news_detail.php?id=2'>其他公告</a>
        </body></html>
        """
        items = parse_matching_news(
            html=html,
            base_url="http://www.ctba.org.tw/news.php?cate=works&type=16",
            keyword="裁判講習",
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "2026 年裁判講習課程")
        self.assertEqual(items[0].url, "http://www.ctba.org.tw/news_detail.php?id=1")

    def test_build_message_formats_links(self):
        html = "<a href='x.php'>A 裁判講習</a><a href='y.php'>B 裁判講習</a>"
        items = parse_matching_news(html, "https://example.com/list", "裁判講習")
        message = build_message(items)
        self.assertIn("【CTBA 新的裁判講習公告】", message)
        self.assertIn("1. A 裁判講習", message)
        self.assertIn("https://example.com/x.php", message)
        self.assertIn("2. B 裁判講習", message)


if __name__ == "__main__":
    unittest.main()
