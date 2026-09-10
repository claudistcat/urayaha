# -*- coding: utf-8 -*-
"""名前解決と型検査(仕様 §33-§37, §66-§70, §75)。

型検査は「確実に間違っているものだけを落とす」方針にしてある。
Urayaha は §93 で実用モードを認めているので、推論できない箇所は ナンカッ(Any)へ
落として通す。ここで誤検知を出すと、まともに書けない言語になるため。
"""

from . import ast_nodes as A
from .errors import Diagnostic, UrayahaError

# ------------------------------------------------------------------ 型

ANY = "ナンカッ"
INT = "プルッ"
FLOAT = "プルァッ"
BOOL = "ヤハ?ッ"
STRING = "ワァッ"
LIST = "ムレッ"
MAP = "ウララッ"
VOID = "ナシッ"
NULL = "ヌルッ"
FUNC = "フゥンッ型"
TUPLE = "タプルッ"
RESULT = "ヤッタッ"

NUMERIC = (INT, FLOAT)

# v0.4 §67 の標準モジュール
STANDARD_MODULES = ("プスン", "プルャ", "プルャウラウラ", "ウロル",
                    "フゥ～ンフゥン", "ウラーヤッハ")


class Type(object):
    __slots__ = ("name", "args", "optional", "info")

    def __init__(self, name, args=None, optional=False, info=None):
        self.name = name
        self.args = tuple(args or ())
        self.optional = optional
        self.info = info          # FuncType なら (params, ret), StructType なら fields

    def __eq__(self, other):
        return (isinstance(other, Type) and self.name == other.name
                and self.args == other.args and self.optional == other.optional)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.name, self.args, self.optional))

    def opt(self):
        return Type(self.name, self.args, True, self.info)

    def __repr__(self):
        s = self.name
        if self.args:
            s += "<" + ", ".join(repr(a) for a in self.args) + ">"
        return s + ("?" if self.optional else "")


T_ANY = Type(ANY)
T_INT = Type(INT)
T_FLOAT = Type(FLOAT)
T_BOOL = Type(BOOL)
T_STRING = Type(STRING)
T_VOID = Type(VOID)
T_NULL = Type(NULL)

BUILTIN_TYPE_NAMES = set([ANY, INT, FLOAT, BOOL, STRING, LIST, MAP, VOID, RESULT])


def func_type(params, ret, min_args, max_args):
    t = Type(FUNC)
    t.info = (params, ret, min_args, max_args)
    return t


def struct_type(name, fields):
    t = Type(name)
    t.info = fields          # OrderedDict 相当の [(name, Type)]
    return t


def is_any(t):
    return t is None or t.name == ANY


def assignable(target, value):
    """value を target へ入れてよいか。判断できないときは通す。"""
    if is_any(target) or is_any(value):
        return True
    if value.name == NULL:
        return target.optional or target.name in (NULL, VOID)
    if target.optional and not value.optional:
        target = Type(target.name, target.args, False, target.info)
    if target.name == FLOAT and value.name == INT:
        return True
    if target.name != value.name:
        return False
    if target.args and value.args:
        if len(target.args) != len(value.args):
            return False
        for a, b in zip(target.args, value.args):
            if not assignable(a, b):
                return False
    return True


# ------------------------------------------------------------------ シンボル

class Symbol(object):
    __slots__ = ("name", "type", "is_const", "span", "used", "kind")

    def __init__(self, name, type_, is_const, span, kind="var"):
        self.name = name
        self.type = type_
        self.is_const = is_const
        self.span = span
        self.used = False
        self.kind = kind


class Scope(object):
    def __init__(self, parent=None, kind="block"):
        self.parent = parent
        self.kind = kind
        self.symbols = {}

    def declare(self, sym):
        self.symbols[sym.name] = sym

    def lookup_local(self, name):
        return self.symbols.get(name)

    def lookup(self, name):
        s = self
        while s is not None:
            if name in s.symbols:
                return s.symbols[name]
            s = s.parent
        return None


# ------------------------------------------------------------------ 組み込み

# メンバ名 -> (受け手の型名 or None, 戻り型を返す関数)
LIST_METHODS = {
    "ン?": lambda recv: T_INT,
    "ヤハ": lambda recv: T_VOID,
    "イヤッ": lambda recv: T_VOID,
    "フゥン": lambda recv: Type(LIST, (T_ANY,)),
    "ハァ?": lambda recv: recv,
    "ウラ": lambda recv: T_ANY,
    "ツナグ": lambda recv: T_STRING,
    "ナラベ": lambda recv: recv,
    "アル?": lambda recv: T_BOOL,
}
MAP_METHODS = {
    "ン?": lambda recv: T_INT,
    "ハァ?": lambda recv: T_BOOL,
    "ヤハ": lambda recv: T_VOID,
    "イヤッ": lambda recv: T_VOID,
    "カギ": lambda recv: Type(LIST, (T_STRING,)),
}
STRING_METHODS = {
    "ン?": lambda recv: T_INT,
    "ワケ": lambda recv: Type(LIST, (T_STRING,)),
    "ツナグ": lambda recv: T_STRING,
    "ハァ?": lambda recv: T_BOOL,
}
RESULT_METHODS = {
    "なんとかなれーッ!": lambda recv: (recv.args[0] if recv.args else T_ANY),
    "ヤッタ?": lambda recv: T_BOOL,
    "フゥン": lambda recv: T_ANY,
}


class Checker(object):
    def __init__(self, filename, bag, builtins, repl_state=None):
        self.file = filename
        self.bag = bag
        self.global_scope = Scope(None, "global")
        self.scope = self.global_scope
        self.structs = {}
        self.struct_methods = {}      # 型名 -> {メソッド名: 型}
        self.func_stack = []
        self.loop_depth = 0
        # REPL は 1 行ずつ別々にコンパイルするので、前の入力で宣言したものを
        # 引き継がないと 2 行目から E1001 になる。持ち越し分をここで流し込む。
        self.repl_state = repl_state
        self.repl = repl_state is not None
        for name, type_ in builtins.items():
            self.global_scope.declare(Symbol(name, type_, True, None, "builtin"))
        if self.repl:
            for name, type_ in repl_state.get("types", {}).items():
                self.global_scope.declare(
                    Symbol(name, type_, False, None, "builtin"))
            self.structs.update(repl_state.get("structs", {}))
            self.struct_methods.update(repl_state.get("methods", {}))

    # -------------------------------------------------------- 補助

    def _fail(self, code, message, span, notes=None):
        raise UrayahaError(Diagnostic(code, message, span, notes))

    def _warn(self, code, message, span, notes=None):
        self.bag.warn(code, message, span, notes)

    def _push(self, kind="block"):
        self.scope = Scope(self.scope, kind)
        return self.scope

    def _pop(self):
        scope = self.scope
        for sym in scope.symbols.values():
            if (not sym.used and sym.kind == "var" and not self.repl
                    and not sym.name.startswith("_")):
                self._warn("W1001", "「%s」、一回も使ってないみたい" % sym.name,
                           sym.span)
        self.scope = scope.parent

    def _declare(self, name, type_, is_const, span, kind="var"):
        existing = self.scope.lookup_local(name)
        if existing is not None:
            if self.repl and self.scope is self.global_scope:
                self.scope.symbols.pop(name)      # REPL では上書きしてよい
                existing = None
            else:
                self._fail("E1002", "「%s」、この中にもういるみたい" % name, span)
        outer = self.scope.parent.lookup(name) if self.scope.parent else None
        if outer is not None and outer.kind == "var":
            self._warn("W1002", "「%s」、もういたみたい" % name, span)
        sym = Symbol(name, type_, is_const, span, kind)
        self.scope.declare(sym)
        return sym

    def _resolve_type_ref(self, ref):
        if ref is None:
            return None
        args = [self._resolve_type_ref(a) for a in ref.args]
        if ref.name in BUILTIN_TYPE_NAMES:
            return Type(ref.name, args, ref.optional)
        if ref.name in self.structs:
            t = self.structs[ref.name]
            return Type(t.name, args, ref.optional, t.info)
        self._fail("E1001", "「%s」って…なに？" % ref.name, ref.span)

    # -------------------------------------------------------- 走査

    def check(self, program):
        self._hoist(program.body)
        for stmt in program.body:
            self._stmt(stmt)
        if self.repl:
            self.repl_state.setdefault("types", {}).update(
                dict((n, s.type) for n, s in self.global_scope.symbols.items()
                     if s.span is not None or s.kind != "builtin"))
            self.repl_state.setdefault("structs", {}).update(self.structs)
            self.repl_state.setdefault("methods", {}).update(self.struct_methods)
            return program
        for sym in self.global_scope.symbols.values():
            if not sym.used and sym.kind == "var" and not sym.name.startswith("_"):
                self._warn("W1001", "「%s」、一回も使ってないみたい" % sym.name, sym.span)
        return program

    def _hoist(self, body):
        """関数と型はブロック内で前方参照できるようにする。"""
        for stmt in body:
            if stmt.kind == "TypeDecl":
                if stmt.name in BUILTIN_TYPE_NAMES:
                    self._fail("E1002",
                               "「%s」は最初からある型だから、別の名前がほしいみたい"
                               % stmt.name, stmt.span)
                fields = []
                self.structs[stmt.name] = struct_type(stmt.name, fields)
        for stmt in body:
            if stmt.kind == "TypeDecl":
                st = self.structs[stmt.name]
                seen = set()
                for f in stmt.fields:
                    if f.name in seen:
                        self._fail("E1002", "「%s」、この型にもういるみたい" % f.name,
                                   f.span)
                    seen.add(f.name)
                    st.info.append((f.name, self._resolve_type_ref(f.type)))
        for stmt in body:
            if stmt.kind != "FuncDecl":
                continue
            if stmt.recv is None:
                self._declare(stmt.name, self._func_signature(stmt), True,
                              stmt.span, "func")
            else:
                if stmt.recv not in self.structs:
                    self._fail("E1001", "「%s」って…なに？" % stmt.recv, stmt.span)
                self.struct_methods.setdefault(stmt.recv, {})[stmt.name] =                     self._func_signature(stmt)

    def _func_signature(self, decl):
        params = []
        min_args = 0
        max_args = 0
        variadic = False
        for p in decl.params:
            params.append(self._resolve_type_ref(p.type) or T_ANY)
            if p.variadic:
                variadic = True
            elif p.default is None:
                min_args += 1
            max_args += 1
        ret = self._resolve_type_ref(decl.ret_type) or T_ANY
        return func_type(params, ret, min_args, -1 if variadic else max_args)

    # -------------------------------------------------------- 文

    def _stmt(self, node):
        method = getattr(self, "_s_" + node.kind, None)
        if method is None:
            self._fail("E0001", "この文はまだ読めないみたい(%s)" % node.kind, node.span)
        return method(node)

    def _body(self, stmts, scope_kind="block"):
        self._push(scope_kind)
        self._hoist(stmts)
        reachable = True
        for stmt in stmts:
            if not reachable:
                self._warn("W1003", "ここ、たどりつかないみたい", stmt.span)
                reachable = True          # 1 回言えば十分
            self._stmt(stmt)
            if stmt.kind in ("Return", "Break", "Continue", "Throw"):
                reachable = False
        self._pop()

    def _s_VarDecl(self, node):
        declared = self._resolve_type_ref(node.type)
        actual = self._expr(node.init)
        if declared is not None and not assignable(declared, actual):
            self._fail("E2001", "ここに来るもの、なんか違うみたい…", node.init.span,
                       ["ほしかったもの : %r" % declared,
                        "きたもの       : %r" % actual])
        final = declared if declared is not None else actual
        if final.name == NULL and declared is None:
            final = T_ANY.opt()
            self._warn("W1004", "「%s」、なんの型かわからないみたい" % node.name, node.span)
        # 外へ出すものは、そのファイルの中で使われていなくても未使用ではない
        self._declare(node.name, final, node.is_const, node.span,
                      "pub" if node.is_pub else "var")

    def _s_DestructDecl(self, node):
        actual = self._expr(node.init)
        parts = actual.args if actual.name == TUPLE else ()
        for i, name in enumerate(node.names):
            t = parts[i] if i < len(parts) else T_ANY
            self._declare(name, t, node.is_const, node.span)

    def _s_FuncDecl(self, node):
        if node.recv is not None:
            if node.recv not in self.structs:
                self._fail("E1001", "「%s」って…なに？" % node.recv, node.span)
        elif self.scope.lookup_local(node.name) is None:
            self._declare(node.name, self._func_signature(node), True,
                          node.span, "func")
        sig = self._func_signature(node)
        self.func_stack.append(sig)
        self._push("func")
        if node.recv is not None:
            recv_t = self.structs[node.recv]
            self.scope.declare(Symbol("コレ", recv_t, True, node.span, "builtin"))
            for fname, ftype in recv_t.info:
                self.scope.declare(Symbol(fname, ftype, False, node.span, "builtin"))
        for p, ptype in zip(node.params, sig.info[0]):
            if p.default is not None:
                self._expr(p.default)
            actual = Type(LIST, (ptype,)) if p.variadic else ptype
            self.scope.declare(Symbol(p.name, actual, False, p.span, "param"))
        self._hoist(node.body)
        for stmt in node.body:
            self._stmt(stmt)
        self._pop()
        self.func_stack.pop()

    def _s_TypeDecl(self, node):
        return None          # _hoist で処理済み

    def _s_ImportDecl(self, node):
        if node.is_module and node.path not in STANDARD_MODULES:
            self._fail("E1004", "「%s」ってモジュール、知らないみたい" % node.path,
                       node.span)
        name = node.alias or (node.path if node.is_module
                              else _module_name(node.path))
        self._declare(name, T_ANY, True, node.span, "module")

    def _s_ExprStmt(self, node):
        self._expr(node.expr)

    def _s_If(self, node):
        for cond, body in node.branches:
            t = self._expr(cond)
            self._require_bool(t, cond.span)
            self._body(body)
        if node.else_body is not None:
            self._body(node.else_body)

    def _s_While(self, node):
        self._require_bool(self._expr(node.cond), node.cond.span)
        self.loop_depth += 1
        self._body(node.body)
        self.loop_depth -= 1

    def _s_For(self, node):
        it = self._expr(node.iterable)
        elem = T_ANY
        if it.name == LIST and it.args:
            elem = it.args[0]
        elif it.name == STRING:
            elem = T_STRING
        elif it.name not in (ANY, LIST, MAP, STRING, TUPLE):
            self._fail("E2002", "これ、ひとつずつ取り出せないみたい", node.iterable.span)
        self.loop_depth += 1
        self._push("loop")
        self.scope.declare(Symbol(node.var, elem, False, node.span, "param"))
        self._hoist(node.body)
        for stmt in node.body:
            self._stmt(stmt)
        self._pop()
        self.loop_depth -= 1

    def _s_Return(self, node):
        if not self.func_stack:
            self._fail("E1003", "ここでは ハァーッ できないみたい", node.span)
        expected = self.func_stack[-1].info[1]
        actual = self._expr(node.value) if node.value is not None else T_VOID
        if node.value is None and expected.name not in (VOID, ANY):
            self._fail("E2004", "戻すものがないみたい", node.span,
                       ["ほしかったもの : %r" % expected])
        if node.value is not None and not assignable(expected, actual):
            self._fail("E2004", "戻すもの、なんか違うみたい…", node.value.span,
                       ["ほしかったもの : %r" % expected,
                        "きたもの       : %r" % actual])

    def _s_Break(self, node):
        if self.loop_depth == 0:
            self._fail("E1003", "ここでは ムリッ できないみたい", node.span)

    def _s_Continue(self, node):
        if self.loop_depth == 0:
            self._fail("E1003", "ここでは イヤッ できないみたい", node.span)

    def _s_Try(self, node):
        self._body(node.body)
        self._push("catch")
        if node.catch_var:
            self.scope.declare(
                Symbol(node.catch_var, T_ANY, False, node.span, "param"))
        self._hoist(node.catch_body)
        for stmt in node.catch_body:
            self._stmt(stmt)
        self._pop()

    def _s_Match(self, node):
        subject = self._expr(node.subject)
        for pattern, body in node.cases:
            pt = self._expr(pattern)
            if not is_any(subject) and not is_any(pt) and not assignable(subject, pt):
                self._warn("W1003", "この ってこと？ は当たらないみたい", pattern.span)
            self._body(body)
        if node.default_body is not None:
            self._body(node.default_body)

    def _s_Throw(self, node):
        self._expr(node.value)

    def _require_bool(self, t, span):
        if not is_any(t) and t.name != BOOL:
            self._fail("E2001", "ここに来るもの、なんか違うみたい…", span,
                       ["ほしかったもの : %s" % BOOL, "きたもの       : %r" % t])

    # -------------------------------------------------------- 式

    def _expr(self, node):
        method = getattr(self, "_e_" + node.kind, None)
        if method is None:
            self._fail("E0001", "この式はまだ読めないみたい(%s)" % node.kind, node.span)
        return method(node)

    def _e_IntLit(self, node):
        return T_INT

    def _e_FloatLit(self, node):
        return T_FLOAT

    def _e_BoolLit(self, node):
        return T_BOOL

    def _e_NullLit(self, node):
        return T_NULL

    def _e_StrLit(self, node):
        for kind, value in node.parts:
            if kind == "expr":
                self._expr(value)
        return T_STRING

    def _e_SelfExpr(self, node):
        sym = self.scope.lookup("コレ")
        if sym is None:
            self._fail("E1003", "「コレ」はメソッドの中でしか使えないみたい", node.span)
        return sym.type

    def _e_Ident(self, node):
        sym = self.scope.lookup(node.name)
        if sym is None:
            self._fail("E1001", "「%s」って…なに？" % node.name, node.span)
        sym.used = True
        return sym.type

    def _e_ArrayLit(self, node):
        elem = None
        for item in node.items:
            t = self._expr(item)
            if elem is None:
                elem = t
            elif elem != t:
                elem = T_ANY
        return Type(LIST, (elem or T_ANY,))

    def _e_MapLit(self, node):
        key = None
        val = None
        for k, v in node.pairs:
            kt = self._expr(k)
            vt = self._expr(v)
            key = kt if key is None else (key if key == kt else T_ANY)
            val = vt if val is None else (val if val == vt else T_ANY)
        return Type(MAP, (key or T_STRING, val or T_ANY))

    def _e_TupleLit(self, node):
        return Type(TUPLE, tuple(self._expr(i) for i in node.items))

    def _e_OkExpr(self, node):
        return Type(RESULT, (self._expr(node.value), T_ANY))

    def _e_ErrExpr(self, node):
        return Type(RESULT, (T_ANY, self._expr(node.value)))

    def _e_Unary(self, node):
        t = self._expr(node.operand)
        if node.op == "!":
            self._require_bool(t, node.operand.span)
            return T_BOOL
        if is_any(t):
            return T_ANY
        if t.name not in NUMERIC:
            self._fail("E2002", "これにはマイナス付けられないみたい", node.span)
        return t

    def _e_Binary(self, node):
        lt = self._expr(node.left)
        rt = self._expr(node.right)
        op = node.op
        if op in ("==", "!="):
            return T_BOOL
        if is_any(lt) or is_any(rt):
            return T_BOOL if op in ("<", "<=", ">", ">=") else T_ANY
        if op in ("<", "<=", ">", ">="):
            if not (_both_numeric(lt, rt) or (lt.name == STRING == rt.name)):
                self._fail("E2002", "これ同士は比べられないみたい", node.span)
            return T_BOOL
        if op == "+":
            if lt.name == STRING and rt.name == STRING:
                return T_STRING
            if lt.name == LIST and rt.name == LIST:
                return lt if lt == rt else Type(LIST, (T_ANY,))
            if _both_numeric(lt, rt):
                return _numeric_result(lt, rt)
            self._fail("E2001", "ここに来るもの、なんか違うみたい…", node.right.span,
                       ["ほしかったもの : %r" % lt, "きたもの       : %r" % rt])
        if op == "%" and lt.name == STRING:
            return T_STRING
        if not _both_numeric(lt, rt):
            self._fail("E2002", "これ同士では計算できないみたい", node.span)
        return _numeric_result(lt, rt)

    def _e_Logical(self, node):
        self._require_bool(self._expr(node.left), node.left.span)
        self._require_bool(self._expr(node.right), node.right.span)
        return T_BOOL

    def _e_Coalesce(self, node):
        lt = self._expr(node.left)
        rt = self._expr(node.right)
        if is_any(lt):
            return rt
        return Type(lt.name, lt.args, False, lt.info)

    def _e_Assign(self, node):
        vt = self._expr(node.value)
        if node.target.kind == "Ident":
            sym = self.scope.lookup(node.target.name)
            if sym is None:
                self._fail("E1001", "「%s」って…なに？" % node.target.name,
                           node.target.span)
            if sym.is_const:
                self._fail("E1003", "「%s」は変えられないみたい" % node.target.name,
                           node.span)
            sym.used = True
            if node.op == "=" and not assignable(sym.type, vt):
                self._fail("E2001", "ここに来るもの、なんか違うみたい…",
                           node.value.span,
                           ["ほしかったもの : %r" % sym.type,
                            "きたもの       : %r" % vt])
            return sym.type
        self._expr(node.target)
        return vt

    def _e_Index(self, node):
        obj = self._expr(node.obj)
        idx = self._expr(node.index)
        if is_any(obj):
            return T_ANY
        if obj.name == LIST:
            if not is_any(idx) and idx.name != INT:
                self._fail("E2001", "ここに来るもの、なんか違うみたい…",
                           node.index.span,
                           ["ほしかったもの : %s" % INT, "きたもの       : %r" % idx])
            return obj.args[0] if obj.args else T_ANY
        if obj.name == MAP:
            return obj.args[1] if len(obj.args) > 1 else T_ANY
        if obj.name == STRING:
            return T_STRING
        if obj.name == TUPLE:
            return T_ANY
        self._fail("E2002", "これは [ ] で取り出せないみたい", node.span)

    def _e_Member(self, node):
        obj = self._expr(node.obj)
        name = node.name
        if is_any(obj):
            return T_ANY
        if obj.optional and not node.optional:
            self._fail("E3003", "「……」かもしれないみたい(「?.」がいるかも)",
                       node.span)
        table = {LIST: LIST_METHODS, MAP: MAP_METHODS,
                 STRING: STRING_METHODS, RESULT: RESULT_METHODS}.get(obj.name)
        if table is not None:
            if name in table:
                return func_type([], table[name](obj), 0, -1)
            if name in _runtime_members(obj.name):
                # 実行時には在るが、ここの表に戻り値型が無いだけ。
                # 2 つの表がずれても弾いてしまわないための逃がし。
                return func_type([], T_ANY, 0, -1)
            self._fail("E2005", "「%s」って…なに？" % name, node.span)
        if obj.name in self.structs:
            for fname, ftype in (obj.info or ()):
                if fname == name:
                    return ftype.opt() if node.optional else ftype
            method = self.struct_methods.get(obj.name, {}).get(name)
            if method is not None:
                return method
            self._fail("E1001", "「%s」って…なに？" % name, node.span)
        return T_ANY

    def _e_Call(self, node):
        if node.callee.kind == "Ident" and node.callee.name in self.structs:
            return self._struct_construction(node)
        from .compiler import named_argument_names
        names = named_argument_names(node.args)
        if names is False:
            self._fail("E0001", "名前つきと順番、混ぜないでほしいみたい",
                       node.span)
        callee = self._expr(node.callee)
        if names is not None:
            # 生成先が実行時にしか分からない名前つき生成。値だけ見ておく。
            for arg in node.args:
                self._expr(arg.value)
            return T_ANY
        for arg in node.args:
            self._expr(arg)
        if is_any(callee):
            return T_ANY
        if callee.name != FUNC:
            self._fail("E2002", "これは呼べないみたい", node.callee.span)
        params, ret, min_args, max_args = callee.info
        n = len(node.args)
        if n < min_args or (max_args >= 0 and n > max_args):
            want = ("ン・%s 以上" % _urayaha_num(min_args)) if max_args < 0 \
                else ("ン・" + _urayaha_num(min_args) if min_args == max_args
                      else "ン・%s 〜 ン・%s" % (_urayaha_num(min_args),
                                              _urayaha_num(max_args)))
            self._fail("E2003", "もうちょっとほしいみたい" if n < min_args
                       else "そんなにいらないみたい", node.span,
                       ["ほしい : %s" % want, "きた   : ン・%s" % _urayaha_num(n)])
        return ret

    def _struct_construction(self, node):
        """§38 の生成式。`名前 = 値` は代入ではなくフィールド指定として読む。"""
        st = self.structs[node.callee.name]
        field_types = dict(st.info)
        named = {}
        positional = []
        for arg in node.args:
            if (arg.kind == "Assign" and arg.op == "="
                    and arg.target.kind == "Ident"):
                named[arg.target.name] = arg.value
            else:
                positional.append(arg)
        if named and positional:
            self._fail("E0001", "名前つきと順番、混ぜないでほしいみたい", node.span)
        for name, value in named.items():
            if name not in field_types:
                self._fail("E1001", "「%s」って…なに？" % name, value.span)
            actual = self._expr(value)
            if not assignable(field_types[name], actual):
                self._fail("E2001", "ここに来るもの、なんか違うみたい…", value.span,
                           ["ほしかったもの : %r" % field_types[name],
                            "きたもの       : %r" % actual])
        if named:
            missing = [f for f, _ in st.info if f not in named]
            if missing:
                self._fail("E2003", "「%s」がまだ来てないみたい" % missing[0],
                           node.span)
        else:
            if len(positional) > len(st.info):
                self._fail("E2003", "そんなにいらないみたい", node.span)
            for value, (fname, ftype) in zip(positional, st.info):
                actual = self._expr(value)
                if not assignable(ftype, actual):
                    self._fail("E2001", "ここに来るもの、なんか違うみたい…",
                               value.span,
                               ["ほしかったもの : %r" % ftype,
                                "きたもの       : %r" % actual])
        return Type(st.name, (), False, st.info)

    def _e_Lambda(self, node):
        params = [self._resolve_type_ref(p.type) or T_ANY for p in node.params]
        min_args = len([p for p in node.params
                        if p.default is None and not p.variadic])
        variadic = any(p.variadic for p in node.params)
        self._push("func")
        sig = func_type(params, T_ANY, min_args,
                        -1 if variadic else len(node.params))
        self.func_stack.append(sig)
        for p, pt in zip(node.params, params):
            self.scope.declare(Symbol(p.name, pt, False, p.span, "param"))
        if node.is_expr:
            ret = self._expr(node.body)
            sig.info = (params, ret, min_args, sig.info[3])
        else:
            self._hoist(node.body)
            for stmt in node.body:
                self._stmt(stmt)
        self.func_stack.pop()
        self._pop()
        return sig


def _runtime_members(type_name):
    """VM 側が実際に持っているメンバ名。表のずれで誤検知しないために見る。"""
    from . import stdlib
    return {LIST: stdlib.LIST_MEMBERS, MAP: stdlib.MAP_MEMBERS,
            STRING: stdlib.STRING_MEMBERS,
            RESULT: stdlib.RESULT_MEMBERS}.get(type_name, {})


def _both_numeric(a, b):
    return a.name in NUMERIC and b.name in NUMERIC


def _numeric_result(a, b):
    return T_FLOAT if FLOAT in (a.name, b.name) else T_INT


def _urayaha_num(n):
    from .lexer import to_urayaha_digits
    return to_urayaha_digits(n)


def _module_name(path):
    base = path.replace("\\", "/").split("/")[-1]
    return base[:-4] if base.endswith(".ura") else base


def check(program, filename, bag, builtins, return_checker=False,
          repl_state=None):
    checker = Checker(filename, bag, builtins, repl_state)
    checker.check(program)
    return checker if return_checker else program
