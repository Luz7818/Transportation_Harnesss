"""harness-client 命令行:装完 SDK 即可在终端直接查询评测服务。

    harness-client health --base-url http://47.114.37.174:8765 --token <TOKEN>
    harness-client versions
    harness-client analyze --version v2 --dataset base
    harness-client eval --version v2

地址与令牌支持环境变量 HARNESS_BASE_URL / HARNESS_TOKEN,免去重复输入。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .client import TransportationHarnessClient


def _make_client(args: argparse.Namespace) -> TransportationHarnessClient:
    return TransportationHarnessClient(
        base_url=args.base_url, token=args.token, timeout=args.timeout,
    )


def _print(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _common_args(defaults: bool) -> argparse.ArgumentParser:
    """连接参数组。defaults=True 用于主解析器(带默认值);
    False 用于子解析器(默认值用 SUPPRESS,避免覆盖子命令前已解析的值)。"""
    common = argparse.ArgumentParser(add_help=False)
    d = (lambda v: v) if defaults else (lambda v: argparse.SUPPRESS)
    common.add_argument("--base-url", default=d(os.getenv("HARNESS_BASE_URL", "http://127.0.0.1:8765")),
                        help="服务地址(默认取 HARNESS_BASE_URL,再退 http://127.0.0.1:8765)")
    common.add_argument("--token", default=d(os.getenv("HARNESS_TOKEN", "")),
                        help="机器令牌(默认取 HARNESS_TOKEN)")
    common.add_argument("--timeout", default=d(10.0), type=float, help="单请求超时秒数")
    return common


def build_parser() -> argparse.ArgumentParser:
    """全局参数置于子命令前后均可:主解析器持默认值,子解析器仅显式覆盖。"""
    parser = argparse.ArgumentParser(
        prog="harness-client", description="交通分析自进化 Harness 命令行客户端",
        parents=[_common_args(defaults=True)])
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (("health", "健康检查:版本、鉴权模式、资产数量"),
                            ("versions", "列出管线版本(v0/v1/v2)与各轮优化内容"),
                            ("datasets", "列出情景数据集(常规/雨天/事故/晚高峰)")):
        sub.add_parser(name, help=help_text, parents=[_common_args(defaults=False)])

    p_eval = sub.add_parser("eval", help="运行一次评测", parents=[_common_args(defaults=False)])
    p_eval.add_argument("--version", default="v2", help="管线版本(默认 v2)")
    p_eval.add_argument("--evalset", default="evalset_v1", help="评测集(默认 evalset_v1)")

    p_an = sub.add_parser("analyze", help="发起一次交通分析", parents=[_common_args(defaults=False)])
    p_an.add_argument("--version", default="v2", help="管线版本(默认 v2)")
    p_an.add_argument("--dataset", required=True, help="情景数据集名(见 datasets)")

    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        client = _make_client(args)
        try:
            if args.command == "health":
                _print(client.health())
            elif args.command == "versions":
                _print(client.versions())
            elif args.command == "datasets":
                _print(client.datasets())
            elif args.command == "eval":
                result = client.run_eval(version=args.version, evalset=args.evalset)
                print(f"{result.version} 于 {result.evalset_id}:"
                      f"{result.passed_count}/{result.total} 通过({result.accuracy:.1%})")
                if result.report_id:
                    print(f"报告:{result.report_id}")
                for case in result.failed_cases():
                    print(f"  FAIL {case.case_id} [{case.label}] {case.title}")
            elif args.command == "analyze":
                _print(client.analyze(version=args.version, dataset_name=args.dataset))
        finally:
            client.close()
    except Exception as exc:  # CLI 边界:统一转为非零退出码
        print(f"错误:{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
