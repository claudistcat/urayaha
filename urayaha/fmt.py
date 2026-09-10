# -*- coding: utf-8 -*-
"""urayaha fmt(v0.4 §114, CLI §164-§166)。

いまの版が直すのはインデントと行末の空白だけで、字句は一切書き換えない。
§139 / §166 のとおり `～ ー … ッ ァ ィ ゥ ャ` は絶対に触らない。
演算子まわりの空白調整は、文字列や補間を壊す危険があるのでまだやらない。

段の数え方は 3 つを足し合わせる。

* ブロック段  `ヤーッ` で深くなり `ハァッ` で浅くなる。
  `ウラ` と `ダメだった…` は前のブロックを閉じて次を開くので、その行だけ
  1 段戻して出し、段の総数は変えない。
* 括弧段      `( [ {` で深くなる。複数行にまたがるリテラルや引数並びが
  行頭に貼りつくのを防ぐ。
* match の腕  `=>` で終わる行の次の行は 1 段深くする。
"""

from .errors import DiagnosticBag, UrayahaError
from .lexer import lex

INDENT = "    "
CHAIN_KINDS = ("ELSE", "CATCH")
OPEN_BRACKETS = ("(", "[", "{")
CLOSE_BRACKETS = (")", "]", "}")


def format_source(source, filename="main.ura"):
    lines = source.splitlines()
    try:
        tokens = lex(source, filename, DiagnosticBag())
    except UrayahaError:
        return source          # 読めないものは触らない

    by_line = {}
    inside_string = set()
    for tok in tokens:
        if tok.kind == "EOF":
            continue
        by_line.setdefault(tok.span.line, []).append(tok)
        if tok.kind == "STRING":
            for extra in range(1, _string_line_count(tok) + 1):
                inside_string.add(tok.span.line + extra)

    out = []
    block_depth = 0
    bracket_depth = 0
    arm_extra = 0
    for number, raw in enumerate(lines, start=1):
        if number in inside_string:
            out.append(raw)          # 複数行文字列の中は原文のまま
            continue
        stripped = raw.strip()
        if not stripped:
            out.append("")
            continue
        toks = by_line.get(number, [])
        if not toks:                 # コメントだけの行
            out.append(INDENT * max(0, block_depth + bracket_depth) + stripped)
            continue

        opens = len([t for t in toks if t.kind == "BEGIN"])
        closes = len([t for t in toks if t.kind == "END"])
        first = toks[0]
        chain = first.kind in CHAIN_KINDS
        dedent = 1 if (first.kind == "END" or chain) else 0
        leading_close = 0
        for tok in toks:
            if tok.kind == "OP" and tok.text in CLOSE_BRACKETS:
                leading_close += 1
            else:
                break

        level = (block_depth - dedent
                 + max(0, bracket_depth - leading_close)
                 + arm_extra)
        out.append(INDENT * max(0, level) + stripped)

        block_depth = max(0, block_depth + opens - closes - (1 if chain else 0))
        for tok in toks:
            if tok.kind != "OP":
                continue
            if tok.text in OPEN_BRACKETS:
                bracket_depth += 1
            elif tok.text in CLOSE_BRACKETS:
                bracket_depth = max(0, bracket_depth - 1)
        last = toks[-1]
        arm_extra = 1 if (last.kind == "OP" and last.text == "=>"
                          and opens == 0) else 0

    # 改行の種類は入力に合わせる。勝手に LF へ寄せると、CRLF で取得した
    # リポジトリで fmt --check が全ファイルを未整形と判定してしまう。
    newline = "\r\n" if "\r\n" in source else "\n"
    text = newline.join(out)
    if not text:
        return text
    return text + newline if source.endswith(("\n", "\r")) else text


def _string_line_count(tok):
    """文字列リテラルが何行にまたがっているか。"""
    count = 0
    for part in (tok.value or []):
        if part[0] == "str":
            count += part[1].count("\n")
    return count
