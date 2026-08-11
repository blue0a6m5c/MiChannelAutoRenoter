# MiChannelAutoRenoter

Misskey のグローバルタイムラインまたはアンテナタイムラインから、指定したキーワードやハッシュタグを含む投稿を取得し、決められたチャンネルへ Renote するための自動化スクリプトです。

GitHub リポジトリ: https://github.com/blue0a6m5c/MiChannelAutoRenoter

## まずは試す

依存関係は Python 標準ライブラリのみです。

```bash
git clone https://github.com/blue0a6m5c/MiChannelAutoRenoter.git
cd MiChannelAutoRenoter
cp .env.example .env
python main.py --once --dry-run
```

## 設定項目

`.env` で次の項目を設定します。

- `MISSKEY_API_BASE_URL`: Misskey インスタンスの URL
- `MISSKEY_ACCESS_TOKEN`: API トークン
- `MISSKEY_CHANNEL_ID`: Renote 先のチャンネル ID
- `MISSKEY_MODE`: `global` または `antenna`
- `MISSKEY_ANTENNA_ID`: アンテナモード時に使用するアンテナ ID
- `MISSKEY_KEYWORDS`: カンマ区切りのキーワードやハッシュタグ
- `MISSKEY_KEYWORDS_FILE`: キーワードを外部ファイルから読み込む場合のパス（例: `keywords.txt`）
- `MISSKEY_FETCH_LIMIT`: 1回に取得する投稿数
- `MISSKEY_POLL_INTERVAL_SECONDS`: ポーリング間隔
- `MISSKEY_STATE_FILE`: 重複投稿を避けるための状態ファイル
- `MISSKEY_MEDIA_MODE`: `any` / `required` / `absent`
- `MISSKEY_SKIP_RENOTES`: Renote 投稿を拾わないかどうか（推奨: `true`）
- `MISSKEY_IGNORE_SELF`: 自分の投稿を拾わないかどうか（推奨: `true`）
- `MISSKEY_SELF_USER_ID`: 自分の Misskey ユーザー ID。`ignore_self` を有効にする場合に設定
- `MISSKEY_LOG_LEVEL`: ログの詳細度。通常運用は `INFO`、詳細確認時は `DEBUG`

`MISSKEY_CHANNEL_ID` は必須です。未設定の場合は起動時にエラーとして終了し、通常タイムラインへ誤って Renote することを防ぎます。

## 実行方法

### 1回だけ実行

```bash
python main.py --once --dry-run
```

### 常時監視

```bash
python main.py
```

## Linux サーバーでの運用

Linux サーバーで常時実行させるのが自然です。Ubuntu では、`systemd` を使うと起動時自動開始・再起動・ログ管理がしやすいです。

### 1. Ubuntu に Python を入れる

```bash
sudo apt update
sudo apt install -y python3 python3-pip git
```

### 2. このリポジトリをサーバーに置く

```bash
cd /home/your-user
sudo git clone https://github.com/blue0a6m5c/MiChannelAutoRenoter.git
cd MiChannelAutoRenoter
cp .env.example .env
```

### 3. `.env` を編集する

```bash
nano .env
```

次の項目を必ず埋めてください。

- `MISSKEY_API_BASE_URL`
- `MISSKEY_ACCESS_TOKEN`
- `MISSKEY_CHANNEL_ID`
- `MISSKEY_KEYWORDS` または `MISSKEY_KEYWORDS_FILE`

### 4. 動作確認する

```bash
python3 main.py --once --dry-run
```

### 5. systemd サービスを登録する

サンプルの unit ファイルは [michannel-autorenoter.service.example](michannel-autorenoter.service.example) です。実際のパスに合わせて編集します。

```bash
sudo cp michannel-autorenoter.service.example /etc/systemd/system/michannel-autorenoter.service
sudo nano /etc/systemd/system/michannel-autorenoter.service
```

`WorkingDirectory` と `ExecStart` のパスを、自分の環境に合わせて変更してください。

```bash
sudo systemctl daemon-reload
sudo systemctl enable michannel-autorenoter
sudo systemctl start michannel-autorenoter
```

### 6. 状態確認

```bash
sudo systemctl status michannel-autorenoter
sudo journalctl -u michannel-autorenoter -f
```

### 7. 再起動や停止

```bash
sudo systemctl restart michannel-autorenoter
sudo systemctl stop michannel-autorenoter
```

`main.py` は標準出力にログを出すため、`journalctl` で追跡できます。

## 補足

- まずは `--dry-run` で動作確認してください。
- アンテナ機能を使う場合は、`MISSKEY_MODE=antenna` と `MISSKEY_ANTENNA_ID` を設定してください。
- もし Misskey の API バージョン差異でエンドポイント名が変わっている場合は、必要に応じて [main.py](main.py) の `fetch_notes()` を調整してください。
- 既定では `state.json` に見た投稿 ID を保存し、重複 Renote を避けます。
