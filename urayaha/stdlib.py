# -*- coding: utf-8 -*-
"""標準ライブラリ(v0.4 §66-§83)。

v0.3 までの `ス.モグ` 形式は廃止し、標準モジュール自体にうさぎ語名を与える。
モジュールは `これって… プスン` のように文字列なし import で取り込む。

共通操作語(§69):
    フゥン      取得・読込・変換
    ヤハ        設定・追加・書込
    ハァ?       確認・問い合わせ
    イヤッ      削除・破棄
    イヤッハー  外部化・文字列化・出力
    ン?         サイズ・件数

予測できる失敗は Result を返す(§82)。呼ぶ側は `.なんとかなれーッ!()` で
取り出すか、`.ヤッタ?()` で確かめる。unwrap の失敗は例外送出と同じ扱いで、
`ダメだった…` で捕捉できる。
"""

import json as _json
import os
import random as _random
import sys
import time as _time

from .errors import UrayahaRuntimeError
from .vm import (NativeFunc, BoundMethod, Namespace, ResultValue,
                 urayaha_repr, is_truthy)
from . import checker as K


def _err(code, message, span):
    raise UrayahaRuntimeError(code, message, span)


def _ok(value):
    return ResultValue(True, value)


def _fail(message):
    return ResultValue(False, message)


# ------------------------------------------------------------------ 組み込み

def _print(vm, args, span):
    sys.stdout.write(" ".join(urayaha_repr(a, vm.human_number)
                              for a in args) + "\n")
    return None


def _print_no_newline(vm, args, span):
    sys.stdout.write(" ".join(urayaha_repr(a, vm.human_number) for a in args))
    sys.stdout.flush()
    return None


def _stdin(vm, args, span):
    line = sys.stdin.readline()
    if not line:
        return None
    return line.rstrip("\n").rstrip("\r")


def _urayaha_number_text(text):
    """`ン・プルャ` 形式の文字列も 10 進へ直して受ける。"""
    from .lexer import DIGIT_VALUE
    body = text.strip()
    if body.startswith("ン・"):
        if len(body) == 2:
            raise ValueError(text)
        n = 0
        for ch in body[2:]:
            if ch not in DIGIT_VALUE:
                raise ValueError(text)
            n = n * 4 + DIGIT_VALUE[ch]
        return str(n)
    return body


def _to_int(vm, args, span):
    v = args[0]
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        try:
            return int(_urayaha_number_text(v))
        except ValueError:
            _err("E2001", "これは数にできないみたい", span)
    _err("E2001", "これは数にできないみたい", span)


def _to_float(vm, args, span):
    v = args[0]
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(_urayaha_number_text(v))
        except ValueError:
            _err("E2001", "これは数にできないみたい", span)
    _err("E2001", "これは数にできないみたい", span)


def _to_string(vm, args, span):
    return urayaha_repr(args[0], vm.human_number)


def _to_bool(vm, args, span):
    return is_truthy(args[0])


# ------------------------------------------------------------------ プスン

def _fs_read(vm, args, span):
    try:
        f = open(args[0], "rb")
        try:
            raw = f.read()
        finally:
            f.close()
    except IOError:
        return _fail('"%s" ないみたい…' % args[0])
    try:
        return _ok(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return _fail('"%s" UTF-8 じゃないみたい…' % args[0])


def _fs_write(vm, args, span):
    try:
        f = open(args[0], "wb")
        try:
            f.write(urayaha_repr(args[1], vm.human_number).encode("utf-8"))
        finally:
            f.close()
        return _ok(None)
    except IOError:
        return _fail('"%s" 書けないみたい…' % args[0])


def _fs_exists(vm, args, span):
    return os.path.exists(args[0])


def _fs_remove(vm, args, span):
    try:
        os.remove(args[0])
        return _ok(None)
    except OSError:
        return _fail('"%s" 消せないみたい…' % args[0])


def _fs_list(vm, args, span):
    target = args[0] if args else "."
    try:
        return _ok(sorted(os.listdir(target)))
    except OSError:
        return _fail('"%s" のぞけないみたい…' % target)


# ------------------------------------------------------------------ プルャ

def _plain(v):
    from .vm import StructValue
    if isinstance(v, StructValue):
        return dict((k, _plain(x)) for k, x in v.fields.items())
    if isinstance(v, dict):
        return dict((k, _plain(x)) for k, x in v.items())
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v


def _data_parse(vm, args, span):
    try:
        return _ok(_json.loads(args[0]))
    except Exception:
        return _fail("JSON として読めなかったみたい")


def _data_dump(vm, args, span):
    try:
        return _ok(_json.dumps(_plain(args[0]), ensure_ascii=False))
    except Exception:
        return _fail("JSON にできなかったみたい")


# ------------------------------------------------------------ プルャウラウラ

def _urlopen(url, data=None, content_type=None):
    from urllib.request import urlopen, Request
    headers = {"User-Agent": "urayaha/0.4"}
    if content_type:
        headers["Content-Type"] = content_type
    return urlopen(Request(url, data=data, headers=headers), timeout=30)


def _net_get(vm, args, span):
    try:
        resp = _urlopen(args[0])
        try:
            return _ok(resp.read().decode("utf-8", "replace"))
        finally:
            resp.close()
    except Exception as exc:
        return _fail("つながらなかったみたい… %s" % exc)


def _net_post(vm, args, span):
    body = args[1] if len(args) > 1 else None
    if isinstance(body, (dict, list)):
        data = _json.dumps(_plain(body), ensure_ascii=False).encode("utf-8")
        ctype = "application/json; charset=utf-8"
    else:
        data = (body or "").encode("utf-8")
        ctype = "text/plain; charset=utf-8"
    try:
        resp = _urlopen(args[0], data, ctype)
        try:
            return _ok(resp.read().decode("utf-8", "replace"))
        finally:
            resp.close()
    except Exception as exc:
        return _fail("つながらなかったみたい… %s" % exc)


def _net_check(vm, args, span):
    try:
        _urlopen(args[0]).close()
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ ウロル

def _os_env(vm, args, span):
    return os.environ.get(args[0])


def _os_exit(vm, args, span):
    raise SystemExit(args[0] if args else 0)


# ------------------------------------------------------------------ 時刻・乱数

def _time_now(vm, args, span):
    return int(_time.time())


def _time_sleep(vm, args, span):
    _time.sleep(args[0])
    return None


def _rand(vm, args, span):
    if not args:
        return _random.random()
    if len(args) != 2:
        _err("E2003", "ウラーヤッハ.フゥン は ン・ン 個か ン・ル 個みたい", span)
    lo, hi = args[0], args[1]
    if not isinstance(lo, int) or not isinstance(hi, int):
        _err("E2001", "ここに来るもの、なんか違うみたい…", span)
    if hi < lo:
        _err("E2002", "その範囲は逆さまみたい", span)
    return _random.randint(lo, hi)


# ------------------------------------------------------------------ メンバ

def _bind(name, fn, min_args=0, max_args=-1):
    return NativeFunc(name, fn, min_args + 1,
                      -1 if max_args < 0 else max_args + 1)


def _count(vm, args, span):
    return len(args[0])


def _l_push(vm, args, span):
    args[0].append(args[1])
    return None


def _l_remove(vm, args, span):
    try:
        args[0].remove(args[1])
    except ValueError:
        pass
    return None


def _l_map(vm, args, span):
    return [vm.call_value(args[1], [x], span) for x in list(args[0])]


def _l_filter(vm, args, span):
    return [x for x in list(args[0])
            if is_truthy(vm.call_value(args[1], [x], span))]


def _l_reduce(vm, args, span):
    acc = args[2] if len(args) > 2 else None
    for x in list(args[0]):
        acc = vm.call_value(args[1], [acc, x], span)
    return acc


def _l_join(vm, args, span):
    sep = args[1] if len(args) > 1 else ""
    return sep.join(urayaha_repr(x, vm.human_number) for x in args[0])


def _l_sort(vm, args, span):
    try:
        return sorted(args[0])
    except TypeError:
        _err("E2002", "これ同士は比べられないみたい", span)


def _l_contains(vm, args, span):
    return args[1] in args[0]


def _m_has(vm, args, span):
    return args[1] in args[0]


def _m_set(vm, args, span):
    args[0][args[1]] = args[2]
    return None


def _m_del(vm, args, span):
    args[0].pop(args[1], None)
    return None


def _m_keys(vm, args, span):
    return list(args[0].keys())


def _s_split(vm, args, span):
    sep = args[1] if len(args) > 1 else None
    return args[0].split(sep) if sep else list(args[0])


def _s_contains(vm, args, span):
    return args[1] in args[0]


def _s_join(vm, args, span):
    return args[0].join(urayaha_repr(x, vm.human_number) for x in args[1])


def _r_unwrap(vm, args, span):
    """Err の unwrap は throw と同じ(v0.4 追補)。ダメだった… で捕まえられる。"""
    result = args[0]
    if not isinstance(result, ResultValue):
        _err("E2002", "これは ヤッター/ワァ… じゃないみたい", span)
    if result.is_ok:
        return result.value
    raise UrayahaRuntimeError("E3006",
                              urayaha_repr(result.value, vm.human_number),
                              span, result.value)


def _r_is_ok(vm, args, span):
    return isinstance(args[0], ResultValue) and args[0].is_ok


def _r_value(vm, args, span):
    return args[0].value


LIST_MEMBERS = {
    "ン?": _bind("ン?", _count, 0, 0),
    "ヤハ": _bind("ヤハ", _l_push, 1, 1),
    "イヤッ": _bind("イヤッ", _l_remove, 1, 1),
    "フゥン": _bind("フゥン", _l_map, 1, 1),
    "ハァ?": _bind("ハァ?", _l_filter, 1, 1),
    "ウラ": _bind("ウラ", _l_reduce, 1, 2),
    "ツナグ": _bind("ツナグ", _l_join, 0, 1),
    "ナラベ": _bind("ナラベ", _l_sort, 0, 0),
    "アル?": _bind("アル?", _l_contains, 1, 1),
}
MAP_MEMBERS = {
    "ン?": _bind("ン?", _count, 0, 0),
    "ハァ?": _bind("ハァ?", _m_has, 1, 1),
    "ヤハ": _bind("ヤハ", _m_set, 2, 2),
    "イヤッ": _bind("イヤッ", _m_del, 1, 1),
    "カギ": _bind("カギ", _m_keys, 0, 0),
}
STRING_MEMBERS = {
    "ン?": _bind("ン?", _count, 0, 0),
    "ワケ": _bind("ワケ", _s_split, 0, 1),
    "ハァ?": _bind("ハァ?", _s_contains, 1, 1),
    "ツナグ": _bind("ツナグ", _s_join, 1, 1),
}
RESULT_MEMBERS = {
    "なんとかなれーッ!": _bind("なんとかなれーッ!", _r_unwrap, 0, 0),
    "ヤッタ?": _bind("ヤッタ?", _r_is_ok, 0, 0),
    "フゥン": _bind("フゥン", _r_value, 0, 0),
}


TUPLE_MEMBERS = dict((k, v) for k, v in LIST_MEMBERS.items()
                     if k not in ("ヤハ", "イヤッ"))


def member_of_builtin(obj, name):
    """組み込み型のメンバ。見つからなければ None。"""
    if isinstance(obj, ResultValue):
        fn = RESULT_MEMBERS.get(name)
    elif isinstance(obj, tuple):
        fn = TUPLE_MEMBERS.get(name)
    elif isinstance(obj, list):
        fn = LIST_MEMBERS.get(name)
    elif isinstance(obj, dict):
        fn = MAP_MEMBERS.get(name)
    elif isinstance(obj, str):
        fn = STRING_MEMBERS.get(name)
    else:
        return None
    return BoundMethod(obj, fn) if fn else None


# ------------------------------------------------------------------ モジュール

def build_standard_modules(argv=None):
    return {
        "プスン": Namespace("プスン", {
            "フゥン": NativeFunc("プスン.フゥン", _fs_read, 1, 1),
            "ヤハ": NativeFunc("プスン.ヤハ", _fs_write, 2, 2),
            "ハァ?": NativeFunc("プスン.ハァ?", _fs_exists, 1, 1),
            "イヤッ": NativeFunc("プスン.イヤッ", _fs_remove, 1, 1),
            "ツツウラウラ": NativeFunc("プスン.ツツウラウラ", _fs_list, 0, 1),
        }),
        "プルャ": Namespace("プルャ", {
            "フゥン": NativeFunc("プルャ.フゥン", _data_parse, 1, 1),
            "イヤッハー": NativeFunc("プルャ.イヤッハー", _data_dump, 1, 1),
        }),
        "プルャウラウラ": Namespace("プルャウラウラ", {
            "フゥン": NativeFunc("プルャウラウラ.フゥン", _net_get, 1, 1),
            "ヤハ": NativeFunc("プルャウラウラ.ヤハ", _net_post, 1, 2),
            "ハァ?": NativeFunc("プルャウラウラ.ハァ?", _net_check, 1, 1),
        }),
        "ウロル": Namespace("ウロル", {
            "フゥン": NativeFunc("ウロル.フゥン", _os_env, 1, 1),
            "プルャ": list(argv or []),
            "イヤッ": NativeFunc("ウロル.イヤッ", _os_exit, 0, 1),
        }),
        "フゥ～ンフゥン": Namespace("フゥ～ンフゥン", {
            "フゥン": NativeFunc("フゥ～ンフゥン.フゥン", _time_now, 0, 0),
            "ウ～ラ～": NativeFunc("フゥ～ンフゥン.ウ～ラ～", _time_sleep, 1, 1),
        }),
        "ウラーヤッハ": Namespace("ウラーヤッハ", {
            "フゥン": NativeFunc("ウラーヤッハ.フゥン", _rand, 0, 2),
        }),
    }


def build_globals():
    """import なしで使える組み込み。"""
    return {
        "イヤッハー": NativeFunc("イヤッハー", _print, 0, -1),
        "イヤッハー…": NativeFunc("イヤッハー…", _print_no_newline, 0, -1),
        "ワァ?": NativeFunc("ワァ?", _stdin, 0, 0),
        "プルッ": NativeFunc("プルッ", _to_int, 1, 1),
        "プルァッ": NativeFunc("プルァッ", _to_float, 1, 1),
        "ワァッ": NativeFunc("ワァッ", _to_string, 1, 1),
        "ヤハ?ッ": NativeFunc("ヤハ?ッ", _to_bool, 1, 1),
    }


def build_builtin_types():
    """型検査に渡す組み込みの型。"""
    any_t = K.T_ANY
    return {
        "イヤッハー": K.func_type([], K.T_VOID, 0, -1),
        "イヤッハー…": K.func_type([], K.T_VOID, 0, -1),
        "ワァ?": K.func_type([], K.T_STRING.opt(), 0, 0),
        "プルッ": K.func_type([any_t], K.T_INT, 1, 1),
        "プルァッ": K.func_type([any_t], K.T_FLOAT, 1, 1),
        "ワァッ": K.func_type([any_t], K.T_STRING, 1, 1),
        "ヤハ?ッ": K.func_type([any_t], K.T_BOOL, 1, 1),
        "__これって__": K.func_type([K.T_STRING, K.T_BOOL], any_t, 2, 2),
    }
