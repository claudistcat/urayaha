# -*- coding: utf-8 -*-
"""AST -> バイトコード(仕様 §82, §84)。

ジョーク性は表面構文だけの話なので、IR と VM 命令は普通の英語名にしてある。
ローカル変数はすべて Cell に入れる。こうするとクロージャの捕捉が
「親フレームの Cell をそのまま持つ」だけになり、捕捉解析が不要になる。
"""

from . import ast_nodes as A
from .errors import Diagnostic, UrayahaError

# ------------------------------------------------------------------ 命令

(LOAD_CONST, LOAD_LOCAL, STORE_LOCAL, LOAD_UPVAL, STORE_UPVAL,
 LOAD_GLOBAL, STORE_GLOBAL, DEFINE_GLOBAL, POP, DUP,
 ADD, SUB, MUL, DIV, MOD, NEG, NOT,
 CMP_EQ, CMP_NE, CMP_LT, CMP_LE, CMP_GT, CMP_GE,
 JUMP, JUMP_IF_FALSE, JUMP_IF_TRUE, JUMP_IF_NULL,
 CALL, RETURN, MAKE_LIST, MAKE_MAP, MAKE_TUPLE,
 GET_INDEX, SET_INDEX, GET_MEMBER, SET_MEMBER,
 MAKE_CLOSURE, MAKE_STRUCT, CONCAT,
 ITER_NEW, ITER_NEXT, SETUP_TRY, POP_TRY, THROW,
 MAKE_OK, MAKE_ERR, UNPACK, JUMP_IF_SET, CALL_KW) = range(49)

OP_NAMES = {
    LOAD_CONST: "LOAD_CONST", LOAD_LOCAL: "LOAD_LOCAL",
    STORE_LOCAL: "STORE_LOCAL", LOAD_UPVAL: "LOAD_UPVAL",
    STORE_UPVAL: "STORE_UPVAL", LOAD_GLOBAL: "LOAD_GLOBAL",
    STORE_GLOBAL: "STORE_GLOBAL", DEFINE_GLOBAL: "DEFINE_GLOBAL",
    POP: "POP", DUP: "DUP", ADD: "ADD", SUB: "SUB", MUL: "MUL",
    DIV: "DIV", MOD: "MOD", NEG: "NEG", NOT: "NOT",
    CMP_EQ: "CMP_EQ", CMP_NE: "CMP_NE", CMP_LT: "CMP_LT",
    CMP_LE: "CMP_LE", CMP_GT: "CMP_GT", CMP_GE: "CMP_GE",
    JUMP: "JUMP", JUMP_IF_FALSE: "JUMP_IF_FALSE",
    JUMP_IF_TRUE: "JUMP_IF_TRUE", JUMP_IF_NULL: "JUMP_IF_NULL",
    CALL: "CALL", RETURN: "RETURN", MAKE_LIST: "MAKE_LIST",
    MAKE_MAP: "MAKE_MAP", MAKE_TUPLE: "MAKE_TUPLE",
    GET_INDEX: "GET_INDEX", SET_INDEX: "SET_INDEX",
    GET_MEMBER: "GET_MEMBER", SET_MEMBER: "SET_MEMBER",
    MAKE_CLOSURE: "MAKE_CLOSURE", MAKE_STRUCT: "MAKE_STRUCT",
    CONCAT: "CONCAT", ITER_NEW: "ITER_NEW", ITER_NEXT: "ITER_NEXT",
    SETUP_TRY: "SETUP_TRY", POP_TRY: "POP_TRY", THROW: "THROW",
    MAKE_OK: "MAKE_OK", MAKE_ERR: "MAKE_ERR", UNPACK: "UNPACK",
    JUMP_IF_SET: "JUMP_IF_SET", CALL_KW: "CALL_KW",
}

BINARY_OPS = {"+": ADD, "-": SUB, "*": MUL, "/": DIV, "%": MOD,
              "==": CMP_EQ, "!=": CMP_NE, "<": CMP_LT, "<=": CMP_LE,
              ">": CMP_GT, ">=": CMP_GE}


class FuncProto(object):
    __slots__ = ("name", "code", "consts", "spans", "params", "n_locals",
                 "upvalues", "is_method", "variadic_at", "min_args")

    def __init__(self, name):
        self.name = name
        self.code = []          # [op, arg]
        self.spans = []
        self.consts = []
        self.params = []        # 引数名
        self.n_locals = 0
        self.upvalues = []      # (is_local_of_parent, index)
        self.is_method = False
        self.variadic_at = -1
        self.min_args = 0       # 既定値も可変長も無い引数の数

    def __repr__(self):
        return "FuncProto(%s)" % self.name


class StructInfo(object):
    __slots__ = ("name", "fields", "methods")

    def __init__(self, name, fields):
        self.name = name
        self.fields = fields          # [名前]
        self.methods = {}             # 名前 -> FuncProto


class _Local(object):
    __slots__ = ("name", "depth", "slot")

    def __init__(self, name, depth, slot):
        self.name = name
        self.depth = depth
        self.slot = slot


class FunctionCompiler(object):
    def __init__(self, name, enclosing=None):
        self.proto = FuncProto(name)
        self.enclosing = enclosing
        self.locals = []
        self.depth = 0
        self.loop_stack = []


class Compiler(object):
    def __init__(self, filename, known_structs=None):
        self.file = filename
        self.structs = dict(known_structs or {})
        self.fc = FunctionCompiler("<main>")
        self.pub_names = set()
        self.current_recv = None

    # -------------------------------------------------------- 出力

    def _emit(self, op, arg=None, span=None):
        self.fc.proto.code.append([op, arg])
        self.fc.proto.spans.append(span)
        return len(self.fc.proto.code) - 1

    def _const(self, value):
        consts = self.fc.proto.consts
        for i, existing in enumerate(consts):
            if type(existing) is type(value) and existing == value:
                return i
        consts.append(value)
        return len(consts) - 1

    def _load_const(self, value, span=None):
        self._emit(LOAD_CONST, self._const(value), span)

    def _patch(self, at, target=None):
        self.fc.proto.code[at][1] = (len(self.fc.proto.code)
                                     if target is None else target)

    def _fail(self, code, message, span):
        raise UrayahaError(Diagnostic(code, message, span))

    # -------------------------------------------------------- スコープ

    def _begin_scope(self):
        self.fc.depth += 1

    def _end_scope(self):
        fc = self.fc
        fc.depth -= 1
        while fc.locals and fc.locals[-1].depth > fc.depth:
            fc.locals.pop()

    def _declare_local(self, name):
        fc = self.fc
        slot = fc.proto.n_locals
        fc.proto.n_locals += 1
        fc.locals.append(_Local(name, fc.depth, slot))
        return slot

    def _resolve_local(self, fc, name):
        for local in reversed(fc.locals):
            if local.name == name:
                return local.slot
        return -1

    def _resolve_upvalue(self, fc, name):
        if fc.enclosing is None:
            return -1
        slot = self._resolve_local(fc.enclosing, name)
        if slot >= 0:
            return self._add_upvalue(fc, True, slot)
        upper = self._resolve_upvalue(fc.enclosing, name)
        if upper >= 0:
            return self._add_upvalue(fc, False, upper)
        return -1

    def _add_upvalue(self, fc, is_local, index):
        for i, (l, idx) in enumerate(fc.proto.upvalues):
            if l == is_local and idx == index:
                return i
        fc.proto.upvalues.append((is_local, index))
        return len(fc.proto.upvalues) - 1

    # -------------------------------------------------------- エントリ

    def compile_program(self, program):
        self._hoist_structs(program.body)
        for stmt in program.body:
            self._stmt(stmt)
        self._load_const(None)
        self._emit(RETURN)
        return self.fc.proto, self.structs, self.pub_names

    def _hoist_structs(self, body):
        for stmt in body:
            if stmt.kind == "TypeDecl":
                self.structs[stmt.name] = StructInfo(
                    stmt.name, [f.name for f in stmt.fields])
                if stmt.is_pub:
                    self.pub_names.add(stmt.name)

    # -------------------------------------------------------- 文

    def _stmt(self, node):
        getattr(self, "_s_" + node.kind)(node)

    def _block(self, stmts):
        self._begin_scope()
        for stmt in stmts:
            self._stmt(stmt)
        self._end_scope()

    def _is_global_scope(self):
        return self.fc.enclosing is None and self.fc.depth == 0

    def _define(self, name, span):
        if self._is_global_scope():
            self._emit(DEFINE_GLOBAL, name, span)
        else:
            slot = self._declare_local(name)
            self._emit(STORE_LOCAL, slot, span)

    def _s_VarDecl(self, node):
        self._expr(node.init)
        self._define(node.name, node.span)
        if node.is_pub:
            self.pub_names.add(node.name)

    def _s_DestructDecl(self, node):
        self._expr(node.init)
        self._emit(UNPACK, len(node.names), node.span)
        # UNPACK は先頭から積むので、取り出しは後ろの名前から
        for name in reversed(node.names):
            self._define(name, node.span)

    def _s_FuncDecl(self, node):
        if node.recv is not None and node.recv not in self.structs:
            self._fail("E1001", "「%s」って…なに？" % node.recv, node.span)
        saved_recv = self.current_recv
        if node.recv is not None:
            self.current_recv = node.recv
        proto = self._compile_function(node.name, node.params, node.body,
                                       False, node.recv is not None)
        self.current_recv = saved_recv
        if node.recv is not None:
            self.structs[node.recv].methods[node.name] = proto
            return
        self._emit(MAKE_CLOSURE, proto, node.span)
        self._define(node.name, node.span)
        if node.is_pub:
            self.pub_names.add(node.name)

    def _compile_function(self, name, params, body, is_expr_body, is_method):
        fc = FunctionCompiler(name, self.fc)
        outer = self.fc
        self.fc = fc
        fc.proto.is_method = is_method
        if is_method:
            self._declare_local("コレ")
        param_slots = []
        for i, p in enumerate(params):
            fc.proto.params.append(p.name)
            param_slots.append(self._declare_local(p.name))
            if p.variadic:
                fc.proto.variadic_at = i
            elif p.default is None:
                fc.proto.min_args += 1
        # 既定値は関数本体の先頭で埋める。渡されなかった引数には VM が
        # MISSING 番兵を入れてくるので、それを見て評価する。
        # 本体スコープで組み立てるので、既定値から先行する引数を参照できる。
        for i, p in enumerate(params):
            if p.default is None:
                continue
            self._emit(LOAD_LOCAL, param_slots[i], p.span)
            skip = self._emit(JUMP_IF_SET, None, p.span)
            self._expr(p.default)
            self._emit(STORE_LOCAL, param_slots[i], p.span)
            self._patch(skip)
        if is_expr_body:
            self._expr(body)
            self._emit(RETURN)
        else:
            for stmt in body:
                self._stmt(stmt)
            self._load_const(None)
            self._emit(RETURN)
        self.fc = outer
        return fc.proto

    def _s_TypeDecl(self, node):
        return None

    def _s_ImportDecl(self, node):
        from .checker import _module_name
        name = node.alias or (node.path if node.is_module
                              else _module_name(node.path))
        self._emit(LOAD_GLOBAL, "__これって__", node.span)
        self._load_const(node.path, node.span)
        self._load_const(node.is_module, node.span)
        self._emit(CALL, 2, node.span)
        self._define(name, node.span)


    def _s_ExprStmt(self, node):
        self._expr(node.expr)
        self._emit(POP, None, node.span)

    def _s_If(self, node):
        end_jumps = []
        for cond, body in node.branches:
            self._expr(cond)
            skip = self._emit(JUMP_IF_FALSE, None, cond.span)
            self._block(body)
            end_jumps.append(self._emit(JUMP, None, node.span))
            self._patch(skip)
        if node.else_body is not None:
            self._block(node.else_body)
        for j in end_jumps:
            self._patch(j)

    def _s_While(self, node):
        start = len(self.fc.proto.code)
        self._expr(node.cond)
        exit_jump = self._emit(JUMP_IF_FALSE, None, node.cond.span)
        self.fc.loop_stack.append({"start": start, "breaks": [], "continues": []})
        self._block(node.body)
        loop = self.fc.loop_stack.pop()
        self._emit(JUMP, start, node.span)
        self._patch(exit_jump)
        for j in loop["breaks"]:
            self._patch(j)
        for j in loop["continues"]:
            self._patch(j, start)

    def _s_For(self, node):
        self._expr(node.iterable)
        self._emit(ITER_NEW, None, node.span)
        self._begin_scope()
        var_slot = self._declare_local(node.var)
        start = len(self.fc.proto.code)
        exit_jump = self._emit(ITER_NEXT, None, node.span)
        self._emit(STORE_LOCAL, var_slot, node.span)
        self.fc.loop_stack.append({"start": start, "breaks": [], "continues": []})
        self._block(node.body)
        loop = self.fc.loop_stack.pop()
        self._emit(JUMP, start, node.span)
        self._patch(exit_jump)
        for j in loop["breaks"]:
            self._patch(j)
        for j in loop["continues"]:
            self._patch(j, start)
        self._end_scope()
        self._emit(POP, None, node.span)          # イテレータを捨てる

    def _s_Return(self, node):
        if node.value is None:
            self._load_const(None, node.span)
        else:
            self._expr(node.value)
        self._emit(RETURN, None, node.span)

    def _s_Break(self, node):
        if not self.fc.loop_stack:
            self._fail("E1003", "ここでは ムリッ できないみたい", node.span)
        self.fc.loop_stack[-1]["breaks"].append(
            self._emit(JUMP, None, node.span))

    def _s_Continue(self, node):
        if not self.fc.loop_stack:
            self._fail("E1003", "ここでは イヤッ できないみたい", node.span)
        self.fc.loop_stack[-1]["continues"].append(
            self._emit(JUMP, None, node.span))

    def _s_Try(self, node):
        setup = self._emit(SETUP_TRY, None, node.span)
        self._block(node.body)
        self._emit(POP_TRY, None, node.span)
        done = self._emit(JUMP, None, node.span)
        self._patch(setup)
        self._begin_scope()
        if node.catch_var:
            slot = self._declare_local(node.catch_var)
            self._emit(STORE_LOCAL, slot, node.span)
        else:
            self._emit(POP, None, node.span)
        for stmt in node.catch_body:
            self._stmt(stmt)
        self._end_scope()
        self._patch(done)

    def _s_Match(self, node):
        self._expr(node.subject)
        end_jumps = []
        for pattern, body in node.cases:
            self._emit(DUP, None, pattern.span)
            self._expr(pattern)
            self._emit(CMP_EQ, None, pattern.span)
            skip = self._emit(JUMP_IF_FALSE, None, pattern.span)
            self._emit(POP, None, pattern.span)          # subject を捨てる
            self._block(body)
            end_jumps.append(self._emit(JUMP, None, pattern.span))
            self._patch(skip)
        self._emit(POP, None, node.span)
        if node.default_body is not None:
            self._block(node.default_body)
        for j in end_jumps:
            self._patch(j)

    def _s_Throw(self, node):
        self._expr(node.value)
        self._emit(THROW, None, node.span)

    # -------------------------------------------------------- 式

    def _expr(self, node):
        getattr(self, "_e_" + node.kind)(node)

    def _e_IntLit(self, node):
        self._load_const(node.value, node.span)

    def _e_FloatLit(self, node):
        self._load_const(node.value, node.span)

    def _e_BoolLit(self, node):
        self._load_const(node.value, node.span)

    def _e_NullLit(self, node):
        self._load_const(None, node.span)

    def _e_StrLit(self, node):
        if len(node.parts) == 1 and node.parts[0][0] == "str":
            self._load_const(node.parts[0][1], node.span)
            return
        for kind, value in node.parts:
            if kind == "str":
                self._load_const(value, node.span)
            else:
                self._expr(value)
        self._emit(CONCAT, len(node.parts), node.span)

    def _e_ArrayLit(self, node):
        for item in node.items:
            self._expr(item)
        self._emit(MAKE_LIST, len(node.items), node.span)

    def _e_MapLit(self, node):
        for key, value in node.pairs:
            self._expr(key)
            self._expr(value)
        self._emit(MAKE_MAP, len(node.pairs), node.span)

    def _e_TupleLit(self, node):
        for item in node.items:
            self._expr(item)
        self._emit(MAKE_TUPLE, len(node.items), node.span)

    def _e_OkExpr(self, node):
        self._expr(node.value)
        self._emit(MAKE_OK, None, node.span)

    def _e_ErrExpr(self, node):
        self._expr(node.value)
        self._emit(MAKE_ERR, None, node.span)

    def _e_SelfExpr(self, node):
        self._load_name("コレ", node.span)

    def _e_Ident(self, node):
        self._load_name(node.name, node.span)

    def _field_of_receiver(self, name):
        """メソッドの中ではフィールド名をそのまま書ける(§39)。"""
        if self.current_recv is None or name == "コレ":
            return False
        info = self.structs.get(self.current_recv)
        return info is not None and name in info.fields

    def _load_name(self, name, span):
        slot = self._resolve_local(self.fc, name)
        if slot >= 0:
            self._emit(LOAD_LOCAL, slot, span)
            return
        up = self._resolve_upvalue(self.fc, name)
        if up >= 0:
            self._emit(LOAD_UPVAL, up, span)
            return
        if self._field_of_receiver(name):
            self._load_name("コレ", span)
            self._emit(GET_MEMBER, name, span)
            return
        self._emit(LOAD_GLOBAL, name, span)

    def _store_name(self, name, span):
        slot = self._resolve_local(self.fc, name)
        if slot >= 0:
            self._emit(STORE_LOCAL, slot, span)
            return
        up = self._resolve_upvalue(self.fc, name)
        if up >= 0:
            self._emit(STORE_UPVAL, up, span)
            return
        if self._field_of_receiver(name):
            self._load_name("コレ", span)
            self._emit(SET_MEMBER, name, span)
            self._emit(POP, None, span)
            return
        self._emit(STORE_GLOBAL, name, span)

    def _e_Unary(self, node):
        self._expr(node.operand)
        self._emit(NOT if node.op == "!" else NEG, None, node.span)

    def _e_Binary(self, node):
        self._expr(node.left)
        self._expr(node.right)
        self._emit(BINARY_OPS[node.op], None, node.span)

    def _e_Logical(self, node):
        self._expr(node.left)
        self._emit(DUP, None, node.span)
        jump = self._emit(JUMP_IF_FALSE if node.op == "&&" else JUMP_IF_TRUE,
                          None, node.span)
        self._emit(POP, None, node.span)
        self._expr(node.right)
        self._patch(jump)

    def _e_Coalesce(self, node):
        self._expr(node.left)
        self._emit(DUP, None, node.span)
        take_right = self._emit(JUMP_IF_NULL, None, node.span)
        done = self._emit(JUMP, None, node.span)
        self._patch(take_right)
        self._emit(POP, None, node.span)
        self._expr(node.right)
        self._patch(done)

    def _e_Assign(self, node):
        target = node.target
        if node.op != "=":
            binop = BINARY_OPS[node.op[0]]
            if target.kind == "Ident":
                self._load_name(target.name, node.span)
                self._expr(node.value)
                self._emit(binop, None, node.span)
                self._emit(DUP, None, node.span)
                self._store_name(target.name, node.span)
                return
            self._expr(target)
            self._expr(node.value)
            self._emit(binop, None, node.span)
            self._assign_to(target, node.span)
            return
        self._expr(node.value)
        self._assign_to(target, node.span)

    def _assign_to(self, target, span):
        """スタックトップの値を target へ書き、値は残す。"""
        if target.kind == "Ident":
            self._emit(DUP, None, span)
            self._store_name(target.name, span)
            return
        if target.kind == "Index":
            self._expr(target.obj)
            self._expr(target.index)
            self._emit(SET_INDEX, None, span)
            return
        if target.kind == "Member":
            self._expr(target.obj)
            self._emit(SET_MEMBER, target.name, span)
            return
        self._fail("E0001", "ここには代入できないみたい", span)

    def _e_Index(self, node):
        self._expr(node.obj)
        self._expr(node.index)
        self._emit(GET_INDEX, None, node.span)

    def _e_Member(self, node):
        self._expr(node.obj)
        if node.optional:
            self._emit(DUP, None, node.span)
            is_null = self._emit(JUMP_IF_NULL, None, node.span)
            self._emit(GET_MEMBER, node.name, node.span)
            done = self._emit(JUMP, None, node.span)
            self._patch(is_null)
            self._patch(done)
            return
        self._emit(GET_MEMBER, node.name, node.span)

    def _e_Call(self, node):
        if node.callee.kind == "Ident" and node.callee.name in self.structs:
            self._struct_literal(node)
            return
        names = named_argument_names(node.args)
        if names is False:
            self._fail("E0001", "名前つきと順番、混ぜないでほしいみたい",
                       node.span)
        self._expr(node.callee)
        if names is None:
            for arg in node.args:
                self._expr(arg)
            self._emit(CALL, len(node.args), node.span)
            return
        # 別モジュールから来た型など、生成先が実行時にしか分からない場合。
        for arg in node.args:
            self._expr(arg.value)
        self._emit(CALL_KW, tuple(names), node.span)

    def _struct_literal(self, node):
        info = self.structs[node.callee.name]
        named = {}
        positional = []
        for arg in node.args:
            if arg.kind == "Assign" and arg.target.kind == "Ident" and arg.op == "=":
                named[arg.target.name] = arg.value
            else:
                positional.append(arg)
        if named and positional:
            self._fail("E0001", "名前つきと順番、混ぜないでほしいみたい", node.span)
        for i, field in enumerate(info.fields):
            if named:
                if field not in named:
                    self._fail("E2003", "「%s」がまだ来てないみたい" % field, node.span)
                self._expr(named[field])
            elif i < len(positional):
                self._expr(positional[i])
            else:
                self._load_const(None, node.span)
        if named:
            unknown = [k for k in named if k not in info.fields]
            if unknown:
                self._fail("E1001", "「%s」って…なに？" % unknown[0], node.span)
        elif len(positional) > len(info.fields):
            self._fail("E2003", "そんなにいらないみたい", node.span)
        self._emit(MAKE_STRUCT, info.name, node.span)

    def _e_Lambda(self, node):
        proto = self._compile_function("<フゥン>", node.params, node.body,
                                       node.is_expr, False)
        self._emit(MAKE_CLOSURE, proto, node.span)


def named_argument_names(args):
    """全部が `名前 = 値` なら名前の並び、全部そうでなければ None、混在は False。"""
    if not args:
        return None
    named = []
    for arg in args:
        if (arg.kind == "Assign" and arg.op == "="
                and arg.target.kind == "Ident"):
            named.append(arg.target.name)
    if not named:
        return None
    if len(named) != len(args):
        return False
    return named


def compile_program(program, filename, known_structs=None):
    return Compiler(filename, known_structs).compile_program(program)


def disassemble(proto, indent=0):
    """`urayaha build --dump` 用。"""
    pad = "  " * indent
    out = ["%s== %s ==" % (pad, proto.name)]
    for i, (op, arg) in enumerate(proto.code):
        if op == MAKE_CLOSURE:
            out.append("%s%4d  %-16s <%s>" % (pad, i, OP_NAMES[op], arg.name))
        elif op == LOAD_CONST:
            out.append("%s%4d  %-16s %r" % (pad, i, OP_NAMES[op],
                                            proto.consts[arg]))
        elif arg is None:
            out.append("%s%4d  %s" % (pad, i, OP_NAMES[op]))
        else:
            out.append("%s%4d  %-16s %s" % (pad, i, OP_NAMES[op], arg))
    for op, arg in proto.code:
        if op == MAKE_CLOSURE:
            out.append("")
            out.append(disassemble(arg, indent + 1))
    return "\n".join(out)
