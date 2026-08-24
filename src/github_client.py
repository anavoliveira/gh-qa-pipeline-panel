"""Wrapper fino sobre PyGithub, autenticado com o token do GitHub CLI (`gh auth token`)."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from functools import lru_cache

from github import Github
from github.GithubException import GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun


class GitHubClientError(Exception):
    pass


@dataclass
class WorkflowRunStatus:
    status: str  # queued|in_progress|completed
    conclusion: str | None  # success|failure|cancelled|None
    html_url: str


def _get_cli_token() -> str:
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise GitHubClientError(
            "GitHub CLI (`gh`) não encontrado no PATH. Instale e rode `gh auth login`."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise GitHubClientError(
            f"Não foi possível obter o token do `gh auth token`: {exc.stderr.strip()}"
        ) from exc
    token = result.stdout.strip()
    if not token:
        raise GitHubClientError("`gh auth token` retornou vazio. Rode `gh auth login` novamente.")
    return token


@lru_cache(maxsize=1)
def get_client() -> Github:
    return Github(_get_cli_token())


def get_repo(full_name: str) -> Repository:
    return get_client().get_repo(full_name)


def ensure_branch(full_name: str, branch: str, base_branch: str) -> bool:
    """Garante que `branch` existe, criando a partir de `base_branch` se necessário.

    Retorna True se a branch foi criada agora, False se já existia.
    """
    repo = get_repo(full_name)
    try:
        repo.get_branch(branch)
        return False
    except GithubException as exc:
        if exc.status != 404:
            raise GitHubClientError(f"Erro ao consultar branch '{branch}': {exc}") from exc
    base = repo.get_branch(base_branch)
    repo.create_git_ref(ref=f"refs/heads/{branch}", sha=base.commit.sha)
    return True


def commit_config_touch(full_name: str, branch: str, config_path: str = "config.yml") -> str:
    """Adiciona um espaço ao final de config.yml na branch informada e comita.

    Retorna o sha do commit criado.
    """
    repo = get_repo(full_name)
    file_content = repo.get_contents(config_path, ref=branch)
    new_content = file_content.decoded_content.decode("utf-8") + " "
    result = repo.update_file(
        path=config_path,
        message="chore: trigger pipeline (espaço adicionado via painel de QA)",
        content=new_content,
        sha=file_content.sha,
        branch=branch,
    )
    return result["commit"].sha


def find_pull_request(full_name: str, head_branch: str, base_branch: str) -> PullRequest | None:
    repo = get_repo(full_name)
    owner = full_name.split("/")[0]
    prs = repo.get_pulls(state="all", head=f"{owner}:{head_branch}", base=base_branch)
    for pr in prs:
        return pr
    return None


def create_pull_request(
    full_name: str, head_branch: str, base_branch: str, title: str, body: str = ""
) -> PullRequest:
    repo = get_repo(full_name)
    return repo.create_pull(title=title, body=body, head=head_branch, base=base_branch)


def approve_pull_request(pr: PullRequest) -> None:
    try:
        pr.create_review(event="APPROVE")
    except GithubException as exc:
        if exc.status == 422:
            raise GitHubClientError(
                "GitHub recusou a auto-aprovação (provavelmente o token pertence ao mesmo "
                "usuário que abriu o PR e a branch protection exige outro revisor)."
            ) from exc
        raise GitHubClientError(f"Erro ao aprovar PR #{pr.number}: {exc}") from exc


def pull_request_is_merged(pr: PullRequest) -> bool:
    pr.update()
    return pr.merged


def get_latest_workflow_run(
    full_name: str, workflow_name: str, branch: str
) -> WorkflowRunStatus | None:
    repo = get_repo(full_name)
    workflows = repo.get_workflows()
    workflow = next((w for w in workflows if w.name == workflow_name), None)
    if workflow is None:
        raise GitHubClientError(
            f"Workflow '{workflow_name}' não encontrado em {full_name}. "
            "Confira o nome cadastrado em Repositórios."
        )
    runs = workflow.get_runs(branch=branch)
    run: WorkflowRun | None = next(iter(runs), None)
    if run is None:
        return None
    return WorkflowRunStatus(status=run.status, conclusion=run.conclusion, html_url=run.html_url)
