# ローカル開発手順（Windows）

## 初回セットアップ

```powershell
cd /path/to/symptoport
pip install -r requirements.txt
python create_user.py yourname yourpassword
```

## サーバー起動

```powershell
cd /path/to/symptoport
python -m uvicorn main:app --reload --port 8001
```

ブラウザで http://localhost:8001 を開く。

`--reload` をつけるとコード変更時に自動再起動。

## ユーザー追加

```powershell
python create_user.py 追加したいユーザー名 パスワード
```

## DB確認

```powershell
# 全ユーザー
sqlite3 data/health.db "SELECT id, username FROM users;"

# 特定日の記録
sqlite3 data/health.db "SELECT * FROM records WHERE date='2026-05-25';"

# 全記録
sqlite3 data/health.db "SELECT * FROM records ORDER BY date DESC LIMIT 20;"
```

sqlite3コマンドが無い場合: https://sqlite.org/download.html からDLするか、
Pythonで代用:

```powershell
python -c "import sqlite3; conn=sqlite3.connect('data/health.db'); [print(r) for r in conn.execute('SELECT * FROM records ORDER BY date DESC LIMIT 20')]"
```

## DB初期化（やり直し）

```powershell
Remove-Item data/health.db
python -m uvicorn main:app --reload --port 8001  # 起動時に自動再作成
```

---

## 本番環境セットアップ（Linux / systemd / Nginx）

付属の `memai_kanri.service` を用い、Linux（Ubuntu等）の `/opt/memai_kanri` ディレクトリへデプロイして本番稼働させる際の手順です。

### 1. 配置と権限の設定

アプリケーション一式を `/opt/memai_kanri` に配置し、Webサーバーの実行ユーザー（例: `www-data`）に所有権を変更します。データ保存用のディレクトリが書き込み可能である必要があります。

```bash
# ディレクトリの所有権を変更
sudo chown -R www-data:www-data /opt/memai_kanri
```

### 2. 仮想環境（venv）の作成とパッケージインストール

安全のため、`www-data` ユーザーの権限で仮想環境を構築し、必要なパッケージをインストールします。

```bash
cd /opt/memai_kanri

# www-data ユーザーとして仮想環境（venv）を作成
sudo -u www-data python3 -m venv venv

# 依存パッケージを仮想環境内にインストール
sudo -u www-data ./venv/bin/pip install -r requirements.txt
```

### 3. 初期ユーザーの作成

管理者（利用）ユーザーをデータベースへ登録します。

```bash
sudo -u www-data ./venv/bin/python create_user.py [希望するユーザー名] [希望するパスワード]
```

### 4. systemd サービスの設定

付属の `memai_kanri.service` をシステムに登録し、OS起動時の自動起動とプロセス管理を設定します。

```bash
# systemd設定ディレクトリにコピー
sudo cp memai_kanri.service /etc/systemd/system/

# systemdの設定をリロード
sudo systemctl daemon-reload

# サービスの有効化と起動
sudo systemctl enable memai_kanri.service
sudo systemctl start memai_kanri.service

# サービスが正常に稼働しているかステータスを確認
sudo systemctl status memai_kanri.service
```

### 5. リバースプロキシ（Nginx）の設定例

アプリケーションは `127.0.0.1:8001` で起動するため、Nginxなどを前に挟んでリバースプロキシ設定を行います。また、静的ファイルはNginxから直接配信するように設定することでパフォーマンスを向上させます。

`/etc/nginx/sites-available/memai_kanri` の設定例:

```nginx
# HTTP (80) から HTTPS (443) への自動リダイレクト設定
server {
    listen 80;
    server_name your-domain.com; # あなたのドメインを指定
    return 301 https://$host$request_uri;
}

# HTTPS (443) 設定例
server {
    listen 443 ssl;
    server_name your-domain.com; # あなたのドメインを指定

    # SSL証明書のパス（Let's Encryptを使用する場合の一般的な例）
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # 推奨されるセキュリティ設定
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # 静的ファイルの直接配信設定（Nginx側で配信して高速化）
    location /static/ {
        alias /opt/memai_kanri/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # FastAPIアプリ（Uvicorn）へのプロキシ設定
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Nginxの有効化と Let's Encrypt によるSSL証明書の取得手順

1.  **設定ファイルの有効化とテスト:**
    ```bash
    # シンボリックリンクの作成（未作成の場合）
    sudo ln -s /etc/nginx/sites-available/memai_kanri /etc/nginx/sites-enabled/

    # 設定ファイルの構文テスト
    sudo nginx -t

    # Nginxの再起動
    sudo systemctl restart nginx
    ```

2.  **Let's Encrypt (Certbot) を使用したSSL証明書の自動設定:**
    上記のSSL設定を手動で書く代わりに、最初はHTTP（80番ポート）の設定のみを書き、以下のツールを使うことで証明書の取得からNginxの設定書き換えまでをすべて自動で行うことも可能です。

    ```bash
    # CertbotとNginx用プラグインのインストール
    sudo apt update
    sudo apt install certbot python3-certbot-nginx -y

    # SSL証明書の自動取得とNginxの自動HTTPS設定を実行
    sudo certbot --nginx -d your-domain.com
    ```

---

## 環境変数の設定方法 (Ubuntu / Debian環境)

本アプリケーションでは、セキュリティ強化（セッション秘密鍵の管理、ボット保護など）のために複数の環境変数を利用します。

### 利用する環境変数一覧

| 環境変数名 | 役割 | 設定値の例 | 必須フラグ |
| :--- | :--- | :--- | :--- |
| `ENV` | 実行環境の指定 | `production`（本番） / `development`（開発） | 任意（本番運用時は `production` 推奨） |
| `SESSION_SECRET_KEY` | セッションCookieの暗号署名用秘密鍵 | `super-secret-random-string-12345` | **本番環境で必須** |
| `TURNSTILE_SITE_KEY` | Cloudflare Turnstile のサイトキー | `0x4AAAAAA...` (Cloudflareから取得) | ボット保護有効化時に必須 |
| `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile のシークレットキー | `0x4AAAAAA...` (Cloudflareから取得) | ボット保護有効化時に必須 |
| `APP_BASE_URL` | OGP・SNS共有用の絶対URL prefix | `https://symptoport.app` | OGP画像URLを正しく出力したい場合に必須 |

---

### 🛡️ Cloudflare Turnstile (ボット保護) キーの取得手順

1. [Cloudflare ダッシュボード](https://dash.cloudflare.com/) にログインします。
2. 左メニューから **「Turnstile」** を選択し、**「サイトの追加 (Add site)」** をクリックします。
3. 以下の情報を入力・選択します：
   * **サイト名:** 任意のわかりやすい名前（例: `SymptoPort`）
   * **ドメイン:** アプリを公開するドメイン名（例: `your-domain.com`）
   * **ウィジェットタイプ:** 「マネージド（非表示・自動検証）」（推奨）または「非インタラクティブ」
4. 登録が完了すると、**「サイトキー (Site Key)」** と **「シークレットキー (Secret Key)」** が発行されます。これらを上記の環境変数に設定します。

---

### ⚙️ Ubuntuでの環境変数設定方法

Ubuntuの本番環境において、環境変数を安全かつ永続的に設定・反映させるには、**「systemdの環境変数ファイル（EnvironmentFile）」** を使用するのが最もセキュアで推奨されるベストプラクティスです。

#### 1. 環境変数ファイル (`.env`) の作成

プロジェクトのディレクトリ内に、Git管理外となる `.env` ファイルを作成します。

```bash
# ファイルの新規作成・編集
sudo nano /opt/memai_kanri/.env
```

以下の形式でキーと値を記述します。

```ini
ENV=production
SESSION_SECRET_KEY=十分に長く推測されにくいランダムな英数字の文字列
TURNSTILE_SITE_KEY=あなたのTurnstileサイトキー
TURNSTILE_SECRET_KEY=あなたのTurnstileシークレットキー
```

ファイルの読み取り権限をWebサーバー実行ユーザー（`www-data`）のみに制限し、セキュリティを保護します。

```bash
# 所有者を変更
sudo chown www-data:www-data /opt/memai_kanri/.env

# 権限を所有者のみの読み書き(600)に設定
sudo chmod 600 /opt/memai_kanri/.env
```

#### 2. systemd サービスファイルの編集

サービス定義ファイル `/etc/systemd/system/memai_kanri.service` を開き、作成した環境変数ファイル（`.env`）を読み込む設定を追加します。

```bash
sudo nano /etc/systemd/system/memai_kanri.service
```

`[Service]` セクションの中に `EnvironmentFile=/opt/memai_kanri/.env` を追記します。

```ini
[Unit]
Description=からだの天気図
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/memai_kanri
ExecStart=/opt/memai_kanri/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001
# 👇 環境変数ファイルを読み込む設定を追記
EnvironmentFile=/opt/memai_kanri/.env
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### 3. 設定の反映とサービスの再起動

systemdの設定をリロードし、アプリサービスを再起動して環境変数を適用します。

```bash
# systemd設定のリロード
sudo systemctl daemon-reload

# アプリの再起動
sudo systemctl restart memai_kanri.service

# サービスが正常に稼働しているかステータスを確認
sudo systemctl status memai_kanri.service
```

---

#### 💡 (参考) 一時的または手動起動時にコマンドラインからセットする場合

テスト目的などで手動でUvicornサーバーを起動する際は、コマンドの直前で環境変数を指定して実行します。

```bash
ENV=production SESSION_SECRET_KEY="my-test-secret" TURNSTILE_SITE_KEY="xxx" TURNSTILE_SECRET_KEY="yyy" ./venv/bin/uvicorn main:app --port 8001
```

---

## OGP画像の再生成

SNS共有プレビュー用画像（`static/og-image.png` / `static/og-image-app.png`）を更新する場合:

```powershell
python static/generate_og.py
```

依存: `Pillow`（`requirements.txt` に含まれる）

---

## 変更履歴

### v0.6.0 — 2026-05-29
- **居住地設定（全国48地域）**: 47都道府県庁所在地および北海道・釧路から居住地を選択可能に。地域ごとの緯度・経度に基づいて Open-Meteo API から正確に気象データを自動取得・計算・キャッシュするよう拡張
- **服薬チェック機能**: 朝、昼、夜、寝る前、全体から記録したい時間帯を個別に設定可能。記録画面（お薬トグルボタン💊）および印刷レポート（詳細データ行最下部への服薬状況✓の美しいプロット）を追加
- **入力画面の1列化（縦並び）**: 各時間帯（朝、昼、夜、全体）の2列表示を廃止し、上から下への1列構成に変更。スマホ画面でもスコアボタンが絶対に折り返さず綺麗に一行表示されるようにUI/レイアウトを改善
- **WBGTマイナス（0未満）の無効化処理**: 暑さ指数（WBGT）が冬場などで0未満（マイナス）になった場合、自動・手動ともに「取得不可（`-` / `None`）」として扱い、グラフや保存データからも適切に除外するようロジックを変更
- **印刷画面の気温(Ta)2軸プロット**: 印刷およびPDFレポートの折れ線グラフにおいて、従来のWBGT（実線・左軸）に加え、気温（Ta）の推移を薄い赤色の点線（右軸スケール）として重ねて描画するようChart.jsの設定を拡張
- **データバックアップ・リストア機能**: ユーザーデータを丸ごとJSONファイルとしてエクスポートできる機能と、警告ダイアログを経てSQLiteトランザクション安全にデータを上書き復旧（インポート）できる機能を設定画面に追加
- **免責事項・注意事項の明記**: 本アプリが医療機器ではない旨、および暑さ指数(WBGT)が環境省の公式値とは異なり簡易計算式に基づく疑似値（参考値）である旨を、ヘルプガイド、記録画面、および印刷用レポート画面（画面表示＆A4紙出力フッター）のそれぞれに上品かつ明確に追記


### v0.5.0 — 2026-05-29
- **アプリ名変更**: カラダノート → **SymptoPort**（からだの天気図）
- **PWA対応**: manifest.json・Service Worker・アプリアイコン（8サイズ）を追加。ホーム画面インストール対応
- **PWAインストールボタン**: LP・アプリヘッダーに `beforeinstallprompt` ベースのインストールボタンを実装
- **ランディングページ** (`/lp`): 未ログイン時のトップ画面として新設。競合調査に基づく構成
- **印刷レポート** (`/print`): 日付範囲指定・症状×時間帯テーブル・印刷用CSS対応ページを追加
- **OGP / SNS共有**: Open Graph・Twitter Card メタタグ、OG画像（1200×630px）を追加
- **新規ルート追加**: `/register`・`/privacy`・`/terms`・`/contact`・`/sw.js`
- **Service Worker**: Cache First（静的）/ Network First（ページ）/ Network Only（API）戦略で実装
- **未ログイン動線**: `/` アクセス時にゲストユーザーを `/lp` にリダイレクト
- **DB追加**: `get_records_for_range` / `get_notes_for_range` / `get_user_by_username_by_id`
- **依存追加**: `Pillow>=10.0.0`（OGP画像生成用）

### v0.4.0 — 2026-05-25
- 自動保存（オートセーブ）機能の追加
- 新規登録時の症状選択機能の追加

### v0.3.0 — 2026-05-24
- 開発環境での Turnstile チェック失敗を解消
- 逆スコア設定と配色自動反転機能を追加
- 使い方ガイドページ (`/help`) を追加

### v0.2.0 — 2026-05-23
- セキュリティ強化（ログイン画面に Turnstile 追加、各種バリデーション、セッション期限設定）
- SessionMiddleware によるセッション管理にリファクタリング
- Cloudflare Turnstile による新規登録時のボット対策を実装
