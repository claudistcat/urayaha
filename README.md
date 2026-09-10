# URAYAHA

うさぎの鳴き声を構文語彙にした、小規模汎用プログラミング言語です。

見た目はジョーク言語ですが、中身は普通の静的型付きスクリプト言語です。
字句解析 → 構文解析 → 名前解決 → 型検査 → バイトコード生成 → VM という、
ごく普通のパイプラインで動きます。

```
$ urayaha run examples/urayaha.ura
ウーラーヤハー
ウ～ラ～ウ～ラ～ウ～ラ～
ヤハヤハヤーッ！
```

> **コードは鳴き声。構文はまとも。エラーは泣く。**

---

## これは何か

Brainfuck のような「わざとプログラミングを難しくした言語」ではありません。
日本語プログラミング言語でもありません。

**現代的な小型スクリプト言語 + 異常な表面構文** です。

```
フゥン フゥンッ(ヤハァ, ヤハッ) ヤーッ
    ハァーッ ヤハァ + ヤハッ
ハァッ
```

数分眺めれば「関数を定義して足して return している」と分かる程度の難易度に
留めてあります。CLI ツール、ファイル変換、JSON 処理、HTTP アクセス、
テキスト処理、ちょっとした自動化なら実際に書けます。

エラーが出ると処理系が泣きます。

```
[E2001] 泣いちゃった！

main.ura:3:13

    イヤッハー(ヤハァ + ヤハッ)
                        ^^^^^^

ここに来るもの、なんか違うみたい…

ほしかったもの : プルッ
きたもの       : ワァッ
```

---

## 入れる

必要なのは **Python 3.10 以上** だけです。依存パッケージはありません。

### 方法 1: GitHub から直接入れる(いちばん短い)

```bash
pip install git+https://github.com/claudistcat/urayaha.git
```

これで `urayaha` コマンドが使えるようになります。

### 方法 2: clone してから入れる(処理系も触るなら)

```bash
git clone https://github.com/claudistcat/urayaha.git
cd urayaha
pip install -e .
```

`-e` を付けると、ソースを書き換えた結果がそのまま `urayaha` コマンドに反映されます。

### 方法 3: 入れずに使う

clone するだけでも動きます。`bin/` のラッパが必要な環境変数を設定します。

```bash
git clone https://github.com/claudistcat/urayaha.git
cd urayaha
```

```powershell
# Windows (PowerShell / cmd)
.\bin\urayaha.cmd run examples\hello.ura
```

```bash
# macOS / Linux
./bin/urayaha run examples/hello.ura
```

Python を直接呼ぶこともできます。

```bash
PYTHONIOENCODING=utf-8 python -m urayaha run examples/hello.ura
```

---

### 入ったか確かめる

```bash
urayaha version
```

```
URAYAHA 0.4.0
```

`hello.ura` を作って動かします。

```bash
echo 'イヤッハー("ワァ……！")' > hello.ura
urayaha run hello.ura
```

```
ワァ……！
```

プロジェクトのひな形も作れます。

```bash
urayaha new myproject
cd myproject
urayaha run src/main.ura
```

```
myproject/
├─ urayaha.toml
├─ src/
│  └─ main.ura
└─ tests/
```

---

### うまくいかないとき

**`urayaha` が見つからない**

pip の入れ先が PATH に入っていません。モジュールとして呼べば動きます。

```bash
python -m urayaha version
```

PATH を通したい場合は、`python -m site --user-base` が指す場所の `bin`
(Windows なら `Scripts`)を PATH に足してください。

**日本語が化ける(Windows)**

コンソールの文字コードが UTF-8 でないときに起きます。

```powershell
$env:PYTHONIOENCODING = "utf-8"
```

`bin/urayaha.cmd` と `bin/urayaha` を使う場合は自動で設定されるので不要です。

**数値が読めない**

`--human-number` を付けると 10 進で表示されます。

```bash
urayaha run main.ura --human-number
```

---

### 消す

```bash
pip uninstall urayaha
```

---

## 5 分で書き始める

`hello.ura` を作ります。

```
イヤッハー("ワァ……！")
```

```bash
$ urayaha run hello.ura
ワァ……！
```

もう少し書いてみます。

```
// 数値は ン・ で始める 4 進数。ン=0 プ=1 ル=2 ャ=3
ヤハ ヤハァ = ン・プ

ウ～ラ～ ヤハァ <= ン・ププン ヤーッ

    ハァ？ ヤハァ % ン・ャ == ン・ン && ヤハァ % ン・ププ == ン・ン ヤーッ
        イヤッハー("イヤッハー！")
    ウラ ハァ？ ヤハァ % ン・ャ == ン・ン ヤーッ
        イヤッハー("ヤハ")
    ウラ ハァ？ ヤハァ % ン・ププ == ン・ン ヤーッ
        イヤッハー("フゥン")
    ウラ ヤーッ
        イヤッハー(ヤハァ)
    ハァッ

    ヤハァ += ン・プ

ハァッ
```

これが FizzBuzz です。数値が読めないときは `--human-number` を付けると
10 進で表示されます。

次は **[言語ガイド](docs/language-guide.md)** を読んでください。
上から読めばプログラムが書けるようになります。

---

## ドキュメント

| | |
|---|---|
| [言語ガイド](docs/language-guide.md) | 言語の全体。まずこれ |
| [標準ライブラリ](docs/stdlib.md) | ファイル・JSON・HTTP・時刻・乱数・OS |
| [CLI リファレンス](docs/cli.md) | コマンドとオプションと終了コード |
| [エラー一覧](docs/errors.md) | 全エラーコードと、それが出る最小プログラム |
| [うさぎ語早見表](docs/vocabulary.md) | 予約語と意味の対応 |

処理系そのものを触りたい人は [CONTRIBUTING.md](CONTRIBUTING.md) と
[docs/dev/](docs/dev/) を見てください。

---

## コマンド

正式なコマンドは英語です。CLI は言語ではなく処理系のインターフェースなので、
CI やシェルから素直に扱えることを優先しています。

```bash
urayaha run   main.ura        # 実行する
urayaha check main.ura        # 実行せず構文と型だけ調べる
urayaha build main.ura        # バイトコード .urab を dist/ へ出す
urayaha fmt   main.ura        # 整形する(--check で差分の有無だけ)
urayaha test                  # tests/ を走らせる
urayaha repl                  # 対話環境
urayaha dump  --tokens main.ura
urayaha new   myproject
```

うさぎ語の alias もあります。**純粋な別名**で、機能差はありません。

```bash
urayaha イヤッハー main.ura        # = urayaha run
urayaha ハァ? main.ura             # = urayaha check
urayaha ウラーヤッハ main.ura      # = urayaha build
urayaha ヤッハーヤーハー           # = urayaha repl
```

---

## 言語のかたち

```
ヤハ ヤハァ = ン・プルャ                    // 変数(4 進で 27)
ヤハ！ プルャ = ン・ル                       // 定数

フゥン フゥンッ(ヤハァ: プルッ) -> プルッ ヤーッ    // 関数と型注釈
    ハァーッ ヤハァ * ン・ル
ハァッ

こういうこと？ ウララ ヤーッ                 // 型
    ヤハァ: ワァッ
    ヤハッ: プルッ
ハァッ

フゥン ウララ.フゥンッ() -> ワァッ ヤーッ      // メソッド
    ハァーッ "${ヤハァ} が ${ヤハッ} 匹"
ハァッ

もしかして ヤハァ ヤーッ                     // match
    ってこと？ ン・プ =>
        イヤッハー("ワァ")
    じゃないってこと？ =>
        イヤッハー("……")
ハァッ

なんとかなれーッ ヤーッ                      // 例外
    ワァーッ！("なんかダメ")
ダメだった… -> ヤハッ ヤーッ
    イヤッハー(ヤハッ)
ハァッ

これって… プスン                            // 標準モジュール
ヤハ ヤハーッ = プスン.フゥン("data.txt").なんとかなれーッ！()
```

型推論・クロージャ・パイプ演算子 `|>`・Null 合体 `??`・Optional・
可変長引数・既定値引数・分解代入・文字列補間があります。

---

## 中身

```
urayaha/
    lexer.py      字句解析(正規化・最長一致・うさぎ数字)
    parser.py     再帰下降パーサ
    checker.py    名前解決と型検査
    compiler.py   AST -> バイトコード
    vm.py         スタックマシン
    stdlib.py     標準ライブラリ
    fmt.py        整形器
    runtime.py    パイプラインの駆動と import
    cli.py        コマンドライン
    errors.py     診断
```

表面構文のジョーク性は VM や IR には持ち込んでいません。命令名は
`LOAD_CONST` や `JUMP_IF_FALSE` のような普通の英語です。

```bash
PYTHONIOENCODING=utf-8 python -m unittest discover -s tests
```

---

## いまできないこと

- async / await、スレッド
- 高度なジェネリック制約、マクロ、メタプログラミング
- クラス継承
- native FFI、パッケージレジストリ
- 整形器が直すのはインデントと行末空白だけ(演算子まわりの空白は触りません)
- `.urab` は Python の pickle 形式なので、信頼できないファイルを実行しないでください

---

## ライセンス / License

本プロジェクトは、非公式の二次創作・ジョークプログラミング言語です。
原作者、出版社、その他の公式関係者とは一切関係ありません。

本リポジトリに含まれるオリジナルのソースコードは、MIT License の下で公開されています。

MIT License は本プロジェクト独自のソースコードにのみ適用され、第三者が権利を有する
キャラクター、名称、台詞、商標、その他の知的財産に関する権利を許諾するものではありません。

---

This project is an unofficial fan-made derivative work and joke programming language.
It is not affiliated with or endorsed by the original creator, publisher, or any other
official parties.

Original source code contained in this repository is released under the MIT License.

The MIT License applies only to the original source code of this project. It does not
grant any rights to third-party characters, names, dialogue, trademarks, or other
intellectual property.
