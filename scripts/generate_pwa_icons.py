"""生成 PWA 图标资产:python scripts/generate_pwa_icons.py

用 resvg-py 把 webapp/static/assets/icon.svg 栅格化为:
  icon-192.png / icon-512.png          —— 常规用途(透明圆角)
  icon-maskable-512.png                —— Android 自适应图标(全出血底 + 80% 安全区)
  apple-touch-icon-180.png             —— iOS 主屏(不透明方底,iOS 自行加圆角)
并从 icon.svg 内联组合出 logo-lockup.svg(横版 Logo,单一来源保持同步)。
产物提交入库:浏览器与 manifest 直接引用,运行时无需再生成。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "webapp" / "static" / "assets"

# 与 icon.svg 背景渐变中段一致的自适应/苹果图标出血底色
BRAND_BG = "#10183a"

try:
    import resvg_py
except ModuleNotFoundError:
    sys.exit("缺少依赖 resvg-py:请先执行  pip install resvg-py")


def render(svg_text: str, size: int) -> bytes:
    return bytes(resvg_py.svg_to_bytes(svg_string=svg_text, width=size, height=size))


def icon_body() -> str:
    """icon.svg 去掉外壳后的内容(defs + 图形),供嵌套组合。"""
    inner = (ASSETS / "icon.svg").read_text(encoding="utf-8")
    return inner[inner.index(">") + 1:].rsplit("</svg>", 1)[0]


def maskable_svg(size: int = 512) -> str:
    """自适应图标:原 SVG 以 0.78 缩放居中(安全区),底为不透明的品牌深蓝。"""
    inner_size = round(size * 0.78)
    offset = round((size - inner_size) / 2)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"
 viewBox="0 0 {size} {size}">
  <rect width="{size}" height="{size}" fill="{BRAND_BG}"/>
  <svg x="{offset}" y="{offset}" width="{inner_size}" height="{inner_size}"
       viewBox="0 0 512 512">{icon_body()}</svg>
</svg>"""


def apple_svg(size: int = 180) -> str:
    """iOS 主屏图标:不透明方形底(圆角交给系统),内容铺满。"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"
 viewBox="0 0 {size} {size}">
  <rect width="{size}" height="{size}" fill="{BRAND_BG}"/>
  <svg width="{size}" height="{size}" viewBox="0 0 512 512">{icon_body()}</svg>
</svg>"""


def lockup_svg() -> str:
    """横版 Logo 组合(README/文档用,置于深色底):内联图标 + 双语字标。"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="680" height="160"
 viewBox="0 0 680 160" role="img" aria-label="Transportation Harness · 交通分析自进化评测系统">
  <defs>
    <linearGradient id="tg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#f2f5fb"/>
      <stop offset="1" stop-color="#a5b4fc"/>
    </linearGradient>
  </defs>
  <svg x="16" y="16" width="128" height="128" viewBox="0 0 512 512">{icon_body()}</svg>
  <text x="172" y="78" font-family="'Segoe UI','PingFang SC','Microsoft YaHei',system-ui,sans-serif"
        font-size="42" font-weight="800" letter-spacing=".5" fill="url(#tg)">Transportation Harness</text>
  <text x="174" y="118" font-family="'Segoe UI','PingFang SC','Microsoft YaHei',system-ui,sans-serif"
        font-size="17" font-weight="500" letter-spacing="5" fill="#8b98ad">交通分析自进化评测系统</text>
</svg>
"""


def banner_svg() -> str:
    """README/文档品牌横幅:夜城路网 + 进化轨道背景,内联图标 + 双语字标 + 标语胶囊。"""
    pills = [
        ("评测驱动 · 自进化 · 回归守护", "#c7d2fe", "rgba(129,140,248,.45)", 338),
        ("实测 7.7% → 100%", "#6ee7b7", "rgba(52,211,153,.5)", 218),
        ("全程零回归", "#93c5fd", "rgba(96,165,250,.5)", 150),
    ]
    pill_marks, x = [], 300
    for text, fg, bd, w in pills:
        pill_marks.append(
            f'<rect x="{x}" y="252" width="{w}" height="42" rx="21" fill="rgba(99,102,241,.10)" '
            f'stroke="{bd}" stroke-width="1.4"/>\n'
            f'  <text x="{x + w / 2}" y="279" text-anchor="middle" '
            f'font-family="\'Segoe UI\',\'PingFang SC\',\'Microsoft YaHei\',system-ui,sans-serif" '
            f'font-size="18" font-weight="600" letter-spacing="1" fill="{fg}">{text}</text>'
        )
        x += w + 14
    pill_svg = "\n  ".join(pill_marks)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="400"
 viewBox="0 0 1280 400" role="img" aria-label="Transportation Harness · 交通分析自进化评测系统">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#05080f"/>
      <stop offset=".55" stop-color="#0b1226"/>
      <stop offset="1" stop-color="#1b1140"/>
    </linearGradient>
    <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#4f46e5"/>
      <stop offset=".55" stop-color="#7c3aed"/>
      <stop offset="1" stop-color="#22d3ee"/>
    </linearGradient>
    <linearGradient id="tg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#f2f5fb"/>
      <stop offset="1" stop-color="#a5b4fc"/>
    </linearGradient>
    <linearGradient id="trail" x1="0" y1="1" x2="1" y2="0">
      <stop offset="0" stop-color="#22d3ee" stop-opacity="0"/>
      <stop offset=".5" stop-color="#67e8f9" stop-opacity=".8"/>
      <stop offset="1" stop-color="#a5f3fc" stop-opacity="0"/>
    </linearGradient>
    <radialGradient id="blobP" cx=".5" cy=".5" r=".5">
      <stop offset="0" stop-color="#7c3aed" stop-opacity=".3"/>
      <stop offset="1" stop-color="#7c3aed" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="blobC" cx=".5" cy=".5" r=".5">
      <stop offset="0" stop-color="#22d3ee" stop-opacity=".22"/>
      <stop offset="1" stop-color="#22d3ee" stop-opacity="0"/>
    </radialGradient>
    <pattern id="dots" width="46" height="46" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="1.3" fill="#8ea2c9" opacity=".13"/>
    </pattern>
    <filter id="blurL" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="14"/>
    </filter>
  </defs>

  <rect width="1280" height="400" fill="url(#sky)"/>
  <rect width="1280" height="400" fill="url(#dots)"/>
  <ellipse cx="1060" cy="120" rx="480" ry="260" fill="url(#blobP)"/>
  <ellipse cx="220" cy="380" rx="460" ry="240" fill="url(#blobC)"/>

  <!-- 数据光轨 -->
  <path d="M-40 340 C 300 280, 640 360, 980 280 S 1240 180, 1330 190"
        fill="none" stroke="url(#trail)" stroke-width="10" stroke-linecap="round"
        opacity=".45" filter="url(#blurL)"/>
  <path d="M-40 340 C 300 280, 640 360, 980 280 S 1240 180, 1330 190"
        fill="none" stroke="url(#trail)" stroke-width="2.4" stroke-linecap="round" opacity=".7"/>

  <!-- 进化轨道大环(右侧) -->
  <g transform="rotate(-16 1040 175)" fill="none">
    <ellipse cx="1040" cy="175" rx="228" ry="80" stroke="url(#ring)" stroke-width="4.5"
             stroke-dasharray="1130 290" stroke-linecap="round" opacity=".62"/>
    <path d="M1256 144 L 1272 162 L 1252 177" stroke="#22d3ee" stroke-width="6"
         stroke-linecap="round" stroke-linejoin="round" opacity=".9"/>
    <circle cx="812" cy="175" r="7" fill="#a5b4fc" opacity=".9"/>
    <circle cx="965" cy="97" r="8" fill="#34d399" opacity=".95"/>
    <circle cx="1160" cy="122" r="5.5" fill="#67e8f9" opacity=".9"/>
  </g>

  <!-- 天际线与路面 -->
  <g fill="#0a0f28" opacity=".95">
    <rect x="560" y="306" width="40" height="60"/><rect x="608" y="322" width="48" height="44"/>
    <rect x="1120" y="286" width="44" height="80"/>
    <rect x="1172" y="312" width="52" height="54"/>
  </g>
  <path d="M-20 374 L 1300 374 L 1300 336 L -20 336 Z" fill="#0d142e"/>
  <path d="M-20 336 H 1300" stroke="#2b3660" stroke-width="2" opacity=".7"/>
  <path d="M-20 356 H 1300" stroke="#67e8f9" stroke-width="4.5"
        stroke-linecap="round" stroke-dasharray="30 24" opacity=".5"/>

  <!-- 品牌区:内联应用图标 + 字标 -->
  <svg x="72" y="104" width="176" height="176" viewBox="0 0 512 512">{icon_body()}</svg>
  <text x="300" y="182" font-family="'Segoe UI','PingFang SC','Microsoft YaHei',system-ui,sans-serif"
        font-size="54" font-weight="800" letter-spacing=".5" fill="url(#tg)">Transportation Harness</text>
  <text x="303" y="224" font-family="'Segoe UI','PingFang SC','Microsoft YaHei',system-ui,sans-serif"
        font-size="21" font-weight="500" letter-spacing="6" fill="#8b98ad">交通分析自进化评测系统</text>
  {pill_svg}
</svg>
"""


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
    (ASSETS / "logo-lockup.svg").write_text(lockup_svg(), encoding="utf-8")
    print(f"{(ASSETS / 'logo-lockup.svg').relative_to(ROOT)}  (由 icon.svg 内联组合)")
    (ASSETS / "banner.svg").write_text(banner_svg(), encoding="utf-8")
    print(f"{(ASSETS / 'banner.svg').relative_to(ROOT)}  (由 icon.svg 内联组合)")
    print(f"完成:{len(targets)} 个图标 + 横版 Logo + 品牌横幅已生成")


if __name__ == "__main__":
    main()
