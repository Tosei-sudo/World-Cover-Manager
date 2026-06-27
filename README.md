# World Cover Manager

衛星による全世界陸域撮影プロジェクトの進捗管理・次オーダー決定UIです。

TLE軌道情報をもとにパス（通過）を自動計算し、実際の観測機会に基づいて次の撮影オーダーを提案します。

## 機能

| 機能 | 説明 |
|------|------|
| グローバルタイルグリッド | 10°×10°（可変）の緯度経度グリッドで陸域を管理 |
| カバレッジ地図 | Leaflet.js ベースのインタラクティブ世界地図。ステータスごとに色分け表示 |
| テーブルビュー | タイル一覧。ステータス・座標でフィルタリング可能 |
| 衛星管理 | TLE・観測幅・センサーモード等を登録・編集 |
| 自動パス計算 | TLE から SGP4 で軌道を伝播し、各タイルへの通過時刻を自動算出 |
| 地上トラック表示 | 衛星の6時間予測地上軌跡を地図上に描画 |
| 撮影機会ビュー | 未撮影タイルへの通過機会を時刻順にランキング表示 |
| オーダー管理 | 撮影オーダーの作成・ステータス更新・削除 |
| モックモード | バックエンド不要でブラウザ単体動作（デモ・開発用） |

## アーキテクチャ

```
World-Cover-Manager/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI アプリ（フロントも配信）
│   │   ├── database.py          # SQLAlchemy エンジン（DB 切替対応）
│   │   ├── models.py            # ORM モデル（Tile, Satellite, OrbitalPass, Order）
│   │   ├── schemas.py           # Pydantic スキーマ
│   │   ├── routers/
│   │   │   ├── tiles.py         # GET/PATCH /api/tiles
│   │   │   ├── satellites.py    # CRUD /api/satellites（TLE管理）
│   │   │   ├── passes.py        # /api/passes, compute-passes, ground-track, pass-status
│   │   │   ├── orders.py        # CRUD /api/orders
│   │   │   └── stats.py         # /api/stats/coverage, next-targets, opportunities
│   │   └── services/
│   │       ├── orbit.py         # skyfield + SGP4 によるパス計算ロジック
│   │       └── auto_pass.py     # 自動パス計算（鮮度チェック・バックグラウンドタスク）
│   ├── init_db.py               # DB 初期化（タイル生成・サンプル衛星データ挿入）
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── css/style.css
    └── js/
        ├── config.js            # MOCK_MODE スイッチ
        ├── mock-data.js         # インメモリモックデータ
        ├── api.js               # Real / Mock API を同一インタフェースで提供
        ├── map-view.js          # Leaflet マップ描画・地上トラック表示
        └── app.js               # アプリケーションコントローラ
```

## クイックスタート

### 前提条件

- Python 3.11 以上

### 1. 仮想環境の作成とライブラリのインストール

```bash
cd backend
python -m venv .venv
```

仮想環境を有効化します。

```bash
# Linux / macOS
source .venv/bin/activate

# Windows（PowerShell）
.venv\Scripts\Activate.ps1
```

有効化後、依存ライブラリをインストールします。

```bash
pip install -r requirements.txt
```

> **閉域網環境でのインストール**  
> インターネット接続のある端末で `pip download -r requirements.txt -d ./wheels` を実行して wheel ファイルをダウンロードしておき、閉域網側で `pip install --no-index --find-links=./wheels -r requirements.txt` としてインストールしてください。

### 2. データベースの初期化

```bash
python init_db.py
```

サンプル衛星（Sentinel-2A/B、Landsat 9）と陸域タイルが作成されます。

オプション:

```bash
python init_db.py --reset          # テーブルを一度削除して再作成
python init_db.py --tile-size 2.5  # タイルサイズを手動指定（度）
```

**タイルサイズの自動決定**

`--tile-size` を省略すると、`_SAMPLE_SATELLITES` に登録されている衛星の中で最も狭い `swath_width_km` を基準に、1パスで必ず全タイルをカバーできる最大のきりの良いサイズを自動選択します。

```
例: Landsat 9 (185 km) と Sentinel-2 (290 km) が登録されている場合
  → 最小観測幅 185 km ÷ 111 km/° ≈ 1.67°
  → きりの良い最大値: 1.5°
  → 1.5°×1.5° グリッドを生成
```

衛星の追加登録後に `swath_width_km` が現在のタイルサイズより狭い場合、
衛星カードに警告が表示されます。その際は `--reset` で再初期化してください。

> **TLE の更新について**  
> サンプルTLEは初期化時点のものです。本番運用では社内システムや CelesTrak 等から最新TLEを取得し、衛星管理画面（Satellites タブ）で更新してください。

### 3. サーバー起動

仮想環境が有効な状態で実行してください。

```bash
uvicorn app.main:app --reload
```

ブラウザで http://localhost:8000 を開くと地図UIが表示されます。

API ドキュメント（Swagger UI）は http://localhost:8000/docs で確認できます。

### 4. 仮想環境の移送（閉域網への持ち込み）

インターネット接続のある環境で仮想環境を構築し、`backend/` ディレクトリごと閉域網端末にコピーするだけで動作します。

```
backend/
├── .venv/          ← venv ごとコピー
├── app/
├── init_db.py
└── requirements.txt
```

Python のバージョンが移送元・移送先で一致している必要があります。異なる場合は上記の wheel ファイル方式を使用してください。

---

## パス自動計算の仕組み

パス計算は**手動操作不要**で自動的に行われます。

| トリガー | 動作 |
|----------|------|
| 衛星の新規登録 | 登録直後にバックグラウンドでパスを計算 |
| TLE の更新（PATCH） | 旧パスを削除し、バックグラウンドで再計算 |
| 撮影機会・次候補の取得 | アクティブ衛星のパスが古い場合にリクエスト内で自動再計算 |

**鮮度の定義:** 最新の `pass_end` が `現在 + 24時間` より前になると「期限切れ」とみなし、168時間分（7日間）を再計算します。

衛星カードには現在のパスの有効期限と件数がリアルタイム表示されます。手動で強制再計算したい場合は「Recompute now」ボタンを使用します。

---

## 閉域網（オフライン）での使用

フロントエンドは外部ネットワークに依存しません。

- **Leaflet** (`vendor/leaflet/`) は npm からダウンロード済みのファイルをバンドルしています
- **背景地図タイル** はデフォルト無効（`CONFIG.TILE_SERVER_URL = null`）

社内タイルサーバー（XYZ/スリッピーマップ形式）がある場合は `frontend/js/config.js` を編集してください:

```js
TILE_SERVER_URL: "https://your-internal-tileserver/{z}/{x}/{y}.png",
TILE_ATTRIBUTION: "© Your Tile Server",
```

インターネット接続がある環境で OSM を使いたい場合:

```js
TILE_SERVER_URL: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
TILE_ATTRIBUTION: "© OpenStreetMap contributors",
```

---

## モックモード（バックエンド不要）

`frontend/index.html` をブラウザで直接開くか、URL に `?mock=1` を付けると、
バックエンドなしで全機能を体験できます。

```
http://localhost:8000/?mock=1
# または index.html をダブルクリック → ブラウザで開く
```

モックモードは `frontend/js/config.js` の `MOCK_MODE` フラグで恒久的に設定できます。

```js
const CONFIG = {
  MOCK_MODE: true,   // ← ここを true にする
  ...
};
```

---

## データベース切替

`DATABASE_URL` 環境変数で接続先を変更できます（SQLAlchemy 対応 DB ならすべて使用可能）。

```bash
# SQLite（デフォルト）
export DATABASE_URL="sqlite:///./world_cover.db"

# PostgreSQL
export DATABASE_URL="postgresql://user:pass@host:5432/world_cover"

# Oracle
export DATABASE_URL="oracle+oracledb://user:pass@host:1521/?service_name=XE"
```

---

## API エンドポイント

### タイル

| Method | Path | 説明 |
|--------|------|------|
| GET | `/api/tiles` | タイル一覧（`?is_land=true&status=NOT_STARTED` でフィルタ可） |
| GET | `/api/tiles/{id}` | タイル詳細 |
| PATCH | `/api/tiles/{id}` | タイル更新（ステータス変更など） |

### 衛星

| Method | Path | 説明 |
|--------|------|------|
| GET | `/api/satellites` | 衛星一覧（`?is_active=true` でフィルタ可） |
| POST | `/api/satellites` | 衛星登録（TLE検証・バックグラウンドパス計算を自動実行） |
| GET | `/api/satellites/{id}` | 衛星詳細 |
| PATCH | `/api/satellites/{id}` | 衛星更新（TLE変更時は自動再計算） |
| DELETE | `/api/satellites/{id}` | 衛星削除（パスも連鎖削除） |

### パス

| Method | Path | 説明 |
|--------|------|------|
| GET | `/api/passes` | パス一覧（`?satellite_id=1&tile_id=2&limit=200` でフィルタ可） |
| POST | `/api/satellites/{id}/compute-passes` | パス強制再計算（手動オーバーライド） |
| GET | `/api/satellites/{id}/pass-status` | パス鮮度情報（有効期限・件数・再計算要否） |
| GET | `/api/satellites/{id}/ground-track` | 地上軌跡（`?hours=6&step_s=120`） |

### オーダー

| Method | Path | 説明 |
|--------|------|------|
| GET | `/api/orders` | オーダー一覧 |
| POST | `/api/orders` | オーダー作成 |
| GET | `/api/orders/{id}` | オーダー詳細 |
| PATCH | `/api/orders/{id}` | オーダー更新（ステータス進行など） |
| DELETE | `/api/orders/{id}` | オーダー削除 |

### 統計・提案

| Method | Path | 説明 |
|--------|------|------|
| GET | `/api/stats/coverage` | カバレッジ統計（完了率・オーダー数など） |
| GET | `/api/stats/next-targets` | 次撮影候補タイル一覧。パスが早い順に返す（`?limit=10`） |
| GET | `/api/stats/opportunities` | 未撮影タイルへの通過機会を時刻順にランキング表示（`?limit=20`） |

---

## オーダーのステータスフロー

```
PLANNED → SCHEDULED → IN_PROGRESS → COMPLETED
                               └──────→ FAILED
                               └──────→ CANCELLED
```

オーダーが **COMPLETED** になると、紐付けられたタイルのステータスが自動的に
`COMPLETED` に更新され、カバレッジカウンタがインクリメントされます。

---

## タイルの陸地分類

`init_db.py` の `_classify()` 関数で大陸バウンディングボックスに基づいた
ヒューリスティックを使用しています。

より高精度な陸地分類が必要な場合は、`geopandas` と `naturalearth_lowres` を
使ったポリゴン交差判定に置き換えることができます:

```python
import geopandas as gpd
world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
```

---

## 技術スタック

| レイヤ | 技術 |
|--------|------|
| バックエンド | Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| 軌道計算 | skyfield 1.49, SGP4, NumPy（ベクトル化処理で高速化） |
| DB | SQLite（デフォルト）/ Oracle / PostgreSQL / その他 SQLAlchemy 対応 DB |
| フロントエンド | Vanilla JavaScript (ES2020), Leaflet.js 1.9, OpenStreetMap |
| 依存関係 | バックエンド: `requirements.txt` 参照。フロントエンド: ベンダーバンドル済み（外部通信不要） |
