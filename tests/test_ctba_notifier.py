import re
import unittest
from pathlib import Path


class N8nCodeNodeScriptTests(unittest.TestCase):
    def setUp(self):
        self.script = Path('ctba_notifier.py').read_text(encoding='utf-8')

    def test_contains_n8n_static_data_usage(self):
        self.assertIn("$getWorkflowStaticData('global')", self.script)

    def test_contains_line_push_endpoint(self):
        self.assertIn('https://api.line.me/v2/bot/message/push', self.script)

    def test_supports_multi_target_parse(self):
        self.assertRegex(self.script, re.compile(r"split\(/\[\\n,\]\+/") )


if __name__ == '__main__':
    unittest.main()
