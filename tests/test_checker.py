import unittest

from urayaha.errors import UrayahaError
from urayaha.runtime import Runtime


def diagnostic_code(source):
    runtime = Runtime(".", [], False, False)
    try:
        runtime.compile_source(source, "checker.ura")
    except UrayahaError as error:
        return error.diagnostic.code
    raise AssertionError("Expected compilation to raise UrayahaError")


class CheckerTests(unittest.TestCase):
    def test_int_plus_string(self):
        self.assertEqual(diagnostic_code('ン・プ + "ワァ"\n'), "E2001")

    def test_bool_plus_int(self):
        self.assertEqual(diagnostic_code("ヤー + ン・プ\n"), "E2001")

    def test_undefined_variable(self):
        self.assertEqual(diagnostic_code("イヤッハー(ヤハァ)\n"), "E1001")

    def test_wrong_argument_count(self):
        declaration = (
            "フゥン フゥンッ(ヤハァ: プルッ) -> プルッ ヤーッ\n"
            "    ハァーッ ヤハァ\n"
            "ハァッ\n"
        )
        for call in ("フゥンッ()\n", "フゥンッ(ン・プ, ン・ル)\n"):
            with self.subTest(call=call):
                self.assertEqual(diagnostic_code(declaration + call), "E2003")

    def test_wrong_return_type(self):
        source = (
            "フゥン フゥンッ() -> プルッ ヤーッ\n"
            '    ハァーッ "ワァ"\n'
            "ハァッ\n"
        )
        self.assertEqual(diagnostic_code(source), "E2004")

    def test_invalid_member(self):
        self.assertEqual(diagnostic_code('"ワァ".ヤハァ()\n'), "E2005")

    def test_assignment_to_constant(self):
        source = "ヤハ! ヤハァ = ン・プ\nヤハァ = ン・ル\n"
        self.assertEqual(diagnostic_code(source), "E1003")


if __name__ == "__main__":
    unittest.main()
