# ADR-0002: `.urab` を pickle から自前のバイナリ形式へ移す

- 状態: 採用(実装は v0.7)
- 日付: 2026-09-12
- 対象: v0.7。**一般配布(v0.8)より前に完了させる**
- 関連: [ADR-0001](0001-event-loop-ownership.md)

## 決定

`.urab` の直列化を Python の `pickle` から **自前のバイナリ形式** に置き換える。

到達したい状態は次の一文である。

> **バージョン間の互換性は保証しないが、読み込むだけでホストの Python コードが
> 実行されることはない。**

互換性を保証しないという既存の方針と、安全な形式にすることは両立する。

## 理由

現在の `cli.py` は `pickle.dump` / `pickle.load` で `.urab` を読み書きしている。
pickle は設計上、**逆直列化の際に任意のコードを実行できる**。マジック文字列と
形式バージョンの検査は入れてあるが、これは検査の前に pickle を展開しなければ
確認できないため、防御になっていない。

手元のツールとして使っているうちは許容範囲だが、`pip install urayaha` で
配布され、第三者が `.urab` を配れる状態になると、そのまま任意コード実行の
経路になる。README の注意書きで防げる種類の問題ではない。

配布後に形式を変えるほうが難しいので、配布フェーズより前に済ませる。

## 形式の骨格

```
ヘッダ
    magic       "URAB"
    version     形式バージョン
    flags

定数表
    Int
    Float
    String
    ...

関数表
    name
    arity
    locals
    upvalues
    bytecode offset

バイトコード
    opcode
    operands

デバッグ情報
    source map
    line table
```

現在 `FuncProto` が持っている情報(`code` / `consts` / `spans` / `params` /
`n_locals` / `upvalues` / `is_method` / `variadic_at` / `min_args`)と
`StructInfo`(`name` / `fields` / `methods`)がそのまま対象になる。

`spans` は診断に使っているので、デバッグ情報として line table の形で残す。

## 影響

- `cli.py` の `cmd_build` と `_load_bytecode` を書き換える
- 形式バージョンが合わない `.urab` は、いまと同じく実行を拒否する
- README と `docs/cli.md` の「pickle なので信頼できないファイルを実行しないで
  ください」という注意書きを削除できる
- 読み込み時に、定数表の型・関数表のオフセット・命令の引数が範囲内かを検査する。
  壊れたファイルで VM がクラッシュせず、診断で落ちるようにする

## やらないこと

- バージョン間の互換性の保証。`.ura` は資産として残すが、`.urab` は必要に応じて
  再ビルドする前提を変えない
- 署名や暗号化。目的は「読み込みが安全であること」であって、真正性の証明ではない
