# -*- coding: utf-8 -*-
"""Urayaha 字句解析器。

v0.3 で確定した字句規則:

* 数値リテラルは `ン・` プレフィックス必須(v0.3 §1)。`ン・プルャ` = 4 進 123 = 27。
  プレフィックスの無い `プルャ` は常に識別子。
* `！`/`？` は語の走査中のみ `!`/`?` へ正規化する(v0.3 §4)。
  文字列リテラルの中身は正規化しない。NFKC を丸ごと掛けると `…` が `...` へ
  展開されて NULL(`……`)と可変長引数(`...`)が衝突するため、対象は 2 文字だけ。
* 語はバックトラック付き最長一致で切り出す(v0.3 §6)。
  最大長で読んだ語が既知語でなければ、`! ? …` を含まない最長接頭辞まで後退する。
  これにより `ヤハ?ッ`(Bool)は 1 語、`プルッ?`(Optional)は `プルッ` + `?` に割れる。
* 語と語の間には空白が要る。`ウラウラ` は while、`ウラ ウラ` は else が 2 つ。
"""

from .errors import Span, Diagnostic, UrayahaError

# ---------------------------------------------------------------- 文字クラス

DIGIT_VALUE = {"ン": 0, "プ": 1, "ル": 2, "ャ": 3}
NUM_PREFIX = "ン・"
ELLIPSIS = "…"
NORMALIZE = {"！": "!", "？": "?"}

_WORD_EXTRA_START = "_" + ELLIPSIS
WAVE = "～"
_WORD_EXTRA_CONT = "_" + ELLIPSIS + WAVE + "!?"


def _is_word_start(ch):
    return ch.isalpha() or ch in _WORD_EXTRA_START


def _is_word_cont(ch):
    # 全角の ！ ？ も語中文字。正規化は語を組み立てるときに掛ける(v0.3 §4)。
    ch = NORMALIZE.get(ch, ch)
    return ch.isalpha() or ch.isdigit() or ch in _WORD_EXTRA_CONT


# ---------------------------------------------------------------- 語彙表

KEYWORDS = {
    "ヤハ": "LET",
    "ヤハ!": "CONST",
    "フゥン": "FN",
    "ハァ?": "IF",
    "ウラ": "ELSE",
    "ウ～ラ～": "WHILE",
    "ツツウラウラ": "FOR",
    "ヤーッ": "BEGIN",
    "ハァッ": "END",
    "ハァーッ": "RETURN",
    "ムリッ": "BREAK",
    "イヤッ": "CONTINUE",
    "イヤッハー": "PRINT",
    "イヤッハー…": "PRINTN",
    "ヤッハーヤーハー": "PUB",
    "ヤー": "TRUE",
    "イヤ": "FALSE",
    "……": "NULL",
    "なんとかなれーッ": "TRY",
    "なんとかなれーッ!": "UNWRAP",
    "ダメだった…": "CATCH",
    "これって…": "IMPORT",
    "こういうこと?": "TYPEDECL",
    "もしかして": "MATCH",
    "ってこと?": "CASE",
    "じゃないってこと?": "DEFAULT",
    "ワァーッ!": "THROW",
    "ヤッター": "OK",
    "ワァ…": "ERR",
    "コレ": "SELF",
}

# 型名。字句上はただの識別子だが、最長一致の後退先として既知語に含める。
TYPE_WORDS = {
    "プルッ": "Int",
    "プルァッ": "Float",
    "ワァッ": "String",
    "ヤハ?ッ": "Bool",
    "ムレッ": "List",
    "ウララッ": "Map",
    "ナンカッ": "Any",
    "ナシッ": "Void",
    "ヤッタッ": "Result",
}

# `?` や `…` を含むため 1 語として読ませたい非キーワード。
KNOWN_WORDS = set(KEYWORDS) | set(TYPE_WORDS) | set([
    "ン?",       # コレクション要素数
    "ヤッタ?",   # Result が成功か
    "ワァ?",     # 標準入力
    "できる?",   # テスト宣言(v0.3 予約)
])

# 長い順に並べた既知語(後退時の探索用)
_KNOWN_SORTED = sorted(KNOWN_WORDS, key=len, reverse=True)

OPERATORS = [
    "...", "|>", "??", "?.", "->", "=>", "==", "!=", "<=", ">=",
    "&&", "||", "+=", "-=", "*=", "/=",
    "+", "-", "*", "/", "%", "<", ">", "=", "!", "?",
    ".", ",", ":", ";", "(", ")", "[", "]", "{", "}",
]


class Token(object):
    __slots__ = ("kind", "text", "value", "span")

    def __init__(self, kind, text, span, value=None):
        self.kind = kind
        self.text = text
        self.span = span
        self.value = value

    def __repr__(self):
        return "Token(%s, %r)" % (self.kind, self.text)


class Lexer(object):
    def __init__(self, source, filename="main.ura", bag=None):
        self.src = source
        self.file = filename
        self.i = 0
        self.line = 1
        self.col = 1
        self.tokens = []
        self.bag = bag

    # -------------------------------------------------------- 基本操作

    def _peek(self, off=0):
        j = self.i + off
        return self.src[j] if j < len(self.src) else ""

    def _advance(self, n=1):
        for _ in range(n):
            if self.i >= len(self.src):
                return
            if self.src[self.i] == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.i += 1

    def _span(self, line, col, length):
        return Span(self.file, line, col, length)

    def _fail(self, code, message, line=None, col=None, length=1, notes=None):
        raise UrayahaError(Diagnostic(
            code, message,
            self._span(line or self.line, col or self.col, length), notes))

    def _warn(self, code, message, line, col, length=1, notes=None):
        if self.bag is not None:
            self.bag.warn(code, message, self._span(line, col, length), notes)

    def _emit(self, kind, text, line, col, length, value=None):
        self.tokens.append(Token(kind, text, self._span(line, col, length), value))

    # -------------------------------------------------------- 本体

    def lex(self):
        while self.i < len(self.src):
            ch = self._peek()
            if ch in " \t\r\n　":
                self._advance()
                continue
            if ch == "/" and self._peek(1) == "/":
                while self.i < len(self.src) and self._peek() != "\n":
                    self._advance()
                continue
            if ch == "/" and self._peek(1) == "*":
                self._lex_block_comment()
                continue
            if ch == '"':
                self._lex_string()
                continue
            if ch == "ン" and self._peek(1) == "・":
                self._lex_urayaha_number()
                continue
            if ch.isdigit() and ord(ch) < 128:
                self._lex_ascii_number()
                continue
            if _is_word_start(ch):
                self._lex_word()
                continue
            if self._lex_operator():
                continue
            self._fail("E0001", "「%s」、ここでは読めないみたい" % ch)
        self._emit("EOF", "", self.line, self.col, 1)
        return self.tokens

    def _lex_block_comment(self):
        line, col = self.line, self.col
        self._advance(2)
        while self.i < len(self.src):
            if self._peek() == "*" and self._peek(1) == "/":
                self._advance(2)
                return
            self._advance()
        self._fail("E0002", "コメントが閉じてないみたい(「*/」がほしい)", line, col, 2)

    # -------------------------------------------------------- 数値

    def _lex_urayaha_number(self):
        line, col = self.line, self.col
        start = self.i
        self._advance(2)  # ン・
        int_digits = self._take_urayaha_digits()
        if not int_digits:
            self._fail("E0003", "「ン・」のあとに数字(ン プ ル ャ)がないみたい",
                       line, col, 2)
        frac_digits = ""
        if self._peek() == "." and self._peek(1) in DIGIT_VALUE:
            self._advance()
            frac_digits = self._take_urayaha_digits()
        text = self.src[start:self.i]
        length = self.i - start
        if frac_digits:
            value = _base4_int(int_digits) + _base4_frac(frac_digits)
            self._emit("FLOAT", text, line, col, length, value)
        else:
            self._emit("INT", text, line, col, length, _base4_int(int_digits))

    def _take_urayaha_digits(self):
        out = []
        while self._peek() != "" and self._peek() in DIGIT_VALUE:
            out.append(self._peek())
            self._advance()
        return "".join(out)

    def _lex_ascii_number(self):
        """実用モード向けにアラビア数字も受ける(§93)。--urayaha では弾く。"""
        line, col = self.line, self.col
        start = self.i
        while self._peek().isdigit() and ord(self._peek()) < 128:
            self._advance()
        is_float = False
        if self._peek() == "." and self._peek(1).isdigit() and ord(self._peek(1)) < 128:
            is_float = True
            self._advance()
            while self._peek().isdigit() and ord(self._peek()) < 128:
                self._advance()
        text = self.src[start:self.i]
        self._warn("W1006",
                   "「%s」って普通に喋ってない？(うさぎ数字だと「%s」)"
                   % (text, _to_urayaha_number(text)), line, col, len(text))
        if is_float:
            self._emit("FLOAT", text, line, col, len(text), float(text))
        else:
            self._emit("INT", text, line, col, len(text), int(text))

    # -------------------------------------------------------- 語

    def _lex_word(self):
        line, col = self.line, self.col
        raw = []
        j = self.i
        while j < len(self.src) and _is_word_cont(self.src[j]):
            raw.append(NORMALIZE.get(self.src[j], self.src[j]))
            j += 1
        after = self.src[j] if j < len(self.src) else ""
        after = NORMALIZE.get(after, after)
        word = self._resolve_word("".join(raw), after, line, col)
        # 正規化は 1 文字 -> 1 文字なので、原文上の長さは正規化後と同じ。
        # v0.3 §4 のとおり全角と半角は同じ語なので、ここでは警告を出さない。
        self._advance(len(word))
        kind = KEYWORDS.get(word)
        if kind is not None:
            self._emit(kind, word, line, col, len(word))
        else:
            self._emit("IDENT", word, line, col, len(word))

    def _resolve_word(self, word, after, line, col):
        """最長一致(v0.4 §9)。既知語を最優先し、無ければ自然な語境界で切る。

        `?` と `!` は語の末尾に 1 文字だけ取り込む。ただし直後が `? . = !` の
        ときは演算子(`??` `?.` `!=` など)なので取り込まない。これで
        `フゥン?` は識別子、`ヤハァ??ヤハッ` は `ヤハァ` + `??` に割れる。
        Optional の `プルッ?` は識別子として読み、型注釈の位置で Parser が
        末尾の `?` を Optional として切り離す。
        """
        if word in KNOWN_WORDS:
            return word
        cut = 0
        while cut < len(word) and word[cut] not in "!?" and word[cut] != ELLIPSIS:
            cut += 1
        natural = word
        if cut < len(word):
            if word[cut] == ELLIPSIS:
                natural = word[:cut]
            else:
                following = word[cut + 1] if cut + 1 < len(word) else after
                natural = word[:cut] if following in ("?", ".", "=", "!")                     else word[:cut + 1]
        for cand in _KNOWN_SORTED:
            if len(cand) > len(natural) and word.startswith(cand):
                return cand
        if not natural:
            self._fail("E0004", "「%s」、名前としては読めないみたい" % word,
                       line, col, len(word))
        return natural

    # -------------------------------------------------------- 文字列

    def _lex_string(self):
        line, col = self.line, self.col
        self._advance()  # 開き "
        parts = []
        buf = []
        escapes = {"n": "\n", "t": "\t", "r": "\r",
                   '"': '"', "\\": "\\", "$": "$"}
        while True:
            if self.i >= len(self.src):
                self._fail("E0002", "文字列が閉じてないみたい(「\"」がほしい)",
                           line, col, 1)
            ch = self._peek()
            if ch == '"':
                self._advance()
                break
            if ch == "\\":
                self._advance()
                esc = self._peek()
                if esc == "":
                    self._fail("E0003", "エスケープが途中で終わってるみたい")
                buf.append(escapes.get(esc, esc))
                self._advance()
                continue
            if ch == "$" and self._peek(1) == "{":
                if buf:
                    parts.append(("str", "".join(buf)))
                    buf = []
                parts.append(self._lex_interpolation())
                continue
            buf.append(ch)          # 文字列の中身は正規化しない
            self._advance()
        if buf or not parts:
            parts.append(("str", "".join(buf)))
        length = max(1, self.col - col) if self.line == line else 1
        flat = "".join(p[1] for p in parts if p[0] == "str")
        self._emit("STRING", flat, line, col, length, parts)

    def _lex_interpolation(self):
        eline, ecol = self.line, self.col
        self._advance(2)  # ${
        depth = 1
        start = self.i
        while self.i < len(self.src):
            ch = self._peek()
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            elif ch == '"':
                self._skip_nested_string()
                continue
            self._advance()
        if self.i >= len(self.src):
            self._fail("E0002", "文字列の中の補間が閉じてないみたい", eline, ecol, 2)
        expr_src = self.src[start:self.i]
        self._advance()  # }
        return ("expr", expr_src, eline, ecol + 2)

    def _skip_nested_string(self):
        self._advance()
        while self.i < len(self.src) and self._peek() != '"':
            if self._peek() == "\\":
                self._advance()
            self._advance()
        self._advance()

    # -------------------------------------------------------- 演算子

    def _lex_operator(self):
        line, col = self.line, self.col
        # 演算子位置でも全角の ！ ？ を受ける(v0.3 §4)。1 文字 -> 1 文字の
        # 正規化なので、正規化した窓で照合しても原文上の長さは変わらない。
        window = "".join(NORMALIZE.get(c, c) for c in self.src[self.i:self.i + 3])
        for op in OPERATORS:
            if window.startswith(op):
                self._advance(len(op))
                self._emit("OP", op, line, col, len(op))
                return True
        return False


# ---------------------------------------------------------------- 数値変換

def _base4_int(digits):
    n = 0
    for ch in digits:
        n = n * 4 + DIGIT_VALUE[ch]
    return n


def _base4_frac(digits):
    v = 0.0
    scale = 0.25
    for ch in digits:
        v += DIGIT_VALUE[ch] * scale
        scale /= 4.0
    return v


def to_urayaha_digits(n):
    """10 進整数 -> うさぎ 4 進表記(`ン・` は付けない)。"""
    if n == 0:
        return "ン"
    sign = "-" if n < 0 else ""
    n = abs(n)
    out = []
    inv = "ンプルャ"
    while n:
        out.append(inv[n % 4])
        n //= 4
    return sign + "".join(reversed(out))


def _to_urayaha_number(text):
    try:
        if "." in text:
            return "ン・" + to_urayaha_digits(int(float(text)))
        return "ン・" + to_urayaha_digits(int(text))
    except ValueError:
        return text


def lex(source, filename="main.ura", bag=None):
    return Lexer(source, filename, bag).lex()
