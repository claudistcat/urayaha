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
import locale as _locale
import math as _math
import shutil as _shutil
import random as _random
import subprocess as _subprocess
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


def _print_err(vm, args, span):
    """標準エラー出力。うまくいかなかった方の出力はこちらに流す。"""
    sys.stderr.write(" ".join(urayaha_repr(a, vm.human_number)
                              for a in args) + "\n")
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
    """1 引数ならディレクトリを作る。2 引数で上書き、3 引数目が真なら追記。"""
    if len(args) == 1:
        try:
            os.makedirs(args[0], exist_ok=True)
            return _ok(None)
        except OSError:
            return _fail('"%s" つくれないみたい…' % args[0])
    mode = "ab" if len(args) > 2 and is_truthy(args[2]) else "wb"
    try:
        f = open(args[0], mode)
        try:
            f.write(urayaha_repr(args[1], vm.human_number).encode("utf-8"))
        finally:
            f.close()
        return _ok(None)
    except IOError:
        return _fail('"%s" 書けないみたい…' % args[0])


def _fs_exists(vm, args, span):
    """1 引数なら在るか。2 引数目が真なら「ディレクトリか」を見る。"""
    if len(args) > 1 and is_truthy(args[1]):
        return os.path.isdir(args[0])
    return os.path.exists(args[0])


def _fs_remove(vm, args, span):
    try:
        os.remove(args[0])
        return _ok(None)
    except OSError:
        return _fail('"%s" 消せないみたい…' % args[0])


def _fs_list(vm, args, span):
    """直下の名前を返す。2 引数目が真なら下まで潜って相対パスで返す。"""
    target = args[0] if args else "."
    if not (len(args) > 1 and is_truthy(args[1])):
        try:
            return _ok(sorted(os.listdir(target)))
        except OSError:
            return _fail('"%s" のぞけないみたい…' % target)
    if not os.path.isdir(target):
        return _fail('"%s" のぞけないみたい…' % target)
    found = []
    for root, dirs, files in os.walk(target):
        for name in dirs + files:
            rel = os.path.relpath(os.path.join(root, name), target)
            found.append(rel.replace(os.sep, "/"))
    return _ok(sorted(found))


def _fs_move(vm, args, span):
    """移動とリネーム。移した先に同じ名前があれば上書きする。"""
    try:
        _shutil.move(args[0], args[1])
        return _ok(None)
    except (OSError, _shutil.Error):
        return _fail('"%s" を "%s" に移せないみたい…' % (args[0], args[1]))


def _fs_copy(vm, args, span):
    """コピー。ディレクトリを渡したら中身ごと写す。"""
    try:
        if os.path.isdir(args[0]):
            _shutil.copytree(args[0], args[1], dirs_exist_ok=True)
        else:
            _shutil.copy2(args[0], args[1])
        return _ok(None)
    except (OSError, _shutil.Error):
        return _fail('"%s" を "%s" に写せないみたい…' % (args[0], args[1]))


def _fs_size(vm, args, span):
    """ファイルならバイト数、ディレクトリなら直下の件数。"""
    target = args[0]
    try:
        if os.path.isdir(target):
            return _ok(len(os.listdir(target)))
        return _ok(os.path.getsize(target))
    except OSError:
        return _fail('"%s" ないみたい…' % target)


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


_opener = None


def set_opener(fn):
    """「対象を開く」処理をホストのものに差し替える(Android の Intent 発行など)。

    ADR-0005 の「開く処理はホストの責任」を実装するフック。未設定なら
    デスクトップの os.startfile / open / xdg-open にフォールバックする。
    """
    global _opener
    _opener = fn


_runner = None


def set_runner(fn):
    """コマンド起動をホストのものに差し替える(ADR-0006 のフック)。

    引数の argv(文字列の List)を受け取り、ResultValue を返す関数を渡す。
    起動させたくないホスト(Android など)は、失敗を返す関数を渡して塞ぐ。
    """
    global _runner
    _runner = fn


def _decode_out(raw):
    """子プロセスの出力を読む。UTF-8 で読めなければ OS の既定で読み直す。

    Windows の多くのコマンドは cp932 で書くので、UTF-8 固定にすると化ける。
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        enc = _locale.getpreferredencoding(False) or "utf-8"
        return raw.decode(enc, "replace")


def _os_run(vm, args, span):
    """コマンドを起動して標準出力を取る。シェルは通さない(ADR-0006)。"""
    cmd = [args[0]] + [urayaha_repr(x, vm.human_number) for x in args[1]]
    if _runner is not None:
        return _runner(cmd)
    try:
        done = _subprocess.run(cmd, stdout=_subprocess.PIPE,
                               stderr=_subprocess.PIPE)
    except OSError:
        return _fail('"%s" 動かせないみたい…' % args[0])
    if done.returncode != 0:
        why = _decode_out(done.stderr).strip()
        return _fail('"%s" が %d で終わったみたい… %s'
                     % (args[0], done.returncode, why))
    return _ok(_decode_out(done.stdout))


def _os_get(vm, args, span):
    """1 引数なら環境変数の取得、2 引数ならコマンドを起動して出力を取る。"""
    if len(args) == 1:
        return _os_env(vm, args, span)
    return _os_run(vm, args, span)


def _os_has(vm, args, span):
    """そのコマンドが使えるか。起動はしない。"""
    return _shutil.which(args[0]) is not None


def _os_launch_target(target):
    """対象を OS に開かせる。Android の Intent、iOS の openURL と同じ契約。"""
    if _opener is not None:
        _opener(target)
        return
    if sys.platform == "win32":
        os.startfile(target)
    elif sys.platform == "darwin":
        _subprocess.Popen(["open", target])
    else:
        _subprocess.Popen(["xdg-open", target])


def _os_open(vm, args, span):
    target = args[0]
    if not (target.startswith("http://") or target.startswith("https://")):
        if not os.path.exists(target):
            return _fail('"%s" ないみたい…' % target)
    try:
        _os_launch_target(target)
        return _ok(None)
    except OSError as exc:
        return _fail("開けなかったみたい… %s" % exc)


# ------------------------------------------------------------------ 時刻・乱数

DEFAULT_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _time_now(vm, args, span):
    if not args:
        return int(_time.time())
    text = args[0]
    fmt = args[1] if len(args) > 1 else DEFAULT_TIME_FORMAT
    try:
        return _ok(int(_time.mktime(_time.strptime(text, fmt))))
    except (ValueError, OverflowError):
        return _fail('"%s" 読めなかったみたい…' % text)


def _time_format(vm, args, span):
    fmt = args[1] if len(args) > 1 else DEFAULT_TIME_FORMAT
    return _time.strftime(fmt, _time.localtime(args[0]))


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
    """1 引数でキー関数、2 引数目が真なら大きい順。

    キーを渡さず順序だけ変えたいときは `……` を渡す。
    """
    key = args[1] if len(args) > 1 and args[1] is not None else None
    down = len(args) > 2 and is_truthy(args[2])
    try:
        if key is not None:
            return sorted(args[0],
                          key=lambda x: vm.call_value(key, [x], span),
                          reverse=down)
        return sorted(args[0], reverse=down)
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


def _s_slice(vm, args, span):
    end = args[2] if len(args) > 2 else None
    return args[0][args[1]:end]


def _s_replace(vm, args, span):
    return args[0].replace(args[1], args[2])


def _s_strip(vm, args, span):
    return args[0].strip()


def _s_find(vm, args, span):
    idx = args[0].find(args[1])
    return None if idx == -1 else idx


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
    "ナラベ": _bind("ナラベ", _l_sort, 0, 2),
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
    "フゥン": _bind("フゥン", _s_slice, 1, 2),
    "ヤハ": _bind("ヤハ", _s_replace, 2, 2),
    "イヤッ": _bind("イヤッ", _s_strip, 0, 0),
    "フゥー…ン?": _bind("フゥー…ン?", _s_find, 1, 1),
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


# ------------------------------------------------------------------ ウリリ(数)

def _num_abs(vm, args, span):
    """大きさ(絶対値)。"""
    if not isinstance(args[0], (int, float)) or isinstance(args[0], bool):
        _err("E2001", "これは数じゃないみたい", span)
    return abs(args[0])


def _num_drop(vm, args, span):
    """小数を落とす。2 引数目が真なら上へ寄せる(切り上げ)。"""
    if not isinstance(args[0], (int, float)) or isinstance(args[0], bool):
        _err("E2001", "これは数じゃないみたい", span)
    up = len(args) > 1 and is_truthy(args[1])
    return int(_math.ceil(args[0])) if up else int(_math.floor(args[0]))


def _num_get(vm, args, span):
    """1 引数なら平方根、2 引数なら累乗。どちらも Float で返す。"""
    for a in args:
        if not isinstance(a, (int, float)) or isinstance(a, bool):
            _err("E2001", "これは数じゃないみたい", span)
    if len(args) == 1:
        if args[0] < 0:
            return _fail("マイナスの平方根はないみたい…")
        return _ok(_math.sqrt(args[0]))
    try:
        return _ok(float(args[0]) ** float(args[1]))
    except (OverflowError, ZeroDivisionError, ValueError):
        return _fail("その累乗は計算できないみたい…")


# ------------------------------------------------------------------ ウィーヤ(画面)

# 画面の定義のキー。ホストはこれだけを見る
_GUI_TITLE = "だいめい"
_GUI_PARTS = "ぶひん"
_GUI_KIND = "たね"
_GUI_NAME = "なまえ"
_GUI_TEXT = "ぶんめん"
_GUI_PRESS = "おしたら"
_GUI_EVERY = "まつ"
_GUI_TICK = "まつとき"
_GUI_KINDS = ("もじ", "ボタン", "いれる")


class TkBackend(object):
    """既定のバックエンド。Tkinter は Python 標準なので追加の用意が要らない。"""

    def __init__(self):
        self.root = None
        self.widgets = {}
        self.kinds = {}

    def alive(self):
        return self.root is not None

    def show(self, vm, spec, call, span):
        try:
            import tkinter as tk
        except ImportError:
            return _fail("この環境では画面を出せないみたい…")
        if self.root is not None:
            return _fail("画面はもう出ているみたい…")

        self.root = tk.Tk()
        self.widgets = {}
        self.kinds = {}
        self.root.title(spec.get(_GUI_TITLE) or "うさぎ")

        for part in spec.get(_GUI_PARTS) or []:
            kind = part.get(_GUI_KIND)
            name = part.get(_GUI_NAME)
            text = part.get(_GUI_TEXT)
            text = "" if text is None else urayaha_repr(text, vm.human_number)
            if kind == "もじ":
                widget = tk.Label(self.root, text=text)
            elif kind == "ボタン":
                widget = tk.Button(self.root, text=text)
                pressed = part.get(_GUI_PRESS)
                if pressed is not None:
                    widget.config(command=call(pressed))
            elif kind == "いれる":
                widget = tk.Entry(self.root)
                widget.insert(0, text)
            else:
                self.close()
                return _fail('"%s" って部品は知らないみたい…' % kind)
            widget.pack(fill="x", padx=8, pady=4)
            if name is not None:
                self.widgets[name] = widget
                self.kinds[name] = kind

        every = spec.get(_GUI_EVERY)
        tick = spec.get(_GUI_TICK)
        if every is not None and tick is not None:
            wait = max(1, int(every))
            handler = call(tick)

            def again():
                if self.root is None:
                    return
                handler()
                if self.root is not None:
                    self.root.after(wait, again)

            self.root.after(wait, again)

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        try:
            self.root.mainloop()
        finally:
            self.close()
        return _ok(None)

    def set(self, name, text):
        widget = self.widgets.get(name)
        if widget is None:
            return _fail('"%s" って部品はないみたい…' % name)
        if self.kinds.get(name) == "いれる":
            widget.delete(0, "end")
            widget.insert(0, text)
        else:
            widget.config(text=text)
        return _ok(None)

    def get(self, name):
        widget = self.widgets.get(name)
        if widget is None:
            return _fail('"%s" って部品はないみたい…' % name)
        if self.kinds.get(name) == "いれる":
            return _ok(widget.get())
        return _ok(widget.cget("text"))

    def close(self):
        if self.root is None:
            return _ok(None)
        root, self.root = self.root, None
        self.widgets = {}
        self.kinds = {}
        try:
            root.destroy()
        except Exception:
            pass
        return _ok(None)


_gui = None


def set_gui(backend):
    """画面を出す係をホストのものに差し替える。None で既定(Tk)に戻す。

    backend は alive / show / set / get / close を持つオブジェクト。
    Android のように Tk が無いホストは、自分の実装を渡す。
    """
    global _gui
    _gui = backend


def _gui_backend():
    global _gui
    if _gui is None:
        _gui = TkBackend()
    return _gui


def _gui_show(vm, args, span):
    """画面を出して、閉じられるまで回す。ループを持つのはホスト(ADR-0001)。"""
    spec = args[0]
    if not isinstance(spec, dict):
        _err("E2001", "画面の定義は Map で渡すみたい", span)

    def call(fn):
        def handler():
            try:
                vm.call_value(fn, [], span)
            except UrayahaRuntimeError as err:
                sys.stderr.write("ワァ…… %s\n" % err)
                _gui_backend().close()
        return handler

    return _gui_backend().show(vm, spec, call, span)


def _gui_set(vm, args, span):
    return _gui_backend().set(args[0], urayaha_repr(args[1], vm.human_number))


def _gui_get(vm, args, span):
    return _gui_backend().get(args[0])


def _gui_alive(vm, args, span):
    return _gui_backend().alive()


def _gui_close(vm, args, span):
    return _gui_backend().close()


# ------------------------------------------------------------------ モジュール

def build_standard_modules(argv=None):
    return {
        "プスン": Namespace("プスン", {
            "フゥン": NativeFunc("プスン.フゥン", _fs_read, 1, 1),
            "ヤハ": NativeFunc("プスン.ヤハ", _fs_write, 1, 3),
            "ハァ?": NativeFunc("プスン.ハァ?", _fs_exists, 1, 2),
            "イヤッ": NativeFunc("プスン.イヤッ", _fs_remove, 1, 1),
            "ン?": NativeFunc("プスン.ン?", _fs_size, 1, 1),
            "トウッ": NativeFunc("プスン.トウッ", _fs_move, 2, 2),
            "プルップラッ": NativeFunc("プスン.プルップラッ", _fs_copy, 2, 2),
            "ツツウラウラ": NativeFunc("プスン.ツツウラウラ", _fs_list, 0, 2),
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
            "フゥン": NativeFunc("ウロル.フゥン", _os_get, 1, 2),
            "ハァ?": NativeFunc("ウロル.ハァ?", _os_has, 1, 1),
            "プルャ": list(argv or []),
            "イヤッ": NativeFunc("ウロル.イヤッ", _os_exit, 0, 1),
            "イヤッハー": NativeFunc("ウロル.イヤッハー", _os_open, 1, 1),
        }),
        "フゥ～ンフゥン": Namespace("フゥ～ンフゥン", {
            "フゥン": NativeFunc("フゥ～ンフゥン.フゥン", _time_now, 0, 2),
            "イヤッハー": NativeFunc("フゥ～ンフゥン.イヤッハー", _time_format, 1, 2),
            "ウ～ラ～": NativeFunc("フゥ～ンフゥン.ウ～ラ～", _time_sleep, 1, 1),
        }),
        "ウラーヤッハ": Namespace("ウラーヤッハ", {
            "フゥン": NativeFunc("ウラーヤッハ.フゥン", _rand, 0, 2),
        }),
        "ウィーヤ": Namespace("ウィーヤ", {
            "イヤッハー": NativeFunc("ウィーヤ.イヤッハー", _gui_show, 1, 1),
            "ヤハ": NativeFunc("ウィーヤ.ヤハ", _gui_set, 2, 2),
            "フゥン": NativeFunc("ウィーヤ.フゥン", _gui_get, 1, 1),
            "ハァ?": NativeFunc("ウィーヤ.ハァ?", _gui_alive, 0, 0),
            "イヤッ": NativeFunc("ウィーヤ.イヤッ", _gui_close, 0, 0),
        }),
        "ウリリ": Namespace("ウリリ", {
            "ン?": NativeFunc("ウリリ.ン?", _num_abs, 1, 1),
            "イヤッ": NativeFunc("ウリリ.イヤッ", _num_drop, 1, 2),
            "フゥン": NativeFunc("ウリリ.フゥン", _num_get, 1, 2),
        }),
    }


def build_globals():
    """import なしで使える組み込み。"""
    return {
        "イヤッハー": NativeFunc("イヤッハー", _print, 0, -1),
        "イヤッハー…": NativeFunc("イヤッハー…", _print_no_newline, 0, -1),
        "ウギッッ": NativeFunc("ウギッッ", _print_err, 0, -1),
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
        "ウギッッ": K.func_type([], K.T_VOID, 0, -1),
        "ワァ?": K.func_type([], K.T_STRING.opt(), 0, 0),
        "プルッ": K.func_type([any_t], K.T_INT, 1, 1),
        "プルァッ": K.func_type([any_t], K.T_FLOAT, 1, 1),
        "ワァッ": K.func_type([any_t], K.T_STRING, 1, 1),
        "ヤハ?ッ": K.func_type([any_t], K.T_BOOL, 1, 1),
        "__これって__": K.func_type([K.T_STRING, K.T_BOOL], any_t, 2, 2),
    }
