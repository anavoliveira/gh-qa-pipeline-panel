"""Leitura e escrita dos casos de teste em data/tests/<id>.json."""
from __future__ import annotations

import json
from pathlib import Path

from src.models import TestCase

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "tests"


def _path_for(test_id: str, data_dir: Path) -> Path:
    return data_dir / f"{test_id}.json"


def list_tests(data_dir: Path = DEFAULT_DATA_DIR) -> list[TestCase]:
    if not data_dir.exists():
        return []
    tests = []
    for file in sorted(data_dir.glob("*.json")):
        tests.append(TestCase.from_dict(json.loads(file.read_text(encoding="utf-8"))))
    return tests


def load_test(test_id: str, data_dir: Path = DEFAULT_DATA_DIR) -> TestCase | None:
    path = _path_for(test_id, data_dir)
    if not path.exists():
        return None
    return TestCase.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_test(test: TestCase, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = _path_for(test.id, data_dir)
    path.write_text(json.dumps(test.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def delete_test(test_id: str, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    path = _path_for(test_id, data_dir)
    if path.exists():
        path.unlink()
