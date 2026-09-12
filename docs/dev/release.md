# リリース手順

PyPI へ公開するまでの手順です。**公開は取り消せません。** PyPI はリリースの削除が
できず、yank(インストール対象から外す)しかできません。バージョン番号の再利用も
できないので、一度上げたら同じ番号では上げ直せません。

---

## 一度だけやること

### 1. PyPI のアカウントを作る

https://pypi.org/account/register/

- メールアドレスの確認が要ります
- **2 要素認証(2FA)が必須** です。認証アプリ(Google Authenticator、1Password、
  Authy など)かセキュリティキーを用意してください
- リカバリーコードが表示されるので、必ず保存してください。これを失くすと
  アカウントに入れなくなります

### 2. API トークンを発行する

https://pypi.org/manage/account/token/

- Token name は分かるものなら何でも構いません(例: `urayaha-release`)
- Scope は、**最初の 1 回だけ** `Entire account` を選びます。プロジェクトが
  まだ存在しないので、プロジェクト単位のトークンを作れないためです
- **トークンは発行時の一度しか表示されません。** 閉じると二度と見られません

初回の公開が済んだら、`urayaha` プロジェクト単位のトークンを作り直して、
アカウント全体のトークンは失効させてください。事故ったときの被害範囲が狭くなります。

### 3. トークンを設定する

`~/.pypirc`(Windows なら `C:\Users\<ユーザー名>\.pypirc`)を開き、

```ini
password = PASTE_YOUR_PYPI_TOKEN_HERE
```

の右側を、発行されたトークン(`pypi-` で始まる長い文字列)にまるごと
差し替えます。`username = __token__` は変えません。

このファイルはアクセス権を本人のみに絞ってあります。

> **トークンをチャットやメール、スクリーンショットに貼らないでください。**
> パスワードと同じものです。漏れたと思ったら、すぐ PyPI で失効させて
> 作り直してください。

---

## 毎回の手順

### 1. 出す前に通すもの

```bash
urayaha fmt --check .
urayaha check examples
python -m unittest discover -s tests
urayaha test
```

### 2. バージョンを上げる

`urayaha/__init__.py` の `__version__` だけを直します。`pyproject.toml` は
ここから自動で引くので、2 か所を直す必要はありません。

### 3. 組み立てて検査する

```bash
rm -rf build_dist urayaha.egg-info build
python -m build --outdir build_dist
python -m twine check build_dist/*
```

`twine check` が PASSED にならないものは上げないでください。

### 4. クリーンな環境で確かめる

```bash
python -m venv /tmp/urayaha-check
/tmp/urayaha-check/bin/pip install build_dist/urayaha-*.whl
/tmp/urayaha-check/bin/urayaha version
```

Windows なら `Scripts/` です。

### 5. TestPyPI で試す(任意だが推奨)

```bash
python -m twine upload --repository testpypi build_dist/*
pip install --index-url https://test.pypi.org/simple/ urayaha
```

TestPyPI は別アカウント・別トークンです。

### 6. 本番へ上げる

```bash
python -m twine upload build_dist/*
```

### 7. 確認する

```bash
pip install urayaha
urayaha version
```

https://pypi.org/project/urayaha/ の表示も確認してください。README がそのまま
説明文になります。

### 8. タグを打つ

```bash
git tag -a v0.4.0 -m "URAYAHA 0.4.0"
git push origin v0.4.0
```

---

## 失敗したとき

### 間違ったものを上げてしまった

削除はできません。**バージョンを上げて出し直します。** 古いほうは PyPI の
管理画面から yank してください。yank したものは新規インストールの対象から
外れますが、バージョンを明示すれば入れられます(既存の環境が壊れないようにする
ための仕様です)。

### トークンが漏れた

https://pypi.org/manage/account/token/ で該当トークンを失効させ、
新しく作り直して `~/.pypirc` を更新します。

### `File already exists` と言われた

同じバージョン番号で 2 回上げようとしています。バージョンを上げてください。
