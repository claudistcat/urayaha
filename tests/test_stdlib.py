import contextlib
import io
import tempfile
import time
import unittest
from pathlib import Path

from urayaha import stdlib
from urayaha.runtime import Runtime


def run_source(src, human_number=False):
    rt = Runtime(".", [], human_number, False)
    proto, structs, _pub = rt.compile_source(src, "t.ura")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rt.vm.run(proto, structs)
    return buf.getvalue()


class TimeFormatTests(unittest.TestCase):
    def test_now_without_arguments_is_unchanged(self):
        source = '''
これって… フゥ～ンフゥン
イヤッハー(フゥ～ンフゥン.フゥン() > ン・ン)
'''
        self.assertEqual(run_source(source), "ヤー\n")

    def test_format_default_pattern(self):
        source = '''
これって… フゥ～ンフゥン
イヤッハー(フゥ～ンフゥン.イヤッハー(ン・ン))
'''
        self.assertEqual(run_source(source),
                         time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(0)) + "\n")

    def test_format_custom_pattern(self):
        source = '''
これって… フゥ～ンフゥン
イヤッハー(フゥ～ンフゥン.イヤッハー(ン・ン, "%Y/%m/%d"))
'''
        self.assertEqual(run_source(source),
                         time.strftime("%Y/%m/%d", time.localtime(0)) + "\n")

    def test_parse_then_format_round_trip(self):
        source = '''
これって… フゥ～ンフゥン
ヤハ ヤハァ = フゥ～ンフゥン.フゥン()
ヤハ ヤハーッ = フゥ～ンフゥン.イヤッハー(ヤハァ)
ヤハ ヤハーァ = フゥ～ンフゥン.フゥン(ヤハーッ).なんとかなれーッ！()
イヤッハー(ヤハァ == ヤハーァ)
'''
        self.assertEqual(run_source(source), "ヤー\n")

    def test_format_then_parse_round_trip_with_custom_pattern(self):
        seconds = int(time.mktime(time.strptime("2024-01-02", "%Y-%m-%d")))
        source = f'''
これって… フゥ～ンフゥン
ヤハ ヤハァ = フゥ～ンフゥン.イヤッハー({seconds}, "%Y-%m-%d")
イヤッハー(フゥ～ンフゥン.フゥン(ヤハァ, "%Y-%m-%d").なんとかなれーッ！())
'''
        self.assertEqual(run_source(source, human_number=True), "%d\n" % seconds)

    def test_parse_failure_is_result_fail(self):
        source = '''
これって… フゥ～ンフゥン
ヤハ ヤハァ = フゥ～ンフゥン.フゥン("そんな日付ない")
イヤッハー(ヤハァ.ヤッタ？())
'''
        self.assertEqual(run_source(source), "イヤ\n")


class OsOpenTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self._orig = stdlib._os_launch_target
        stdlib._os_launch_target = self.calls.append
        self.addCleanup(self._restore)

    def _restore(self):
        stdlib._os_launch_target = self._orig

    def test_missing_local_path_fails_without_launching(self):
        source = '''
これって… ウロル
ヤハ ヤハァ = ウロル.イヤッハー("そんざいしないファイル-xyz.txt")
イヤッハー(ヤハァ.ヤッタ？())
'''
        self.assertEqual(run_source(source), "イヤ\n")
        self.assertEqual(self.calls, [])

    def test_existing_local_path_is_passed_to_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "うさぎ.txt"
            path.write_text("ワァ", encoding="utf-8")
            literal = '"%s"' % path.as_posix()
            source = f'''
これって… ウロル
イヤッハー(ウロル.イヤッハー({literal}).ヤッタ？())
'''
            self.assertEqual(run_source(source), "ヤー\n")
            self.assertEqual(self.calls, [str(path.as_posix())])

    def test_url_skips_existence_check_and_is_passed_to_launcher(self):
        source = '''
これって… ウロル
イヤッハー(ウロル.イヤッハー("https://example.com/").ヤッタ？())
'''
        self.assertEqual(run_source(source), "ヤー\n")
        self.assertEqual(self.calls, ["https://example.com/"])


if __name__ == "__main__":
    unittest.main()
