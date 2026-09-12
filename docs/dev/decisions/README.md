# Architecture Decision Records

設計上の判断のうち、**後から見て理由が分からなくなると困るもの** をここに残します。

ロードマップは [docs/roadmap.md](../../roadmap.md)、仕様の矛盾をどう潰したかの
経緯は [spec-decisions.md](../spec-decisions.md) にあります。

| | 決定 | 状態 |
|---|---|---|
| [ADR-0001](0001-event-loop-ownership.md) | GUI とゲームのイベントループはホストが所有する | 採用 |
| [ADR-0002](0002-urab-format.md) | `.urab` を pickle から自前のバイナリ形式へ移す | 採用(実装は v0.7) |
| [ADR-0003](0003-regex-deferred.md) | 正規表現は保留する | 保留 |

## 書き方

1 ファイル 1 決定です。決定・理由・影響を書きます。特に **なぜその選択肢を
採らなかったか** を残してください。

状態は「採用」「保留」「破棄」「置き換え(ADR-XXXX)」のいずれかです。
決定が覆ったときは、元の ADR を書き換えるのではなく状態を更新し、
新しい ADR から参照します。
