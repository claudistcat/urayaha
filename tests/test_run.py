import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from urayaha.runtime import Runtime


def run_source(src):
    rt = Runtime(".", [], False, False)
    proto, structs, _pub = rt.compile_source(src, "t.ura")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rt.vm.run(proto, structs)
    return buf.getvalue()


class RunTests(unittest.TestCase):
    def test_hello_world(self):
        self.assertEqual(run_source('イヤッハー("Hello, World!")'), "Hello, World!\n")

    def test_fizzbuzz_one_through_fifteen(self):
        source = '''
ヤハ ヤハァ = ン・プ
ウ～ラ～ ヤハァ <= ン・ャャ ヤーッ
    ハァ? ヤハァ % ン・ャ == ン・ン && ヤハァ % ン・ププ == ン・ン ヤーッ
        イヤッハー("FizzBuzz")
    ウラ ハァ? ヤハァ % ン・ャ == ン・ン ヤーッ
        イヤッハー("Fizz")
    ウラ ハァ? ヤハァ % ン・ププ == ン・ン ヤーッ
        イヤッハー("Buzz")
    ウラ ヤーッ
        イヤッハー(ヤハァ)
    ハァッ
    ヤハァ += ン・プ
ハァッ
'''
        self.assertEqual(run_source(source), "\n".join([
            "ン・プ", "ン・ル", "Fizz", "ン・プン", "Buzz", "Fizz",
            "ン・プャ", "ン・ルン", "Fizz", "Buzz", "ン・ルャ", "Fizz",
            "ン・ャプ", "ン・ャル", "FizzBuzz", "",
        ]))

    def test_fibonacci(self):
        source = '''
フゥン フゥンァ(ヤハァ: プルッ) -> プルッ ヤーッ
    ハァ? ヤハァ <= ン・プ ヤーッ
        ハァーッ ヤハァ
    ハァッ
    ハァーッ フゥンァ(ヤハァ - ン・プ) + フゥンァ(ヤハァ - ン・ル)
ハァッ
ツツウラウラ [ン・ン, ン・プ, ン・ル, ン・ャ, ン・プン, ン・ププ, ン・プル] -> ヤハァ ヤーッ
    イヤッハー(フゥンァ(ヤハァ))
ハァッ
'''
        self.assertEqual(run_source(source), "ン・ン\nン・プ\nン・プ\nン・ル\nン・ャ\nン・ププ\nン・ルン\n")

    def test_recursive_factorial(self):
        source = '''
フゥン フゥンァ(ヤハァ: プルッ) -> プルッ ヤーッ
    ハァ? ヤハァ <= ン・プ ヤーッ
        ハァーッ ン・プ
    ハァッ
    ハァーッ ヤハァ * フゥンァ(ヤハァ - ン・プ)
ハァッ
イヤッハー(フゥンァ(ン・ン))
イヤッハー(フゥンァ(ン・ププ))
'''
        self.assertEqual(run_source(source), "ン・プ\nン・プャルン\n")

    def test_list_reduce(self):
        source = '''
ヤハ プルャッ = [ン・プ, ン・ル, ン・ャ, ン・プン, ン・ププ]
イヤッハー(プルャッ.ウラ(フゥン(ヤハァ, ヤハッ) => ヤハァ + ヤハッ, ン・ン))
'''
        self.assertEqual(run_source(source), "ン・ャャ\n")

    def test_map_operations(self):
        source = '''
ヤハ ウララァ = {"うさぎ": ン・プ}
イヤッハー(ウララァ.ン?())
イヤッハー(ウララァ.ハァ?("うさぎ"))
ウララァ.ヤハ("うさぎ", ン・ル)
ウララァ.ヤハ("ワァ", ン・ャ)
イヤッハー(ウララァ["うさぎ"])
イヤッハー(ウララァ["ワァ"])
イヤッハー(ウララァ.ン?())
ウララァ.イヤッ("うさぎ")
イヤッハー(ウララァ.ハァ?("うさぎ"))
イヤッハー(ウララァ.ン?())
'''
        self.assertEqual(run_source(source), "ン・プ\nヤー\nン・ル\nン・ャ\nン・ル\nイヤ\nン・プ\n")

    def test_result_ok(self):
        source = '''
ヤハ ヤハァ = ヤッター(ン・プルャ)
イヤッハー(ヤハァ.ヤッタ?())
イヤッハー(ヤハァ.なんとかなれーッ!())
'''
        self.assertEqual(run_source(source), "ヤー\nン・プルャ\n")

    def test_result_err(self):
        source = '''
ヤハ ヤハァ = ワァ…("ダメだった")
イヤッハー(ヤハァ.ヤッタ?())
イヤッハー(ヤハァ.フゥン())
'''
        self.assertEqual(run_source(source), "イヤ\nダメだった\n")

    def test_result_err_unwrap_is_caught(self):
        source = '''
なんとかなれーッ ヤーッ
    ワァ…("失敗").なんとかなれーッ!()
    イヤッハー("到達しない")
ダメだった… -> ヤハァ ヤーッ
    イヤッハー(ヤハァ)
ハァッ
'''
        self.assertEqual(run_source(source), "失敗\n")

    def test_try_catch_throw(self):
        source = '''
なんとかなれーッ ヤーッ
    ワァーッ!("わざと転んだ")
    イヤッハー("到達しない")
ダメだった… -> ヤハァ ヤーッ
    イヤッハー(ヤハァ)
ハァッ
イヤッハー("続く")
'''
        self.assertEqual(run_source(source), "わざと転んだ\n続く\n")

    def test_closures_count_independently(self):
        source = '''
フゥン フゥンーッ() ヤーッ
    ヤハ ヤハァ = ン・ン
    ハァーッ フゥン() ヤーッ
        ヤハァ += ン・プ
        ハァーッ ヤハァ
    ハァッ
ハァッ
ヤハ ヤハーァ = フゥンーッ()
ヤハ ヤハーッ = フゥンーッ()
イヤッハー(ヤハーァ())
イヤッハー(ヤハーァ())
イヤッハー(ヤハーッ())
イヤッハー(ヤハーァ())
'''
        self.assertEqual(run_source(source), "ン・プ\nン・ル\nン・プ\nン・ャ\n")

    def test_default_arguments(self):
        source = '''
フゥン フゥーン(ヤハァ: プルッ, ヤハッ: プルッ = ン・ル) -> プルッ ヤーッ
    ハァーッ ヤハァ * ヤハッ
ハァッ
イヤッハー(フゥーン(ン・ププ))
イヤッハー(フゥーン(ン・ププ, ン・ャ))
'''
        self.assertEqual(run_source(source), "ン・ルル\nン・ャャ\n")

    def test_variadic_arguments(self):
        source = '''
フゥン フゥン?(...ヤハァ) -> プルッ ヤーッ
    ヤハ ヤハッ = ン・ン
    ツツウラウラ ヤハァ -> ヤハァッ ヤーッ
        ヤハッ += ヤハァッ
    ハァッ
    ハァーッ ヤハッ
ハァッ
イヤッハー(フゥン?())
イヤッハー(フゥン?(ン・プ))
イヤッハー(フゥン?(ン・プ, ン・ル, ン・ャ, ン・プン))
'''
        self.assertEqual(run_source(source), "ン・ン\nン・プ\nン・ルル\n")

    def test_string_interpolation(self):
        source = '''
ヤハ ヤハァ = "うさぎ"
イヤッハー("${ヤハァ}！ ${ン・プ + ン・ル}？")
'''
        self.assertEqual(run_source(source), "うさぎ！ ン・ャ？\n")

    def test_integer_division_and_modulo_signed_operands(self):
        cases = [
            ("ン・プャ", "ン・ャ", "ン・ル", "ン・プ"),
            ("-ン・プャ", "ン・ャ", "ン・-ル", "ン・-プ"),
            ("ン・プャ", "-ン・ャ", "ン・-ル", "ン・プ"),
            ("-ン・プャ", "-ン・ャ", "ン・ル", "ン・-プ"),
            ("-ン・ル", "ン・ャ", "ン・ン", "ン・-ル"),
        ]
        for dividend, divisor, quotient, remainder in cases:
            with self.subTest(dividend=dividend, divisor=divisor):
                source = f"イヤッハー({dividend} / {divisor})\nイヤッハー({dividend} % {divisor})"
                self.assertEqual(run_source(source), f"{quotient}\n{remainder}\n")

    def test_file_io_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "うさぎ.txt"
            literal = json.dumps(path.as_posix(), ensure_ascii=False)
            source = f'''
これって… プスン
プスン.ヤハ({literal}, "ワァ！\\nうさぎ").なんとかなれーッ!()
イヤッハー(プスン.ハァ?({literal}))
イヤッハー(プスン.フゥン({literal}).なんとかなれーッ!())
'''
            self.assertEqual(run_source(source), "ヤー\nワァ！\nうさぎ\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "ワァ！\nうさぎ")
            self.assertEqual(run_source(f'''
これって… プスン
プスン.イヤッ({literal}).なんとかなれーッ!()
イヤッハー(プスン.ハァ?({literal}))
'''), "イヤ\n")
            self.assertFalse(path.exists())

    def test_string_slice(self):
        source = '''
ヤハ ヤハァ = "うさぎとハチワレ"
イヤッハー(ヤハァ.フゥン(ン・ン, ン・ャ))
イヤッハー(ヤハァ.フゥン(ン・ャ))
'''
        self.assertEqual(run_source(source), "うさぎ\nとハチワレ\n")

    def test_string_replace_replaces_all_occurrences(self):
        source = '''
イヤッハー("うさぎとハチワレとうさぎ".ヤハ("うさぎ", "ワァ"))
'''
        self.assertEqual(run_source(source), "ワァとハチワレとワァ\n")

    def test_string_strip(self):
        source = '''
イヤッハー("  うさぎ  ".イヤッ())
'''
        self.assertEqual(run_source(source), "うさぎ\n")

    def test_string_find_returns_position_or_null(self):
        source = '''
ヤハ ヤハァ = "うさぎとハチワレ"
イヤッハー(ヤハァ.フゥー…ン?("ハチワレ"))
イヤッハー(ヤハァ.フゥー…ン?("パジャマ"))
'''
        self.assertEqual(run_source(source), "ン・プン\n……\n")

    def test_compound_assign_evaluates_index_target_once(self):
        source = '''
ヤハ ヤハッ = ン・ン
フゥン つぎ() ヤーッ
    ヤハッ += ン・プ
    ハァーッ ヤハッ - ン・プ
ハァッ
ヤハ ヤハァ = [ン・ン, ン・プ, ン・ル, ン・ャ]
ヤハァ[つぎ()] += ン・プン
イヤッハー(ヤハァ)
イヤッハー(ヤハッ)
'''
        self.assertEqual(run_source(source),
                         "[ン・プン, ン・プ, ン・ル, ン・ャ]\nン・プ\n")

    def test_compound_assign_evaluates_member_receiver_once(self):
        source = '''
こういうこと？ ワッチ ヤーッ
    ヤハァ: プルッ
ハァッ
ヤハ ヤハッ = ン・ン
ヤハ プルャッ = [ワッチ(ヤハァ = ン・ン), ワッチ(ヤハァ = ン・プ)]
フゥン つぎ() ヤーッ
    ヤハッ += ン・プ
    ハァーッ プルャッ[ヤハッ - ン・プ]
ハァッ
つぎ().ヤハァ += ン・プン
イヤッハー(プルャッ[ン・ン].ヤハァ)
イヤッハー(プルャッ[ン・プ].ヤハァ)
イヤッハー(ヤハッ)
'''
        self.assertEqual(run_source(source), "ン・プン\nン・プ\nン・プ\n")

    def test_foreach_closures_capture_independent_bindings(self):
        source = '''
ヤハ プルャッ = []
ツツウラウラ [ン・ン, ン・プ, ン・ル] -> ヤハァ ヤーッ
    プルャッ.ヤハ(フゥン() => ヤハァ)
ハァッ
ツツウラウラ プルャッ -> ヤハッ ヤーッ
    イヤッハー(ヤハッ())
ハァッ
'''
        self.assertEqual(run_source(source), "ン・ン\nン・プ\nン・ル\n")

    def test_while_loop_closures_capture_independent_bindings(self):
        source = '''
ヤハ プルャッ = []
ヤハ ヤハァ = ン・ン
ウ～ラ～ ヤハァ < ン・ャ ヤーッ
    ヤハ ヤハッ = ヤハァ
    プルャッ.ヤハ(フゥン() => ヤハッ)
    ヤハァ += ン・プ
ハァッ
ツツウラウラ プルャッ -> ヤハーッ ヤーッ
    イヤッハー(ヤハーッ())
ハァッ
'''
        self.assertEqual(run_source(source), "ン・ン\nン・プ\nン・ル\n")

    def test_json_round_trip(self):
        source = r'''
これって… プルャ
ヤハ ヤハァ = プルャ.フゥン("{\"うさぎ\": [1, 2], \"ワァ\": true}").なんとかなれーッ!()
イヤッハー(ヤハァ["うさぎ"][ン・プ])
イヤッハー(ヤハァ["ワァ"])
イヤッハー(プルャ.イヤッハー(ヤハァ).なんとかなれーッ!())
'''
        output = run_source(source).splitlines()
        self.assertEqual(output[:2], ["ン・ル", "ヤー"])
        self.assertEqual(len(output), 3)
        self.assertEqual(json.loads(output[2]), {"うさぎ": [1, 2], "ワァ": True})


if __name__ == "__main__":
    unittest.main()
class ReplExpressionTests(unittest.TestCase):
    """repl と term が式をどう包むか。窓は出さない。"""

    def setUp(self):
        from urayaha.runtime import Runtime
        self.rt = Runtime(".", [], True, False)

    def _wrap(self, source):
        from urayaha import cli
        return cli._as_expression(self.rt, source)

    def test_bare_expression_is_printed(self):
        self.assertEqual(self._wrap("ン・プルャ"), ("イヤッハー(ン・プルャ)", True))

    def test_print_call_is_not_wrapped_again(self):
        for source in ('イヤッハー("ワァ")', 'イヤッハー…("ワァ")',
                       'ウギッッ("なき")'):
            self.assertEqual(self._wrap(source), (source, False))

    def test_statement_is_left_alone(self):
        source = "ヤハ ヤハァ = ン・プ"
        self.assertEqual(self._wrap(source), (source, False))

    def test_call_that_is_not_a_printer_is_wrapped(self):
        source = "フゥンッ(ン・プ)"
        self.assertEqual(self._wrap(source), ("イヤッハー(フゥンッ(ン・プ))", True))


class TerminalCommandTests(unittest.TestCase):
    """term が CLI に居ること。窓は開かない。"""

    def test_term_is_a_command(self):
        from urayaha import cli
        self.assertIn("term", cli.COMMANDS)
        self.assertTrue(callable(cli.cmd_term))

    def test_term_says_so_when_there_is_no_tk(self):
        import builtins
        from urayaha import cli
        real_import = builtins.__import__

        def no_tk(name, *args, **kwargs):
            if name == "tkinter":
                raise ImportError("tkinter なんて知らない")
            return real_import(name, *args, **kwargs)

        err = io.StringIO()
        builtins.__import__ = no_tk
        try:
            with contextlib.redirect_stderr(err):
                code = cli.cmd_term({"human": False, "strict": False,
                                     "quiet": False, "debug": False})
        finally:
            builtins.__import__ = real_import
        self.assertEqual(code, cli.EXIT_FAIL)
        self.assertIn("窓を出せない", err.getvalue())
