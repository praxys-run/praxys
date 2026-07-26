"""Tests for locale-aware theory loading."""
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

import analysis.science as science


ZONE_THEORIES = (
    (
        "coggan_5zone",
        {
            "power": ["恢复", "耐力", "节奏跑", "乳酸阈", "VO2max"],
            "hr": ["恢复", "耐力", "节奏跑", "乳酸阈", "VO2max"],
            "pace": ["恢复", "耐力", "节奏跑", "乳酸阈", "VO2max"],
        },
    ),
    (
        "polarized_3zone",
        ["第 1 区（轻松）", "第 2 区（中等）", "第 3 区（高强度）"],
    ),
    (
        "pyramidal_3zone",
        ["第 1 区（轻松）", "第 2 区（中等）", "第 3 区（高强度）"],
    ),
)


def _write_theory(path: Path, name: str, description: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({
        "id": path.stem,
        "pillar": "load",
        "name": name,
        "description": description,
        "params": {"ctl_time_constant": 42, "atl_time_constant": 7},
    }), encoding="utf-8")


def test_loader_prefers_localized_file(tmp_path: Path) -> None:
    en_path = tmp_path / "load" / "banister_pmc.yaml"
    zh_path = tmp_path / "zh" / "load" / "banister_pmc.yaml"
    _write_theory(en_path, "Banister PMC", "Performance Management Chart")
    _write_theory(zh_path, "Banister xunlian biao", "jixiao guanli tubiao")

    with patch.object(science, "_SCIENCE_DIR", str(tmp_path)):
        en_theory = science.load_theory("load", "banister_pmc")
        zh_theory = science.load_theory("load", "banister_pmc", locale="zh")

    assert en_theory.name == "Banister PMC"
    assert zh_theory.name == "Banister xunlian biao"
    assert zh_theory.description == "jixiao guanli tubiao"


def test_localized_file_cannot_override_canonical_science_fields(
    tmp_path: Path,
) -> None:
    en_path = tmp_path / "load" / "banister_pmc.yaml"
    zh_path = tmp_path / "zh" / "load" / "banister_pmc.yaml"
    _write_theory(en_path, "Banister PMC", "English")
    _write_theory(zh_path, "Banister xunlian biao", "Chinese")
    localized = yaml.safe_load(zh_path.read_text(encoding="utf-8"))
    localized.update({
        "id": "other",
        "pillar": "prediction",
        "author": "translator",
        "params": {"ctl_time_constant": 1, "atl_time_constant": 1},
        "science_decision_id": "sdr-unknown-v1",
        "model_version": "unknown-v1",
        "citations": [{"not": "valid"}],
    })
    zh_path.write_text(
        yaml.safe_dump(localized, sort_keys=False),
        encoding="utf-8",
    )

    with patch.object(science, "_SCIENCE_DIR", str(tmp_path)):
        theory = science.load_theory("load", "banister_pmc", locale="zh")

    assert theory.id == "banister_pmc"
    assert theory.pillar == "load"
    assert theory.author == "system"
    assert theory.params["ctl_time_constant"] == 42
    assert theory.params["atl_time_constant"] == 7
    assert theory.science_decision_id is None
    assert theory.citations == []


@pytest.mark.parametrize(("theory_id", "expected_names"), ZONE_THEORIES)
def test_real_zh_zone_theories_localize_names_only(
    theory_id: str,
    expected_names: list[str] | dict[str, list[str]],
) -> None:
    en = science.load_theory("zones", theory_id)
    zh = science.load_theory("zones", theory_id, locale="zh")

    assert zh.zone_names == expected_names
    assert zh.zone_names != en.zone_names
    assert zh.zone_boundaries == en.zone_boundaries
    assert zh.target_distribution == en.target_distribution
    assert {
        key: value for key, value in zh.params.items() if key != "zone_names"
    } == {
        key: value for key, value in en.params.items() if key != "zone_names"
    }
    assert zh.citations == en.citations
    assert zh.tsb_zones == en.tsb_zones


def test_localized_zone_params_cannot_override_behavioral_values(
    tmp_path: Path,
) -> None:
    base = {
        "id": "coggan_5zone",
        "pillar": "zones",
        "name": "Test zones",
        "description": "English",
        "params": {
            "zone_count": 3,
            "boundaries": {"power": [0.8, 1.0]},
            "zone_names": ["Easy", "Moderate", "Hard"],
            "target_distribution": [0.8, 0.05, 0.15],
        },
    }
    localized = {
        **base,
        "name": "测试区间",
        "params": {
            "zone_count": 2,
            "boundaries": {"power": [0.5]},
            "zone_names": ["轻松", "中等", "高强度"],
            "target_distribution": [0.5, 0.5],
        },
    }
    en_path = tmp_path / "zones" / "coggan_5zone.yaml"
    zh_path = tmp_path / "zh" / "zones" / "coggan_5zone.yaml"
    en_path.parent.mkdir(parents=True)
    zh_path.parent.mkdir(parents=True)
    en_path.write_text(yaml.safe_dump(base, sort_keys=False), encoding="utf-8")
    zh_path.write_text(
        yaml.safe_dump(localized, sort_keys=False),
        encoding="utf-8",
    )

    with patch.object(science, "_SCIENCE_DIR", str(tmp_path)):
        theory = science.load_theory("zones", "coggan_5zone", locale="zh")

    assert theory.name == "测试区间"
    assert theory.zone_names == ["轻松", "中等", "高强度"]
    assert theory.zone_count == 3
    assert theory.zone_boundaries == {"power": [0.8, 1.0]}
    assert theory.target_distribution == [0.8, 0.05, 0.15]


def test_loader_falls_back_when_locale_missing(tmp_path: Path) -> None:
    _write_theory(tmp_path / "load" / "banister_pmc.yaml", "Banister PMC", "English copy")
    with patch.object(science, "_SCIENCE_DIR", str(tmp_path)):
        zh_theory = science.load_theory("load", "banister_pmc", locale="zh")
    assert zh_theory.name == "Banister PMC"
    assert zh_theory.description == "English copy"


def test_list_theories_resolves_locale_per_file(tmp_path: Path) -> None:
    _write_theory(
        tmp_path / "load" / "banister_pmc.yaml",
        "PMC",
        "en PMC",
    )
    _write_theory(
        tmp_path / "load" / "banister_ultra.yaml",
        "Ultra",
        "en Ultra",
    )
    _write_theory(
        tmp_path / "zh" / "load" / "banister_pmc.yaml",
        "PMC zh",
        "zh PMC",
    )
    with patch.object(science, "_SCIENCE_DIR", str(tmp_path)):
        theories = {t.id: t for t in science.list_theories("load", locale="zh")}
    assert theories["banister_pmc"].name == "PMC zh"
    assert theories["banister_ultra"].name == "Ultra"


def test_locale_none_matches_legacy_behavior(tmp_path: Path) -> None:
    _write_theory(tmp_path / "load" / "banister_pmc.yaml", "Banister PMC", "Original")
    _write_theory(tmp_path / "zh" / "load" / "banister_pmc.yaml", "ignored", "ignored")
    with patch.object(science, "_SCIENCE_DIR", str(tmp_path)):
        theory = science.load_theory("load", "banister_pmc", locale=None)
    assert theory.name == "Banister PMC"


def test_localized_theory_requires_english_base(tmp_path: Path) -> None:
    _write_theory(
        tmp_path / "zh" / "load" / "banister_pmc.yaml",
        "Banister xunlian biao",
        "jixiao guanli tubiao",
    )

    with (
        patch.object(science, "_SCIENCE_DIR", str(tmp_path)),
        pytest.raises(FileNotFoundError, match="English base theory"),
    ):
        science.load_theory("load", "banister_pmc", locale="zh")


def test_new_theory_requires_an_accepted_science_decision(tmp_path: Path) -> None:
    _write_theory(
        tmp_path / "load" / "new_theory.yaml",
        "New theory",
        "Unregistered",
    )

    with (
        patch.object(science, "_SCIENCE_DIR", str(tmp_path)),
        pytest.raises(ValueError, match="accepted Science Decision Record"),
    ):
        science.load_theory("load", "new_theory")


def test_theory_provenance_includes_all_behavioral_fields() -> None:
    values = science._theory_provenance_values(
        {"constant": 42},
        {"readiness_rest": 60},
        {"work_split_min_sec": 120},
        [{"min": None, "max": -30}],
    )

    assert values == {
        "constant": 42,
        "signal.readiness_rest": 60,
        "diagnosis.work_split_min_sec": 120,
        "tsb_zones": [{"min": None, "max": -30}],
    }


def test_registered_load_theory_applies_behavioral_defaults(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from analysis.evidence_registry import (
        AffectedSurfaces,
        ParameterClassification,
        ParameterProvenance,
        RecordStatus,
        ScienceDecisionRecord,
        ScienceRegistry,
    )

    theory_path = tmp_path / "load" / "registered.yaml"
    _write_theory(theory_path, "Registered", "Registry governed")
    theory_data = yaml.safe_load(theory_path.read_text(encoding="utf-8"))
    theory_data.update({
        "model_version": "registered-v1",
        "science_decision_id": "sdr-registered-v1",
        "tsb_zones": [
            {"min": None, "max": -20},
            {"min": -20, "max": None},
        ],
    })
    theory_path.write_text(
        yaml.safe_dump(theory_data, sort_keys=False),
        encoding="utf-8",
    )
    expected_values = science._theory_provenance_values(
        {
            "ctl_time_constant": 42,
            "atl_time_constant": 7,
            "rss_exponent": 2.0,
            "trimp_k_male": 1.92,
            "trimp_k_female": 1.67,
        },
        {
            "readiness_rest": 60,
            "readiness_modify": 70,
            "tsb_high_fatigue": -20,
            "hrv_decline_pct": -15,
        },
        {
            "work_split_min_sec": 120,
            "work_split_max_sec": 1800,
            "volume_strong_km": 60,
            "volume_moderate_km": 40,
        },
        theory_data["tsb_zones"],
    )
    decision = ScienceDecisionRecord.model_construct(
        id="sdr-registered-v1",
        status=RecordStatus.ACCEPTED,
        model_version="registered-v1",
        model_parameters=[
            ParameterProvenance(
                name=name,
                value=value,
                classification=ParameterClassification.GUARDRAIL,
                rationale="Synthetic registry fixture.",
            )
            for name, value in expected_values.items()
        ],
        affected_surfaces=AffectedSurfaces(
            models=["load/registered"],
        ),
        evidence_review_ids=[],
        evidence_claim_ids=[],
    )
    registry = ScienceRegistry(
        science_dir=tmp_path,
        evidence_reviews={},
        decisions={decision.id: decision},
        claims={},
        citations={},
        claim_review_ids={},
        review_paths={},
        decision_paths={},
    )
    monkeypatch.setattr(
        "analysis.evidence_registry.load_science_registry",
        lambda: registry,
    )

    with patch.object(science, "_SCIENCE_DIR", str(tmp_path)):
        theory = science.load_theory("load", "registered")

    assert theory.signal == {
        "readiness_rest": 60,
        "readiness_modify": 70,
        "tsb_high_fatigue": -20,
        "hrv_decline_pct": -15,
    }
    assert theory.diagnosis == {
        "work_split_min_sec": 120,
        "work_split_max_sec": 1800,
        "volume_strong_km": 60,
        "volume_moderate_km": 40,
    }
    assert [(zone.min, zone.max) for zone in theory.tsb_zones] == [
        (None, -20),
        (-20, None),
    ]
