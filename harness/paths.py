"""项目根定位(全仓唯一):cases/evalsets/reports、.env、static 都从这里出发。

- 源码模式:按本文件位置向上找仓库根,与历史行为完全一致;
- 打包 exe:windowed 模式下代码在临时解包目录里,只读且退出即清,
  启动器(packaging/exe_entry.py)会在导入任何业务模块之前设 HARNESS_HOME
  指向可写的数据家目录,本模块优先采用该值 —— 全仓其余模块一律引用这里的
  PROJECT_ROOT,不允许再出现第二处 Path(__file__) 定位。
"""

from __future__ import annotations

import os
from pathlib import Path


def _resolve_root() -> Path:
    """HARNESS_HOME 优先(打包模式由启动器设置);否则按包位置回溯仓库根。"""
    override = os.environ.get("HARNESS_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


PROJECT_ROOT = _resolve_root()
