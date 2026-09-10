import unittest

from urayaha.errors import DiagnosticBag
from urayaha.lexer import lex


class LexerTests(unittest.TestCase):
    def tokens(self, source):
        tokens = lex(source, "lexer.ura", DiagnosticBag())
        self.assertEqual(tokens[-1].kind, "EOF")
        return tokens[:-1]

    def test_bare_digits_are_an_identifier(self):
        tokens = self.tokens("プルャ")
        self.assertEqual([(t.kind, t.text) for t in tokens], [("IDENT", "プルャ")])

    def test_prefixed_digits_are_an_integer(self):
        tokens = self.tokens("ン・プルャ")
        self.assertEqual([(t.kind, t.value) for t in tokens], [("INT", 27)])

    def test_let_and_const_are_distinct(self):
        self.assertEqual([t.kind for t in self.tokens("ヤハ ヤハ!")], ["LET", "CONST"])

    def test_else_while_and_for_are_distinct(self):
        self.assertEqual(
            [t.kind for t in self.tokens("ウラ ウ～ラ～ ツツウラウラ")],
            ["ELSE", "WHILE", "FOR"],
        )

    def test_full_width_question_mark_is_normalized(self):
        self.assertEqual(
            [(t.kind, t.text) for t in self.tokens("ハァ？ ハァ?")],
            [("IF", "ハァ?"), ("IF", "ハァ?")],
        )

    def test_full_width_exclamation_mark_is_normalized(self):
        self.assertEqual(
            [(t.kind, t.text) for t in self.tokens("ヤハ！ ヤハ!")],
            [("CONST", "ヤハ!"), ("CONST", "ヤハ!")],
        )

    def test_wave_dash_and_long_vowel_mark_are_distinct(self):
        self.assertEqual(
            [(t.kind, t.text) for t in self.tokens("フゥー フゥ～")],
            [("IDENT", "フゥー"), ("IDENT", "フゥ～")],
        )

    def test_keyword_members(self):
        for module, member, kind in (
            ("プスン", "ヤハ", "LET"),
            ("プスン", "ハァ?", "IF"),
            ("プスン", "イヤッ", "CONTINUE"),
            ("プルャ", "イヤッハー", "PRINT"),
        ):
            with self.subTest(member=member):
                self.assertEqual(
                    [(t.kind, t.text) for t in self.tokens(module + "." + member)],
                    [("IDENT", module), ("OP", "."), (kind, member)],
                )

    def test_string_punctuation_is_preserved(self):
        for value in ("ワァ！", "ハァ？", "ワァ！？"):
            with self.subTest(value=value):
                tokens = self.tokens('イヤッハー("' + value + '")')
                self.assertEqual([t.kind for t in tokens], ["PRINT", "OP", "STRING", "OP"])
                self.assertEqual(tokens[2].text, value)
                self.assertEqual(tokens[2].value, [("str", value)])

    def test_base_four_values(self):
        for literal, value in (("ン・ン", 0), ("ン・プン", 4), ("ン・ルル", 10), ("ン・ャャ", 15)):
            with self.subTest(literal=literal):
                self.assertEqual([(t.kind, t.value) for t in self.tokens(literal)], [("INT", value)])

    def test_base_four_float(self):
        tokens = self.tokens("ン・プ.ル")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].kind, "FLOAT")
        self.assertEqual(tokens[0].value, 1.5)

    def test_word_tokens_require_whitespace(self):
        self.assertEqual([t.kind for t in self.tokens("ウラ ウラ")], ["ELSE", "ELSE"])
        self.assertEqual([(t.kind, t.text) for t in self.tokens("ウラウラ")], [("IDENT", "ウラウラ")])

    def test_spans_use_one_based_character_positions(self):
        source = 'ヤハ 名前 = ン・プルャ\n  イヤッハー("ワァ！")\n'
        expected = [
            ("LET", 1, 1, 2, "ヤハ"),
            ("IDENT", 1, 4, 2, "名前"),
            ("OP", 1, 7, 1, "="),
            ("INT", 1, 9, 5, "ン・プルャ"),
            ("PRINT", 2, 3, 5, "イヤッハー"),
            ("OP", 2, 8, 1, "("),
            ("STRING", 2, 9, 5, '"ワァ！"'),
            ("OP", 2, 14, 1, ")"),
        ]
        tokens = self.tokens(source)
        self.assertEqual(len(tokens), len(expected))
        for token, (kind, line, col, length, raw) in zip(tokens, expected):
            with self.subTest(raw=raw):
                self.assertEqual(token.kind, kind)
                self.assertEqual((token.span.file, token.span.line, token.span.col, token.span.length),
                                 ("lexer.ura", line, col, length))
                self.assertEqual(source.splitlines()[line - 1][col - 1:col - 1 + length], raw)


if __name__ == "__main__":
    unittest.main()
