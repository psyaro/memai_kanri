"""
OGP画像 (og-image.png / og-image-app.png) を生成するスクリプト。
実行: python static/generate_og.py
依存: pip install Pillow
"""
import os
import math
from PIL import Image, ImageDraw

W, H = 1200, 630

# ---- 色定数 ----
C_BLUE   = (0x2d, 0x6f, 0xb0)
C_PURPLE = (0x7b, 0x5e, 0xa7)
C_WHITE  = (255, 255, 255)
C_WHITE_80 = (255, 255, 255, 204)

SCORE_COLORS = [
    (39,  174,  96),   # 0 green
    (46,  204, 113),   # 1 light green
    (241, 196,  15),   # 2 yellow
    (230, 126,  34),   # 3 orange
    (231,  76,  60),   # 4 red
    (142,  68, 163),   # 5 purple
]


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_gradient(img):
    """斜めグラデーション背景"""
    pixels = img.load()
    for y in range(H):
        for x in range(W):
            t = (x / W * 0.7 + y / H * 0.3)
            r, g, b = lerp_color(C_BLUE, C_PURPLE, t)
            pixels[x, y] = (r, g, b, 255)


def draw_chart(draw, ox, oy, scale=1.0, alpha=60):
    """折れ線グラフ装飾（右側）"""
    pts_base = [(80, 340), (160, 260), (240, 300), (320, 180), (400, 240), (480, 160)]
    pts = [(int(ox + x * scale), int(oy + (y - 250) * scale)) for x, y in pts_base]

    # 影
    draw.line(pts, fill=(255, 255, 255, alpha // 2), width=max(2, int(8 * scale)))
    # 本線
    draw.line(pts, fill=(255, 255, 255, alpha), width=max(2, int(5 * scale)))

    dot_r = max(3, int(10 * scale))
    for i, (x, y) in enumerate(pts[1:], 1):
        draw.ellipse([(x - dot_r, y - dot_r), (x + dot_r, y + dot_r)],
                     fill=(255, 255, 255, alpha))

    # ハイライト点
    hx, hy = pts[3]
    hr = dot_r + max(1, int(5 * scale))
    draw.ellipse([(hx - hr, hy - hr), (hx + hr, hy + hr)],
                 fill=(255, 255, 255, alpha))
    draw.ellipse([(hx - dot_r, hy - dot_r), (hx + dot_r, hy + dot_r)],
                 fill=(int(C_PURPLE[0] * 1.1), C_PURPLE[1], C_PURPLE[2], 255))


def find_font(size):
    """利用可能な日本語フォントを探す"""
    from PIL import ImageFont

    candidates = [
        ("C:\\Windows\\Fonts\\YuGothM.ttc",    0),
        ("C:\\Windows\\Fonts\\YuGothR.ttc",    0),
        ("C:\\Windows\\Fonts\\YuGoth.ttc",     0),
        ("C:\\Windows\\Fonts\\meiryo.ttc",     0),
        ("C:\\Windows\\Fonts\\msgothic.ttc",   0),
        ("C:\\Windows\\Fonts\\NotoSansCJK-Regular.ttc", 0),
        ("/usr/share/fonts/truetype/noto/NotoSansCJKjp-Regular.otf", 0),
        ("/usr/share/fonts/noto-cjk/NotoSansCJKjp-Regular.otf", 0),
    ]
    for path, idx in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size, index=idx)
            except Exception:
                pass
    # フォールバック: デフォルトフォント（日本語不可だが最低限動く）
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def draw_score_dots(draw, x, y, gap=16):
    """スコアカラードット列"""
    r = 10
    for i, color in enumerate(SCORE_COLORS):
        cx = x + i * (r * 2 + gap)
        draw.ellipse([(cx - r, y - r), (cx + r, y + r)],
                     fill=color + (230,))


def make_og_image(title_line1, title_line2, subtitle, tagline, outpath):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_gradient(img)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # ---- 右側の装飾チャート ----
    draw_chart(od, ox=560, oy=320, scale=1.15, alpha=50)

    # ---- 左側パネル（半透明白） ----
    panel_w = 680
    panel = Image.new("RGBA", (panel_w, H), (255, 255, 255, 22))
    overlay.paste(panel, (0, 0), panel)

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # ---- テキスト ----
    pad_x = 70
    # アプリ名
    f_title = find_font(86)
    f_sub   = find_font(38)
    f_tag   = find_font(30)
    f_small = find_font(26)

    # タイトル（2行）
    ty = 130
    draw.text((pad_x, ty),      title_line1, font=f_title, fill=C_WHITE)
    bbox1 = draw.textbbox((pad_x, ty), title_line1, font=f_title)
    ty2 = bbox1[3] + 8
    draw.text((pad_x, ty2),     title_line2, font=f_title, fill=C_WHITE)
    bbox2 = draw.textbbox((pad_x, ty2), title_line2, font=f_title)

    # セパレーター
    sep_y = bbox2[3] + 28
    draw.rectangle([(pad_x, sep_y), (pad_x + 180, sep_y + 4)],
                   fill=(255, 255, 255, 160))

    # サブタイトル
    sub_y = sep_y + 24
    draw.text((pad_x, sub_y),   subtitle, font=f_sub, fill=(255, 255, 255, 220))
    bbox3 = draw.textbbox((pad_x, sub_y), subtitle, font=f_sub)

    # タグライン
    tag_y = bbox3[3] + 20
    draw.text((pad_x, tag_y),   tagline,  font=f_tag, fill=(255, 255, 255, 180))

    # スコアドット
    draw_score_dots(draw, pad_x, H - 70)

    # 凡例テキスト
    draw.text((pad_x + 6 * (10 * 2 + 16) + 16, H - 82),
              "0=なし  5=最重度",
              font=f_small, fill=(255, 255, 255, 130))

    # ドメイン（右下）
    f_domain = find_font(24)
    domain_text = "SymptoPort.app"
    d_bbox = draw.textbbox((0, 0), domain_text, font=f_domain)
    d_w = d_bbox[2] - d_bbox[0]
    draw.text((W - d_w - 40, H - 50), domain_text,
              font=f_domain, fill=(255, 255, 255, 100))

    # RGBA → RGB に変換して保存
    final = Image.new("RGB", (W, H), (0, 0, 0))
    final.paste(img, mask=img.split()[3])
    final.save(outpath, "PNG", optimize=True)
    print(f"生成: {outpath}")


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # LP 用 OG 画像
    make_og_image(
        title_line1 = "SymptoPort",
        title_line2 = "",
        subtitle    = "からだの天気図",
        tagline     = "症状を記録して、医師に伝える",
        outpath     = os.path.join(base_dir, "og-image.png"),
    )

    # アプリ内（ログイン済みページ）用 OG 画像
    make_og_image(
        title_line1 = "SymptoPort",
        title_line2 = "",
        subtitle    = "からだの天気図",
        tagline     = "毎日のスコアを記録・可視化",
        outpath     = os.path.join(base_dir, "og-image-app.png"),
    )


if __name__ == "__main__":
    main()
