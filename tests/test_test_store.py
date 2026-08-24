from pathlib import Path

from src import test_store
from src.models import Subtest, TestCase


def test_save_and_load_roundtrip(tmp_path: Path):
    test = TestCase(name="Meu teste", objective="Validar X", repo="meu-repo", branch="feature/x")
    test.subtests.append(Subtest(name="Passo 1"))
    test_store.save_test(test, data_dir=tmp_path)

    loaded = test_store.load_test(test.id, data_dir=tmp_path)

    assert loaded is not None
    assert loaded.name == "Meu teste"
    assert loaded.subtests[0].name == "Passo 1"
    assert loaded.pipeline.state == "not_started"


def test_list_tests_empty_dir_returns_empty_list(tmp_path: Path):
    assert test_store.list_tests(data_dir=tmp_path / "missing") == []


def test_delete_test(tmp_path: Path):
    test = TestCase(name="T", repo="r", branch="feature/t")
    test_store.save_test(test, data_dir=tmp_path)
    assert test_store.load_test(test.id, data_dir=tmp_path) is not None

    test_store.delete_test(test.id, data_dir=tmp_path)
    assert test_store.load_test(test.id, data_dir=tmp_path) is None
