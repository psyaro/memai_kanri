"""
Pillowでアプリアイコン(PNG)を生成するスクリプト。
実行: python static/icons/generate_icons.py
依存: pip install Pillow
"""
import os
import math

def draw_icon(size: int) -> "Image":
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 背景（角丸矩形）グラデント代わりに2色混合
    radius = size // 6
    # 背景を単色（#2d6fb0）で塗り、グラデントは省略（Pillowはグラデ未対応）
    # 角丸四角形
    draw.rounded_rectangle(
        [(0, 0), (size - 1, size - 1)],
        radius=radius,
        fill="#4a90d9",
    )

    # 折れ線グラフのポイント（512基準 → size にスケール）
    base = 512
    pts_base = [(80, 340), (160, 260), (240, 300), (320, 180), (400, 240), (480, 160)]
    pts = [(int(x * size / base), int(y * size / base)) for x, y in pts_base]

    lw = max(2, size // 26)

    # 影（半透明白）
    shadow_pts = [(x + lw // 2, y + lw // 2) for x, y in pts]
    draw.line(shadow_pts, fill=(255, 255, 255, 60), width=lw + 4)

    # 折れ線（白）
    draw.line(pts, fill="white", width=lw)

    # データ点
    dot_r = max(3, size // 32)
    for i, (x, y) in enumerate(pts[1:], 1):  # 最初の点は端なので省略
        draw.ellipse(
            [(x - dot_r, y - dot_r), (x + dot_r, y + dot_r)],
            fill="white",
        )

    # ハイライト点（最高点 = pts[3]）
    hx, hy = pts[3]
    hr = dot_r + max(2, size // 64)
    draw.ellipse([(hx - hr, hy - hr), (hx + hr, hy + hr)], fill="white")
    draw.ellipse(
        [(hx - dot_r, hy - dot_r), (hx + dot_r, hy + dot_r)],
        fill="#7b5ea7",
    )

    return img


def generate():
    try:
        from PIL import Image
    except ImportError:
        print("Pillow が未インストールです。以下を実行してください:")
        print("  pip install Pillow")
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]

    for size in sizes:
        img = draw_icon(size)
        out = os.path.join(base_dir, f"icon-{size}.png")
        img.save(out, "PNG")
        print(f"生成: {out}")

    print("完了。")


if __name__ == "__main__":
    generate()
