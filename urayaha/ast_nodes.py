# -*- coding: utf-8 -*-
"""Urayaha の AST ノード定義(仕様 §83)。

ノードは `kind` 文字列で識別し、各パスは kind でディスパッチする。
全ノードは診断用に `span` を持つ。
"""


class Node(object):
    _fields = ()
    kind = "Node"

    def __init__(self, span, *args):
        self.span = span
        if len(args) != len(self._fields):
            raise TypeError("%s は %d 個の引数がいる (%d 個来た)"
                            % (self.kind, len(self._fields), len(args)))
        for name, value in zip(self._fields, args):
            setattr(self, name, value)

    def __repr__(self):
        inner = ", ".join("%s=%r" % (f, getattr(self, f)) for f in self._fields)
        return "%s(%s)" % (self.kind, inner)


def _node(name, fields=""):
    return type(name, (Node,), {"_fields": tuple(fields.split()), "kind": name})


# ------------------------------------------------------------------ 式

IntLit = _node("IntLit", "value")
FloatLit = _node("FloatLit", "value")
StrLit = _node("StrLit", "parts")          # [("str", s) | ("expr", Node)]
BoolLit = _node("BoolLit", "value")
NullLit = _node("NullLit")
ArrayLit = _node("ArrayLit", "items")
MapLit = _node("MapLit", "pairs")          # [(key_node, value_node)]
TupleLit = _node("TupleLit", "items")
Ident = _node("Ident", "name")
SelfExpr = _node("SelfExpr")
Unary = _node("Unary", "op operand")
Binary = _node("Binary", "op left right")
Logical = _node("Logical", "op left right")
Coalesce = _node("Coalesce", "left right")
Assign = _node("Assign", "target op value")
Call = _node("Call", "callee args")
Index = _node("Index", "obj index")
Member = _node("Member", "obj name optional")
Lambda = _node("Lambda", "params body is_expr")
OkExpr = _node("OkExpr", "value")
ErrExpr = _node("ErrExpr", "value")

# ------------------------------------------------------------------ 文

Param = _node("Param", "name type default variadic")
Field = _node("Field", "name type")

VarDecl = _node("VarDecl", "name type init is_const is_pub")
DestructDecl = _node("DestructDecl", "names init is_const")
FuncDecl = _node("FuncDecl", "name recv params ret_type body is_pub")
TypeDecl = _node("TypeDecl", "name fields is_pub")
ImportDecl = _node("ImportDecl", "path alias is_module")
ExprStmt = _node("ExprStmt", "expr")
PrintStmt = _node("PrintStmt", "args newline")
If = _node("If", "branches else_body")     # branches: [(cond, [stmt])]
While = _node("While", "cond body")
For = _node("For", "iterable var body")
Return = _node("Return", "value")
Break = _node("Break")
Continue = _node("Continue")
Try = _node("Try", "body catch_var catch_body")
Match = _node("Match", "subject cases default_body")
Throw = _node("Throw", "value")
Program = _node("Program", "body")

# ------------------------------------------------------------------ 型注釈

TypeRef = _node("TypeRef", "name args optional")   # ムレッ[プルッ]? など
