# 処理系に手を入れる

言語の使い方は [README](README.md) と [言語ガイド](docs/language-guide.md) を
見てください。ここは処理系そのものを触る人向けです。

---

## 手元で動かす

Python 3.10 以上。依存パッケージはありません。

```bash
git clone https://github.com/claudistcat/urayaha.git
cd urayaha
pip install -e .
```

インストールせずに走らせることもできます。

```bash
PYTHONIOENCODING=utf-8 python -m urayaha run examples/hello.ura
```

`PYTHONIOENCODING=utf-8` は Windows で日本語が化けないために要ります。
`bin/urayaha` と `bin/urayaha.cmd` は自動で設定します。

---

## 変更したら通すもの

```bash
urayaha fmt --check .
urayaha check examples
python -m unittest discover -s tests
urayaha test
```

CI(`.github/workflows/ci.yml`)もこの 4 つを Linux と Windows、
Python 3.10 と 3.12 で走らせます。

`examples/json_http.ura` はネットワークが要るので CI では走らせません。

---

## 中の構造

```
urayaha/
    errors.py     診断(Span, Diagnostic, 例外, エラーコード表)
    lexer.py      字句解析
    parser.py     再帰下降パーサ
    ast_nodes.py  AST ノード定義
    checker.py    名前解決と型検査
    compiler.py   AST -> バイトコード
    vm.py         スタックマシン
    stdlib.py     標準ライブラリ
    fmt.py        整形器
    runtime.py    パイプラインの駆動と import
    cli.py        コマンドライン
```

詳しくは [docs/dev/architecture.md](docs/dev/architecture.md)。
仕様の矛盾をどう潰したかは
[docs/dev/spec-decisions.md](docs/dev/spec-decisions.md) にあります。

設計上の判断は [docs/dev/decisions/](docs/dev/decisions/) に ADR として
残しています。**新しい機能を足す前に、関係する ADR を確認してください。**
特に GUI やゲームに触るときは
[ADR-0001(イベントループはホストが所有する)](docs/dev/decisions/0001-event-loop-ownership.md)
が効きます。

どの順で何をやるかは [ロードマップ](docs/roadmap.md) にあります。

---

## 気をつけること

### 語彙を足すとき

予約語や標準ライブラリの名前は、**実在する発話を優先** します。
思いつきの造語より、原作で実際に使われた鳴き声を選んでください。

新しい語を足すときは、既存の語の接頭辞にならないか確認してください。
Lexer は最長一致なので、`ウラ` と `ウ～ラ～` のように区別できる形である
必要があります。

### 型検査を厳しくしすぎない

型検査は「確実に間違っているものだけを落とす」方針です。推論できないところは
`ナンカッ`(Any)に落として通します。ここで誤検知を出すと、まともに書けない言語に
なります。

### 2 つのメソッド表

組み込み型のメソッドは、`stdlib.py`(実行時の実体)と `checker.py`(戻り値の型)の
2 か所に書きます。**片方だけ足すとずれます。** ずれても誤検知しないよう
`checker._runtime_members()` が逃がしを入れてありますが、両方に書いてください。

### 整形器は字句を書き換えない

`～ ー … ッ ァ ィ ゥ ャ` を別の文字へ置き換えてはいけません。特に
`ウ～ラ～` を `ウーラー` にすると while が壊れます。整形器が直してよいのは
インデントと行末の空白だけです。

### Windows

- ファイルの読み書きはバイナリモードで開いて明示的に UTF-8 でデコード・
  エンコードしてください。テキストモードだと改行が壊れます。
- 端末へ出す前に `cli._setup_stdio()` が stdout/stderr を UTF-8 に
  張り替えます。

---

## テストの置き場所

| 場所 | 中身 |
|---|---|
| `tests/test_*.py` | Python の単体テスト(字句・構文・実行・型検査・整形) |
| `tests/ura/*.ura` | URAYAHA で書いたテスト。`urayaha test` が走らせる |
| `examples/*.ura` | ドキュメントから参照するサンプル。CI で実行する |

`tests/ura/` のテストは、食い違ったら `ワァーッ！` を投げます。捕まらずに
落ちれば終了コードが 3 になり、`urayaha test` が失敗として数えます。

---

## デバッグ

```bash
urayaha dump --tokens    main.ura     # 字句
urayaha dump --ast       main.ura     # 構文木
urayaha dump --resolved  main.ura     # 名前解決の結果
urayaha dump --types     main.ura     # 推論された型
urayaha dump --bytecode  main.ura     # バイトコード
urayaha run --trace      main.ura     # VM の実行トレース
urayaha run --no-check   main.ura     # 型検査を飛ばす
urayaha run --debug      main.ura     # 診断に内部エラー名を足す
```

`dump` の出力形式は安定させません。処理系開発用です。
