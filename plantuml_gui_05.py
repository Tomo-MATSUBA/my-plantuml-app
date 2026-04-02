"""
PlantUML Generator - リアルタイムプレビュー付きGUI
左画面: コードエディタ  /  右画面: PNGプレビュー（ローカル完全動作）

必要なもの:
  pip install pillow
  plantuml.jar を同じフォルダに配置
  Java (java コマンドが使えること)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
import subprocess
import os
import zlib
import threading
import tempfile
import shutil
import webbrowser
import sys

try:
    from PIL import Image, ImageTk

    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ─── PlantUML URL エンコード ──────────────────────────────────
def _e6(b):
    if b < 10:
        return chr(48 + b)
    b -= 10
    if b < 26:
        return chr(65 + b)
    b -= 26
    if b < 26:
        return chr(97 + b)
    return "-" if b - 26 == 0 else "_"


def _a3(b1, b2, b3):
    return (
        _e6((b1 >> 2) & 63)
        + _e6((((b1 & 3) << 4) | (b2 >> 4)) & 63)
        + _e6((((b2 & 0xF) << 2) | (b3 >> 6)) & 63)
        + _e6(b3 & 63)
    )


def encode_plantuml(text):
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


def plantuml_url(code):
    return f"https://www.plantuml.com/plantuml/png/{encode_plantuml(code)}"


# ─── テンプレート ─────────────────────────────────────────────
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

# ─── カラー定義 ───────────────────────────────────────────────
C = {
    "bg": "#0d1117",
    "sidebar": "#161b22",
    "toolbar": "#21262d",
    "border": "#30363d",
    "accent": "#58a6ff",
    "accent_dim": "#1f6feb",
    "danger": "#f85149",
    "success": "#3fb950",
    "warning": "#e3b341",
    "text": "#e6edf3",
    "text_dim": "#8b949e",
    "editor_bg": "#0d1117",
    "editor_fg": "#e6edf3",
    "lineno_bg": "#0d1117",
    "lineno_fg": "#3d444d",
    "sel_bg": "#1f6feb",
    "canvas_bg": "#f6f8fa",
    "btn_green": "#238636",
    "btn_green2": "#2ea043",
}

JAR_NAME = "plantuml.jar"
DEBOUNCE_MS = 800
TMP_DIR = tempfile.mkdtemp(prefix="plantuml_gui_")


# ─── スクロール付きプレビューキャンバス ──────────────────────
class PreviewCanvas(tk.Frame):
    """PIL画像をスクロール可能なキャンバスに表示"""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["canvas_bg"], **kw)
        self._img_tk = None  # GC防止

        # スクロールバー
        self._vsb = tk.Scrollbar(self, orient="vertical")
        self._hsb = tk.Scrollbar(self, orient="horizontal")
        self._vsb.pack(side="right", fill="y")
        self._hsb.pack(side="bottom", fill="x")

        # キャンバス
        self._cv = tk.Canvas(
            self,
            bg=C["canvas_bg"],
            highlightthickness=0,
            yscrollcommand=self._vsb.set,
            xscrollcommand=self._hsb.set,
        )
        self._cv.pack(fill="both", expand=True)
        self._vsb.config(command=self._cv.yview)
        self._hsb.config(command=self._cv.xview)

        # マウスホイール
        self._cv.bind(
            "<MouseWheel>",
            lambda e: self._cv.yview_scroll(int(-1 * e.delta / 120), "units"),
        )
        self._cv.bind("<Button-4>", lambda e: self._cv.yview_scroll(-1, "units"))
        self._cv.bind("<Button-5>", lambda e: self._cv.yview_scroll(1, "units"))
        self._cv.bind("<Configure>", self._on_resize)

        self._pil_img = None
        self.show_message("← コードを編集すると\nここにプレビューが表示されます")

    # ── 画像表示 ──────────────────────────────────────────────
    def show_pil(self, img: Image.Image):
        self._pil_img = img
        self._cv.configure(bg=C["canvas_bg"])
        self.configure(bg=C["canvas_bg"])
        self._redraw()

    def _redraw(self):
        if self._pil_img is None:
            return
        img = self._pil_img
        iw, ih = img.size
        self._img_tk = ImageTk.PhotoImage(img)
        cw = max(self._cv.winfo_width(), 1)

        self._cv.delete("all")
        # 水平中央揃え（画像がcanvasより小さい場合）
        x = max(iw // 2, cw // 2)
        self._cv.create_image(x, 8, anchor="n", image=self._img_tk)
        self._cv.configure(scrollregion=(0, 0, max(iw, cw), ih + 16))

    def _on_resize(self, _event):
        self._redraw()

    # ── メッセージ表示 ────────────────────────────────────────
    def show_message(self, msg, color="#888888"):
        self._pil_img = None
        self._img_tk = None
        self._cv.delete("all")
        self._cv.configure(bg=C["canvas_bg"])
        self.configure(bg=C["canvas_bg"])
        self._cv.create_text(
            16, 16, anchor="nw", text=msg, fill=color, font=("Arial", 11), width=500
        )
        self._cv.configure(scrollregion=(0, 0, 600, 300))

    # ── エラー表示 ────────────────────────────────────────────
    def show_error(self, msg):
        self._pil_img = None
        self._img_tk = None
        self._cv.delete("all")
        bg = "#fff5f5"
        self._cv.configure(bg=bg)
        self.configure(bg=bg)
        self._cv.create_text(
            16,
            16,
            anchor="nw",
            text=f"❌  エラー\n\n{msg}",
            fill="#c0392b",
            font=("Courier New", 10),
            width=560,
        )
        self._cv.configure(scrollregion=(0, 0, 640, 500))


# ─── メインアプリ ─────────────────────────────────────────────
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PlantUML Generator")
        self.root.geometry("1400x860+0+0")
        self.root.configure(bg=C["bg"])
        self.root.minsize(900, 600)

        self._jar = self._find_jar()
        self._modified = False
        self._cur_file = None
        self._timer = None
        self._lock = threading.Lock()
        self._last_code = ""
        # Vim風エディタ状態
        self._vim_mode = "insert"  # "insert" or "normal"
        self._vim_pending = None   # 2文字コマンドなどの待機状態用
        self._vim_clipboard = ""   # yy / p 用の簡易レジスタ

        self._fonts()
        self._menu()
        self._ui()
        self._apply_tpl("シーケンス図")
        self.root.after(500, self._jar_check_startup)

    # ── フォント ────────────────────────────────────────────────
    def _fonts(self):
        self.f_mono = tkfont.Font(family="Courier New", size=12)
        self.f_ui = tkfont.Font(family="Arial", size=10)
        self.f_small = tkfont.Font(family="Arial", size=9)
        self.f_title = tkfont.Font(family="Arial", size=11, weight="bold")

    # ── メニューバー ────────────────────────────────────────────
    def _menu(self):
        mb = tk.Menu(
            self.root,
            bg=C["toolbar"],
            fg=C["text"],
            activebackground=C["accent_dim"],
            relief="flat",
        )
        self.root.config(menu=mb)

        def add_menu(label, items):
            m = tk.Menu(
                mb,
                tearoff=0,
                bg=C["toolbar"],
                fg=C["text"],
                activebackground=C["accent_dim"],
            )
            mb.add_cascade(label=label, menu=m)
            for it in items:
                if it == "-":
                    m.add_separator()
                else:
                    m.add_command(label=it[0], command=it[1])

        add_menu(
            "ファイル",
            [
                ("開く  Ctrl+O", self.open_file),
                ("保存  Ctrl+S", self.save_file),
                ("名前で保存", self.save_as),
                "-",
                ("終了", self.root.quit),
            ],
        )
        add_menu(
            "エクスポート",
            [
                ("SVGとして保存", lambda: self.export("svg")),
                ("PNGとして保存", lambda: self.export("png")),
            ],
        )
        add_menu(
            "表示",
            [
                ("プレビュー更新  F5", self._preview_now),
            ],
        )
        add_menu(
            "ヘルプ",
            [
                ("Vim コマンド一覧  F1",        self._show_vim_help),
                ("plantuml.jar のセットアップ", self._jar_help),
                (
                    "PlantUML 公式サイト",
                    lambda: webbrowser.open("https://plantuml.com/ja/"),
                ),
            ],
        )

        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<F5>",        lambda e: self._preview_now())
        self.root.bind("<F1>",        lambda e: self._show_vim_help())

    # ── Vim コマンド一覧ダイアログ ──────────────────────────────
    def _show_vim_help(self):
        win = tk.Toplevel(self.root)
        win.title("Vim コマンド一覧")
        win.geometry("640x620")
        win.configure(bg=C["bg"])
        win.transient(self.root)
        win.resizable(True, True)

        # ── ヘッダー ──
        hdr = tk.Frame(win, bg=C["accent_dim"], height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="⌨  Vim キーボードショートカット",
                 font=self.f_title, bg=C["accent_dim"],
                 fg="white").pack(side="left", padx=16, pady=10)
        tk.Label(hdr, text="F1 で開閉",
                 font=self.f_small, bg=C["accent_dim"],
                 fg="#aac8ff").pack(side="right", padx=16)

        # ── スクロール可能な本体 ──
        container = tk.Frame(win, bg=C["bg"])
        container.pack(fill="both", expand=True, padx=0, pady=0)

        vsb = tk.Scrollbar(container, bg=C["toolbar"])
        vsb.pack(side="right", fill="y")
        canvas = tk.Canvas(container, bg=C["bg"],
                           highlightthickness=0,
                           yscrollcommand=vsb.set)
        canvas.pack(fill="both", expand=True)
        vsb.config(command=canvas.yview)

        inner = tk.Frame(canvas, bg=C["bg"])
        canvas_win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_configure(e):
            canvas.itemconfig(canvas_win, width=e.width)
        inner.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # マウスホイール: canvas だけでなく子ウィジェット全体に伝播させる
        def _scroll(e):
            if e.num == 4 or e.delta > 0:
                canvas.yview_scroll(-1, "units")
            elif e.num == 5 or e.delta < 0:
                canvas.yview_scroll(1, "units")

        def _bind_scroll(widget):
            widget.bind("<MouseWheel>", _scroll)
            widget.bind("<Button-4>",   _scroll)
            widget.bind("<Button-5>",   _scroll)
            for child in widget.winfo_children():
                _bind_scroll(child)

        # inner に追加されたウィジェットにも後から自動バインド
        def _on_inner_changed(e):
            _bind_scroll(inner)
        inner.bind("<Configure>", lambda e: (_on_frame_configure(e), _bind_scroll(inner)))

        _bind_scroll(canvas)

        # ── コンテンツ定義 ──
        SECTIONS = [
            ("🔄  モード切替", [
                ("ESC  /  Ctrl+[", "NORMAL モードへ"),
                ("i",              "カーソル前から INSERT"),
                ("a",              "カーソル後から INSERT"),
                ("I",              "行頭（非空白）から INSERT"),
                ("A",              "行末から INSERT"),
                ("o",              "下に新行を開けて INSERT"),
                ("O",              "上に新行を開けて INSERT"),
            ]),
            ("🧭  移動（NORMAL モード）", [
                ("h  j  k  l",    "← ↓ ↑ →"),
                ("w",             "次の単語先頭へ"),
                ("b",             "前の単語先頭へ"),
                ("e",             "単語末尾へ"),
                ("0",             "行頭へ"),
                ("^",             "行頭の最初の非空白文字へ"),
                ("$",             "行末へ"),
                ("gg",            "ファイル先頭へ"),
                ("G",             "ファイル末尾へ"),
            ]),
            ("✂️  編集（NORMAL モード）", [
                ("x  /  X",       "1文字削除（後 / 前）"),
                ("dd",            "行を削除（レジスタへ）"),
                ("dw",            "単語を削除"),
                ("d$",            "行末まで削除"),
                ("d0",            "行頭まで削除"),
                ("D",             "行末まで削除（dd と違いレジスタには入らない）"),
                ("cc",            "行を空にして INSERT"),
                ("cw",            "単語を削除して INSERT"),
                ("C",             "行末まで削除して INSERT"),
                ("s",             "1文字削除して INSERT"),
                ("J",             "次行を現在行に結合"),
            ]),
            ("📋  コピー＆ペースト", [
                ("yy",            "行をヤンク（コピー）"),
                ("yw",            "単語をヤンク"),
                ("p",             "カーソル行の下に貼り付け"),
                ("P",             "カーソル行の上に貼り付け"),
            ]),
            ("↩  アンドゥ / リドゥ", [
                ("u",             "アンドゥ（元に戻す）"),
                ("Ctrl + r",      "リドゥ（やり直し）"),
            ]),
        ]

        f_key  = tkfont.Font(family="Courier New", size=10, weight="bold")
        f_desc = tkfont.Font(family="Arial",        size=10)
        f_sec  = tkfont.Font(family="Arial",        size=11, weight="bold")

        for sec_title, rows in SECTIONS:
            # セクションヘッダー
            sec_frame = tk.Frame(inner, bg=C["sidebar"])
            sec_frame.pack(fill="x", padx=12, pady=(12, 0))
            tk.Label(sec_frame, text=sec_title,
                     font=f_sec, bg=C["sidebar"],
                     fg=C["accent"], padx=10, pady=5).pack(anchor="w")

            # 行
            for key, desc in rows:
                row = tk.Frame(inner, bg=C["bg"])
                row.pack(fill="x", padx=12)
                row.bind("<Enter>", lambda e, r=row: r.config(bg=C["toolbar"]))
                row.bind("<Leave>", lambda e, r=row: r.config(bg=C["bg"]))

                # キーラベル（幅固定）
                key_lbl = tk.Label(row, text=key,
                                   font=f_key, bg=C["editor_bg"],
                                   fg=C["success"], width=18,
                                   anchor="w", padx=8, pady=4)
                key_lbl.pack(side="left", padx=(0, 0))

                # 説明
                desc_lbl = tk.Label(row, text=desc,
                                    font=f_desc, bg=C["bg"],
                                    fg=C["text"], anchor="w", padx=12)
                desc_lbl.pack(side="left", fill="x", expand=True)

                row.bind("<Enter>", lambda e, r=row, k=key_lbl, d=desc_lbl:
                         (r.config(bg=C["toolbar"]),
                          k.config(bg=C["toolbar"]),
                          d.config(bg=C["toolbar"])))
                row.bind("<Leave>", lambda e, r=row, k=key_lbl, d=desc_lbl:
                         (r.config(bg=C["bg"]),
                          k.config(bg=C["editor_bg"]),
                          d.config(bg=C["bg"])))

        # 下部の閉じるボタン
        tk.Frame(inner, bg=C["bg"], height=8).pack()
        bf = tk.Frame(inner, bg=C["bg"])
        bf.pack(pady=8)
        tk.Button(bf, text="閉じる  ( F1 )",
                  command=win.destroy,
                  bg=C["accent_dim"], fg="white",
                  relief="flat", font=self.f_ui,
                  cursor="hand2", padx=16, pady=4).pack()
        tk.Frame(inner, bg=C["bg"], height=12).pack()

        win.bind("<F1>",   lambda e: win.destroy())
        win.bind("<Escape>", lambda e: win.destroy())

    # ── UI 全体 ─────────────────────────────────────────────────
    def _ui(self):
        self._toolbar()

        self._pane = tk.PanedWindow(
            self.root,
            orient="horizontal",
            bg=C["border"],
            sashwidth=5,
            sashrelief="flat",
        )
        self._pane.pack(fill="both", expand=True)

        self._left_panel()
        self._right_panel()
        self._statusbar()

    # ── ツールバー ──────────────────────────────────────────────
    def _toolbar(self):
        tb = tk.Frame(self.root, bg=C["toolbar"], height=46)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        def btn(text, cmd, fg=C["text_dim"], bg=C["toolbar"]):
            lbl = tk.Label(
                tb,
                text=text,
                bg=bg,
                fg=fg,
                font=self.f_ui,
                cursor="hand2",
                padx=10,
                pady=5,
            )
            lbl.pack(side="left", padx=2, pady=5)
            lbl.bind("<Button-1>", lambda e: cmd())
            lbl.bind("<Enter>", lambda e: lbl.config(bg=C["border"], fg=C["text"]))
            lbl.bind("<Leave>", lambda e: lbl.config(bg=bg, fg=fg))

        def gbtn(text, cmd):
            lbl = tk.Label(
                tb,
                text=text,
                bg=C["btn_green"],
                fg="white",
                font=self.f_ui,
                cursor="hand2",
                padx=12,
                pady=5,
            )
            lbl.pack(side="left", padx=(6, 2), pady=5)
            lbl.bind("<Button-1>", lambda e: cmd())
            lbl.bind("<Enter>", lambda e: lbl.config(bg=C["btn_green2"]))
            lbl.bind("<Leave>", lambda e: lbl.config(bg=C["btn_green"]))

        def sep():
            tk.Frame(tb, bg=C["border"], width=1).pack(
                side="left", fill="y", padx=5, pady=8
            )

        btn("📂 開く", self.open_file)
        btn("💾 保存", self.save_file)
        btn("📄 名前で保存", self.save_as)
        sep()
        gbtn("⟳  プレビュー更新  F5", self._preview_now)
        sep()
        btn("💾 SVG出力", lambda: self.export("svg"))
        btn("🖼 PNG出力", lambda: self.export("png"))

        self._jar_lbl = tk.Label(tb, text="", font=self.f_small, bg=C["toolbar"])
        self._jar_lbl.pack(side="right", padx=14)
        self._update_jar_lbl()

    # ── 左パネル（エディタ） ────────────────────────────────────
    def _left_panel(self):
        frame = tk.Frame(self._pane, bg=C["bg"])
        self._pane.add(frame, minsize=380)

        # テンプレートバー
        tbar = tk.Frame(frame, bg=C["sidebar"], height=34)
        tbar.pack(fill="x")
        tbar.pack_propagate(False)
        tk.Label(
            tbar,
            text="テンプレート:",
            font=self.f_small,
            bg=C["sidebar"],
            fg=C["text_dim"],
        ).pack(side="left", padx=8, pady=7)
        self._tpl_var = tk.StringVar(value="シーケンス図")
        cb = ttk.Combobox(
            tbar,
            textvariable=self._tpl_var,
            values=list(TEMPLATES.keys()),
            state="readonly",
            width=18,
            font=self.f_small,
        )
        cb.pack(side="left", padx=4, pady=5)
        cb.bind("<<ComboboxSelected>>", self._on_tpl)

        # ファイル名ラベル
        self._fname_lbl = tk.Label(
            frame,
            text="  新規ファイル",
            font=self.f_small,
            bg=C["toolbar"],
            fg=C["text_dim"],
            anchor="w",
        )
        self._fname_lbl.pack(fill="x")

        # エディタ
        ef = tk.Frame(frame, bg=C["editor_bg"])
        ef.pack(fill="both", expand=True)

        self._lineno = tk.Text(
            ef,
            width=5,
            bg=C["lineno_bg"],
            fg=C["lineno_fg"],
            font=self.f_mono,
            state="disabled",
            relief="flat",
            padx=4,
            pady=4,
            cursor="arrow",
            selectbackground=C["lineno_bg"],
        )
        self._lineno.pack(side="left", fill="y")

        vsc = tk.Scrollbar(ef)
        hsc = tk.Scrollbar(ef, orient="horizontal")
        vsc.pack(side="right", fill="y")
        hsc.pack(side="bottom", fill="x")

        self._ed = tk.Text(
            ef,
            bg=C["editor_bg"],
            fg=C["editor_fg"],
            insertbackground=C["accent"],
            selectbackground=C["sel_bg"],
            font=self.f_mono,
            relief="flat",
            wrap="none",
            undo=True,
            padx=6,
            pady=4,
            yscrollcommand=lambda *a: (vsc.set(*a), self._sync_ln()),
            xscrollcommand=hsc.set,
        )
        self._ed.pack(fill="both", expand=True)
        vsc.config(command=self._ed.yview)
        hsc.config(command=self._ed.xview)

        self._ed.bind("<KeyRelease>", self._on_key)
        self._ed.bind("<Tab>", lambda e: (self._ed.insert("insert", "  "), "break")[1])

        # Vim風キーバインドをセットアップ
        self._setup_vim()

    # ══════════════════════════════════════════════════════════════
    #  Vim モード実装
    # ══════════════════════════════════════════════════════════════

    def _set_vim_mode(self, mode):
        """モード切替 + カーソル形状 + ステータス更新"""
        if mode not in ("insert", "normal"):
            return
        self._vim_mode    = mode
        self._vim_pending = None
        # ブロックカーソル（NORMAL）/ ビームカーソル（INSERT）
        try:
            self._ed.config(blockcursor=(mode == "normal"))
        except tk.TclError:
            pass
        self._update_info()

    def _setup_vim(self):
        """Vim キーバインドを登録"""
        ed = self._ed
        # ESC / Ctrl+[ でノーマルモードへ
        ed.bind("<Escape>",              self._vim_esc)
        ed.bind("<Control-bracketleft>", self._vim_esc)
        # すべての KeyPress をフック（ノーマルモード時に横取り）
        ed.bind("<KeyPress>", self._vim_keypress, add="+")

    def _vim_esc(self, event):
        self._set_vim_mode("normal")
        return "break"

    # ── ヘルパー: カーソル位置 ──────────────────────────────────
    def _cur_line(self):
        return int(self._ed.index("insert").split(".")[0])

    def _line_start(self, line=None):
        l = line or self._cur_line()
        return f"{l}.0"

    def _line_end(self, line=None):
        l = line or self._cur_line()
        return f"{l}.0 lineend"

    def _line_end_plus1(self, line=None):
        l = line or self._cur_line()
        return f"{l}.0 lineend +1c"

    # ── ヘルパー: ヤンク ────────────────────────────────────────
    def _yank_line(self, line=None):
        """行をヤンクしてレジスタとクリップボードへ"""
        text = self._ed.get(self._line_start(line), self._line_end(line))
        self._vim_clipboard = text
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except tk.TclError:
            pass

    # ── ヘルパー: 単語境界 ──────────────────────────────────────
    def _word_forward(self):
        """w: 次の単語先頭へ"""
        pos = self._ed.index("insert")
        # まず非空白を読み飛ばし、次に空白を読み飛ばす
        self._ed.mark_set("insert", f"{pos} wordend")
        self._ed.mark_set("insert", "insert +1c wordstart")
        self._ed.see("insert")

    def _word_back(self):
        """b: 前の単語先頭へ"""
        pos = self._ed.index("insert")
        self._ed.mark_set("insert", f"{pos} -1c wordstart")
        self._ed.see("insert")

    def _word_end(self):
        """e: 単語末尾へ"""
        self._ed.mark_set("insert", "insert wordend -1c")
        self._ed.see("insert")

    # ── ヘルパー: 行頭の非空白 ──────────────────────────────────
    def _first_nonblank(self):
        """^: 行の最初の非空白文字へ"""
        line = self._cur_line()
        content = self._ed.get(self._line_start(line), self._line_end(line))
        col = len(content) - len(content.lstrip())
        self._ed.mark_set("insert", f"{line}.{col}")
        self._ed.see("insert")

    # ── メインディスパッチャ ────────────────────────────────────
    def _vim_keypress(self, event):
        # INSERT モードはほぼ素通し
        if self._vim_mode == "insert":
            return  # 通常の文字入力

        # 特殊キー（矢印・Ctrl系など）は通常処理に任せる
        keysym = event.keysym
        char   = event.char

        # Ctrl+r: redo（ノーマルモードでも効かせる）
        if event.state & 0x4 and keysym == "r":
            try:
                self._ed.edit_redo()
                self._on_key()
            except tk.TclError:
                pass
            return "break"

        # 矢印キーは移動を許可
        if keysym in ("Up", "Down", "Left", "Right",
                      "Home", "End", "Prior", "Next"):
            return  # デフォルト動作

        # 文字キー以外（Shift、Alt、Function等）は無視
        if not char and keysym not in ("BackSpace",):
            return "break"

        # ─── ペンディングコマンド処理 ──────────────────────────
        if self._vim_pending:
            pending = self._vim_pending
            self._vim_pending = None

            if pending == "d":
                if char == "d":          # dd: 行削除
                    self._yank_line()
                    self._ed.delete(self._line_start(), self._line_end_plus1())
                    self._on_key()
                elif char == "w":        # dw: 単語削除
                    start = self._ed.index("insert")
                    self._ed.mark_set("insert", "insert wordend")
                    self._ed.delete(start, "insert")
                    self._on_key()
                elif char == "$":        # d$: 行末まで削除
                    self._ed.delete("insert", "insert lineend")
                    self._on_key()
                elif char == "0":        # d0: 行頭まで削除
                    self._ed.delete("insert linestart", "insert")
                    self._on_key()

            elif pending == "y":
                if char == "y":          # yy: 行ヤンク
                    self._yank_line()
                elif char == "w":        # yw: 単語ヤンク
                    start = self._ed.index("insert")
                    end   = self._ed.index("insert wordend")
                    self._vim_clipboard = self._ed.get(start, end)

            elif pending == "c":
                if char == "c":          # cc: 行を空にしてINSERT
                    self._yank_line()
                    self._ed.delete(self._line_start(), self._line_end())
                    self._set_vim_mode("insert")
                elif char == "w":        # cw: 単語置換
                    start = self._ed.index("insert")
                    self._ed.mark_set("insert", "insert wordend")
                    self._ed.delete(start, "insert")
                    self._set_vim_mode("insert")

            elif pending == "g":
                if char == "g":          # gg: 先頭行へ
                    self._ed.mark_set("insert", "1.0")
                    self._ed.see("insert")

            return "break"

        # ─── 単独コマンド ──────────────────────────────────────

        # 【移動】
        if char == "h":
            self._ed.mark_set("insert", "insert -1c"); self._ed.see("insert")
        elif char == "l":
            self._ed.mark_set("insert", "insert +1c"); self._ed.see("insert")
        elif char == "j":
            self._ed.mark_set("insert", "insert +1l"); self._ed.see("insert")
        elif char == "k":
            self._ed.mark_set("insert", "insert -1l"); self._ed.see("insert")
        elif char == "0":
            self._ed.mark_set("insert", "insert linestart"); self._ed.see("insert")
        elif char == "^":
            self._first_nonblank()
        elif char == "$":
            self._ed.mark_set("insert", "insert lineend"); self._ed.see("insert")
        elif char == "w":
            self._word_forward()
        elif char == "b":
            self._word_back()
        elif char == "e":
            self._word_end()
        elif char == "G":
            self._ed.mark_set("insert", "end -1c"); self._ed.see("insert")
        elif char == "{":   # 段落単位で上移動
            self._ed.mark_set("insert", "insert -1l linestart"); self._ed.see("insert")
        elif char == "}":   # 段落単位で下移動
            self._ed.mark_set("insert", "insert +1l linestart"); self._ed.see("insert")

        # 【ペンディング開始】
        elif char == "d":
            self._vim_pending = "d"
        elif char == "y":
            self._vim_pending = "y"
        elif char == "c":
            self._vim_pending = "c"
        elif char == "g":
            self._vim_pending = "g"

        # 【編集】
        elif char == "x":   # 1文字削除
            self._ed.delete("insert"); self._on_key()
        elif char == "X":   # 前の1文字削除
            self._ed.delete("insert -1c"); self._on_key()
        elif char == "D":   # 行末まで削除
            self._ed.delete("insert", "insert lineend"); self._on_key()
        elif char == "C":   # 行末まで削除してINSERT
            self._ed.delete("insert", "insert lineend")
            self._set_vim_mode("insert")
        elif char == "s":   # 1文字削除してINSERT
            self._ed.delete("insert"); self._set_vim_mode("insert")
        elif char == "J":   # 次行を結合
            line = self._cur_line()
            self._ed.delete(self._line_end(line), self._line_start(line + 1) + " +1c")
            self._ed.insert(self._line_end(line), " ")
            self._on_key()

        # 【貼り付け】
        elif char == "p":   # カーソルの後（行の下）に貼り付け
            if self._vim_clipboard:
                self._ed.insert("insert lineend", "\n" + self._vim_clipboard)
                self._on_key()
        elif char == "P":   # カーソルの前（行の上）に貼り付け
            if self._vim_clipboard:
                self._ed.insert("insert linestart", self._vim_clipboard + "\n")
                self._ed.mark_set("insert", "insert -1l linestart")
                self._on_key()

        # 【INSERT モードへ】
        elif char == "i":
            self._set_vim_mode("insert")
        elif char == "I":   # 行頭でINSERT
            self._first_nonblank(); self._set_vim_mode("insert")
        elif char == "a":   # カーソルの後ろでINSERT
            self._ed.mark_set("insert", "insert +1c"); self._set_vim_mode("insert")
        elif char == "A":   # 行末でINSERT
            self._ed.mark_set("insert", "insert lineend"); self._set_vim_mode("insert")
        elif char == "o":   # 下に新行を開けてINSERT
            self._ed.insert("insert lineend", "\n")
            self._ed.mark_set("insert", "insert lineend")
            self._set_vim_mode("insert"); self._on_key()
        elif char == "O":   # 上に新行を開けてINSERT
            self._ed.insert("insert linestart", "\n")
            self._ed.mark_set("insert", "insert -1l linestart")
            self._set_vim_mode("insert"); self._on_key()

        # 【アンドゥ】
        elif char == "u":
            try:
                self._ed.edit_undo(); self._on_key()
            except tk.TclError:
                pass

        # その他（NORMALモードでは文字入力させない）
        else:
            pass

        return "break"

    # ── 右パネル（プレビュー） ──────────────────────────────────
    def _right_panel(self):
        frame = tk.Frame(self._pane, bg=C["bg"])
        self._pane.add(frame, minsize=380)

        # ヘッダー
        ph = tk.Frame(frame, bg=C["sidebar"], height=34)
        ph.pack(fill="x")
        ph.pack_propagate(False)
        tk.Label(
            ph,
            text="📐 プレビュー",
            font=self.f_small,
            bg=C["sidebar"],
            fg=C["text_dim"],
        ).pack(side="left", padx=10, pady=8)
        self._prev_stat = tk.Label(
            ph, text="", font=self.f_small, bg=C["sidebar"], fg=C["text_dim"]
        )
        self._prev_stat.pack(side="right", padx=10)

        # プレビューウィジェット
        if HAS_PIL:
            self._preview = PreviewCanvas(frame)
            self._preview.pack(fill="both", expand=True)
        else:
            self._preview = None
            tk.Label(
                frame,
                text="⚠️  pip install pillow  でプレビューが使えます",
                bg=C["bg"],
                fg=C["warning"],
                font=self.f_ui,
            ).pack(pady=20)

    # ── ステータスバー ──────────────────────────────────────────
    def _statusbar(self):
        sb = tk.Frame(self.root, bg=C["toolbar"], height=28)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)

        # Vim モードバッジ（左端・目立つ色）
        self._vim_badge = tk.Label(
            sb, text=" INSERT ",
            font=tkfont.Font(family="Courier New", size=9, weight="bold"),
            bg=C["success"], fg=C["bg"], padx=4, pady=2
        )
        self._vim_badge.pack(side="left", padx=(6, 2), pady=4)

        self._stat_lbl = tk.Label(
            sb, text="✅ 準備完了", font=self.f_small, bg=C["toolbar"], fg=C["success"]
        )
        self._stat_lbl.pack(side="left", padx=8)

        self._info_lbl = tk.Label(
            sb, text="", font=self.f_small, bg=C["toolbar"], fg=C["text_dim"]
        )
        self._info_lbl.pack(side="right", padx=10)

    # ── jar 管理 ────────────────────────────────────────────────
    def _find_jar(self):
        for p in [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), JAR_NAME),
            os.path.join(os.getcwd(), JAR_NAME),
            os.path.expanduser(f"~/{JAR_NAME}"),
        ]:
            if os.path.isfile(p) and os.path.getsize(p) > 10_000:
                return p
        return None

    def _java_cmd(self):
        # WindowsのGUIアプリから java.exe を叩くと別コンソールが一瞬出ることがあるため、
        # javaw.exe を優先する。
        if sys.platform.startswith("win"):
            return shutil.which("javaw") or "javaw"
        return shutil.which("java") or "java"

    def _subprocess_kwargs(self):
        # Windowsで外部プロセスのコンソール表示を抑止
        if not sys.platform.startswith("win"):
            return {}
        return {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
            "startupinfo": self._startupinfo_no_window(),
        }

    def _startupinfo_no_window(self):
        # 古いPython/環境では startupinfo が効く場合があるため併用
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            return si
        except Exception:
            return None

    def _update_jar_lbl(self):
        if self._jar:
            self._jar_lbl.config(
                text=f"✅ {os.path.basename(self._jar)}", fg=C["success"]
            )
        else:
            self._jar_lbl.config(text="⚠️ plantuml.jar なし", fg=C["warning"])

    def _jar_check_startup(self):
        if not self._jar:
            self._jar_help()

    def _jar_help(self):
        w = tk.Toplevel(self.root)
        w.title("plantuml.jar のセットアップ")
        w.geometry("520x310")
        w.configure(bg=C["bg"])
        w.transient(self.root)
        w.grab_set()

        tk.Label(
            w,
            text="⚠️  plantuml.jar が見つかりません",
            font=self.f_title,
            bg=C["bg"],
            fg=C["warning"],
        ).pack(pady=(18, 6))
        tk.Label(
            w,
            text="リアルタイムプレビューには plantuml.jar と Java が必要です。\n\n"
            "【手順】\n"
            "1. 下のボタンでダウンロードページを開く\n"
            "2. 最新の plantuml-X.X.X.jar をダウンロード\n"
            "3. このスクリプトと同じフォルダに plantuml.jar として保存\n"
            "4. アプリを再起動",
            font=self.f_small,
            bg=C["bg"],
            fg=C["text"],
            justify="left",
            padx=24,
        ).pack(anchor="w")
        bf = tk.Frame(w, bg=C["bg"])
        bf.pack(pady=16)
        tk.Button(
            bf,
            text="🌐 ダウンロードページを開く",
            command=lambda: webbrowser.open("https://plantuml.com/download"),
            bg=C["accent_dim"],
            fg="white",
            relief="flat",
            font=self.f_ui,
            cursor="hand2",
            padx=12,
        ).pack(side="left", padx=6)
        tk.Button(
            bf,
            text="閉じる",
            command=w.destroy,
            bg=C["toolbar"],
            fg=C["text"],
            relief="flat",
            font=self.f_ui,
            cursor="hand2",
            padx=12,
        ).pack(side="left", padx=6)

    # ── エディタ操作 ────────────────────────────────────────────
    def _on_key(self, _event=None):
        self._modified = True
        self._sync_ln()
        self._update_info()
        self._schedule()

    def _on_tpl(self, _event=None):
        name = self._tpl_var.get()
        if self._modified and not messagebox.askyesno(
            "確認", "変更が保存されていません。テンプレートを読み込みますか？"
        ):
            return
        self._apply_tpl(name)

    def _apply_tpl(self, name):
        self._ed.delete("1.0", "end")
        self._ed.insert("1.0", TEMPLATES.get(name, ""))
        self._modified = False
        self._tpl_var.set(name)
        self._sync_ln()
        self._update_info()
        self._preview_now()

    def _sync_ln(self):
        n = self._ed.get("1.0", "end-1c").count("\n") + 1
        self._lineno.config(state="normal")
        self._lineno.delete("1.0", "end")
        self._lineno.insert("1.0", "\n".join(f"{i:>4}" for i in range(1, n + 1)))
        self._lineno.config(state="disabled")
        self._lineno.yview_moveto(self._ed.yview()[0])

    def _update_info(self):
        code = self._ed.get("1.0", "end-1c")
        mod  = " ●" if self._modified else ""
        fname = os.path.basename(self._cur_file) if self._cur_file else "新規ファイル"
        self._fname_lbl.config(text=f"  {fname}{mod}")
        self._info_lbl.config(
            text=f"行: {code.count(chr(10))+1}  文字: {len(code)}"
        )
        # Vim モードバッジ更新
        if hasattr(self, "_vim_badge"):
            is_normal = getattr(self, "_vim_mode", "insert") == "normal"
            if is_normal:
                self._vim_badge.config(
                    text=" NORMAL ",
                    bg=C["accent"],       # 青
                    fg="white"
                )
            else:
                self._vim_badge.config(
                    text=" INSERT ",
                    bg=C["success"],      # 緑
                    fg=C["bg"]
                )

    def _set_stat(self, msg, col=None, sec=3):
        self._stat_lbl.config(text=msg, fg=col or C["success"])
        if sec:
            self.root.after(
                sec * 1000,
                lambda: self._stat_lbl.config(text="✅ 準備完了", fg=C["success"]),
            )

    # ── プレビュー ──────────────────────────────────────────────
    def _schedule(self):
        if self._timer:
            self.root.after_cancel(self._timer)
        self._timer = self.root.after(DEBOUNCE_MS, self._preview_now)

    def _preview_now(self):
        if self._timer:
            self.root.after_cancel(self._timer)
            self._timer = None
        code = self._ed.get("1.0", "end-1c").strip()
        if not code:
            return
        if code == self._last_code:
            return
        self._last_code = code

        if not HAS_PIL:
            return
        if not self._jar:
            self._preview.show_message(
                "plantuml.jar が見つかりません。\n\n"
                "ヘルプメニューからダウンロード方法を確認してください。\n\n"
                f"ブラウザで確認できるURL:\n{plantuml_url(code)}"
            )
            return

        self._prev_stat.config(text="⏳ 生成中...", fg=C["warning"])
        threading.Thread(target=self._render_bg, args=(code,), daemon=True).start()

    def _render_bg(self, code):
        """バックグラウンドスレッド: plantuml.jar で PNG 生成"""
        if not self._lock.acquire(blocking=False):
            return
        try:
            puml = os.path.join(TMP_DIR, "preview.puml")
            png = os.path.join(TMP_DIR, "preview.png")

            # 古いPNGを削除（誤検知防止）
            try:
                os.remove(png)
            except FileNotFoundError:
                pass

            with open(puml, "w", encoding="utf-8") as f:
                f.write(code)

            r = subprocess.run(
                [
                    self._java_cmd(),
                    "-jar",
                    self._jar,
                    "-tpng",
                    "-charset",
                    "UTF-8",
                    "-o",
                    TMP_DIR,
                    puml,
                ],
                capture_output=True,
                text=True,
                timeout=25,
                **{k: v for k, v in self._subprocess_kwargs().items() if v is not None},
            )

            if r.returncode != 0:
                err = (r.stderr or r.stdout or "不明なエラー").strip()
                self.root.after(0, self._on_err, err)
                return

            if not os.path.isfile(png):
                self.root.after(0, self._on_err, "PNGが生成されませんでした")
                return

            img = Image.open(png).copy()
            self.root.after(0, self._on_ok, img)

        except subprocess.TimeoutExpired:
            self.root.after(0, self._on_err, "タイムアウト（25秒）")
        except FileNotFoundError:
            self.root.after(
                0,
                self._on_err,
                "Java が見つかりません。Java をインストールして PATH を通してください。",
            )
        except Exception as e:
            self.root.after(0, self._on_err, str(e))
        finally:
            self._lock.release()

    def _on_ok(self, img):
        self._prev_stat.config(text="✅ 更新済み", fg=C["success"])
        self._preview.show_pil(img)

    def _on_err(self, msg):
        self._prev_stat.config(text="❌ エラー", fg=C["danger"])
        self._preview.show_error(msg)

    # ── ファイル操作 ────────────────────────────────────────────
    def open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("PlantUML", "*.puml *.plantuml *.txt"), ("全ファイル", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                self._ed.delete("1.0", "end")
                self._ed.insert("1.0", f.read())
            self._cur_file = path
            self._modified = False
            self._sync_ln()
            self._update_info()
            self._preview_now()
            self._set_stat(f"📂 {os.path.basename(path)} を開きました")
        except Exception as e:
            messagebox.showerror("エラー", str(e))

    def save_file(self):
        if self._cur_file:
            self._write(self._cur_file)
        else:
            self.save_as()

    def save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".puml",
            filetypes=[
                ("PlantUML", "*.puml"),
                ("テキスト", "*.txt"),
                ("全ファイル", "*.*"),
            ],
        )
        if path:
            self._write(path)

    def _write(self, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._ed.get("1.0", "end-1c"))
            self._cur_file = path
            self._modified = False
            self._update_info()
            self._set_stat(f"💾 {os.path.basename(path)} を保存しました")
        except Exception as e:
            messagebox.showerror("保存エラー", str(e))

    # ── エクスポート ────────────────────────────────────────────
    def export(self, fmt):
        if not self._jar:
            messagebox.showwarning(
                "jar なし", "エクスポートには plantuml.jar と Java が必要です。"
            )
            return
        path = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("全ファイル", "*.*")],
        )
        if not path:
            return

        puml = os.path.join(TMP_DIR, "export.puml")
        with open(puml, "w", encoding="utf-8") as f:
            f.write(self._ed.get("1.0", "end-1c"))

        self._set_stat(f"⏳ {fmt.upper()} 生成中...", C["warning"], sec=0)
        try:
            r = subprocess.run(
                [
                    self._java_cmd(),
                    "-jar",
                    self._jar,
                    f"-t{fmt}",
                    "-charset",
                    "UTF-8",
                    "-o",
                    TMP_DIR,
                    puml,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                **{k: v for k, v in self._subprocess_kwargs().items() if v is not None},
            )
            if r.returncode != 0:
                raise RuntimeError(r.stderr or r.stdout)
            gen = os.path.join(TMP_DIR, f"export.{fmt}")
            if not os.path.isfile(gen):
                raise RuntimeError("ファイルが生成されませんでした")
            shutil.copy(gen, path)
            self._set_stat(f"✅ {fmt.upper()} を保存: {os.path.basename(path)}")
        except Exception as e:
            self._set_stat("❌ 失敗", C["danger"])
            messagebox.showerror("エクスポートエラー", str(e))

    # ── 終了 ────────────────────────────────────────────────────
    def on_close(self):
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        self.root.destroy()


# ─── エントリーポイント ───────────────────────────────────────
def main():
    root = tk.Tk()

    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(
        "TCombobox",
        fieldbackground=C["sidebar"],
        background=C["sidebar"],
        foreground=C["text"],
        selectbackground=C["accent_dim"],
        borderwidth=0,
    )

    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
