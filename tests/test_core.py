import json
from unittest.mock import Mock

import pytest

from lab import common, factory
from lab.__main__ import main


@pytest.mark.parametrize("case", common.cases(), ids=lambda case: case["id"])
def test_reference_pipeline(case):
    good = common.answer(case["inputs"])["answer"]
    scores = common.score_answer(good, case["outputs"])
    assert scores == {"keyword_coverage": 1.0, "format": 1.0, "reference": 1.0}
    bad = common.answer(case["inputs"], variant="baseline")["answer"]
    assert common.score_answer(bad, case["outputs"])["keyword_coverage"] == 0.0


def test_unknown_question_does_not_invent_evidence():
    assert common.retrieve("unknown xyz") == []
    assert "확인 필요" in common.answer({"question": "unknown xyz"})["answer"]


def test_recursive_masking_preserves_other_types():
    original = {"Password": "secret", "nested": [{"email": "a@example.com", "number": 42}]}
    assert common.scrub(original) == {
        "Password": "[REDACTED]",
        "nested": [{"email": "[EMAIL]", "number": 42}],
    }
    assert original["Password"] == "secret"


def test_offline_never_initializes_model_client(monkeypatch, tmp_path):
    from lab.offline import run

    monkeypatch.setattr(common, "ARTIFACTS", tmp_path)
    forbidden = Mock(side_effect=AssertionError("network client must not be initialized"))
    monkeypatch.setattr(common, "model_client", forbidden)
    report = run()
    forbidden.assert_not_called()
    assert report["mode"] == "offline-mock"
    assert json.loads((tmp_path / "offline-report.json").read_text(encoding="utf-8"))


def test_live_is_explicit(monkeypatch):
    monkeypatch.setattr("lab.__main__.load_env", lambda: None)
    with pytest.raises(SystemExit) as error:
        main(["langsmith", "trace"])
    assert error.value.code == 2


def test_missing_credentials_do_not_show_values(monkeypatch, capsys):
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="LANGFUSE_SECRET_KEY"):
        common.require_env("LANGFUSE_SECRET_KEY")


def test_generated_datasets_and_recipes():
    assert len(factory.validate()) == 33


def test_prepare_preserves_user_edits(monkeypatch, tmp_path):
    monkeypatch.setattr(factory, "FACTORY", tmp_path)
    factory.prepare()
    path = tmp_path / "configs" / "sft_lora.yaml"
    path.write_text("user: edit\n", encoding="utf-8")
    factory.prepare()
    assert path.read_text(encoding="utf-8") == "user: edit\n"


def test_validation_rejects_malformed_preference_data(monkeypatch, tmp_path):
    monkeypatch.setattr(factory, "FACTORY", tmp_path)
    factory.prepare()
    path = tmp_path / "data" / "pairs.json"
    path.write_text('[{"instruction":"test","chosen":"yes"}]', encoding="utf-8")
    with pytest.raises(ValueError, match="chosen/rejected"):
        factory.validate()


def test_factory_preview_never_starts_training(monkeypatch):
    process = Mock(side_effect=AssertionError("must not execute"))
    monkeypatch.setattr(factory.subprocess, "run", process)
    command = factory.run_recipe("ppo_lora")
    assert command[:2] == ["llamafactory-cli", "train"]
    process.assert_not_called()


def test_factory_missing_prerequisites_fail_before_launch(monkeypatch):
    monkeypatch.setattr(factory.shutil, "which", lambda _: "fake-cli")
    process = Mock()
    monkeypatch.setattr(factory.subprocess, "run", process)
    with pytest.raises(ValueError, match="선행 실습"):
        factory.run_recipe("ppo_lora", execute=True)
    process.assert_not_called()


def test_png_fixture_is_valid():
    import struct
    import zlib

    image = factory.status_png()
    assert image[:8] == b"\x89PNG\r\n\x1a\n"
    position = 8
    while position < len(image):
        size = struct.unpack(">I", image[position : position + 4])[0]
        block = image[position + 4 : position + 8 + size]
        crc = struct.unpack(">I", image[position + 8 + size : position + 12 + size])[0]
        assert zlib.crc32(block) == crc
        position += 12 + size


def test_evaluator_interfaces():
    from types import SimpleNamespace

    from lab.langfuse_demo import evaluator as lf_evaluator
    from lab.langsmith_demo import comparison
    from lab.langsmith_demo import evaluator as ls_evaluator

    case = common.cases()[0]
    output = common.answer(case["inputs"])
    example = SimpleNamespace(outputs=case["outputs"])
    good = SimpleNamespace(id="good", outputs=output)
    bad = SimpleNamespace(id="bad", outputs={"answer": "unknown"})
    assert all(item["score"] == 1 for item in ls_evaluator(good, example)["results"])
    assert all(
        item.value == 1 for item in lf_evaluator(output=output, expected_output=case["outputs"])
    )
    assert comparison([good, bad], example)["scores"] == {"good": 1.0, "bad": 0.0}
