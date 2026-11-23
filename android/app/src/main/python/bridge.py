# -*- coding: utf-8 -*-
"""Kotlin と urayaha ランタイムの間をつなぐ、ごく薄いホストの糊。

判断ロジックはここには書かない。alarm.ura を実行して標準出力の文字列を
そのまま Kotlin に返すだけ。「開く」処理だけは ADR-0005 の opener フックで
Kotlin 側の実装に差し替える。
"""

import io
import os
import sys

from urayaha import stdlib
from urayaha.runtime import Runtime


def set_opener(java_opener):
    """「対象を開く」処理を Kotlin 側の実装に差し替える。

    java_opener は open(target: str) を持つ Kotlin/Java オブジェクト。
    """
    def _opener(target):
        java_opener.open(target)
    stdlib.set_opener(_opener)


def run(base_dir, ura_path, *argv):
    """alarm.ura を実行し、標準出力を文字列で返す。

    プスン(ファイル)の相対パスは Runtime.base_dir ではなくプロセスの
    カレントディレクトリを基準に解決される(標準ライブラリの実装がそう
    なっている)。Android のプロセス CWD は書き込める保証が無いので、
    実行中だけ base_dir へ chdir する。終わったら必ず元に戻す。
    例外は握りつぶさず、そのまま呼び出し側(Chaquopy 経由の Kotlin)へ伝える。

    argv は可変長で受ける。Kotlin の List をそのまま渡すと Java の List
    オブジェクトのまま届いて Python からは反復できない(TypeError)。
    """
    runtime = Runtime(base_dir=base_dir, argv=[str(a) for a in argv],
                      human_number=True)
    original_stdout = sys.stdout
    original_cwd = os.getcwd()
    buffer = io.StringIO()
    sys.stdout = buffer
    os.chdir(base_dir)
    try:
        runtime.run_file(ura_path)
    finally:
        sys.stdout = original_stdout
        os.chdir(original_cwd)
    return buffer.getvalue()
