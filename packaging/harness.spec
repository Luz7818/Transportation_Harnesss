# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置:onefile + windowed(独立桌面窗口,平时无黑窗口)。

构建:packaging/build_exe.bat(或 pyinstaller packaging/harness.spec)
产物:dist/TransportationHarness.exe —— 单文件,双击出 pywebview 窗口(WebView2 渲染看板),
数据落在 exe 旁 harness-home/;--server 参数切无头服务模式。
种子资产经 datas 打入 exe;首次运行由 exe_entry.py 播种到数据家目录(缺了才复制)。
"""

import os

# SPECPATH 由 PyInstaller 注入 = 本 spec 所在目录;仓库根是其上一级,
# pathex 交给静态分析,让 harness/llm/pipeline/webapp 四个顶层包可被 import 解析
REPO_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    ["exe_entry.py"],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=[
        (os.path.join(REPO_ROOT, "cases"), "cases"),
        (os.path.join(REPO_ROOT, "evalsets"), "evalsets"),
        (os.path.join(REPO_ROOT, "reports"), "reports"),
        (os.path.join(REPO_ROOT, "llm_cache"), "llm_cache"),
        (os.path.join(REPO_ROOT, "pipeline", "data"), "pipeline/data"),
        (os.path.join(REPO_ROOT, "webapp", "static"), "webapp/static"),
        (os.path.join(REPO_ROOT, ".env.example"), "."),
    ],
    hiddenimports=[
        # uvicorn 的 loop/http/websockets/lifespan 都是按 "auto" 字符串动态 import 的,
        # 静态分析看不见,必须显式列出;未安装的实现(如 wsproto)缺失仅告警不致命
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # pywebview 的 Windows 后端:WinForms 宿主 + WebView2 渲染(hooks-contrib 的
        # hook-webview/clr/clr_loader 负责包数据,平台模块仍需显式点名)
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="TransportationHarness",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # windowed:平时无黑窗口;GUI 报错走 MessageBox,--server 报错走弹出的控制台
    icon=os.path.join(SPECPATH, "harness.ico"),   # 由 webapp/static/assets/icon-512.png 一次性转换
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
