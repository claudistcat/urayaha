# -*- coding: utf-8 -*-
"""コンパイル一式の駆動とモジュール読込(v0.4 §65, §67, §68, §101)。"""

import os

from .errors import DiagnosticBag, UrayahaRuntimeError
from .lexer import lex
from .parser import parse
from .checker import check
from .compiler import compile_program
from .vm import VM, Module, NativeFunc
from . import stdlib

SOURCE_EXT = ".ura"


class Runtime(object):
    def __init__(self, base_dir=".", argv=None, human_number=False,
                 strict=False):
        self.base_dir = base_dir
        self.argv = list(argv or [])
        self.human_number = human_number
        self.strict = strict
        self.bag = DiagnosticBag()
        self.sources = {}          # ファイル名 -> 行リスト
        self.module_cache = {}
        # REPL は入力ごとに別コンパイルなので、宣言をここに積み上げて持ち越す
        self.repl_state = {"types": {}, "structs": {}, "methods": {},
                           "compiler_structs": {}}
        self.std_modules = stdlib.build_standard_modules(self.argv)
        self.globals = stdlib.build_globals()
        self.globals["__これって__"] = NativeFunc(
            "これって…", self._import_native, 2, 2)
        self.vm = VM(self.globals, human_number)

    # -------------------------------------------------------- パイプライン

    def compile_source(self, source, filename, skip_check=False, repl=False):
        self.sources[filename] = source.splitlines()
        tokens = lex(source, filename, self.bag)
        tree = parse(tokens, filename, self.bag)
        if not skip_check:
            check(tree, filename, self.bag, stdlib.build_builtin_types(),
                  repl_state=self.repl_state if repl else None)
        known = self.repl_state["compiler_structs"] if repl else None
        proto, structs, pub = compile_program(tree, filename, known)
        if repl:
            self.repl_state["compiler_structs"].update(structs)
        return proto, structs, pub

    def compile_file(self, path, skip_check=False):
        return self.compile_source(read_text(path), os.path.basename(path),
                                   skip_check)

    def run_file(self, path):
        proto, structs, _pub = self.compile_file(path)
        self.base_dir = os.path.dirname(os.path.abspath(path)) or "."
        return self.vm.run(proto, structs)

    # -------------------------------------------------------- import

    def _import_native(self, vm, args, span):
        target, is_module = args[0], args[1]
        if is_module:
            module = self.std_modules.get(target)
            if module is None:
                raise UrayahaRuntimeError(
                    "E1004", "「%s」ってモジュール、知らないみたい" % target, span)
            return module
        return self._import_file(target, span)

    def _import_file(self, rel, span):
        path = rel if os.path.isabs(rel) else os.path.join(self.base_dir, rel)
        path = os.path.normpath(path)
        if path in self.module_cache:
            return self.module_cache[path]
        if not os.path.exists(path):
            raise UrayahaRuntimeError("E3004", '"%s" ないみたい…' % rel, span)
        name = os.path.basename(path)
        if name.endswith(SOURCE_EXT):
            name = name[:-len(SOURCE_EXT)]
        module = Module(name, {})
        self.module_cache[path] = module          # 循環 import 対策
        proto, structs, pub = self.compile_source(
            read_text(path), os.path.basename(path))
        module_globals = stdlib.build_globals()
        module_globals["__これって__"] = self.globals["__これって__"]
        saved_globals = self.vm.globals
        saved_base = self.base_dir
        self.vm.globals = module_globals
        self.base_dir = os.path.dirname(path) or "."
        try:
            self.vm.run(proto, structs)
        finally:
            self.vm.globals = saved_globals
            self.base_dir = saved_base
        for exported in pub:
            if exported in module_globals:
                module.exports[exported] = module_globals[exported]
            elif exported in structs:
                module.exports[exported] = structs[exported]
        return module

    # -------------------------------------------------------- 診断

    def render_diagnostic(self, diag, show_internal=False):
        key = diag.span.file if diag.span else None
        return diag.render(self.sources.get(key), show_internal)

    def take_warnings(self):
        out = self.bag.warnings
        self.bag.warnings = []
        if self.strict:
            return out
        return [w for w in out if w.code != "W1006"]

    def promote_strict(self, warnings):
        """Strict URAYAHA Mode では「うさぎっぽくない」警告をエラー扱いにする。"""
        if not self.strict:
            return []
        return [w for w in warnings if w.code == "W1006"]


def read_text(path):
    f = open(path, "rb")
    try:
        return f.read().decode("utf-8")
    finally:
        f.close()
