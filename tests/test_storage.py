"""harness.storage:路径安全、case 沉淀/删除与评测集清单一致性、原子写。"""

import json

import pytest
from harness import storage
from harness.models import ReplayCase


def test_safe_label_neutralizes_path_chars():
    cleaned = storage.safe_label('../../etc')
    assert "/" not in cleaned and "\\" not in cleaned  # 无法构造路径分隔
    assert storage.safe_label("  ") == "未分类"
    cleaned2 = storage.safe_label('阈值/错误:*?"<>|')
    assert set(cleaned2) & set('/\\:*?"<>|') == set()


def test_safe_name_rejects_traversal():
    for bad in ("../secret", "a/b", "", "a b", "x" * 200, ".."):
        with pytest.raises(ValueError):
            storage._safe_name(bad)
    assert storage._safe_name("evalset_v1") == "evalset_v1"
    assert storage._safe_name("evalset_scenario_rain") == "evalset_scenario_rain"


def test_load_dataset_rejects_traversal():
    with pytest.raises(ValueError):
        storage.load_dataset("../../webapp/auth")


def test_load_evalset_rejects_traversal():
    with pytest.raises(ValueError):
        storage.load_evalset("../../webapp/auth")


def test_save_load_delete_case_roundtrip(hermetic_storage):
    case = ReplayCase(case_id="rc-9001", title="t", label="新标签",
                      dataset_name="base")
    path = storage.save_case(case)
    assert path.exists()
    loaded = storage.load_case("rc-9001")
    assert loaded == case

    assert storage.delete_case("rc-9001") is True
    assert storage.load_case("rc-9001") is None
    assert storage.delete_case("rc-9001") is False  # 幂等


def test_delete_case_removes_from_all_evalsets(hermetic_storage):
    """删除 case 必须同步清理评测集清单,避免悬空引用导致后续评测崩溃。"""
    case = ReplayCase(case_id="rc-9002", title="t", label="阈值错误", dataset_name="base")
    storage.save_case(case)
    assert storage.add_case_to_evalset("rc-9002", "evalset_v1") is True   # 新加入
    assert storage.add_case_to_evalset("rc-9002", "evalset_v1") is False  # 重复加入被拒
    storage.add_case_to_evalset("rc-9002", "evalset_scenario_rain")

    storage.delete_case("rc-9002")
    for name in ("evalset_v1", "evalset_scenario_rain"):
        manifest = storage.load_evalset(name)
        assert "rc-9002" not in manifest["case_ids"]


def test_load_evalset_cases_raises_on_missing_reference(hermetic_storage):
    manifest_path = hermetic_storage["evalsets"] / "evalset_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["case_ids"].append("rc-4040")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(KeyError):
        storage.load_evalset_cases("evalset_v1")


def test_list_evalsets_and_datasets(hermetic_storage):
    evalsets = {e["evalset_id"]: e for e in storage.list_evalsets()}
    assert evalsets["evalset_v1"]["case_count"] == 13
    assert evalsets["evalset_scenario_rain"]["case_count"] == 3

    datasets = {d["name"] for d in storage.list_datasets()}
    assert {"base", "rain_peak", "incident", "evening_peak",
            "missing_volume", "empty"} <= datasets


def test_atomic_write_leaves_no_tmp(hermetic_storage):
    case = ReplayCase(case_id="rc-9003", title="t", label="边界处理", dataset_name="base")
    path = storage.save_case(case)
    assert not path.with_suffix(".json.tmp").exists()
    json.loads(path.read_text(encoding="utf-8"))  # 写出的是完整合法 JSON
