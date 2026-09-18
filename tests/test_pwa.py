"""PWA 资产与接入点测试:manifest / Service Worker / 图标 / 页面接线。"""

from __future__ import annotations

import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "webapp" / "static" / "assets"


class TestServiceWorker:
    def test_sw_served_at_root(self, client):
        """/sw.js 必须从根路径提供(SW 作用域 = 脚本目录),否则无法控制页面。"""
        resp = client.get("/sw.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]
        assert "harness-shell-v1" in resp.text  # 版本化缓存标识

    def test_sw_registered_by_pages(self, client):
        for path in ("/", "/help"):
            html = client.get(path).text
            assert 'serviceWorker.register("/sw.js")' in html, path


class TestManifest:
    def test_manifest_served(self, client):
        resp = client.get("/static/manifest.webmanifest")
        assert resp.status_code == 200
        json.loads(resp.text)  # 可解析即通过;字段校验见下一条

    def test_manifest_installability_fields(self, client):
        manifest = json.loads(client.get("/static/manifest.webmanifest").text)
        assert manifest["start_url"] == "/"
        assert manifest["scope"] == "/"
        assert manifest["display"] == "standalone"
        assert manifest["lang"] == "zh-CN"
        png_icons = [i for i in manifest["icons"] if i["type"] == "image/png"]
        sizes = {i["sizes"] for i in png_icons}
        assert {"192x192", "512x512"} <= sizes                      # Chromium 可安装性要求
        assert any(i.get("purpose") == "maskable" for i in manifest["icons"])
        assert {s["url"] for s in manifest.get("shortcuts", [])} == {"/", "/help"}

    def test_manifest_linked_from_pages(self, client):
        for path in ("/", "/help"):
            assert 'rel="manifest"' in client.get(path).text, path


class TestIconAssets:
    def test_png_icons_exist_with_correct_sizes(self):
        from PIL import Image

        expected = {"icon-192.png": (192, 192), "icon-512.png": (512, 512),
                    "icon-maskable-512.png": (512, 512), "apple-touch-icon-180.png": (180, 180)}
        for name, size in expected.items():
            image = Image.open(ASSETS / name)
            assert image.size == size, name

    def test_maskable_is_opaque(self):
        """自适应图标必须全出血不透明,否则 Android 蒙版下会露白。"""
        from PIL import Image

        corner = Image.open(ASSETS / "icon-maskable-512.png").convert("RGBA").getpixel((0, 0))
        assert corner[3] == 255
