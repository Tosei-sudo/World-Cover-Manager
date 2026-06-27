# World Cover Manager

衛星による全世界陸域撮影プロジェクトの進捗管理・次オーダー決定UIです。

## 機能

| 機能 | 説明 |
|------|------|
| グローバルタイルグリッド | 10°×10°（可変）の緯度経度グリッドで陸域を管理 |
| カバレッジ地図 | Leaflet.js ベースのインタラクティブ世界地図。ステータスごとに色分け表示 |
| テーブルビュー | タイル一覧。ステータス・座標でフィルタリング可能 |
| オーダー管理 | 撮影オーダーの作成・ステータス更新・削除 |
| 次オーダー提案 | 未撮影陸地タイルを優先度順（赤道近傍優先）でリスト表示 |
| モックモード | バックエンド不要でブラウザ単体動作（デモ・開発用） |

## アーキテクチャ

```
World-Cover-Manager/
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI アプリ（フロントも配信）
│   │   ├── database.py     # SQLAlchemy エンジン（DB 切替対応）
│   │   ├── models.py       # ORM モデル（Tile, Order）
│   │   ├── schemas.py      # Pydantic スキーマ
│   │   └── routers/
│   │       ├── tiles.py    # GET/PATCH /api/tiles
│   │       ├── orders.py   # CRUD /api/orders
│   │       └── stats.py    # /api/stats/coverage, /api/stats/next-targets
│   ├── init_db.py          # DB 初期化（タイル生成・サンプルデータ挿入）
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── css/style.css
    └── js/
        ├── config.js       # MOCK_MODE スイッチ
        ├── mock-data.js    # インメモリモックデータ
        ├── api.js          # Real / Mock API を同一インタフェースで提供
        ├── map-view.js     # Leaflet マップ描画
        └── app.js          # アプリケーションコントローラ
```

## クイックスタート

### 前提条件

- Python 3.11 以上
- `pip`

### 1. 依存ライブラリのインストール

```bash
cd backend
pip install -r requirements.txt
```

### 2. データベースの初期化

```bash
python init_db.py
```

オプション:

```bash
python init_db.py --tile-size 5   # 5°×5° グリッド（より細かい分割）
python init_db.py --reset          # テーブルを一度削除して再作成
```

### 3. サーバー起動

```bash
uvicorn app.main:app --reload
```

ブラウザで http://localhost:8000 を開くと地図UIが表示されます。

API ドキュメント（Swagger UI）は http://localhost:8000/docs で確認できます。

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

| Method | Path | 説明 |
|--------|------|------|
| GET | `/api/tiles` | タイル一覧（`?is_land=true&status=NOT_STARTED` でフィルタ可） |
| GET | `/api/tiles/{id}` | タイル詳細 |
| PATCH | `/api/tiles/{id}` | タイル更新（ステータス変更など） |
| GET | `/api/orders` | オーダー一覧 |
| POST | `/api/orders` | オーダー作成 |
| GET | `/api/orders/{id}` | オーダー詳細 |
| PATCH | `/api/orders/{id}` | オーダー更新（ステータス進行など） |
| DELETE | `/api/orders/{id}` | オーダー削除 |
| GET | `/api/stats/coverage` | カバレッジ統計 |
| GET | `/api/stats/next-targets` | 次撮影候補タイル一覧（`?limit=10`） |

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
| DB | SQLite（デフォルト）/ Oracle / PostgreSQL / その他 SQLAlchemy 対応 DB |
| フロントエンド | Vanilla JavaScript (ES2020), Leaflet.js 1.9, OpenStreetMap |
| 依存関係 | バックエンド: `requirements.txt` 参照。フロントエンド: CDN のみ |
