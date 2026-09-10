import unittest

from urayaha.fmt import format_source


class FormatterTests(unittest.TestCase):
    def test_reindent_chained_if_else(self):
        source = (
            "   ハァ？ ヤー ヤーッ\n"
            'イヤッハー("ヤハ")   \n'
            "      ウラ ヤーッ\n"
            '  イヤッハー("フゥン")\n'
            "   ハァッ\n"
        )
        expected = (
            "ハァ？ ヤー ヤーッ\n"
            '    イヤッハー("ヤハ")\n'
            "ウラ ヤーッ\n"
            '    イヤッハー("フゥン")\n'
            "ハァッ\n"
        )
        self.assertEqual(format_source(source, "fmt.ura"), expected)

    def test_preserve_rabbit_characters(self):
        source = (
            "   ウ～ラ～ イヤ ヤーッ\n"
            'イヤッハー("～ ー … ッ ァ ィ ゥ ャ")\n'
            "  ハァッ\n"
        )
        expected = (
            "ウ～ラ～ イヤ ヤーッ\n"
            '    イヤッハー("～ ー … ッ ァ ィ ゥ ャ")\n'
            "ハァッ\n"
        )
        formatted = format_source(source, "fmt.ura")
        self.assertEqual(formatted, expected)
        for character in "～ー…ッァィゥャ":
            with self.subTest(character=character):
                self.assertEqual(formatted.count(character), source.count(character))

    def test_already_formatted_source_is_unchanged(self):
        source = (
            "ウ～ラ～ イヤ ヤーッ\n"
            "    ハァ？ ヤー ヤーッ\n"
            '        イヤッハー("ヤハ")\n'
            "    ウラ ヤーッ\n"
            '        イヤッハー("フゥン")\n'
            "    ハァッ\n"
            "ハァッ\n"
        )
        formatted = format_source(source, "fmt.ura")
        self.assertEqual(formatted, source)
        self.assertEqual(format_source(formatted, "fmt.ura"), formatted)


if __name__ == "__main__":
    unittest.main()
