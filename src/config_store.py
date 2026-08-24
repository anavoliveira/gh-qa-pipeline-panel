"""Leitura e escrita de config/repos.yml."""
from __future__ import annotations

from pathlib import Path

import yaml

from src.models import RepoConfig

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "repos.yml"


def load_repos(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, RepoConfig]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    repos_raw = raw.get("repos", {}) or {}
    return {key: RepoConfig.from_dict(key, data) for key, data in repos_raw.items()}


def save_repos(repos: dict[str, RepoConfig], path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"repos": {key: repo.to_dict() for key, repo in repos.items()}}
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def upsert_repo(repo: RepoConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    repos = load_repos(path)
    repos[repo.key] = repo
    save_repos(repos, path)


def delete_repo(key: str, path: Path = DEFAULT_CONFIG_PATH) -> None:
    repos = load_repos(path)
    repos.pop(key, None)
    save_repos(repos, path)
