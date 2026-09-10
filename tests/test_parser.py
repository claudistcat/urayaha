import textwrap
import unittest

from urayaha.errors import DiagnosticBag, UrayahaError
from urayaha.lexer import lex
from urayaha.parser import parse


def parse_source(source):
    source = textwrap.dedent(source).strip() + "\n"
    bag = DiagnosticBag()
    return parse(lex(source, "parser.ura", bag), "parser.ura", bag)


class ParserTests(unittest.TestCase):
    def test_variable(self):
        parse_source("ヤハ ヤハァ: プルッ = ン・プ")

    def test_constant(self):
        parse_source("ヤハ! ヤハァ = ン・プ")

    def test_function(self):
        parse_source("""
            フゥン ヤハァ(プルャ: プルッ) -> プルッ ヤーッ
                ハァーッ プルャ
            ハァッ
        """)

    def test_method(self):
        parse_source("""
            フゥン ヤハァ.プルャ() -> プルッ ヤーッ
                ハァーッ コレ.プルル
            ハァッ
        """)

    def test_type_declaration(self):
        parse_source("""
            こういうこと? ヤハァ ヤーッ
                プルャ: プルッ
                プルル: ワァッ
            ハァッ
        """)

    def test_if(self):
        parse_source("""
            ハァ? ヤー ヤーッ
                イヤッハー("ヤハ")
            ハァッ
        """)

    def test_else(self):
        parse_source("""
            ハァ? イヤ ヤーッ
                イヤッハー("ヤハ")
            ウラ ヤーッ
                イヤッハー("フゥン")
            ハァッ
        """)

    def test_else_if(self):
        parse_source("""
            ハァ? イヤ ヤーッ
                イヤッハー("ヤハ")
            ウラ ハァ? ヤー ヤーッ
                イヤッハー("フゥン")
            ウラ ヤーッ
                イヤッハー("ウラ")
            ハァッ
        """)

    def test_while(self):
        parse_source("""
            ウ～ラ～ イヤ ヤーッ
                イヤッハー("ヤハ")
            ハァッ
        """)

    def test_foreach(self):
        parse_source("""
            ツツウラウラ [ン・プ, ン・ル] -> ヤハァ ヤーッ
                イヤッハー(ヤハァ)
            ハァッ
        """)

    def test_break(self):
        parse_source("""
            ウ～ラ～ ヤー ヤーッ
                ムリッ
            ハァッ
        """)

    def test_continue(self):
        parse_source("""
            ツツウラウラ [ン・プ] -> ヤハァ ヤーッ
                イヤッ
            ハァッ
        """)

    def test_return(self):
        parse_source("""
            フゥン ヤハァ() -> プルッ ヤーッ
                ハァーッ ン・プ
            ハァッ
        """)

    def test_array(self):
        parse_source("ヤハ ヤハァ = [ン・プ, ン・ル, ン・ャ]")

    def test_map(self):
        parse_source('ヤハ ヤハァ = {"ヤハ": ン・プ, "ウラ": ン・ル}')

    def test_tuple(self):
        parse_source('ヤハ ヤハァ = (ン・プ, "ヤハ", ヤー)')

    def test_destructuring(self):
        parse_source("ヤハ (ヤハァ, プルャ) = (ン・プ, ン・ル)")

    def test_lambda(self):
        parse_source("ヤハ ヤハァ = フゥン(プルャ: プルッ) => プルャ + ン・プ")

    def test_pipeline(self):
        parse_source("ン・プ |> ヤハァ |> イヤッハー")

    def test_null_coalescing(self):
        parse_source("ヤハ ヤハァ = …… ?? ン・プ")

    def test_optional_member(self):
        parse_source("ヤハ ヤハァ = プルャ?.プルル")

    def test_try_catch(self):
        parse_source("""
            なんとかなれーッ ヤーッ
                ワァーッ!("ヤハ")
            ダメだった… -> ヤハァ ヤーッ
                イヤッハー(ヤハァ)
            ハァッ
        """)

    def test_throw(self):
        parse_source('ワァーッ!("ヤハ")')

    def test_match(self):
        parse_source("""
            もしかして ン・プ ヤーッ
                ってこと? ン・プ => イヤッハー("ヤハ")
                じゃないってこと? => イヤッハー("ウラ")
            ハァッ
        """)

    def test_file_import(self):
        parse_source('これって… "lib.ura" -> ヤハァ')

    def test_standard_module_import(self):
        parse_source("これって… プスン")

    def test_chained_if_else_rejects_extra_end(self):
        with self.assertRaises(UrayahaError):
            parse_source("""
                ハァ? ヤー ヤーッ
                    イヤッハー("ヤハ")
                ウラ ヤーッ
                    イヤッハー("ウラ")
                ハァッ
                ハァッ
            """)

    def test_unterminated_block_raises_e0002(self):
        with self.assertRaises(UrayahaError) as caught:
            parse_source("""
                ハァ? ヤー ヤーッ
                    イヤッハー("ヤハ")
            """)
        self.assertEqual(caught.exception.diagnostic.code, "E0002")


if __name__ == "__main__":
    unittest.main()
