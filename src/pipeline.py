"""Máquina de estados do fluxo feature -> analytics -> dev, orientada a um único passo por chamada.

`step()` é chamado repetidamente (pelo workflow_monitor) e avança o TestCase.pipeline
de acordo com o estado atual, usando o github_client para consultar/atuar no GitHub.
Cada chamada faz no máximo uma transição, registrando o evento no histórico.
"""
from __future__ import annotations

from src import github_client as gh
from src.models import RepoConfig, TestCase


def step(test: TestCase, repo_cfg: RepoConfig) -> TestCase:
    state = test.pipeline.state

    if state == "not_started":
        gh.ensure_branch(repo_cfg.full_name, test.branch, repo_cfg.base_branch)
        test.pipeline.state = "branch_ready"
        test.pipeline.add_event(f"Branch '{test.branch}' pronta.")

    elif state in ("branch_ready", "committed", "feature_running"):
        _advance_feature_workflow(test, repo_cfg)

    elif state == "pr_analytics_open":
        _advance_open_pr(test, repo_cfg, next_state_on_merge="pr_analytics_merged")

    elif state == "pr_analytics_merged":
        _open_or_wait_dev_pr(test, repo_cfg)

    elif state == "pr_dev_open":
        _advance_open_pr(test, repo_cfg, next_state_on_merge="pr_dev_merged")

    elif state == "pr_dev_merged":
        test.pipeline.state = "done"
        test.pipeline.add_event("Pipeline concluído: PR mergeado em develop.")

    return test


def _advance_feature_workflow(test: TestCase, repo_cfg: RepoConfig) -> None:
    run = gh.get_latest_workflow_run(repo_cfg.full_name, repo_cfg.workflow_feature, test.branch)
    if run is None:
        return
    if run.status != "completed":
        if test.pipeline.state != "feature_running":
            test.pipeline.state = "feature_running"
            test.pipeline.add_event(f"Workflow '{repo_cfg.workflow_feature}' em execução.")
        return
    if run.conclusion != "success":
        test.pipeline.state = "failed"
        test.pipeline.error = f"Workflow '{repo_cfg.workflow_feature}' concluiu com '{run.conclusion}'."
        test.pipeline.add_event(test.pipeline.error)
        return

    base = repo_cfg.branch_develop if repo_cfg.skip_analytics else repo_cfg.branch_analytics
    pr = gh.find_pull_request(repo_cfg.full_name, test.branch, base)
    if pr is None:
        pr = gh.create_pull_request(
            repo_cfg.full_name,
            test.branch,
            base,
            title=f"[QA] {test.name}",
            body=test.objective,
        )
        test.pipeline.add_event(f"PR criado manualmente para '{base}' (esteira não abriu sozinha).")
    gh.approve_pull_request(pr)
    test.pipeline.add_event(f"PR #{pr.number} para '{base}' aprovado.")
    test.pipeline.current_pr_head = test.branch
    test.pipeline.state = "pr_dev_open" if repo_cfg.skip_analytics else "pr_analytics_open"


def _advance_open_pr(test: TestCase, repo_cfg: RepoConfig, next_state_on_merge: str) -> None:
    base = repo_cfg.branch_develop if next_state_on_merge == "pr_dev_merged" else repo_cfg.branch_analytics
    head = test.pipeline.current_pr_head
    if head is None:
        return
    pr = gh.find_pull_request(repo_cfg.full_name, head, base)
    if pr is None:
        return
    if gh.pull_request_is_merged(pr):
        test.pipeline.state = next_state_on_merge
        test.pipeline.current_pr_head = None
        test.pipeline.add_event(f"PR #{pr.number} para '{base}' mergeado.")


def _open_or_wait_dev_pr(test: TestCase, repo_cfg: RepoConfig) -> None:
    if test.target == "analytics":
        test.pipeline.state = "done"
        test.pipeline.add_event("Pipeline concluído: alvo 'analytics' atingido.")
        return

    pr = gh.find_pull_request(repo_cfg.full_name, repo_cfg.branch_analytics, repo_cfg.branch_develop)
    if pr is None:
        pr = gh.create_pull_request(
            repo_cfg.full_name,
            repo_cfg.branch_analytics,
            repo_cfg.branch_develop,
            title=f"[QA] {test.name} -> develop",
            body=test.objective,
        )
        test.pipeline.add_event("PR analytics -> develop criado manualmente (esteira não abriu sozinha).")
    gh.approve_pull_request(pr)
    test.pipeline.add_event(f"PR #{pr.number} para '{repo_cfg.branch_develop}' aprovado.")
    test.pipeline.current_pr_head = repo_cfg.branch_analytics
    test.pipeline.state = "pr_dev_open"
