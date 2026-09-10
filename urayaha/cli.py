# -*- coding: utf-8 -*-
"""urayaha コマンド(CLI 仕様 §151-§201)。

CLI は言語そのものではなく処理系のインターフェースなので、正式コマンドは英語。
うさぎ語は純粋な alias として引数解析の段階で英語へ正規化する(§190)。

終了コード(§184):
    0   成功
    1   ソース/コンパイル/検査の失敗
    2   CLI の使い方の誤り
    3   捕捉されなかった言語例外
    70  処理系内部エラー
"""

import io
import os
import pickle
import sys

from . import __version__
from .errors import UrayahaError, UrayahaRuntimeError, fatal_banner
from .runtime import Runtime, read_text, SOURCE_EXT
from .compiler import disassemble
from .fmt import format_source
from .vm import urayaha_repr

BYTECODE_EXT = ".urab"
BYTECODE_MAGIC = "URAYAHA-BYTECODE"
BYTECODE_FORMAT = 1

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_UNCAUGHT = 3
EXIT_INTERNAL = 70

BANNER = "ウラ\nヤハ\nイヤッハー！！"
REPL_BANNER = "URAYAHA v%s\nウラーヤッハー！" % __version__

# うさぎ語 alias -> 正式コマンド(§189)
ALIASES = {
    "イヤッハー": "run",
    "ハァ?": "check",
    "ハァ？": "check",
    "ウラーヤッハ": "build",
    "ヤッハーヤーハー": "repl",
}

COMMANDS = ("run", "check", "build", "fmt", "test", "repl", "dump",
            "new", "version", "help")

HELP = """urayaha - URAYAHA Programming Language {version}

Usage:
  urayaha run   <file> [-- args...]   プログラムを実行する
  urayaha check <file|dir>            実行せず構文と型だけ調べる
  urayaha build <file>                バイトコード({bext})を dist/ へ出す
  urayaha fmt   <file|dir>            標準スタイルへ整形する
  urayaha test  [dir]                 tests/ のテストを走らせる
  urayaha repl                        対話環境を起動する
  urayaha dump  <file>                処理系の内部表現を表示する
  urayaha new   <name>                プロジェクトの雛形を作る
  urayaha version                     バージョンを表示する
  urayaha help                        このヘルプを表示する

Options:
  --quiet             処理系のメッセージを抑える(プログラムの出力は残す)
  --debug             内部診断情報を足す(alias: --why)
  --trace             VM の実行トレースを出す(出力形式は不安定)
  --no-check          型検査を飛ばして実行する(デバッグ用)
  --human-number      数値を 10 進で表示する
  --strict-usagi      うさぎっぽくない書き方を診断する(alias: --urayaha)
  --no-color          色を使わない(既定でも色は使わない)
  --check             fmt で書き換えず差分の有無だけ見る
  --stdout            fmt の結果をファイルではなく標準出力へ出す

dump options:
  --tokens  --ast  --resolved  --types  --bytecode

Aliases (§189):
  urayaha イヤッハー = run / ハァ? = check / ウラーヤッハ = build
  urayaha ヤッハーヤーハー = repl

Source files use the {ext} extension.
""".format(version=__version__, ext=SOURCE_EXT, bext=BYTECODE_EXT)


# ------------------------------------------------------------------ 入出力

def _setup_stdio():
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        elif hasattr(stream, "buffer"):
            setattr(sys, name, io.TextIOWrapper(stream.buffer,
                                                encoding="utf-8",
                                                errors="replace"))


def _err(text):
    sys.stderr.write(text + "\n")


def _report(rt, diag, show_internal=False):
    sys.stderr.write(rt.render_diagnostic(diag, show_internal) + "\n\n")


def _report_warnings(rt, opts):
    warnings = rt.take_warnings()
    promoted = rt.promote_strict(warnings)
    if not opts["quiet"]:
        for w in warnings:
            _report(rt, w)
    return len(promoted) > 0


# ------------------------------------------------------------------ 引数

def parse_args(argv):
    opts = {"quiet": False, "debug": False, "trace": False, "no_check": False,
            "human": False, "strict": False, "fmt_check": False,
            "fmt_stdout": False, "dump": []}
    positional = []
    program_args = []
    seen_separator = False
    for arg in argv:
        if seen_separator:
            program_args.append(arg)
            continue
        if arg == "--":
            seen_separator = True
        elif arg in ("--quiet", "-q"):
            opts["quiet"] = True
        elif arg in ("--debug", "--why"):
            opts["debug"] = True
        elif arg == "--trace":
            opts["trace"] = True
        elif arg == "--no-check":
            opts["no_check"] = True
        elif arg == "--human-number":
            opts["human"] = True
        elif arg in ("--strict-usagi", "--urayaha"):
            opts["strict"] = True
        elif arg == "--no-color":
            pass
        elif arg == "--check":
            opts["fmt_check"] = True
        elif arg == "--stdout":
            opts["fmt_stdout"] = True
        elif arg in ("--tokens", "--ast", "--resolved", "--types",
                     "--bytecode"):
            opts["dump"].append(arg[2:])
        elif arg in ("--version", "-V"):
            positional.insert(0, "version")
        elif arg in ("--help", "-h"):
            positional.insert(0, "help")
        elif arg.startswith("--"):
            return None, None, None, arg
        else:
            positional.append(arg)
    return opts, positional, program_args, None


def main(argv=None):
    _setup_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    opts, positional, program_args, bad = parse_args(argv)
    if bad is not None:
        _err("知らないオプションみたい: %s\n" % bad)
        _err(HELP)
        return EXIT_USAGE

    if not positional:
        return cmd_repl(opts)

    command = ALIASES.get(positional[0], positional[0])
    rest = positional[1:]
    if command not in COMMANDS:
        _err("知らないコマンドみたい: %s\n" % positional[0])
        _err(HELP)
        return EXIT_USAGE

    if command == "help":
        sys.stdout.write(HELP)
        return EXIT_OK
    if command == "version":
        sys.stdout.write("URAYAHA %s\n" % __version__)
        return EXIT_OK
    if command == "repl":
        return cmd_repl(opts)
    if command == "new":
        return cmd_new(rest, opts)
    if command == "test":
        return cmd_test(rest, opts)

    if not rest:
        if command == "check":
            rest = ["."]
        else:
            _err("ファイルがないみたい\n")
            _err(HELP)
            return EXIT_USAGE

    target = rest[0]
    if not os.path.exists(target):
        _err('[E3004] 泣いちゃった！\n\n"%s"\n\nないみたい…' % target)
        return EXIT_FAIL

    if command == "run":
        return cmd_run(target, program_args, opts)
    if command == "check":
        return cmd_check(target, opts)
    if command == "build":
        return cmd_build(target, opts)
    if command == "fmt":
        return cmd_fmt(target, opts)
    if command == "dump":
        return cmd_dump(target, opts)
    return EXIT_USAGE


# ------------------------------------------------------------------ run

def _new_runtime(path, program_args, opts):
    base = os.path.dirname(os.path.abspath(path)) or "."
    return Runtime(base, program_args, opts["human"], opts["strict"])


def cmd_run(path, program_args, opts):
    rt = _new_runtime(path, program_args, opts)
    if path.endswith(BYTECODE_EXT):
        loaded = _load_bytecode(path)
        if loaded is None:
            return EXIT_FAIL
        proto, structs = loaded
    else:
        try:
            proto, structs, _pub = rt.compile_file(
                path, skip_check=opts["no_check"])
        except UrayahaError as err:
            _report_warnings(rt, opts)
            _report(rt, err.diagnostic, opts["debug"])
            return EXIT_FAIL
        if _report_warnings(rt, opts):
            _err("フゥン…\n\nもうちょっとうさぎっぽくできるみたい")
            return EXIT_FAIL
    if not opts["quiet"] and sys.stderr.isatty():
        _err(BANNER + "\n")
    rt.vm.trace = opts["trace"]
    try:
        rt.vm.run(proto, structs)
    except UrayahaRuntimeError as err:
        _report(rt, err.to_diagnostic(), opts["debug"])
        return EXIT_UNCAUGHT
    except SystemExit as exc:
        return int(exc.code or 0)
    except RecursionError:
        _err(fatal_banner())
        return EXIT_INTERNAL
    except KeyboardInterrupt:
        _err("\nムリッ")
        return EXIT_UNCAUGHT
    if not opts["quiet"]:
        for w in rt.take_warnings():
            _report(rt, w)
    return EXIT_OK


# ------------------------------------------------------------------ check

def _sources_under(target):
    if os.path.isfile(target):
        return [target]
    found = []
    for root, _dirs, files in os.walk(target):
        if "dist" in root.split(os.sep):
            continue
        for name in sorted(files):
            if name.endswith(SOURCE_EXT):
                found.append(os.path.join(root, name))
    return found


def cmd_check(target, opts):
    paths = _sources_under(target)
    if not paths:
        if not opts["quiet"]:
            _err("%s に %s が見つからないみたい" % (target, SOURCE_EXT))
        return EXIT_OK
    failed = False
    for path in paths:
        rt = _new_runtime(path, [], opts)
        try:
            rt.compile_file(path)
        except UrayahaError as err:
            _report_warnings(rt, opts)
            _report(rt, err.diagnostic, opts["debug"])
            failed = True
            continue
        if _report_warnings(rt, opts):
            failed = True
    if failed:
        return EXIT_FAIL
    if not opts["quiet"]:
        sys.stdout.write("ヤー\n")
    return EXIT_OK


# ------------------------------------------------------------------ build

def cmd_build(path, opts):
    rt = _new_runtime(path, [], opts)
    try:
        proto, structs, _pub = rt.compile_file(path)
    except UrayahaError as err:
        _report_warnings(rt, opts)
        _report(rt, err.diagnostic, opts["debug"])
        return EXIT_FAIL
    if _report_warnings(rt, opts):
        return EXIT_FAIL
    out_dir = os.path.join(os.path.dirname(os.path.abspath(path)) or ".",
                           "dist")
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    stem = os.path.basename(path)
    if stem.endswith(SOURCE_EXT):
        stem = stem[:-len(SOURCE_EXT)]
    out_path = os.path.join(out_dir, stem + BYTECODE_EXT)
    payload = {
        "magic": BYTECODE_MAGIC,
        "format_version": BYTECODE_FORMAT,
        "compiler_version": __version__,
        "language_version": "0.4",
        "proto": proto,
        "structs": structs,
    }
    f = open(out_path, "wb")
    try:
        pickle.dump(payload, f, protocol=2)
    finally:
        f.close()
    if not opts["quiet"]:
        sys.stdout.write("%s\n" % out_path)
    return EXIT_OK


def _load_bytecode(path):
    f = open(path, "rb")
    try:
        payload = pickle.load(f)
    except Exception:
        _err("[E9001] %s\n\n%s が読めないみたい" % (fatal_banner(), path))
        return None
    finally:
        f.close()
    if (not isinstance(payload, dict)
            or payload.get("magic") != BYTECODE_MAGIC):
        _err("%s は URAYAHA のバイトコードじゃないみたい" % path)
        return None
    if payload.get("format_version") != BYTECODE_FORMAT:
        _err("このバイトコードは形式が違うみたい"
             "(いる: %s / きた: %s)。もう一度 build してみて"
             % (BYTECODE_FORMAT, payload.get("format_version")))
        return None
    return payload["proto"], payload["structs"]


# ------------------------------------------------------------------ fmt

def cmd_fmt(target, opts):
    paths = _sources_under(target)
    unformatted = []
    for path in paths:
        source = read_text(path)
        formatted = format_source(source, os.path.basename(path))
        if formatted == source:
            continue
        unformatted.append(path)
        if opts["fmt_check"]:
            continue
        if opts["fmt_stdout"]:
            sys.stdout.write(formatted)
        else:
            f = open(path, "wb")
            try:
                f.write(formatted.encode("utf-8"))
            finally:
                f.close()
            if not opts["quiet"]:
                sys.stdout.write("%s\n" % path)
    if opts["fmt_check"]:
        if unformatted:
            for path in unformatted:
                _err("整ってないみたい: %s" % path)
            return EXIT_FAIL
        if not opts["quiet"]:
            sys.stdout.write("ヤー\n")
    return EXIT_OK


# ------------------------------------------------------------------ test

def cmd_test(rest, opts):
    target = rest[0] if rest else "tests"
    if not os.path.exists(target):
        _err("%s がないみたい" % target)
        return EXIT_FAIL
    paths = _sources_under(target)
    passed = 0
    failed = []
    for path in paths:
        code = cmd_run(path, [], dict(opts, quiet=True))
        if code == EXIT_OK:
            passed += 1
        else:
            failed.append(path)
    sys.stdout.write("ヤッター: %d\n" % passed)
    if failed:
        sys.stdout.write("ワァ…  : %d\n" % len(failed))
        for path in failed:
            sys.stdout.write("    %s\n" % path)
        return EXIT_FAIL
    return EXIT_OK


# ------------------------------------------------------------------ dump

def cmd_dump(path, opts):
    kinds = opts["dump"] or ["tokens"]
    rt = _new_runtime(path, [], opts)
    source = read_text(path)
    filename = os.path.basename(path)
    from .lexer import lex
    from .parser import parse
    from .checker import check
    from .compiler import compile_program
    from . import stdlib
    try:
        rt.sources[filename] = source.splitlines()
        tokens = lex(source, filename, rt.bag)
        if "tokens" in kinds:
            for tok in tokens:
                value = tok.value if tok.kind in ("INT", "FLOAT") else tok.text
                sys.stdout.write("%-12s %-22s %d:%d\n"
                                 % (tok.kind, _quote(value),
                                    tok.span.line, tok.span.col))
        need_tree = bool({"ast", "resolved", "types", "bytecode"} & set(kinds))
        if not need_tree:
            return EXIT_OK
        tree = parse(tokens, filename, rt.bag)
        if "ast" in kinds:
            sys.stdout.write(render_ast(tree) + "\n")
        checker = check(tree, filename, rt.bag, stdlib.build_builtin_types(),
                        return_checker=True)
        if "resolved" in kinds:
            sys.stdout.write(_render_resolved(checker) + "\n")
        if "types" in kinds:
            sys.stdout.write(_render_types(checker) + "\n")
        if "bytecode" in kinds:
            proto, _structs, _pub = compile_program(tree, filename)
            sys.stdout.write(disassemble(proto) + "\n")
    except UrayahaError as err:
        _report(rt, err.diagnostic, opts["debug"])
        return EXIT_FAIL
    return EXIT_OK


def _quote(value):
    return '"%s"' % value if isinstance(value, str) else str(value)


def render_ast(node, prefix="", is_last=True):
    from .ast_nodes import Node
    label = node.kind
    details = []
    for field in node._fields:
        value = getattr(node, field)
        if isinstance(value, (str, int, float, bool)) or value is None:
            details.append("%s: %s" % (field, value))
    if details:
        label += "  " + ", ".join(details)
    lines = [prefix + ("└─ " if prefix else "") + label]
    children = []
    for field in node._fields:
        value = getattr(node, field)
        children.extend(_ast_children(field, value))
    child_prefix = prefix + ("   " if prefix else "")
    for i, (name, child) in enumerate(children):
        last = i == len(children) - 1
        if isinstance(child, Node):
            sub = render_ast(child, child_prefix + "│  " if not last
                             else child_prefix + "   ", last)
            head = child_prefix + ("├─ " if not last else "└─ ")
            lines.append(head + name)
            lines.append(sub)
        else:
            lines.append(child_prefix + "├─ %s: %r" % (name, child))
    return "\n".join(lines)


def _ast_children(field, value):
    from .ast_nodes import Node
    out = []
    if isinstance(value, Node):
        out.append((field, value))
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            if isinstance(item, Node):
                out.append("%s[%d]" % (field, i))
                out[-1] = ("%s[%d]" % (field, i), item)
            elif isinstance(item, (list, tuple)):
                for sub in item:
                    if isinstance(sub, Node):
                        out.append(("%s[%d]" % (field, i), sub))
    return out


def _render_resolved(checker):
    lines = ["-- globals --"]
    for name, sym in sorted(checker.global_scope.symbols.items()):
        if sym.kind == "builtin":
            continue
        lines.append("%-16s %-8s %s" % (name, sym.kind, sym.type))
    if checker.structs:
        lines.append("-- types --")
        for name, st in sorted(checker.structs.items()):
            fields = ", ".join("%s: %r" % (f, t) for f, t in st.info)
            lines.append("%-16s { %s }" % (name, fields))
    if checker.struct_methods:
        lines.append("-- methods --")
        for owner, methods in sorted(checker.struct_methods.items()):
            for name, sig in sorted(methods.items()):
                lines.append("%s.%s %s" % (owner, name, _sig_text(sig)))
    return "\n".join(lines)


def _render_types(checker):
    lines = []
    for name, sym in sorted(checker.global_scope.symbols.items()):
        if sym.kind == "builtin":
            continue
        lines.append("%s : %s" % (name, _sig_text(sym.type)))
    return "\n".join(lines)


def _sig_text(t):
    from .checker import FUNC
    if getattr(t, "name", None) == FUNC and t.info:
        params, ret, _min_args, _max_args = t.info
        return "(%s) -> %r" % (", ".join(repr(p) for p in params), ret)
    return repr(t)


# ------------------------------------------------------------------ new

TEMPLATE_MAIN = 'イヤッハー("ワァ……！")\n'
TEMPLATE_TOML = """[project]
name = "%s"
entry = "src/main.ura"

[language]
strict_usagi = false

[build]
output = "dist"
"""


def cmd_new(rest, opts):
    if not rest:
        _err("プロジェクト名がないみたい")
        return EXIT_USAGE
    name = rest[0]
    if os.path.exists(name):
        _err("%s、もうあるみたい" % name)
        return EXIT_FAIL
    os.makedirs(os.path.join(name, "src"))
    os.makedirs(os.path.join(name, "tests"))
    _write(os.path.join(name, "src", "main" + SOURCE_EXT), TEMPLATE_MAIN)
    _write(os.path.join(name, "urayaha.toml"), TEMPLATE_TOML % name)
    if not opts["quiet"]:
        sys.stdout.write("%s/\n" % name)
    return EXIT_OK


def _write(path, text):
    f = open(path, "wb")
    try:
        f.write(text.encode("utf-8"))
    finally:
        f.close()


# ------------------------------------------------------------------ repl

def cmd_repl(opts):
    rt = Runtime(".", [], opts["human"], opts["strict"])
    if not opts["quiet"]:
        sys.stdout.write(REPL_BANNER + "\n\n")
    buffer = []
    while True:
        sys.stdout.write("... " if buffer else ">>> ")
        sys.stdout.flush()
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            buffer = []
            continue
        if not line:
            sys.stdout.write("\nイヤッハー！\n")
            return EXIT_OK
        line = line.rstrip("\n")
        if not buffer and line.strip() in (":q", ":quit"):
            sys.stdout.write("イヤッハー！\n")
            return EXIT_OK
        if not buffer and line.strip() in (":help", ":?"):
            sys.stdout.write(HELP)
            continue
        buffer.append(line)
        source = "\n".join(buffer)
        if _incomplete(source):
            continue
        buffer = []
        _repl_eval(rt, source, opts)


def _incomplete(source):
    from .lexer import lex
    from .errors import DiagnosticBag
    try:
        tokens = lex(source, "<repl>", DiagnosticBag())
    except UrayahaError:
        return False
    depth = 0
    for tok in tokens:
        if tok.kind == "BEGIN":
            depth += 1
        elif tok.kind == "END":
            depth -= 1
    return depth > 0


def _repl_eval(rt, source, opts):
    wrapped, is_expr = _as_expression(rt, source)
    try:
        proto, structs, _pub = rt.compile_source(wrapped, "<repl>", repl=True)
    except UrayahaError as err:
        rt.take_warnings()
        _report(rt, err.diagnostic, opts["debug"])
        return
    for w in rt.take_warnings():
        _report(rt, w)
    try:
        rt.vm.run(proto, structs)
    except UrayahaRuntimeError as err:
        _report(rt, err.to_diagnostic(), opts["debug"])
    except SystemExit:
        raise


def _as_expression(rt, source):
    """式だけを打ったときは値を表示する(§168)。"""
    from .lexer import lex
    from .parser import Parser
    from .errors import DiagnosticBag
    try:
        tokens = lex(source, "<repl>", DiagnosticBag())
        Parser(tokens, "<repl>", DiagnosticBag()).parse_expression_only()
    except UrayahaError:
        return source, False
    return "イヤッハー(%s)" % source, True


if __name__ == "__main__":
    sys.exit(main())
