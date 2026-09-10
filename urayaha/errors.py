# -*- coding: utf-8 -*-
"""Urayaha の診断(エラー・警告)体系。

仕様 §66-§76。内部コードは英語、利用者向け表示はちいかわ・ハチワレ語調。
v0.3 §8: 診断の行番号・桁番号は 10 進数で出す(ソース言語の 4 進うさぎ数字とは分離)。
"""


import unicodedata


def _width(text):
    """CJK は端末で 2 桁ぶん出るので、キャレットの位置合わせに使う。"""
    total = 0
    for ch in text:
        total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return total


class Span:
    """ソース上の位置。line / col は 1 始まり。"""

    __slots__ = ("file", "line", "col", "length")

    def __init__(self, file, line, col, length=1):
        self.file = file
        self.line = line
        self.col = col
        self.length = max(1, length)

    def __repr__(self):
        return "Span(%s:%d:%d+%d)" % (self.file, self.line, self.col, self.length)


# コード -> (内部名, 見出し語)
CATALOG = {
    "E0001": ("UnexpectedToken", "ワァッ！？"),
    "E0002": ("MissingToken", "ワァッ！？"),
    "E0003": ("InvalidLiteral", "ワァッ！？"),
    "E0004": ("InvalidIdentifier", "ワァッ！？"),
    "E1001": ("UndefinedIdentifier", "エッ…エッ…"),
    "E1002": ("DuplicateIdentifier", "エッ…エッ…"),
    "E1003": ("InvalidScope", "エッ…エッ…"),
    "E1004": ("UnknownModule", "エッ…エッ…"),
    "E2001": ("TypeMismatch", "泣いちゃった！"),
    "E2002": ("InvalidOperation", "泣いちゃった！"),
    "E2003": ("WrongArgumentCount", "ワァ…"),
    "E2004": ("InvalidReturnType", "泣いちゃった！"),
    "E2005": ("InvalidMember", "エッ…エッ…"),
    "E3001": ("DivisionByZero", "泣いちゃった！"),
    "E3002": ("IndexOutOfBounds", "ワァァァァ！！"),
    "E3003": ("NullAccess", "ワァァァ！！"),
    "E3004": ("IOError", "泣いちゃった！"),
    "E3005": ("NetworkError", "泣いちゃった！"),
    # ワァーッ！ の送出と Err の unwrap は同じ例外伝播に乗る。どの ダメだった…
    # にも捕まらずトップレベルまで来たときだけ、この診断になる。
    "E3006": ("UncaughtException", "ワァーッ！"),
    "E9001": ("InternalCompilerError", "ワァァァァァァァァァァァァ！！！！！"),
    "W1001": ("UnusedVariable", "フゥン…"),
    "W1002": ("ShadowedVariable", "フゥン…"),
    "W1003": ("UnreachableCode", "フゥン…"),
    "W1004": ("ImplicitAny", "フゥン…"),
    "W1006": ("NotUrayahaEnough", "フゥン…"),
}


class Diagnostic:
    def __init__(self, code, message, span=None, notes=None):
        self.code = code
        self.message = message
        self.span = span
        self.notes = list(notes or [])

    @property
    def internal_name(self):
        return CATALOG.get(self.code, ("Unknown", "ワァ…"))[0]

    @property
    def headline(self):
        return CATALOG.get(self.code, ("Unknown", "ワァ…"))[1]

    @property
    def is_warning(self):
        return self.code.startswith("W")

    def render(self, source_lines=None, show_internal=False):
        out = []
        head = "[%s] %s" % (self.code, self.headline)
        if show_internal:
            head += "   (%s)" % self.internal_name
        out.append(head)
        out.append("")
        if self.span is not None:
            out.append("%s:%d:%d" % (self.span.file, self.span.line, self.span.col))
            out.append("")
            line_text = None
            if source_lines and 1 <= self.span.line <= len(source_lines):
                line_text = source_lines[self.span.line - 1]
            if line_text is not None:
                text = line_text.rstrip("\n")
                out.append("    " + text)
                head = text[:self.span.col - 1]
                body = text[self.span.col - 1:self.span.col - 1 + self.span.length]
                out.append("    " + " " * _width(head)
                           + "^" * max(1, _width(body)))
                out.append("")
        out.append(self.message)
        if self.notes:
            # 「ほしかったもの / きたもの」は並べて読むものなので続けて出す
            out.append("")
            out.extend(self.notes)
        return "\n".join(out)


class UrayahaError(Exception):
    """コンパイル時に投げる致命的診断。"""

    def __init__(self, diagnostic):
        Exception.__init__(self, diagnostic.message)
        self.diagnostic = diagnostic


class UrayahaRuntimeError(Exception):
    """VM 実行時エラー。Urayaha 側の なんとかなれーッ で捕捉できる。"""

    def __init__(self, code, message, span=None, payload=None):
        Exception.__init__(self, message)
        self.code = code
        self.message = message
        self.span = span
        # payload は ワァーッ！ で投げられた Urayaha 値。組み込みエラーでは None。
        self.payload = payload

    def to_diagnostic(self):
        return Diagnostic(self.code, self.message, self.span)


class DiagnosticBag:
    """警告を貯めつつ、エラーは即座に投げるための入れ物。"""

    def __init__(self):
        self.warnings = []

    def warn(self, code, message, span=None, notes=None):
        self.warnings.append(Diagnostic(code, message, span, notes))

    def error(self, code, message, span=None, notes=None):
        raise UrayahaError(Diagnostic(code, message, span, notes))


def fatal_banner():
    return "ワァァァァァァァァァァァァ！！！！！\n\nUrayaha VM Internal Error"
