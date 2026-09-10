# -*- coding: utf-8 -*-
"""Urayaha 構文解析器(再帰下降)。

v0.3 で確定した構文上の変更点:

* §63 の EBNF と §24/§25/§41 の例が矛盾していたので、例に合わせて
  「チェーンブロック」を正式とする。`ウラ` と `ダメだった…` は直前のブロックを
  閉じつつ次のブロックを開き、`ハァッ` は構文全体の末尾に 1 つだけ置く。
* 改行はただの空白として扱う(§64)。ただし `ハァーッ` は同じ行にある式だけを
  戻り値とみなす。これで値なし return が次の行の式を巻き込まない。
* `イヤッハー` / `イヤッハー…` は文ではなく組み込み関数として扱う。
  こうしないと §59 の `プルャッ |> イヤッハー` が書けない。
"""

from . import ast_nodes as A
from .errors import Diagnostic, UrayahaError
from .lexer import lex

# 演算子の優先順位は仕様 §19 を v0.3 §7 で補完したもの(低い順)
ASSIGN_OPS = ("=", "+=", "-=", "*=", "/=")
EQUALITY_OPS = ("==", "!=")
COMPARISON_OPS = ("<", "<=", ">", ">=")
ADDITIVE_OPS = ("+", "-")
MULTIPLICATIVE_OPS = ("*", "/", "%")

_EXPR_START_KINDS = set([
    "INT", "FLOAT", "STRING", "IDENT", "TRUE", "FALSE", "NULL",
    "FN", "OK", "ERR", "SELF", "PRINT", "PRINTN", "UNWRAP",
])
_EXPR_START_OPS = set(["(", "[", "{", "-", "!"])


class Parser(object):
    def __init__(self, tokens, filename="main.ura", bag=None):
        self.toks = tokens
        self.pos = 0
        self.file = filename
        self.bag = bag

    # -------------------------------------------------------- トークン操作

    def _cur(self):
        return self.toks[self.pos]

    def _peek(self, off=0):
        j = self.pos + off
        return self.toks[j] if j < len(self.toks) else self.toks[-1]

    def _at(self, kind, text=None):
        t = self._cur()
        if t.kind != kind:
            return False
        return text is None or t.text == text

    def _at_op(self, *texts):
        t = self._cur()
        return t.kind == "OP" and t.text in texts

    def _next(self):
        t = self.toks[self.pos]
        if self.pos < len(self.toks) - 1:
            self.pos += 1
        return t

    def _accept(self, kind, text=None):
        if self._at(kind, text):
            return self._next()
        return None

    def _accept_op(self, *texts):
        if self._at_op(*texts):
            return self._next()
        return None

    def _expect(self, kind, what):
        if self._at(kind):
            return self._next()
        self._fail("E0002", "「%s」がないみたい" % what)

    def _expect_op(self, text, what=None):
        if self._at_op(text):
            return self._next()
        self._fail("E0002", "「%s」がないみたい" % (what or text))

    def _fail(self, code, message, tok=None):
        tok = tok or self._cur()
        raise UrayahaError(Diagnostic(code, message, tok.span))

    # -------------------------------------------------------- エントリ

    def parse_program(self):
        start = self._cur().span
        body = []
        while not self._at("EOF"):
            body.append(self._declaration())
        return A.Program(start, body)

    def parse_expression_only(self):
        expr = self._expression()
        if not self._at("EOF"):
            self._fail("E0001", "式のあとに「%s」が残ってるみたい" % self._cur().text)
        return expr

    # -------------------------------------------------------- 宣言・文

    def _declaration(self):
        if self._at("PUB"):
            pub = self._next()
            if self._at("FN"):
                return self._func_decl(is_pub=True, span=pub.span)
            if self._at("LET") or self._at("CONST"):
                decl = self._var_decl()
                decl.is_pub = True
                return decl
            if self._at("TYPEDECL"):
                decl = self._type_decl()
                decl.is_pub = True
                return decl
            self._fail("E0001", "「イヤッハーッ」のあとは フゥン か ヤハ か こういうこと？ がほしいみたい")
        if self._at("LET") or self._at("CONST"):
            return self._var_decl()
        if self._at("FN"):
            return self._func_decl(is_pub=False, span=self._cur().span)
        if self._at("TYPEDECL"):
            return self._type_decl()
        if self._at("IMPORT"):
            return self._import_decl()
        return self._statement()

    def _var_decl(self):
        kw = self._next()
        is_const = kw.kind == "CONST"
        if self._at_op("("):
            names = self._destructuring_names()
            self._expect_op("=", "=")
            init = self._expression()
            return A.DestructDecl(kw.span, names, init, is_const)
        name_tok = self._expect("IDENT", "名前")
        type_ref = None
        if self._accept_op(":"):
            type_ref = self._type_ref()
        self._expect_op("=", "=")
        init = self._expression()
        return A.VarDecl(kw.span, name_tok.text, type_ref, init, is_const, False)

    def _destructuring_names(self):
        self._expect_op("(")
        names = []
        while not self._at_op(")"):
            names.append(self._expect("IDENT", "名前").text)
            if not self._accept_op(","):
                break
        self._expect_op(")", ")")
        if len(names) < 2:
            self._fail("E0001", "分解代入は名前が ン・ル 個以上いるみたい")
        return names

    def _func_decl(self, is_pub, span):
        self._next()  # フゥン
        name_tok = self._expect("IDENT", "関数の名前")
        recv = None
        name = name_tok.text
        if self._accept_op("."):
            recv = name
            name = self._expect("IDENT", "メソッドの名前").text
        params = self._param_list()
        ret_type = None
        if self._accept_op("->"):
            ret_type = self._type_ref()
        body = self._block()
        return A.FuncDecl(span, name, recv, params, ret_type, body, is_pub)

    def _param_list(self):
        self._expect_op("(")
        params = []
        while not self._at_op(")"):
            span = self._cur().span
            variadic = self._accept_op("...") is not None
            pname = self._expect("IDENT", "引数の名前").text
            ptype = None
            if self._accept_op(":"):
                ptype = self._type_ref()
            default = None
            if self._accept_op("="):
                default = self._expression()
            params.append(A.Param(span, pname, ptype, default, variadic))
            if not self._accept_op(","):
                break
        self._expect_op(")", ")")
        return params

    def _type_decl(self):
        kw = self._next()  # こういうこと？
        name = self._expect("IDENT", "型の名前").text
        self._expect("BEGIN", "ヤーッ")
        fields = []
        while not self._at("END"):
            if self._at("EOF"):
                self._fail("E0002", "「ハァッ」がないみたい")
            fspan = self._cur().span
            fname = self._expect("IDENT", "フィールド名").text
            self._expect_op(":", ":")
            ftype = self._type_ref()
            fields.append(A.Field(fspan, fname, ftype))
            self._accept_op(",")
            self._accept_op(";")
        self._expect("END", "ハァッ")
        return A.TypeDecl(kw.span, name, fields, False)

    def _import_decl(self):
        kw = self._next()
        if self._at("STRING"):
            target = self._next().text
            is_module = False
        elif self._at("IDENT"):
            target = self._next().text
            is_module = True
        else:
            self._fail("E0001",
                       "これって… のあとは モジュール名か \"パス\" がほしいみたい")
        alias = None
        if self._accept_op("->"):
            alias = self._expect("IDENT", "別名").text
        return A.ImportDecl(kw.span, target, alias, is_module)

    def _statement(self):
        t = self._cur()
        if t.kind == "IF":
            return self._if_statement()
        if t.kind == "WHILE":
            return self._while_statement()
        if t.kind == "FOR":
            return self._for_statement()
        if t.kind == "RETURN":
            return self._return_statement()
        if t.kind == "BREAK":
            self._next()
            self._accept_op(";")
            return A.Break(t.span)
        if t.kind == "CONTINUE":
            self._next()
            self._accept_op(";")
            return A.Continue(t.span)
        if t.kind == "TRY":
            return self._try_statement()
        if t.kind == "MATCH":
            return self._match_statement()
        if t.kind == "THROW":
            return self._throw_statement()
        if t.kind == "BEGIN":
            # 素のブロックは if 相当の入れ子スコープとして扱う
            body = self._block()
            return A.If(t.span, [(A.BoolLit(t.span, True), body)], None)
        expr = self._expression()
        self._accept_op(";")
        return A.ExprStmt(expr.span, expr)

    # ---------------- チェーンブロック構文(v0.3) ----------------

    def _body_until(self, *stop_kinds):
        """`ハァッ` などの終端キーワードが来るまで宣言を読む(終端は消費しない)。"""
        stmts = []
        while self._cur().kind not in stop_kinds:
            if self._at("EOF"):
                self._fail("E0002", "「ハァッ」がないみたい")
            stmts.append(self._declaration())
        return stmts

    def _block(self):
        """`ヤーッ` ... `ハァッ`(独立したブロック)。"""
        self._expect("BEGIN", "ヤーッ")
        body = self._body_until("END")
        self._expect("END", "ハァッ")
        return body

    def _if_statement(self):
        span = self._cur().span
        self._next()  # ハァ？
        branches = []
        cond = self._expression()
        self._expect("BEGIN", "ヤーッ")
        body = self._body_until("ELSE", "END")
        branches.append((cond, body))
        else_body = None
        while self._at("ELSE"):
            self._next()
            if self._at("IF"):
                self._next()
                c = self._expression()
                self._expect("BEGIN", "ヤーッ")
                b = self._body_until("ELSE", "END")
                branches.append((c, b))
            else:
                self._expect("BEGIN", "ヤーッ")
                else_body = self._body_until("END")
                break
        self._expect("END", "ハァッ")
        return A.If(span, branches, else_body)

    def _while_statement(self):
        span = self._cur().span
        self._next()
        cond = self._expression()
        body = self._block()
        return A.While(span, cond, body)

    def _for_statement(self):
        span = self._cur().span
        self._next()
        iterable = self._expression()
        self._expect_op("->", "->")
        var = self._expect("IDENT", "要素の名前").text
        body = self._block()
        return A.For(span, iterable, var, body)

    def _return_statement(self):
        tok = self._next()
        value = None
        nxt = self._cur()
        same_line = nxt.span.line == tok.span.line
        if same_line and self._can_start_expression(nxt):
            value = self._expression()
        self._accept_op(";")
        return A.Return(tok.span, value)

    def _try_statement(self):
        span = self._cur().span
        self._next()  # なんとかなれーッ
        self._expect("BEGIN", "ヤーッ")
        body = self._body_until("CATCH")
        self._expect("CATCH", "ダメだった…")
        catch_var = None
        if self._accept_op("->"):
            catch_var = self._expect("IDENT", "受け取る名前").text
        self._expect("BEGIN", "ヤーッ")
        catch_body = self._body_until("END")
        self._expect("END", "ハァッ")
        return A.Try(span, body, catch_var, catch_body)

    def _match_statement(self):
        span = self._cur().span
        self._next()
        subject = self._expression()
        self._expect("BEGIN", "ヤーッ")
        cases = []
        default_body = None
        while not self._at("END"):
            if self._at("EOF"):
                self._fail("E0002", "「ハァッ」がないみたい")
            if self._at("CASE"):
                self._next()
                pattern = self._expression()
                self._expect_op("=>", "=>")
                cases.append((pattern, self._case_body()))
            elif self._at("DEFAULT"):
                self._next()
                self._expect_op("=>", "=>")
                default_body = self._case_body()
            else:
                self._fail("E0001",
                           "もしかして の中には ってこと？ か じゃないってこと？ がほしいみたい")
        self._expect("END", "ハァッ")
        return A.Match(span, subject, cases, default_body)

    def _case_body(self):
        if self._at("BEGIN"):
            return self._block()
        return [self._declaration()]

    def _throw_statement(self):
        tok = self._next()
        self._expect_op("(")
        value = self._expression()
        self._expect_op(")", ")")
        self._accept_op(";")
        return A.Throw(tok.span, value)

    def _can_start_expression(self, tok):
        if tok.kind in _EXPR_START_KINDS:
            return True
        return tok.kind == "OP" and tok.text in _EXPR_START_OPS

    # -------------------------------------------------------- 型注釈

    def _type_ref(self):
        tok = self._expect("IDENT", "型の名前")
        name = tok.text
        trailing_optional = False
        if len(name) > 1 and name.endswith("?"):
            name = name[:-1]
            trailing_optional = True
        args = []
        if self._at_op("<"):
            self._next()
            while not self._at_op(">"):
                args.append(self._type_ref())
                if not self._accept_op(","):
                    break
            self._expect_op(">", ">")
        optional = trailing_optional or self._accept_op("?") is not None
        return A.TypeRef(tok.span, name, args, optional)

    # -------------------------------------------------------- 式

    def _expression(self):
        return self._assignment()

    def _assignment(self):
        left = self._pipe()
        if self._cur().kind == "OP" and self._cur().text in ASSIGN_OPS:
            op = self._next()
            value = self._assignment()
            if left.kind not in ("Ident", "Index", "Member", "SelfExpr"):
                self._fail("E0001", "ここには代入できないみたい", op)
            return A.Assign(op.span, left, op.text, value)
        return left

    def _pipe(self):
        left = self._coalesce()
        while self._at_op("|>"):
            span = self._next().span
            right = self._coalesce()
            if right.kind == "Call":
                right.args = [left] + list(right.args)
                left = right
            else:
                left = A.Call(span, right, [left])
        return left

    def _coalesce(self):
        left = self._logic_or()
        while self._at_op("??"):
            span = self._next().span
            left = A.Coalesce(span, left, self._logic_or())
        return left

    def _logic_or(self):
        left = self._logic_and()
        while self._at_op("||"):
            span = self._next().span
            left = A.Logical(span, "||", left, self._logic_and())
        return left

    def _logic_and(self):
        left = self._equality()
        while self._at_op("&&"):
            span = self._next().span
            left = A.Logical(span, "&&", left, self._equality())
        return left

    def _equality(self):
        left = self._comparison()
        while self._cur().kind == "OP" and self._cur().text in EQUALITY_OPS:
            tok = self._next()
            left = A.Binary(tok.span, tok.text, left, self._comparison())
        return left

    def _comparison(self):
        left = self._additive()
        while self._cur().kind == "OP" and self._cur().text in COMPARISON_OPS:
            tok = self._next()
            left = A.Binary(tok.span, tok.text, left, self._additive())
        return left

    def _additive(self):
        left = self._multiplicative()
        while self._cur().kind == "OP" and self._cur().text in ADDITIVE_OPS:
            tok = self._next()
            left = A.Binary(tok.span, tok.text, left, self._multiplicative())
        return left

    def _multiplicative(self):
        left = self._unary()
        while self._cur().kind == "OP" and self._cur().text in MULTIPLICATIVE_OPS:
            tok = self._next()
            left = A.Binary(tok.span, tok.text, left, self._unary())
        return left

    def _unary(self):
        if self._at_op("!", "-"):
            tok = self._next()
            return A.Unary(tok.span, tok.text, self._unary())
        return self._postfix()

    def _postfix(self):
        expr = self._primary()
        while True:
            if self._at_op("("):
                span = self._next().span
                args = []
                while not self._at_op(")"):
                    args.append(self._expression())
                    if not self._accept_op(","):
                        break
                self._expect_op(")", ")")
                expr = A.Call(span, expr, args)
            elif self._at_op("["):
                span = self._next().span
                index = self._expression()
                self._expect_op("]", "]")
                expr = A.Index(span, expr, index)
            elif self._at_op(".", "?."):
                tok = self._next()
                optional = tok.text == "?."
                name = self._member_name()
                expr = A.Member(tok.span, expr, name, optional)
            else:
                return expr

    def _member_name(self):
        """member 位置では予約語も名前として使える(v0.3 §3)。"""
        tok = self._cur()
        if tok.kind == "IDENT" or tok.kind in ("EOF",):
            if tok.kind == "EOF":
                self._fail("E0002", "「.」のあとに名前がないみたい")
            self._next()
            return tok.text
        if tok.kind == "OP" or tok.kind in ("INT", "FLOAT", "STRING"):
            self._fail("E0004", "「%s」はメンバ名にできないみたい" % tok.text)
        self._next()
        return tok.text

    def _primary(self):
        tok = self._cur()
        if tok.kind == "INT":
            self._next()
            return A.IntLit(tok.span, tok.value)
        if tok.kind == "FLOAT":
            self._next()
            return A.FloatLit(tok.span, tok.value)
        if tok.kind == "STRING":
            self._next()
            return self._string_literal(tok)
        if tok.kind == "TRUE":
            self._next()
            return A.BoolLit(tok.span, True)
        if tok.kind == "FALSE":
            self._next()
            return A.BoolLit(tok.span, False)
        if tok.kind == "NULL":
            self._next()
            return A.NullLit(tok.span)
        if tok.kind == "SELF":
            self._next()
            return A.SelfExpr(tok.span)
        if tok.kind in ("PRINT", "PRINTN"):
            self._next()
            return A.Ident(tok.span, tok.text)
        if tok.kind == "IDENT":
            self._next()
            return A.Ident(tok.span, tok.text)
        if tok.kind == "OK":
            self._next()
            return A.OkExpr(tok.span, self._wrapped_argument())
        if tok.kind == "ERR":
            self._next()
            return A.ErrExpr(tok.span, self._wrapped_argument())
        if tok.kind == "FN":
            return self._lambda()
        if tok.kind == "OP":
            if tok.text == "(":
                return self._paren_or_tuple()
            if tok.text == "[":
                return self._array_literal()
            if tok.text == "{":
                return self._map_literal()
        self._fail("E0001", "「%s」、ここでは読めないみたい" % (tok.text or "おわり"))

    def _wrapped_argument(self):
        self._expect_op("(")
        if self._at_op(")"):
            self._next()
            return A.NullLit(self._cur().span)
        value = self._expression()
        self._expect_op(")", ")")
        return value

    def _lambda(self):
        tok = self._next()  # フゥン
        params = self._param_list()
        if self._accept_op("=>"):
            return A.Lambda(tok.span, params, self._expression(), True)
        body = self._block()
        return A.Lambda(tok.span, params, body, False)

    def _paren_or_tuple(self):
        span = self._next().span
        if self._at_op(")"):
            self._next()
            return A.TupleLit(span, [])
        first = self._expression()
        if self._at_op(","):
            items = [first]
            while self._accept_op(","):
                if self._at_op(")"):
                    break
                items.append(self._expression())
            self._expect_op(")", ")")
            return A.TupleLit(span, items)
        self._expect_op(")", ")")
        return first

    def _array_literal(self):
        span = self._next().span
        items = []
        while not self._at_op("]"):
            items.append(self._expression())
            if not self._accept_op(","):
                break
        self._expect_op("]", "]")
        return A.ArrayLit(span, items)

    def _map_literal(self):
        span = self._next().span
        pairs = []
        while not self._at_op("}"):
            key = self._expression()
            self._expect_op(":", ":")
            pairs.append((key, self._expression()))
            if not self._accept_op(","):
                break
        self._expect_op("}", "}")
        return A.MapLit(span, pairs)

    def _string_literal(self, tok):
        parts = []
        for part in (tok.value or []):
            if part[0] == "str":
                parts.append(("str", part[1]))
            else:
                _, src, line, col = part
                sub_tokens = lex(src, self.file, self.bag)
                for st in sub_tokens:
                    if st.span.line == 1:
                        st.span.col += col - 1
                    st.span.line += line - 1
                sub = Parser(sub_tokens, self.file, self.bag).parse_expression_only()
                parts.append(("expr", sub))
        return A.StrLit(tok.span, parts)


def parse(tokens, filename="main.ura", bag=None):
    return Parser(tokens, filename, bag).parse_program()
