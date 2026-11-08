"""scripts/import_dataset.py:CSV/JSON 摄取往返、校验失败退出码、真实资产零写入。"""

import importlib.util
import json
from pathlib import Path

import pytest
from harness import storage

PROJECT_ROOT = Path(__file__).resolve().parents[1]

_SPEC = importlib.util.spec_from_file_location(
    "import_dataset_cli", PROJECT_ROOT / "scripts" / "import_dataset.py")
cli = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cli)

CSV_HEADER = ("segment_id,name,length_km,lane_count,"
              "capacity_per_lane,volume,speed,free_flow_speed")


def _write_csv(path: Path, *rows: str) -> Path:
    path.write_text("\n".join((CSV_HEADER, *rows)) + "\n", encoding="utf-8")
    return path


def _snapshot(data_dir: Path) -> dict:
    """真实 pipeline/data 的逐文件字节快照,用于断言「测试前后内容不变」。"""
    return {p.name: p.read_bytes() for p in data_dir.glob("*.json")}


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    """硬性隔离:storage.DATA_DIR 指到临时目录。

    conftest 的 hermetic_storage 只隔离 cases/evalsets/reports(注释自述
    「DATA_DIR 保持真实」),本文件的被测 CLI 是写通道——不隔离就会写进真实
    pipeline/data/、改变 /api/datasets 资产计数。收尾断言真实目录逐文件
    字节不变,即「全程零写入真实评测资产」。
    """
    real_dir = storage.DATA_DIR
    before = _snapshot(real_dir)
    target = tmp_path / "data"
    monkeypatch.setattr(storage, "DATA_DIR", target)
    yield target
    assert _snapshot(real_dir) == before


def _run_expect_reject(argv: list[str], capsys) -> str:
    with pytest.raises(SystemExit) as ei:
        cli.main(argv)
    assert ei.value.code != 0
    return capsys.readouterr().err


def test_import_csv_roundtrip(isolated_data_dir, tmp_path):
    csv_path = _write_csv(
        tmp_path / "sample.csv",
        "S-01,城东大道,3.2,4,1800,3000,45,60",
        "S-02,学府路,1.8,2,1700,,18,50",
        "S-03,长江路,4.5,6,1800,9200,22,60",
    )
    cli.main([str(csv_path), "--name", "import_demo", "--source", "外业采集",
              "--captured-at", "2026-10-01 08:00", "--description", "三路段样例"])

    segments = storage.load_dataset("import_demo")
    assert [s["segment_id"] for s in segments] == ["S-01", "S-02", "S-03"]
    assert segments[1]["volume"] is None  # CSV 空单元格 → 缺测形态
    datasets = {d["name"]: d for d in storage.list_datasets()}
    assert datasets["import_demo"]["source"] == "外业采集"
    assert datasets["import_demo"]["captured_at"] == "2026-10-01 08:00"
    doc = json.loads((isolated_data_dir / "import_demo.json").read_text(encoding="utf-8"))
    assert doc["dataset_id"] == "import_demo"
    assert doc["description"] == "三路段样例"
    assert "scenario" not in doc  # 未提供情景 → 顶层不带 scenario 键


def test_import_empty_segments_without_scenario(isolated_data_dir, tmp_path):
    """空 segments + 缺 scenario 的样例经同一通道往返(同 empty.json 形态)。"""
    json_path = tmp_path / "empty_sample.json"
    json_path.write_text('{"segments": []}', encoding="utf-8")
    cli.main([str(json_path), "--name", "empty_demo", "--source", "合成快照",
              "--captured-at", "2026-10-01 08:00"])

    assert storage.load_dataset("empty_demo") == []
    entry = {d["name"]: d for d in storage.list_datasets()}["empty_demo"]
    assert entry["source"] == "合成快照"
    assert entry["captured_at"] == "2026-10-01 08:00"
    assert entry["scenario"] is None  # list_datasets 对缺 scenario 键回 None
    doc = json.loads((isolated_data_dir / "empty_demo.json").read_text(encoding="utf-8"))
    assert "scenario" not in doc


def test_import_json_segments_and_scenario_passthrough(isolated_data_dir, tmp_path):
    """JSON 带 segments 与 scenario 时透传;--name 缺省取文件主干。"""
    json_path = tmp_path / "field_upload.json"
    payload = {
        "description": "外场设备直传",
        "scenario": {"tag": "现场标定", "insight": "外场设备直传的单段样例"},
        "segments": [{"segment_id": "R-1", "name": "测试段", "length_km": 1.0,
                      "lane_count": 2, "capacity_per_lane": 1600, "volume": 2000,
                      "speed": 40, "free_flow_speed": 60}],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    cli.main([str(json_path), "--source", "外场设备", "--captured-at", "2026-10-02 09:30"])

    doc = json.loads((isolated_data_dir / "field_upload.json").read_text(encoding="utf-8"))
    assert doc["dataset_id"] == "field_upload"
    assert doc["description"] == "外场设备直传"
    assert doc["scenario"] == {"tag": "现场标定", "insight": "外场设备直传的单段样例"}
    assert storage.load_dataset("field_upload")[0]["segment_id"] == "R-1"


def test_reject_missing_field_reports_field(isolated_data_dir, tmp_path, capsys):
    json_path = tmp_path / "missing_field.json"
    seg = {"segment_id": "S-01", "name": "段", "length_km": 1.0, "lane_count": 2,
           "capacity_per_lane": 1600, "volume": 100, "speed": 40}
    json_path.write_text(json.dumps({"segments": [seg]}, ensure_ascii=False),
                         encoding="utf-8")

    err = _run_expect_reject(
        [str(json_path), "--name", "bad_missing", "--source", "x",
         "--captured-at", "2026-10-01 08:00"], capsys)
    assert "free_flow_speed" in err
    assert not (isolated_data_dir / "bad_missing.json").exists()  # 校验失败不落盘


def test_reject_negative_value_reports_field(isolated_data_dir, tmp_path, capsys):
    csv_path = _write_csv(tmp_path / "negative.csv",
                          "S-01,城东大道,3.2,4,1800,-5,45,60")

    err = _run_expect_reject(
        [str(csv_path), "--name", "bad_negative", "--source", "x",
         "--captured-at", "2026-10-01 08:00"], capsys)
    assert "volume" in err and "-5" in err
    assert not (isolated_data_dir / "bad_negative.json").exists()


def test_reject_duplicate_segment_id(isolated_data_dir, tmp_path, capsys):
    json_path = tmp_path / "dup.json"
    seg = {"segment_id": "S-01", "name": "段", "length_km": 1.0, "lane_count": 2,
           "capacity_per_lane": 1600, "volume": 100, "speed": 40, "free_flow_speed": 60}
    json_path.write_text(json.dumps({"segments": [seg, dict(seg)]}, ensure_ascii=False),
                         encoding="utf-8")

    err = _run_expect_reject(
        [str(json_path), "--name", "bad_dup", "--source", "x",
         "--captured-at", "2026-10-01 08:00"], capsys)
    assert "S-01" in err and "重复" in err
    assert not (isolated_data_dir / "bad_dup.json").exists()


def test_reject_unsafe_name(isolated_data_dir, tmp_path, capsys):
    csv_path = _write_csv(tmp_path / "ok.csv", "S-01,城东大道,3.2,4,1800,3000,45,60")

    err = _run_expect_reject([str(csv_path), "--name", "../evil", "--source", "x"], capsys)
    assert "非法数据集名" in err  # 复用 storage._safe_name 的白名单
    assert not (isolated_data_dir / "evil.json").exists()
