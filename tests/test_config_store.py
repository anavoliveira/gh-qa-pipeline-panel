from pathlib import Path

from src import config_store
from src.models import RepoConfig


def test_save_and_load_roundtrip(tmp_path: Path):
    path = tmp_path / "repos.yml"
    repo = RepoConfig(
        key="meu-repo",
        full_name="minha-org/meu-repo",
        base_branch="develop",
        skip_analytics=True,
        workflow_feature="Feature Custom",
    )
    config_store.save_repos({"meu-repo": repo}, path=path)

    loaded = config_store.load_repos(path=path)

    assert set(loaded.keys()) == {"meu-repo"}
    assert loaded["meu-repo"].full_name == "minha-org/meu-repo"
    assert loaded["meu-repo"].skip_analytics is True
    assert loaded["meu-repo"].workflow_feature == "Feature Custom"


def test_load_missing_file_returns_empty(tmp_path: Path):
    path = tmp_path / "does_not_exist.yml"
    assert config_store.load_repos(path=path) == {}


def test_upsert_and_delete(tmp_path: Path):
    path = tmp_path / "repos.yml"
    repo = RepoConfig(key="a", full_name="org/a")
    config_store.upsert_repo(repo, path=path)
    assert "a" in config_store.load_repos(path=path)

    config_store.delete_repo("a", path=path)
    assert config_store.load_repos(path=path) == {}
