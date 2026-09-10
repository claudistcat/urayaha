# CLI リファレンス

`urayaha` は、URAYAHA のプログラムを検査・実行するコマンドです。ソースファイルの拡張子は `.ura`、ビルドしたバイトコードは `.urab` です。

この文書は `urayaha/cli.py` の実装に基づきます。例はバージョン 0.4.0 で実行しました。コマンド例の `$` は入力しません。出力は、特記しない限り標準出力で、終了コードは 0 です。検証では出力を捕捉したため、端末に直接実行するときだけ出る起動バナーは含めていません。

## 呼び出し方

```text
urayaha <command> [options] [target] [-- args...]
```

以下の例では、インストールの有無に依存しない `python -m urayaha` を使います。リポジトリのラッパを使う場合は、Windows では `.\bin\urayaha.cmd`、それ以外では `./bin/urayaha` に置き換えられます。

Windows の PowerShell では、実行前に設定してください。

```powershell
$env:PYTHONIOENCODING = 'utf-8'
```

オプションはコマンドや対象の前後に置けます。`--` より後は、オプションらしい文字列も含めてプログラムへの引数になります。コマンドを省略すると REPL が始まります。引数を複数渡したい場合は必ず `--` を使ってください。対象の後に並べただけの余分な位置引数は、プログラムには渡りません。

## オプション一覧

引数解析が受け付けるオプションは次のとおりです。すべて値を伴わないスイッチです。表の対象以外のコマンドでも構文上は受け付けますが、効果があるとは限りません。

| オプション | 効果と対象 |
|---|---|
| `--quiet`, `-q` | 通常の完了メッセージや起動バナーを抑えます。`run`、`check`、`build` の警告表示も抑えます。プログラムの出力やエラー診断は残ります。`test` の集計、`help`、`version`、`dump` の表示、REPL のプロンプトは残ります。 |
| `--debug` | `run`、`check`、`build`、`dump`、REPL のエラー診断に内部名を加えます。「ほしかったもの / きたもの」の情報が診断にある場合は、それも表示します。通常の警告表示には適用されません。 |
| `--trace` | `run` と `test` で VM の実行トレースを標準エラー出力に出します。形式は安定した公開形式ではありません。`--quiet` と併用しても出ます。 |
| `--no-check` | `run` と `test` で、ソースの名前解決・型検査を省略します。字句解析・構文解析・コンパイルは行います。`check`、`build`、`dump`、REPL の検査は省略しません。 |
| `--human-number` | `run`、`test`、REPL で、数値の表示を通常の 10 進表記にします。ソースに書く数値の構文は変わりません。 |
| `--strict-usagi`, `--urayaha` | `run`、`check`、`build`、`test` で、うさぎ語らしくない識別子の警告 `W1006` を失敗扱いにします。REPL は警告を表示しますが、その理由だけで実行を止めません。 |
| `--no-color` | 受け付けますが処理はありません。現在は既定でも色を付けません。 |
| `--check` | `fmt` で書き換えず、整形が必要かを調べます。差分があれば終了コード 1 です。 |
| `--stdout` | `fmt` で、変更が必要なファイルの整形結果を標準出力に出します。ファイルは書き換えません。`--check` との併用では `--check` が優先します。 |
| `--tokens` | `dump` でトークンを表示します。表示対象を指定しない場合の既定値です。 |
| `--ast` | `dump` で構文木を表示します。その後に名前解決・型検査も行うため、構文木が表示されても失敗する場合があります。 |
| `--resolved` | `dump` で解決したグローバル名、構造体、メソッドを表示します。 |
| `--types` | `dump` で組み込み以外のグローバル名の型を表示します。 |
| `--bytecode` | `dump` でバイトコードを表示します。ファイルは生成しません。 |
| `--version`, `-V` | `version` を選びます。 |
| `--help`, `-h` | `help` を選びます。 |
| `--` | 以後の文字列をプログラム引数にします。現在、その引数を受け取るのは `run` だけです。 |

未知の `--...` は終了コード 2 になります。`--why` は受け付けません。診断の詳細には `--debug` を使ってください。`--help` と `--version` を両方指定すると、後に書いたものが選ばれます。

## うさぎ語の別名

別名と正式コマンドの機能は同じです。`ハァ?` と `ハァ？` は、疑問符が半角でも全角でも使えます。

| 別名 | 正式コマンド |
|---|---|
| `イヤッハー` | `run` |
| `ハァ?` | `check` |
| `ハァ？` | `check` |
| `ウラーヤッハ` | `build` |
| `ヤッハーヤーハー` | `repl` |

```text
$ python -m urayaha イヤッハー hello.ura
こんにちは
$ python -m urayaha ハァ? hello.ura
ヤー
```

## run：プログラムを実行する

```text
urayaha run <file.ura|file.urab> [--quiet] [--debug] [--trace]
            [--no-check] [--human-number] [--strict-usagi] [-- args...]
```

`.ura` は検査・コンパイルして実行します。`.urab` は読み込んで実行します。ソース検査の失敗は終了コード 1、捕捉されない実行時エラーは 3 です。標準エラー出力が端末につながり、`--quiet` がない場合は、実行前に「ウラ」「ヤハ」「イヤッハー！！」の 3 行を標準エラー出力へ出します。

`hello.ura` を次の内容で保存します。

```urayaha
イヤッハー("こんにちは")
```

```text
$ python -m urayaha run hello.ura
こんにちは
```

プログラム引数は `ウロル.プルャ` で取得します。スクリプト名は含みません。`args.ura` を次の内容で保存します。

```urayaha
これって… ウロル
イヤッハー(ウロル.プルャ)
```

```text
$ python -m urayaha run args.ura -- りんご --quiet
[りんご, --quiet]
```

この `--quiet` は処理系のオプションではなく、2 個目の文字列引数です。

## check：実行せず検査する

```text
urayaha check [file|dir] [--quiet] [--debug] [--strict-usagi]
```

対象を省略すると現在のディレクトリを調べます。ディレクトリでは `.ura` を再帰的に探し、パス中に `dist` というディレクトリがあるものを除外します。各ファイルをコンパイルまで処理しますが、プログラムは実行しません。`--no-check` を付けても検査します。

```text
$ python -m urayaha check hello.ura
ヤー
```

`hello.ura` の「こんにちは」は表示されません。対象ディレクトリに `.ura` がなくても終了コードは 0 です。その場合は、`--quiet` がなければ見つからなかった旨を標準エラー出力に出します。

## build：バイトコードを作る

```text
urayaha build <file> [--quiet] [--debug] [--strict-usagi]
```

ソースを検査して、入力ファイルと同じディレクトリ内の `dist/` に `.urab` を書きます。既存の同名ファイルは上書きします。出力先を指定するオプションはありません。`--no-check` を付けても検査します。

次は一時ディレクトリでの実出力です。絶対パスの部分は保存場所によって変わります。

```text
$ python -m urayaha build hello.ura
C:\WINDOWS\TEMP\urayaha-cli-wtmp4a12\dist\hello.urab
$ python -m urayaha run dist/hello.urab
こんにちは
```

バイトコードの形式が合わない場合は、現在の処理系で再度 `build` してください。`.urab` は Python の pickle で読み込むため、自分で生成したものなど、信頼できるファイルだけを実行してください。

## fmt：ソースを整形する

```text
urayaha fmt <file|dir> [--check | --stdout] [--quiet]
```

インデントや行末の空白を整えます。ディレクトリの探索範囲は `check` と同じです。オプションを付けなければ、変更が必要なファイルを UTF-8 で上書きし、そのパスを表示します。字句が読めないソースはそのまま返すため、構文の正しさは別途 `check` で確認してください。

`format.ura` に、次の行を行頭の空白 2 個も含めて保存します。

```urayaha
  イヤッハー("こんにちは")
```

```text
$ python -m urayaha fmt format.ura --check
整ってないみたい: format.ura
```

この出力だけは標準エラー出力で、終了コードは 1 です。続けて実行します。

```text
$ python -m urayaha fmt format.ura --stdout
イヤッハー("こんにちは")
$ python -m urayaha fmt format.ura
format.ura
$ python -m urayaha fmt format.ura --check
ヤー
```

整形済みのファイルに `--stdout` を指定すると、何も出力せず終了コード 0 になります。複数ファイルの整形結果を出す場合、ファイル名の見出しや区切りは付きません。

## test：ファイルを順に実行する

```text
urayaha test [file|dir] [--debug] [--trace] [--no-check]
             [--human-number] [--strict-usagi]
```

省略時は現在のディレクトリの `tests/` が対象です。ディレクトリ内の `.ura` を、`check` と同じ範囲で探して実行します。ファイルを直接指定することもできます。特定の関数名を探す方式ではなく、各ファイルが終了コード 0 で終われば成功です。

```text
$ python -m urayaha test hello.ura
こんにちは
ヤッター: 1
```

各プログラムの標準出力は残ります。通常の警告と起動バナーは抑えられますが、エラーは標準エラー出力へ出ます。成功件数、失敗件数、失敗したパスは標準出力へ出ます。`--quiet` でも集計は消えません。1 件でも失敗すると終了コード 1 です。対象が存在しない場合も 1、存在するディレクトリに対象ファイルがない場合は「ヤッター: 0」と出して 0 です。

## repl：対話環境を使う

```text
urayaha repl [--quiet] [--debug] [--human-number] [--strict-usagi]
urayaha
```

`>>> ` の後に式や文を入力します。式だけなら結果を表示します。開いたブロックが残っていると `... ` で続きを待ちます。括弧だけが閉じていない場合は、この継続判定の対象にはなりません。

次の 2 行を標準入力へ渡して実行しました。

```text
ン・プ + ン・ル
:q
```

得られた標準出力は次のとおりです。入力自体のエコーは含めていません。

```text
URAYAHA v0.4.0
ウラーヤッハー！

>>> ン・ャ
>>> イヤッハー！
```

`:q` または `:quit` で終了し、`:help` または `:?` で CLI のヘルプを表示します。これらは入力途中のブロックがないときに使えます。入力の終端でも終了コード 0 で終わります。入力待ちでの Ctrl+C は現在の入力を取り消します。

`--quiet` は起動バナーを抑えますが、プロンプト、終了メッセージ、評価時の警告は抑えません。`--no-check` と `--trace` は REPL の評価には適用されません。入力ごとに別々にコンパイルしますが、宣言は次の入力へ持ち越されるので、前の行で作った変数・関数・型をそのまま使えます。

## dump：解析結果を表示する

```text
urayaha dump <file> [--tokens] [--ast] [--resolved] [--types]
              [--bytecode] [--debug]
```

プログラムを実行せず、選んだ解析結果を標準出力に出します。指定がなければ `--tokens` と同じです。複数指定すると、指定順によらずトークン、構文木、解決した名前、型、バイトコードの順に表示します。組み込みの名前は名前・型の一覧から省かれます。警告は表示しません。

空の `empty.ura` を保存して実行した例です。

```text
$ python -m urayaha dump empty.ura
EOF          ""                     1:1
$ python -m urayaha dump empty.ura --ast --resolved --types --bytecode
Program
-- globals --

== <main> ==
   0  LOAD_CONST       None
   1  RETURN
```

トークンだけの場合は字句解析で終わるため、成功しても構文や型が正しいとは限りません。他の表示では名前解決・型検査も行います。`--no-check` では省略できません。位置の行番号・列番号は 10 進です。

## new：プロジェクトの雛形を作る

```text
urayaha new <name> [--quiet]
```

指定名のディレクトリを作り、`src/main.ura`、空の `tests/`、`urayaha.toml` を作成します。既存のファイルやディレクトリが同名で存在すると、何も作らず終了コード 1 になります。名前を省略すると 2 です。

```text
$ python -m urayaha new sample
sample/
$ python -m urayaha run sample/src/main.ura
ワァ……！
```

生成する設定ファイルには `project.name`、`project.entry = "src/main.ura"`、`language.strict_usagi = false`、`build.output = "dist"` が入ります。ただし、現在の CLI はこの設定ファイルを読み込みません。実行ファイルや strict モードはコマンドで指定してください。

## version：バージョンを表示する

```text
urayaha version
urayaha --version
urayaha -V
```

処理系のバージョンを標準出力に表示します。専用オプションはありません。`--quiet` でも表示します。

```text
$ python -m urayaha version
URAYAHA 0.4.0
```

## help：ヘルプを表示する

```text
urayaha help
urayaha --help
urayaha -h
```

コマンドと主なオプションの一覧を標準出力に表示します。専用オプションはありません。`--quiet` でも表示します。次は実行結果の全文です。

```text
$ python -m urayaha help
urayaha - URAYAHA Programming Language 0.4.0

Usage:
  urayaha run   <file> [-- args...]   プログラムを実行する
  urayaha check <file|dir>            実行せず構文と型だけ調べる
  urayaha build <file>                バイトコード(.urab)を dist/ へ出す
  urayaha fmt   <file|dir>            標準スタイルへ整形する
  urayaha test  [dir]                 tests/ のテストを走らせる
  urayaha repl                        対話環境を起動する
  urayaha dump  <file>                処理系の内部表現を表示する
  urayaha new   <name>                プロジェクトの雛形を作る
  urayaha version                     バージョンを表示する
  urayaha help                        このヘルプを表示する

Options:
  --quiet             処理系のメッセージを抑える(プログラムの出力は残す)
  --debug             内部診断情報を足す
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

Source files use the .ura extension.
```

## 終了コードと出力先

| 定数名 | 終了コード | 意味 |
|---|---|---|
| `EXIT_OK` | 0 | 成功です。 |
| `EXIT_FAIL` | 1 | ソース・コンパイル・検査の失敗です。整形の差分、テスト失敗、対象の不在、バイトコードの読み込み失敗なども含みます。 |
| `EXIT_USAGE` | 2 | 未知のコマンドやオプション、必須引数の不足です。 |
| `EXIT_UNCAUGHT` | 3 | `run` で捕捉されない言語の実行時エラー、または実行中の割り込みです。 |
| `EXIT_INTERNAL` | 70 | `run` の VM 実行中に Python の再帰上限へ達した場合の内部エラーです。 |

`ウロル.イヤッ(...)` で終了した `run` は、プログラムが指定した終了コードを返します。そのため、この表の値だけに限定されません。`test` は個々のプログラムの失敗コードをそのまま返さず、失敗があれば 1 にまとめます。

| 出力先 | 内容 |
|---|---|
| 標準出力（stdout） | プログラムの表示、`check` の成功、`build` の出力先、`fmt` の変更パスまたは整形結果、`test` の集計、REPL のバナー・プロンプト・評価結果、`dump`、`new` の作成先、`version`、`help` です。 |
| 標準エラー出力（stderr） | エラー診断、警告、`run` の起動バナー、実行トレース、`fmt --check` の差分通知、見つからない対象についての通知です。CLI の使い方が誤っているときのヘルプもこちらに出ます。 |

`--quiet` は標準エラー出力を丸ごと消すオプションではありません。また、診断の `E...` という番号とプロセスの終了コードは別物です。たとえば、破損したバイトコードを読み込んだ際の `E9001` は終了コード 1 です。すべての内部障害が 70 に変換されるわけではありません。

<!-- 要確認 -->

- `--why` は `--debug` の別名として受け付けます。
- ヘルプの `fmt --stdout` の説明だけでは整形済みファイルも出力するように読めますが、現在は差分のあるファイルだけを出します。整形後の再実行で出力が空になることを確認しました。
- `new` が生成する `urayaha.toml` は現在の CLI から読み込まれません。設定値がコマンドの既定値になるわけではありません。
- strict モードの失敗扱いと、`--quiet`、`--no-check`、`--trace` の適用範囲はコマンドごとに異なります。
- 終了コード 70 はソース上の再帰上限処理を確認したものです。この文書のコマンド例では、再帰上限、端末への起動バナー、Ctrl+C、すべての OS 入出力失敗は再現していません。
