"""生成 PWA 图标资产:python scripts/generate_pwa_icons.py

用 resvg-py 把 webapp/static/assets/icon.svg 栅格化为:
  icon-192.png / icon-512.png          —— 常规用途(透明圆角)
  icon-maskable-512.png                —— Android 自适应图标(全出血底 + 80% 安全区)
  apple-touch-icon-180.png             —— iOS 主屏(不透明方底,iOS 自行加圆角)
产物提交入库:浏览器与 manifest 直接引用,运行时无需再生成。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "webapp" / "static" / "assets"

try:
    import resvg_py
except ModuleNotFoundError:
    sys.exit("缺少依赖 resvg-py:请先执行  pip install resvg-py")


def render(svg_text: str, size: int) -> bytes:
    return bytes(resvg_py.svg_to_bytes(svg_string=svg_text, width=size, height=size))


def maskable_svg(size: int = 512) -> str:
    """自适应图标:原 SVG 以 0.78 缩放居中(安全区),底为不透明的品牌深蓝。"""
    inner = (ASSETS / "icon.svg").read_text(encoding="utf-8")
    inner_body = inner[inner.index(">") + 1:].rsplit("</svg>", 1)[0]  # 去掉外壳,保留 defs+内容
    inner_size = round(size * 0.78)
    offset = round((size - inner_size) / 2)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"
 viewBox="0 0 {size} {size}">
  <rect width="{size}" height="{size}" fill="#141b3a"/>
  <svg x="{offset}" y="{offset}" width="{inner_size}" height="{inner_size}"
       viewBox="0 0 512 512">{inner_body}</svg>
</svg>"""


def apple_svg(size: int = 180) -> str:
    """iOS 主屏图标:不透明方形底(圆角交给系统),内容铺满。"""
    inner = (ASSETS / "icon.svg").read_text(encoding="utf-8")
    inner_body = inner[inner.index(">") + 1:].rsplit("</svg>", 1)[0]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"
 viewBox="0 0 {size} {size}">
  <rect width="{size}" height="{size}" fill="#141b3a"/>
  <svg width="{size}" height="{size}" viewBox="0 0 512 512">{inner_body}</svg>
</svg>"""


def main() -> None:
    icon = (ASSETS / "icon.svg").read_text(encoding="utf-8")
    targets = {
        "icon-192.png": render(icon, 192),
        "icon-512.png": render(icon, 512),
        "icon-maskable-512.png": render(maskable_svg(512), 512),
        "apple-touch-icon-180.png": render(apple_svg(180), 180),
    }
    for name, data in targets.items():
        path = ASSETS / name
        path.write_bytes(data)
        print(f"{path.relative_to(ROOT)}  ({len(data)} bytes)")
    print(f"完成:{len(targets)} 个图标已生成")


if __name__ == "__main__":
    main()
