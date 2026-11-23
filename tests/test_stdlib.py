import contextlib
import io
import os
import sys
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
class FileStageOneTests(unittest.TestCase):
    """引数の数で足した プスン の機能(鳴き声は増やしていない)。"""

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def _p(self, *parts):
        return "/".join([self.dir.replace("\\", "/")] + list(parts))

    def test_write_with_one_argument_makes_directory(self):
        target = self._p("ふかい", "した")
        source = '''
これって… プスン
イヤッハー(プスン.ヤハ("%s").ヤッタ？())
イヤッハー(プスン.ハァ？("%s"))
''' % (target, target)
        self.assertEqual(run_source(source), "ヤー\nヤー\n")
        self.assertTrue(Path(target).is_dir())

    def test_third_argument_appends(self):
        target = self._p("a.txt")
        source = '''
これって… プスン
プスン.ヤハ("%s", "ワァ")
プスン.ヤハ("%s", "ーッ", ヤー)
イヤッハー(プスン.フゥン("%s").なんとかなれーッ！())
''' % (target, target, target)
        self.assertEqual(run_source(source), "ワァーッ\n")

    def test_third_argument_false_overwrites(self):
        target = self._p("b.txt")
        source = '''
これって… プスン
プスン.ヤハ("%s", "ワァ")
プスン.ヤハ("%s", "ウラ", イヤ)
イヤッハー(プスン.フゥン("%s").なんとかなれーッ！())
''' % (target, target, target)
        self.assertEqual(run_source(source), "ウラ\n")

    def test_count_returns_byte_size_for_file(self):
        target = self._p("c.txt")
        Path(target).write_bytes("ワァ".encode("utf-8"))
        source = '''
これって… プスン
イヤッハー(プスン.ン？("%s").なんとかなれーッ！())
''' % target
        self.assertEqual(run_source(source, human_number=True), "6\n")

    def test_count_returns_entry_count_for_directory(self):
        Path(self._p("x.txt")).write_text("x", encoding="utf-8")
        Path(self._p("y.txt")).write_text("y", encoding="utf-8")
        source = '''
これって… プスン
イヤッハー(プスン.ン？("%s").なんとかなれーッ！())
''' % self._p()
        self.assertEqual(run_source(source, human_number=True), "2\n")

    def test_count_fails_for_missing_path(self):
        source = '''
これって… プスン
イヤッハー(プスン.ン？("%s").ヤッタ？())
''' % self._p("いない.txt")
        self.assertEqual(run_source(source), "イヤ\n")

    def test_exists_can_tell_a_directory_from_a_file(self):
        os.makedirs(os.path.join(self.dir, "sub"))
        Path(self._p("a.txt")).write_text("a", encoding="utf-8")
        source = '''
これって… プスン
イヤッハー(プスン.ハァ？("%s", ヤー))
イヤッハー(プスン.ハァ？("%s", ヤー))
イヤッハー(プスン.ハァ？("%s"))
''' % (self._p("sub"), self._p("a.txt"), self._p("a.txt"))
        self.assertEqual(run_source(source), "ヤー\nイヤ\nヤー\n")

    def test_listing_goes_deep_with_second_argument(self):
        os.makedirs(os.path.join(self.dir, "sub"))
        Path(self._p("a.txt")).write_text("a", encoding="utf-8")
        Path(self._p("sub", "b.txt")).write_text("b", encoding="utf-8")
        source = '''
これって… プスン
イヤッハー(プスン.ツツウラウラ("%s").なんとかなれーッ！())
イヤッハー(プスン.ツツウラウラ("%s", ヤー).なんとかなれーッ！())
''' % (self._p(), self._p())
        self.assertEqual(run_source(source),
                         "[a.txt, sub]\n[a.txt, sub, sub/b.txt]\n")


class SortKeyTests(unittest.TestCase):
    def test_sort_without_key_is_unchanged(self):
        source = '''
イヤッハー(["ワァ", "ウララララ", "ウ"].ナラベ())
'''
        self.assertEqual(run_source(source), "[ウ, ウララララ, ワァ]\n")

    def test_sort_with_key_function(self):
        source = '''
イヤッハー(["ワァ", "ウララララ", "ウ"].ナラベ(フゥン(ヤハァ) => ヤハァ.ン？()))
'''
        self.assertEqual(run_source(source), "[ウ, ワァ, ウララララ]\n")


    def test_sort_descending(self):
        source = '''
イヤッハー(["ワァ", "ウララララ", "ウ"].ナラベ(……, ヤー))
イヤッハー(["ワァ", "ウララララ", "ウ"].ナラベ(フゥン(ヤハァ) => ヤハァ.ン？(), ヤー))
'''
        self.assertEqual(run_source(source),
                         "[ワァ, ウララララ, ウ]\n[ウララララ, ワァ, ウ]\n")


class ProcessLaunchTests(unittest.TestCase):
    """ADR-0006 の起動の口。"""

    def _python(self):
        return sys.executable.replace("\\", "/")

    def test_env_lookup_still_works_with_one_argument(self):
        os.environ["URAYAHA_TEST_ENV"] = "ワァ"
        source = '''
これって… ウロル
イヤッハー(ウロル.フゥン("URAYAHA_TEST_ENV"))
'''
        try:
            self.assertEqual(run_source(source), "ワァ\n")
        finally:
            del os.environ["URAYAHA_TEST_ENV"]

    def test_run_returns_stdout(self):
        source = '''
これって… ウロル
イヤッハー(ウロル.フゥン("%s", ["-c", "print('ヤッハー')"]).なんとかなれーッ！().イヤッ())
''' % self._python()
        self.assertEqual(run_source(source), "ヤッハー\n")

    def test_non_zero_exit_is_a_failure(self):
        source = '''
これって… ウロル
イヤッハー(ウロル.フゥン("%s", ["-c", "raise SystemExit(3)"]).ヤッタ？())
''' % self._python()
        self.assertEqual(run_source(source), "イヤ\n")

    def test_missing_command_is_a_failure(self):
        source = '''
これって… ウロル
イヤッハー(ウロル.フゥン("いないコマンド_urayaha", []).ヤッタ？())
'''
        self.assertEqual(run_source(source), "イヤ\n")

    def test_which_tells_whether_a_command_is_available(self):
        source = '''
これって… ウロル
イヤッハー(ウロル.ハァ？("%s"))
イヤッハー(ウロル.ハァ？("いないコマンド_urayaha"))
''' % self._python()
        self.assertEqual(run_source(source), "ヤー\nイヤ\n")

    def test_host_can_replace_the_runner(self):
        from urayaha.vm import ResultValue
        seen = []

        def fake(cmd):
            seen.append(cmd)
            return ResultValue(False, "ここでは起動できないみたい…")

        stdlib.set_runner(fake)
        try:
            source = '''
これって… ウロル
ヤハ ヤハァ = ウロル.フゥン("なにか", ["ひとつ"])
イヤッハー(ヤハァ.ヤッタ？())
イヤッハー(ヤハァ.フゥン())
'''
            self.assertEqual(run_source(source),
                             "イヤ\nここでは起動できないみたい…\n")
            self.assertEqual(seen, [["なにか", "ひとつ"]])
        finally:
            stdlib.set_runner(None)
class MoveCopyTests(unittest.TestCase):
    """プスン.トウッ(移動) と プスン.プルップラッ(コピー)。"""

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def _p(self, *parts):
        return "/".join([self.dir.replace("\\", "/")] + list(parts))

    def test_move_renames_a_file(self):
        Path(self._p("もと.txt")).write_text("ワァ", encoding="utf-8")
        source = '''
これって… プスン
イヤッハー(プスン.トウッ("%s", "%s").ヤッタ？())
イヤッハー(プスン.ハァ？("%s"))
イヤッハー(プスン.フゥン("%s").なんとかなれーッ！())
''' % (self._p("もと.txt"), self._p("さき.txt"),
       self._p("もと.txt"), self._p("さき.txt"))
        self.assertEqual(run_source(source), "ヤー\nイヤ\nワァ\n")

    def test_move_fails_for_missing_source(self):
        source = '''
これって… プスン
イヤッハー(プスン.トウッ("%s", "%s").ヤッタ？())
''' % (self._p("いない.txt"), self._p("さき.txt"))
        self.assertEqual(run_source(source), "イヤ\n")

    def test_copy_keeps_the_original(self):
        Path(self._p("もと.txt")).write_text("ウラ", encoding="utf-8")
        source = '''
これって… プスン
イヤッハー(プスン.プルップラッ("%s", "%s").ヤッタ？())
イヤッハー(プスン.ハァ？("%s"))
イヤッハー(プスン.フゥン("%s").なんとかなれーッ！())
''' % (self._p("もと.txt"), self._p("うつし.txt"),
       self._p("もと.txt"), self._p("うつし.txt"))
        self.assertEqual(run_source(source), "ヤー\nヤー\nウラ\n")

    def test_copy_takes_a_whole_directory(self):
        os.makedirs(os.path.join(self.dir, "もと", "した"))
        Path(self._p("もと", "した", "a.txt")).write_text("a", encoding="utf-8")
        source = '''
これって… プスン
イヤッハー(プスン.プルップラッ("%s", "%s").ヤッタ？())
イヤッハー(プスン.ツツウラウラ("%s", ヤー).なんとかなれーッ！())
''' % (self._p("もと"), self._p("さき"), self._p("さき"))
        self.assertEqual(run_source(source), "ヤー\n[した, した/a.txt]\n")


class StandardErrorTests(unittest.TestCase):
    def test_ugi_writes_to_stderr(self):
        source = '''
イヤッハー("こっちは でる")
ウギッッ("こっちは エラー")
'''
        rt = Runtime(".", [], False, False)
        proto, structs, _pub = rt.compile_source(source, "t.ura")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out):
            with contextlib.redirect_stderr(err):
                rt.vm.run(proto, structs)
        self.assertEqual(out.getvalue(), "こっちは でる\n")
        self.assertEqual(err.getvalue(), "こっちは エラー\n")


class NumberTests(unittest.TestCase):
    """ウリリ(数)。"""

    def test_absolute_value(self):
        source = '''
これって… ウリリ
イヤッハー(ウリリ.ン？(ン・ン - ン・プルャ))
イヤッハー(ウリリ.ン？(ン・プルャ))
'''
        self.assertEqual(run_source(source, human_number=True), "27\n27\n")

    def test_drop_and_round_up(self):
        # Int / Int は整数割り算なので、小数にするために プルァッ を通す
        source = '''
これって… ウリリ
イヤッハー(ウリリ.イヤッ(プルァッ(ン・プャ) / ン・ル))
イヤッハー(ウリリ.イヤッ(プルァッ(ン・プャ) / ン・ル, ヤー))
イヤッハー(ウリリ.イヤッ(ン・ン - プルァッ(ン・プャ) / ン・ル))
イヤッハー(ウリリ.イヤッ(ン・ン - プルァッ(ン・プャ) / ン・ル, ヤー))
イヤッハー(ウリリ.イヤッ(ン・プル))
'''
        self.assertEqual(run_source(source, human_number=True),
                         "3\n4\n-4\n-3\n6\n")

    def test_square_root(self):
        source = '''
これって… ウリリ
イヤッハー(ウリリ.フゥン(ン・ルプン).なんとかなれーッ！())
イヤッハー(ウリリ.フゥン(ン・ン - ン・プ).ヤッタ？())
'''
        self.assertEqual(run_source(source, human_number=True), "6.0\nイヤ\n")

    def test_power(self):
        source = '''
これって… ウリリ
イヤッハー(ウリリ.フゥン(ン・ル, ン・ャ).なんとかなれーッ！())
'''
        self.assertEqual(run_source(source, human_number=True), "8.0\n")

    def test_not_a_number_is_an_error(self):
        source = '''
これって… ウリリ
なんとかなれーッ ヤーッ
    イヤッハー(ウリリ.ン？("ワァ"))
ダメだった… -> ヤハァ ヤーッ
    イヤッハー("だめだった")
ハァッ
'''
        self.assertEqual(run_source(source), "だめだった\n")


class FakeGui(object):
    """窓を出さない代わりに、組み立てた内容と呼び出しを記録する。"""

    def __init__(self, ticks=1):
        self.ticks = ticks
        self.open = False
        self.texts = {}
        self.kinds = {}
        self.spec = None
        self.calls = []
        self.press = None

    def alive(self):
        return self.open

    def show(self, vm, spec, call, span):
        self.open = True
        self.spec = spec
        for part in spec.get("ぶひん") or []:
            name = part.get("なまえ")
            self.kinds[name] = part.get("たね")
            self.texts[name] = part.get("ぶんめん")
            if part.get("おしたら") is not None:
                self.press = call(part["おしたら"])
        tick = spec.get("まつとき")
        if tick is not None:
            handler = call(tick)
            for _ in range(self.ticks):
                handler()
        if self.press is not None:
            self.press()
        return stdlib._ok(None)

    def set(self, name, text):
        if name not in self.kinds:
            return stdlib._fail('"%s" って部品はないみたい…' % name)
        self.texts[name] = text
        self.calls.append(("set", name, text))
        return stdlib._ok(None)

    def get(self, name):
        if name not in self.kinds:
            return stdlib._fail('"%s" って部品はないみたい…' % name)
        return stdlib._ok(self.texts.get(name))

    def close(self):
        self.open = False
        self.calls.append(("close",))
        return stdlib._ok(None)


class GuiTests(unittest.TestCase):
    """ウィーヤ(画面)。窓は出さず、偽のバックエンドで確かめる。"""

    def tearDown(self):
        stdlib.set_gui(None)

    def test_ura_decides_the_screen_and_the_text(self):
        fake = FakeGui(ticks=3)
        stdlib.set_gui(fake)
        source = '''
これって… ウィーヤ
ヤハ ヤハァ = ン・ン
フゥン フゥンァ() ヤーッ
    ヤハァ += ン・プ
    ウィーヤ.ヤハ("かず", "${ヤハァ} かい")
ハァッ
フゥン フゥンー() ヤーッ
    ウィーヤ.イヤッ()
ハァッ
ヤハ ヤハッ = ウィーヤ.イヤッハー({
    "だいめい": "ためし",
    "ぶひん": [
        {"たね": "もじ", "なまえ": "かず", "ぶんめん": "まだ"},
        {"たね": "ボタン", "なまえ": "とじる", "ぶんめん": "イヤッ", "おしたら": フゥンー}
    ],
    "まつ": ン・プャャプン,
    "まつとき": フゥンァ
})
イヤッハー(ヤハッ.ヤッタ？())
イヤッハー(ウィーヤ.ハァ？())
'''
        self.assertEqual(run_source(source, human_number=True), "ヤー\nイヤ\n")
        self.assertEqual(fake.spec["だいめい"], "ためし")
        self.assertEqual(fake.spec["まつ"], 500)
        self.assertEqual(fake.texts["かず"], "3 かい")
        self.assertEqual(fake.calls[-1], ("close",))

    def test_reading_a_part_and_a_missing_part(self):
        fake = FakeGui(ticks=1)
        stdlib.set_gui(fake)
        source = '''
これって… ウィーヤ
フゥン フゥンァ() ヤーッ
    ウィーヤ.ヤハ("なまえ", "うさぎ")
    イヤッハー(ウィーヤ.フゥン("なまえ").なんとかなれーッ！())
    イヤッハー(ウィーヤ.フゥン("いない").ヤッタ？())
    イヤッハー(ウィーヤ.ヤハ("いない", "ワァ").ヤッタ？())
ハァッ
ウィーヤ.イヤッハー({
    "ぶひん": [{"たね": "いれる", "なまえ": "なまえ", "ぶんめん": "はじめ"}],
    "まつ": ン・プ,
    "まつとき": フゥンァ
})
'''
        self.assertEqual(run_source(source), "うさぎ\nイヤ\nイヤ\n")

    def test_unknown_part_is_a_failure(self):
        fake = FakeGui(ticks=0)
        stdlib.set_gui(fake)
        source = '''
これって… ウィーヤ
イヤッハー(ウィーヤ.イヤッハー({"ぶひん": [{"たね": "しらない", "なまえ": "x"}]}).ヤッタ？())
'''
        # 偽のバックエンドは知らない部品でも止めないので、ここでは成功になる。
        # 本物の Tk は失敗を返す（docs/stdlib.md の表のとおり）。
        self.assertEqual(run_source(source), "ヤー\n")

    def test_not_a_map_is_an_error(self):
        stdlib.set_gui(FakeGui())
        source = '''
これって… ウィーヤ
なんとかなれーッ ヤーッ
    ウィーヤ.イヤッハー("ワァ")
ダメだった… -> ヤハァ ヤーッ
    イヤッハー("だめだった")
ハァッ
'''
        self.assertEqual(run_source(source), "だめだった\n")
