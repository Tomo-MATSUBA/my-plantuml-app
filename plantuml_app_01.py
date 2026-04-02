"""
PlantUML Generator - Streamlit Web版 with Ace Vim Editor
左カラム: Ace Editor (Vim モード) / 右カラム: プレビュー

必要なもの:
  pip install streamlit pillow requests streamlit-ace

起動方法:
  streamlit run plantuml_app.py
"""

import streamlit as st
import subprocess
import os
import zlib
import tempfile
import shutil
import sys
from pathlib import Path

try:
    from streamlit_ace import st_ace
    HAS_ACE = True
except ImportError:
    HAS_ACE = False

try:
    from PIL import Image
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ─────────────────────────────────────────────────────────────
# PlantUML URL エンコード
# ─────────────────────────────────────────────────────────────
def _e6(b):
    if b < 10: return chr(48 + b)
    b -= 10
    if b < 26: return chr(65 + b)
    b -= 26
    if b < 26: return chr(97 + b)
    return "-" if b - 26 == 0 else "_"

def _a3(b1, b2, b3):
    return (
        _e6((b1 >> 2) & 63)
        + _e6((((b1 & 3) << 4) | (b2 >> 4)) & 63)
        + _e6((((b2 & 0xF) << 2) | (b3 >> 6)) & 63)
        + _e6(b3 & 63)
    )

def encode_plantuml(text: str) -> str:
    comp = zlib.compress(text.encode("utf-8"))
    out, i = "", 0
    while i < len(comp):
        out += _a3(
            comp[i],
            comp[i + 1] if i + 1 < len(comp) else 0,
            comp[i + 2] if i + 2 < len(comp) else 0,
        )
        i += 3
    return out

def plantuml_url(code: str, fmt: str = "png") -> str:
    return f"https://www.plantuml.com/plantuml/{fmt}/~1{encode_plantuml(code)}"

# ─────────────────────────────────────────────────────────────
# テンプレート
# ─────────────────────────────────────────────────────────────
TEMPLATES = {
    "シーケンス図": """\
@startuml
title ログイン処理

actor ユーザー as user
participant "Webブラウザ" as browser
participant "サーバー" as server
database "データベース" as db

user -> browser : ログイン情報入力
browser -> server : POST /login
server -> db : ユーザー検索
db --> server : ユーザーデータ
server -> server : パスワード検証

alt 認証成功
    server --> browser : 200 OK + セッション
    browser --> user : ダッシュボード表示
else 認証失敗
    server --> browser : 401 Unauthorized
    browser --> user : エラーメッセージ
end
@enduml""",

    "クラス図": """\
@startuml
title ショッピングカート

class 顧客 {
  +id: int
  +名前: string
  +メール: string
  +注文する(): void
}
class 注文 {
  +id: int
  +注文日: date
  +合計金額: int
  +確定する(): bool
}
class 商品 {
  +id: int
  +名前: string
  +価格: int
  +在庫数: int
}
class カート {
  +商品追加(商品): void
  +商品削除(商品): void
  +合計計算(): int
}

顧客 "1" --> "0..*" 注文 : 作成
注文 "1" *-- "1..*" 商品 : 含む
顧客 "1" -- "1" カート : 持つ
@enduml""",

    "アクティビティ図": """\
@startuml
title 注文処理フロー
start
:注文受付;
:在庫確認;
if (在庫あり?) then (yes)
  :決済処理;
  if (決済成功?) then (yes)
    :出荷処理;
    :配送;
    :完了通知送信;
  else (no)
    :決済エラー通知;
    stop
  endif
else (no)
  :在庫不足通知;
  stop
endif
:注文完了;
stop
@enduml""",

    "ユースケース図": """\
@startuml
title ECサイト ユースケース
left to right direction

actor 顧客 as customer
actor 管理者 as admin

rectangle ECサイト {
  usecase "商品検索" as UC1
  usecase "カートに追加" as UC2
  usecase "注文する" as UC3
  usecase "決済処理" as UC4
  usecase "注文管理" as UC5
  usecase "在庫管理" as UC6
}

customer --> UC1
customer --> UC2
customer --> UC3
UC3 ..> UC4 : <<include>>
admin --> UC5
admin --> UC6
@enduml""",

    "ERダイアグラム": """\
@startuml
title データベース設計

entity "users" {
  * id : INT <<PK>>
  --
  * name : VARCHAR(100)
  * email : VARCHAR(255)
  * created_at : DATETIME
}
entity "products" {
  * id : INT <<PK>>
  --
  * name : VARCHAR(200)
  * price : DECIMAL(10,2)
  * stock : INT
}
entity "orders" {
  * id : INT <<PK>>
  --
  * user_id : INT <<FK>>
  * total : DECIMAL(10,2)
  * status : VARCHAR(20)
}
entity "order_items" {
  * id : INT <<PK>>
  --
  * order_id : INT <<FK>>
  * product_id : INT <<FK>>
  * quantity : INT
}

users ||--o{ orders : "作成"
orders ||--|{ order_items : "含む"
products ||--o{ order_items : "参照"
@enduml""",

    "コンポーネント図": """\
@startuml
title マイクロサービス構成

package "フロントエンド" {
  [Webアプリ]
  [モバイルアプリ]
}
package "APIゲートウェイ" {
  [Nginx]
  [認証サービス]
}
package "バックエンド" {
  [ユーザーサービス]
  [商品サービス]
  [注文サービス]
}
package "データストア" {
  database "UserDB"
  database "ProductDB"
  database "OrderDB"
}

[Webアプリ] --> [Nginx]
[モバイルアプリ] --> [Nginx]
[Nginx] --> [認証サービス]
[Nginx] --> [ユーザーサービス]
[Nginx] --> [商品サービス]
[Nginx] --> [注文サービス]
[ユーザーサービス] --> UserDB
[商品サービス] --> ProductDB
[注文サービス] --> OrderDB
@enduml""",

    "マインドマップ": """\
@startmindmap
title Python学習ロードマップ
* Python
** 基礎
*** 変数・データ型
*** 条件分岐・ループ
*** 関数
** 中級
*** クラス・OOP
*** ファイル操作
*** 例外処理
** ライブラリ
*** NumPy
*** Pandas
*** Matplotlib
** フレームワーク
*** Django
*** FastAPI
@endmindmap""",

    "ガントチャート": """\
@startgantt
title 開発スケジュール
Project starts 2025-04-01
[要件定義] lasts 10 days
[基本設計] lasts 14 days
[基本設計] starts at [要件定義]'s end
[詳細設計] lasts 14 days
[詳細設計] starts at [基本設計]'s end
[開発] lasts 21 days
[開発] starts at [詳細設計]'s end
[テスト] lasts 14 days
[テスト] starts at [開発]'s end
[リリース] lasts 7 days
[リリース] starts at [テスト]'s end
@endgantt""",

    "新規（空白）": "@startuml\n\n' ここにコードを書く\n\n@enduml",
}

# ─────────────────────────────────────────────────────────────
# jar / Java ユーティリティ
# ─────────────────────────────────────────────────────────────
JAR_NAME = "plantuml.jar"

def find_jar():
    candidates = [
        Path(__file__).parent / JAR_NAME,
        Path.cwd() / JAR_NAME,
        Path.home() / JAR_NAME,
    ]
    for p in candidates:
        if p.is_file() and p.stat().st_size > 10_000:
            return str(p)
    return None

def java_cmd():
    if sys.platform.startswith("win"):
        return shutil.which("javaw") or "javaw"
    return shutil.which("java") or "java"

def subprocess_kwargs():
    if not sys.platform.startswith("win"):
        return {}
    try:
        import subprocess as sp
        si = sp.STARTUPINFO()
        si.dwFlags |= sp.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        return {
            "creationflags": getattr(sp, "CREATE_NO_WINDOW", 0),
            "startupinfo": si,
        }
    except Exception:
        return {}

# ─────────────────────────────────────────────────────────────
# レンダリング
# ─────────────────────────────────────────────────────────────
def render_local(code, jar_path, fmt="png"):
    tmp = tempfile.mkdtemp(prefix="plantuml_st_")
    try:
        puml = os.path.join(tmp, "diagram.puml")
        out_file = os.path.join(tmp, f"diagram.{fmt}")
        with open(puml, "w", encoding="utf-8") as f:
            f.write(code)
        kw = {k: v for k, v in subprocess_kwargs().items() if v is not None}
        r = subprocess.run(
            [java_cmd(), "-jar", jar_path, f"-t{fmt}", "-charset", "UTF-8", "-o", tmp, puml],
            capture_output=True, text=True, timeout=25, **kw
        )
        if r.returncode != 0 or not os.path.isfile(out_file):
            return None
        with open(out_file, "rb") as f:
            return f.read()
    except Exception:
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def render_remote(code, fmt="png"):
    if not HAS_REQUESTS:
        return None
    try:
        url = plantuml_url(code, fmt)
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.content
        return None
    except Exception:
        return None

def get_diagram(code, fmt="png"):
    jar = find_jar()
    if jar:
        data = render_local(code, jar, fmt)
        if data:
            return data, "local"
    data = render_remote(code, fmt)
    if data:
        return data, "remote (plantuml.com)"
    return None, "error"

# ─────────────────────────────────────────────────────────────
# Streamlit アプリ
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PlantUML Generator",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
    background: #0d1117;
    color: #e6edf3;
    font-family: 'Segoe UI', system-ui, sans-serif;
}
[data-testid="stHeader"] { display: none; }
[data-testid="stSidebar"] { background: #161b22; border-right: 1px solid #30363d; }
[data-testid="stSelectbox"] > div > div {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    color: #e6edf3 !important;
}
button[kind="primary"] {
    background: #238636 !important;
    border: none !important;
    color: white !important;
}
button[kind="primary"]:hover { background: #2ea043 !important; }
[data-testid="stImage"] img { border-radius: 8px; max-width: 100%; }
code { background: #161b22 !important; color: #58a6ff !important; }
[data-testid="stDownloadButton"] button {
    background: #1f6feb !important;
    color: white !important;
    border: none !important;
}
hr { border-color: #30363d !important; }
[data-testid="stHorizontalBlock"] { gap: 1rem; }
.app-header {
    background: linear-gradient(90deg, #161b22, #0d1117);
    border-bottom: 1px solid #30363d;
    padding: 12px 20px;
    margin: -1rem -1rem 1rem -1rem;
    display: flex;
    align-items: center;
    gap: 12px;
}
.app-header h1 { margin: 0; font-size: 1.4rem; color: #58a6ff; }
.app-header .badge {
    background: #238636;
    color: white;
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 12px;
    font-weight: bold;
}
.render-source { font-size: 0.75rem; color: #8b949e; margin-top: 4px; }
.info-bar {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 0.8rem;
    color: #8b949e;
    margin-bottom: 8px;
}
.vim-hint {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 0.75rem;
    color: #8b949e;
    font-family: 'Courier New', monospace;
    margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)

# ヘッダー
jar_status = "✅ jar検出" if find_jar() else "🌐 クラウドモード"
jar_color  = "#3fb950" if find_jar() else "#e3b341"
st.markdown(f"""
<div class="app-header">
  <span style="font-size:1.8rem">📐</span>
  <h1>PlantUML Generator</h1>
  <span class="badge">Vim Editor</span>
  <span style="margin-left:auto; font-size:0.8rem; color:{jar_color};">{jar_status}</span>
</div>
""", unsafe_allow_html=True)

# セッション初期化
if "code" not in st.session_state:
    st.session_state.code = TEMPLATES["シーケンス図"]
if "selected_tpl" not in st.session_state:
    st.session_state.selected_tpl = "シーケンス図"
if "auto_preview" not in st.session_state:
    st.session_state.auto_preview = True
if "ace_key" not in st.session_state:
    # st_ace の key を変えることでテンプレート変更時に強制再マウント
    st.session_state.ace_key = 0

# サイドバー
with st.sidebar:
    st.markdown("### ⚙️ 設定")
    st.session_state.auto_preview = st.toggle(
        "自動プレビュー",
        value=st.session_state.auto_preview
    )

    st.markdown("---")
    st.markdown("### 📁 ファイル")
    uploaded = st.file_uploader(
        ".puml / .txt ファイルを開く",
        type=["puml", "plantuml", "txt"],
        label_visibility="collapsed"
    )
    if uploaded:
        content = uploaded.read().decode("utf-8")
        st.session_state.code = content
        st.session_state.ace_key += 1
        st.success(f"📂 {uploaded.name} を読み込みました")

    st.markdown("---")
    st.markdown("### ⌨️ Vim キーバインド")
    st.markdown("""
| キー | 動作 |
|------|------|
| `i` | Insert モードへ |
| `Esc` | Normal モードへ |
| `v` / `V` | Visual / 行 Visual |
| `dd` | 行削除 |
| `yy` / `p` | コピー / ペースト |
| `u` / `Ctrl+r` | Undo / Redo |
| `gg` / `G` | 先頭 / 末尾 |
| `/` | 検索 |
| `:%s/a/b/g` | 一括置換 |
| `Ctrl+Enter` | プレビューへ反映 |
""")

    st.markdown("---")
    st.markdown("### 🔗 リンク")
    st.markdown("[PlantUML 公式](https://plantuml.com/ja/)  |  [ドキュメント](https://plantuml.com/ja/sequence-diagram)")

# メインレイアウト
col_left, col_right = st.columns([1, 1], gap="medium")

# ════════════════════════════════════════════════════════════
# 左カラム: Ace Vim エディタ
# ════════════════════════════════════════════════════════════
with col_left:
    tpl_col, btn_col = st.columns([3, 1])
    with tpl_col:
        tpl_names = list(TEMPLATES.keys())
        new_tpl = st.selectbox(
            "テンプレート",
            tpl_names,
            index=tpl_names.index(st.session_state.selected_tpl),
            label_visibility="collapsed",
        )
    with btn_col:
        if st.button("📋 読み込み", use_container_width=True):
            st.session_state.code = TEMPLATES[new_tpl]
            st.session_state.selected_tpl = new_tpl
            # ace_key を変えると st_ace が新しい value で再マウントされる
            st.session_state.ace_key += 1
            st.rerun()

    if HAS_ACE:
        # ── Ace Editor (Vim モード) ──────────────────────────────
        edited_code = st_ace(
            value=st.session_state.code,
            language="text",           # PlantUML 専用ハイライトはないので plain text
            theme="tomorrow_night",    # 暗いテーマ（他: dracula, monokai, nord_dark）
            keybinding="vim",          # ← Vim キーバインド
            font_size=13,
            tab_size=2,
            min_lines=25,
            max_lines=35,
            show_gutter=True,
            show_print_margin=False,
            auto_update=False,         # False = Ctrl+Enter で Streamlit へ送信
            key=f"ace_{st.session_state.ace_key}",
        )
        # st_ace は None を返すことがあるので guard する
        if edited_code is not None:
            st.session_state.code = edited_code

        st.markdown(
            '<div class="vim-hint">'
            '⌨️ <b>i</b>=Insert &nbsp; <b>Esc</b>=Normal &nbsp; '
            '<b>dd</b>=行削除 &nbsp; <b>yy/p</b>=コピペ &nbsp; '
            '<b>u</b>=Undo &nbsp; <b>/</b>=検索 &nbsp; '
            '<b>Ctrl+Enter</b>=プレビューへ反映'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        # フォールバック: streamlit-ace が入っていない場合は通常のテキストエリア
        st.error("⚠️ `pip install streamlit-ace` を実行してください。通常エディタで表示中。")
        edited_code = st.text_area(
            "PlantUML コード",
            value=st.session_state.code,
            height=480,
            label_visibility="collapsed",
            key=f"code_fallback_{st.session_state.ace_key}",
        )
        if edited_code != st.session_state.code:
            st.session_state.code = edited_code

    # ステータス
    lines = st.session_state.code.count("\n") + 1
    chars = len(st.session_state.code)
    st.markdown(
        f'<div class="info-bar">📝 行数: <b>{lines}</b>　文字数: <b>{chars}</b></div>',
        unsafe_allow_html=True
    )

    st.download_button(
        "💾 .puml ファイルとして保存",
        data=st.session_state.code.encode("utf-8"),
        file_name="diagram.puml",
        mime="text/plain",
        use_container_width=True,
    )

# ════════════════════════════════════════════════════════════
# 右カラム: プレビュー
# ════════════════════════════════════════════════════════════
with col_right:
    preview_top, refresh_btn = st.columns([3, 1])
    with preview_top:
        st.markdown("#### 📐 プレビュー")
    with refresh_btn:
        do_preview = st.button("▶ 更新", type="primary", use_container_width=True)

    should_render = do_preview or st.session_state.auto_preview

    if should_render and st.session_state.code.strip():
        with st.spinner("ダイアグラムを生成中..."):
            png_data, source = get_diagram(st.session_state.code, "png")

        if png_data:
            if HAS_PIL:
                img = Image.open(io.BytesIO(png_data))
                st.image(img, use_container_width=True)
            else:
                st.image(png_data, use_container_width=True)

            st.markdown(
                f'<div class="render-source">レンダリング: {source}</div>',
                unsafe_allow_html=True
            )

            st.markdown("---")
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                st.download_button(
                    "🖼 PNG ダウンロード",
                    data=png_data,
                    file_name="diagram.png",
                    mime="image/png",
                    use_container_width=True,
                )
            with dl_col2:
                svg_data, _ = get_diagram(st.session_state.code, "svg")
                if svg_data:
                    st.download_button(
                        "📄 SVG ダウンロード",
                        data=svg_data,
                        file_name="diagram.svg",
                        mime="image/svg+xml",
                        use_container_width=True,
                    )

            with st.expander("🔗 共有URL（plantuml.com）"):
                url = plantuml_url(st.session_state.code, "png")
                st.code(url, language=None)
                st.markdown(f"[ブラウザで開く ↗]({url})")
        else:
            st.error(
                "⚠️ ダイアグラムを生成できませんでした。\n\n"
                "**考えられる原因:**\n"
                "- コードに文法エラーがある\n"
                "- インターネット接続がない（クラウドモード時）\n"
                "- plantuml.jar / Java の問題（ローカルモード時）\n\n"
                f"**確認用URL:** {plantuml_url(st.session_state.code, 'png')}"
            )

    elif not st.session_state.code.strip():
        st.info("← コードを入力してください")
    else:
        st.info("← コードを編集後、**Ctrl+Enter** でプレビューへ反映されます\n（または「▶ 更新」ボタンを押してください）")

    if not find_jar():
        with st.expander("ℹ️ ローカルレンダリングについて"):
            st.markdown("""
**現在のモード: 🌐 クラウド（plantuml.com）**

オフライン・高速動作のためには `plantuml.jar` を設置してください:

1. [plantuml.com/download](https://plantuml.com/download) からJARをダウンロード
2. `plantuml.jar` という名前でこのスクリプトと同じフォルダに保存
3. アプリを再起動

Java のインストールも必要です。
""")
