# -*- coding: utf-8 -*-
"""Urayaha VM(仕様 §82, §84)。

表面構文のジョーク性はここまで持ち込まない。普通のスタックマシン。
ローカルはすべて Cell 経由なので、クロージャは親フレームの Cell を持つだけ。
"""

from .errors import UrayahaRuntimeError, Span
from . import compiler as C


class Cell(object):
    __slots__ = ("v",)

    def __init__(self, v=None):
        self.v = v


class _Missing(object):
    """引数が渡されなかったことを表す番兵。"""
    __slots__ = ()

    def __repr__(self):
        return "<まだ来てない>"


MISSING = _Missing()


class Closure(object):
    __slots__ = ("proto", "upvalues")

    def __init__(self, proto, upvalues):
        self.proto = proto
        self.upvalues = upvalues


class NativeFunc(object):
    __slots__ = ("name", "fn", "min_args", "max_args")

    def __init__(self, name, fn, min_args=0, max_args=-1):
        self.name = name
        self.fn = fn
        self.min_args = min_args
        self.max_args = max_args


class BoundMethod(object):
    __slots__ = ("recv", "func")

    def __init__(self, recv, func):
        self.recv = recv
        self.func = func


class StructValue(object):
    __slots__ = ("type_name", "fields", "info")

    def __init__(self, type_name, fields, info):
        self.type_name = type_name
        self.fields = fields          # dict
        self.info = info              # StructInfo


class ResultValue(object):
    __slots__ = ("is_ok", "value")

    def __init__(self, is_ok, value):
        self.is_ok = is_ok
        self.value = value


class Namespace(object):
    __slots__ = ("name", "members")

    def __init__(self, name, members=None):
        self.name = name
        self.members = members or {}


class Module(object):
    __slots__ = ("name", "exports")

    def __init__(self, name, exports):
        self.name = name
        self.exports = exports


class Frame(object):
    __slots__ = ("proto", "upvalues", "locals", "stack", "ip", "handlers")

    def __init__(self, proto, upvalues):
        self.proto = proto
        self.upvalues = upvalues
        self.locals = [Cell() for _ in range(proto.n_locals)]
        self.stack = []
        self.ip = 0
        self.handlers = []


# ------------------------------------------------------------------ 表示

def urayaha_repr(v, human=False):
    from .lexer import to_urayaha_digits
    if v is None:
        return "……"
    if v is True:
        return "ヤー"
    if v is False:
        return "イヤ"
    if isinstance(v, int):
        return str(v) if human else "ン・" + to_urayaha_digits(v)
    if isinstance(v, float):
        if human:
            return repr(v)
        whole = int(v)
        frac = abs(v - whole)
        out = "ン・" + to_urayaha_digits(whole)
        if frac:
            digits = []
            for _ in range(6):
                frac *= 4
                d = int(frac)
                digits.append("ンプルャ"[d])
                frac -= d
                if not frac:
                    break
            out += "." + "".join(digits)
        return out
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return "[" + ", ".join(urayaha_repr(x, human) for x in v) + "]"
    if isinstance(v, tuple):
        return "(" + ", ".join(urayaha_repr(x, human) for x in v) + ")"
    if isinstance(v, dict):
        return "{" + ", ".join("%s: %s" % (urayaha_repr(k, human),
                                           urayaha_repr(x, human))
                               for k, x in v.items()) + "}"
    if isinstance(v, ResultValue):
        return ("ヤッター(%s)" if v.is_ok else "ワァ…(%s)") % urayaha_repr(v.value, human)
    if isinstance(v, StructValue):
        inner = ", ".join("%s = %s" % (k, urayaha_repr(x, human))
                          for k, x in v.fields.items())
        return "%s(%s)" % (v.type_name, inner)
    if isinstance(v, (Closure, NativeFunc, BoundMethod)):
        return "<フゥン>"
    if isinstance(v, Namespace):
        return "<%s>" % v.name
    if isinstance(v, Module):
        return "<%s>" % v.name
    return str(v)


def _trace(frame, op, arg):
    """`urayaha run --trace` の実行トレース。出力形式は安定させない(§157)。"""
    import sys
    print("%-14s %4d %-16s %s" % (frame.proto.name, frame.ip,
                                  C.OP_NAMES.get(op, op),
                                  "" if arg is None else arg),
          file=sys.stderr)


def is_truthy(v):
    return not (v is False or v is None)


def type_name_of(v):
    from .checker import INT, FLOAT, BOOL, STRING, LIST, MAP, ANY, RESULT
    if v is None:
        return "……"
    if v is True or v is False:
        return BOOL
    if isinstance(v, int):
        return INT
    if isinstance(v, float):
        return FLOAT
    if isinstance(v, str):
        return STRING
    if isinstance(v, list):
        return LIST
    if isinstance(v, dict):
        return MAP
    if isinstance(v, ResultValue):
        return RESULT
    if isinstance(v, StructValue):
        return v.type_name
    return ANY


# ------------------------------------------------------------------ VM

class VM(object):
    def __init__(self, globals_dict=None, human_number=False):
        self.globals = globals_dict if globals_dict is not None else {}
        self.frames = []
        self.human_number = human_number
        self.structs = {}
        self.trace = False

    # -------------------------------------------------------- 実行

    def run(self, proto, structs=None):
        """プログラムを 1 本走らせる。

        import の実装はネイティブ関数の中からここを再入するので、
        底は 0 固定ではなく「いま積まれているフレーム数」にする。
        そうしないとモジュールの実行が終わったあと、呼び出し元の
        フレームまで巻き込んで走り続けてしまう。
        """
        if structs:
            self.structs.update(structs)
        base = len(self.frames)
        self.frames.append(Frame(proto, []))
        return self._loop(base)

    def call_value(self, fn, args, span=None):
        """ネイティブ関数から Urayaha 側の関数を呼ぶ入口。"""
        base = len(self.frames)
        result = self._invoke(fn, list(args), span)
        if result is not _PUSHED_FRAME:
            return result
        return self._loop(base)

    def _throw(self, code, message, span=None, payload=None):
        raise UrayahaRuntimeError(code, message, span, payload)

    def _invoke(self, fn, args, span):
        """呼べるものを呼ぶ。フレームを積んだ場合は _PUSHED_FRAME を返す。"""
        if isinstance(fn, BoundMethod):
            args = [fn.recv] + args
            fn = fn.func
        if isinstance(fn, NativeFunc):
            n = len(args)
            if n < fn.min_args or (fn.max_args >= 0 and n > fn.max_args):
                self._arity_error(fn.name, fn.min_args, fn.max_args, n, span)
            return fn.fn(self, args, span)
        if hasattr(fn, "fields") and hasattr(fn, "methods"):
            # 別モジュールから来た型を順番の引数で生成する
            if len(args) > len(fn.fields):
                self._throw("E2003", "そんなにいらないみたい", span)
            values = list(args) + [None] * (len(fn.fields) - len(args))
            return StructValue(fn.name, dict(zip(fn.fields, values)), fn)
        if isinstance(fn, Closure):
            proto = fn.proto
            recv = None
            if proto.is_method:
                if not args:
                    self._throw("E2003", "これ、呼び方が違うみたい", span)
                recv = args[0]
                args = args[1:]
            n_params = len(proto.params)
            if proto.variadic_at >= 0:
                fixed = args[:proto.variadic_at]
                rest = args[proto.variadic_at:]
                args = fixed + [rest]
            if len(args) < proto.min_args:
                self._arity_error(proto.name, proto.min_args,
                                  -1 if proto.variadic_at >= 0 else n_params,
                                  len(args), span)
            if len(args) > n_params:
                self._arity_error(proto.name, proto.min_args, n_params,
                                  len(args), span)
            while len(args) < n_params:
                args.append(MISSING)
            frame = Frame(proto, fn.upvalues)
            offset = 0
            if proto.is_method:
                frame.locals[0].v = recv
                offset = 1
            for i, value in enumerate(args):
                frame.locals[i + offset].v = value
            self.frames.append(frame)
            return _PUSHED_FRAME
        self._throw("E2002", "これは呼べないみたい", span)

    def _construct_named(self, target, names, values, span):
        """`型(なまえ = 値)` の生成。型が実行時にしか分からない場合に通る。"""
        info = getattr(target, "fields", None)
        if info is None or not hasattr(target, "methods"):
            self._throw("E2002", "これは名前つきでは作れないみたい", span)
        given = dict(zip(names, values))
        for name in names:
            if name not in target.fields:
                self._throw("E1001", "「%s」って…なに？" % name, span)
        missing = [f for f in target.fields if f not in given]
        if missing:
            self._throw("E2003", "「%s」がまだ来てないみたい" % missing[0], span)
        return StructValue(target.name,
                           dict((f, given[f]) for f in target.fields), target)

    def _arity_error(self, name, min_args, max_args, got, span):
        from .lexer import to_urayaha_digits
        want = ("ン・%s 以上" % to_urayaha_digits(min_args)) if max_args < 0 else (
            "ン・" + to_urayaha_digits(min_args) if min_args == max_args
            else "ン・%s 〜 ン・%s" % (to_urayaha_digits(min_args),
                                     to_urayaha_digits(max_args)))
        self._throw("E2003",
                    "%sはもうちょっとほしいみたい" % name if got < min_args
                    else "%sはそんなにいらないみたい" % name, span,
                    None)

    # -------------------------------------------------------- 主ループ

    def _loop(self, base_depth):
        while len(self.frames) > base_depth:
            frame = self.frames[-1]
            try:
                result = self._step(frame, base_depth)
            except UrayahaRuntimeError as err:
                if not self._unwind(err, base_depth):
                    raise
                continue
            if result is not _CONTINUE:
                return result
        return None

    def _unwind(self, err, base_depth):
        """なんとかなれーッ のハンドラを探す。見つからなければ False。"""
        while len(self.frames) > base_depth:
            frame = self.frames[-1]
            if frame.handlers:
                target, depth = frame.handlers.pop()
                del frame.stack[depth:]
                payload = err.payload if err.payload is not None else err.message
                frame.stack.append(payload)
                frame.ip = target
                return True
            self.frames.pop()
        return False

    def _step(self, frame, base_depth):
        code = frame.proto.code
        while frame.ip < len(code):
            op, arg = code[frame.ip]
            span = frame.proto.spans[frame.ip]
            if self.trace:
                _trace(frame, op, arg)
            frame.ip += 1
            stack = frame.stack

            if op == C.LOAD_CONST:
                stack.append(frame.proto.consts[arg])
            elif op == C.LOAD_LOCAL:
                stack.append(frame.locals[arg].v)
            elif op == C.STORE_LOCAL:
                frame.locals[arg].v = stack.pop()
            elif op == C.LOAD_UPVAL:
                stack.append(frame.upvalues[arg].v)
            elif op == C.STORE_UPVAL:
                frame.upvalues[arg].v = stack.pop()
            elif op == C.LOAD_GLOBAL:
                if arg not in self.globals:
                    self._throw("E1001", "「%s」って…なに？" % arg, span)
                stack.append(self.globals[arg])
            elif op == C.STORE_GLOBAL or op == C.DEFINE_GLOBAL:
                self.globals[arg] = stack.pop()
            elif op == C.POP:
                stack.pop()
            elif op == C.DUP:
                stack.append(stack[-1])
            elif op == C.JUMP:
                frame.ip = arg
            elif op == C.JUMP_IF_FALSE:
                if not is_truthy(stack.pop()):
                    frame.ip = arg
            elif op == C.JUMP_IF_TRUE:
                if is_truthy(stack.pop()):
                    frame.ip = arg
            elif op == C.JUMP_IF_NULL:
                if stack.pop() is None:
                    frame.ip = arg
            elif op == C.JUMP_IF_SET:
                if stack.pop() is not MISSING:
                    frame.ip = arg
            elif op == C.CALL_KW:
                values = [stack.pop() for _ in range(len(arg))][::-1]
                target = stack.pop()
                stack.append(self._construct_named(target, arg, values, span))
            elif op == C.CALL:
                args = [stack.pop() for _ in range(arg)][::-1]
                fn = stack.pop()
                result = self._invoke(fn, args, span)
                if result is _PUSHED_FRAME:
                    return _CONTINUE
                stack.append(result)
            elif op == C.RETURN:
                value = stack.pop()
                self.frames.pop()
                if len(self.frames) <= base_depth:
                    return value
                self.frames[-1].stack.append(value)
                return _CONTINUE
            elif op == C.MAKE_CLOSURE:
                ups = []
                for is_local, index in arg.upvalues:
                    ups.append(frame.locals[index] if is_local
                               else frame.upvalues[index])
                stack.append(Closure(arg, ups))
            elif op == C.MAKE_LIST:
                items = [stack.pop() for _ in range(arg)][::-1]
                stack.append(items)
            elif op == C.MAKE_TUPLE:
                items = [stack.pop() for _ in range(arg)][::-1]
                stack.append(tuple(items))
            elif op == C.MAKE_MAP:
                pairs = [stack.pop() for _ in range(arg * 2)][::-1]
                out = {}
                for i in range(0, len(pairs), 2):
                    out[pairs[i]] = pairs[i + 1]
                stack.append(out)
            elif op == C.MAKE_STRUCT:
                info = self.structs[arg]
                values = [stack.pop() for _ in range(len(info.fields))][::-1]
                stack.append(StructValue(
                    arg, dict(zip(info.fields, values)), info))
            elif op == C.MAKE_OK:
                stack.append(ResultValue(True, stack.pop()))
            elif op == C.MAKE_ERR:
                stack.append(ResultValue(False, stack.pop()))
            elif op == C.CONCAT:
                parts = [stack.pop() for _ in range(arg)][::-1]
                stack.append("".join(
                    p if isinstance(p, str) else urayaha_repr(p, self.human_number)
                    for p in parts))
            elif op == C.UNPACK:
                value = stack.pop()
                if not isinstance(value, (list, tuple)):
                    self._throw("E2002", "これは分けられないみたい", span)
                if len(value) != arg:
                    self._throw("E2003", "分ける数が合わないみたい", span)
                for item in value:
                    stack.append(item)
            elif op == C.GET_INDEX:
                index = stack.pop()
                obj = stack.pop()
                stack.append(self._get_index(obj, index, span))
            elif op == C.SET_INDEX:
                index = stack.pop()
                obj = stack.pop()
                value = stack.pop()
                self._set_index(obj, index, value, span)
                stack.append(value)
            elif op == C.GET_MEMBER:
                stack.append(self._get_member(stack.pop(), arg, span))
            elif op == C.SET_MEMBER:
                obj = stack.pop()
                value = stack.pop()
                self._set_member(obj, arg, value, span)
                stack.append(value)
            elif op == C.ITER_NEW:
                stack.append(_Iter(self._iterable(stack.pop(), span)))
            elif op == C.ITER_NEXT:
                it = stack[-1]
                nxt = it.next()
                if nxt is _STOP:
                    frame.ip = arg
                else:
                    stack.append(nxt)
            elif op == C.SETUP_TRY:
                frame.handlers.append((arg, len(stack)))
            elif op == C.POP_TRY:
                frame.handlers.pop()
            elif op == C.THROW:
                value = stack.pop()
                raise UrayahaRuntimeError(
                    "E3006", urayaha_repr(value, self.human_number), span, value)
            elif op == C.NOT:
                stack.append(not is_truthy(stack.pop()))
            elif op == C.NEG:
                value = stack.pop()
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    self._throw("E2002", "これにはマイナス付けられないみたい", span)
                stack.append(-value)
            else:
                b = stack.pop()
                a = stack.pop()
                stack.append(self._binary(op, a, b, span))
        return None

    # -------------------------------------------------------- 演算

    def _binary(self, op, a, b, span):
        if op == C.CMP_EQ:
            return _equal(a, b)
        if op == C.CMP_NE:
            return not _equal(a, b)
        if op in (C.CMP_LT, C.CMP_LE, C.CMP_GT, C.CMP_GE):
            if not _comparable(a, b):
                self._throw("E2002", "これ同士は比べられないみたい", span)
            if op == C.CMP_LT:
                return a < b
            if op == C.CMP_LE:
                return a <= b
            if op == C.CMP_GT:
                return a > b
            return a >= b
        if op == C.ADD:
            if isinstance(a, str) and isinstance(b, str):
                return a + b
            if isinstance(a, list) and isinstance(b, list):
                return a + b
            if _num(a) and _num(b):
                return a + b
            self._throw("E2001", "ここに来るもの、なんか違うみたい…", span)
        if not (_num(a) and _num(b)):
            self._throw("E2002", "これ同士では計算できないみたい", span)
        if op == C.SUB:
            return a - b
        if op == C.MUL:
            return a * b
        if op == C.DIV:
            if b == 0:
                self._throw("E3001", "これじゃ割れないヨ…", span)
            if isinstance(a, int) and isinstance(b, int):
                q = abs(a) // abs(b)
                return -q if (a < 0) != (b < 0) else q
            return a / b
        if op == C.MOD:
            if b == 0:
                self._throw("E3001", "これじゃ割れないヨ…", span)
            # 商は 0 方向へ切り捨てる。剰余の符号は被除数に合わせる。
            q = abs(a) // abs(b) if isinstance(a, int) and isinstance(b, int)                 else int(abs(a) / abs(b))
            if (a < 0) != (b < 0):
                q = -q
            return a - b * q
        self._throw("E2002", "この計算はできないみたい", span)

    def _iterable(self, obj, span):
        if isinstance(obj, list):
            return list(obj)
        if isinstance(obj, tuple):
            return list(obj)
        if isinstance(obj, str):
            return list(obj)
        if isinstance(obj, dict):
            return list(obj.keys())
        self._throw("E2002", "これ、ひとつずつ取り出せないみたい", span)

    def _get_index(self, obj, index, span):
        if obj is None:
            self._throw("E3003", "「……」だったみたい", span)
        if isinstance(obj, dict):
            return obj.get(index)
        if isinstance(obj, (list, tuple, str)):
            if not isinstance(index, int) or isinstance(index, bool):
                self._throw("E2001", "ここに来るもの、なんか違うみたい…", span)
            if index < 0:
                index += len(obj)
            if index < 0 or index >= len(obj):
                self._throw("E3002", "そこには何もないみたい", span)
            return obj[index]
        self._throw("E2002", "これは [ ] で取り出せないみたい", span)

    def _set_index(self, obj, index, value, span):
        if obj is None:
            self._throw("E3003", "「……」だったみたい", span)
        if isinstance(obj, dict):
            obj[index] = value
            return
        if isinstance(obj, list):
            if not isinstance(index, int) or isinstance(index, bool):
                self._throw("E2001", "ここに来るもの、なんか違うみたい…", span)
            if index < 0:
                index += len(obj)
            if index < 0 or index >= len(obj):
                self._throw("E3002", "そこには何もないみたい", span)
            obj[index] = value
            return
        self._throw("E2002", "これには [ ] で入れられないみたい", span)

    def _get_member(self, obj, name, span):
        from .stdlib import member_of_builtin
        if obj is None:
            self._throw("E3003", "「……」だったみたい", span)
        if isinstance(obj, StructValue):
            if name in obj.fields:
                return obj.fields[name]
            proto = obj.info.methods.get(name)
            if proto is not None:
                return BoundMethod(obj, Closure(proto, []))
            self._throw("E1001", "「%s」って…なに？" % name, span)
        if isinstance(obj, Namespace):
            if name not in obj.members:
                self._throw("E1001", "「%s」って…なに？" % name, span)
            return obj.members[name]
        if isinstance(obj, Module):
            if name not in obj.exports:
                self._throw("E1001", "「%s」、外に出てないみたい" % name, span)
            return obj.exports[name]
        found = member_of_builtin(obj, name)
        if found is not None:
            return found
        self._throw("E1001", "「%s」って…なに？" % name, span)

    def _set_member(self, obj, name, value, span):
        if obj is None:
            self._throw("E3003", "「……」だったみたい", span)
        if isinstance(obj, StructValue):
            if name not in obj.fields:
                self._throw("E1001", "「%s」って…なに？" % name, span)
            obj.fields[name] = value
            return
        self._throw("E2002", "これには入れられないみたい", span)


class _Iter(object):
    __slots__ = ("items", "i")

    def __init__(self, items):
        self.items = items
        self.i = 0

    def next(self):
        if self.i >= len(self.items):
            return _STOP
        value = self.items[self.i]
        self.i += 1
        return value


class _Sentinel(object):
    __slots__ = ("label",)

    def __init__(self, label):
        self.label = label

    def __repr__(self):
        return self.label


_STOP = _Sentinel("<おわり>")
_CONTINUE = _Sentinel("<つづく>")
_PUSHED_FRAME = _Sentinel("<フレーム>")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _comparable(a, b):
    if isinstance(a, str) and isinstance(b, str):
        return True
    return _num(a) and _num(b)


def _equal(a, b):
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, ResultValue) and isinstance(b, ResultValue):
        return a.is_ok == b.is_ok and _equal(a.value, b.value)
    if isinstance(a, StructValue) and isinstance(b, StructValue):
        return a.type_name == b.type_name and a.fields == b.fields
    try:
        return bool(a == b)
    except Exception:
        return False
