# MiChannelAutoRenoter

Misskey のグローバルタイムラインまたはアンテナタイムラインから、指定したキーワードやハッシュタグを含む投稿を取得し、決められたチャンネルへ Renote するための小さな自動化スクリプトです。

## 使い方

1. 依存関係は Python 標準ライブラリのみです。
2. `.env.example` を参考に `.env` を作成します。
3. 1回だけ実行する場合:

```bash
python main.py --once --dry-run
```

4. 常時監視する場合:

```bash
python main.py
```

## 設定項目

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

## Linux サーバーでの運用

はい、Linux サーバーで常時実行させるのが自然です。Ubuntu では、`systemd` を使うと起動時自動開始・再起動・ログ管理がしやすいです。

### 1. Ubuntu に Python を入れる

```bash
sudo apt update
sudo apt install -y python3 python3-pip git
```

### 2. このリポジトリをサーバーに置く

```bash
cd /home/your-user
sudo git clone https://github.com/your-user/MiChannelAutoRenoter.git
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
