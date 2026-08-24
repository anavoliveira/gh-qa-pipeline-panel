from unittest.mock import patch

from src import pipeline
from src.models import RepoConfig, TestCase


class FakePR:
    def __init__(self, number: int, merged: bool = False):
        self.number = number
        self.merged = merged

    def update(self) -> None:
        pass


def make_repo(**overrides) -> RepoConfig:
    defaults = {
        "key": "repo",
        "full_name": "org/repo",
        "base_branch": "develop",
        "skip_analytics": False,
        "branch_analytics": "analytics",
        "branch_develop": "develop",
        "branch_main": "main",
        "workflow_feature": "1 - Feature",
        "workflow_analytics": "2 - Analytics",
        "workflow_dev": "3 - Dev",
    }
    defaults.update(overrides)
    return RepoConfig(**defaults)


def make_test(**overrides) -> TestCase:
    defaults = {"name": "T", "objective": "obj", "repo": "repo", "branch": "feature/x", "target": "analytics"}
    defaults.update(overrides)
    return TestCase(**defaults)


class FakeRun:
    def __init__(self, status: str, conclusion: str | None):
        self.status = status
        self.conclusion = conclusion
        self.html_url = "http://example.com"


@patch("src.pipeline.gh")
def test_happy_path_to_analytics(mock_gh):
    repo = make_repo(skip_analytics=False)
    test = make_test(target="analytics")

    pipeline.step(test, repo)
    assert test.pipeline.state == "branch_ready"
    mock_gh.ensure_branch.assert_called_once_with(repo.full_name, test.branch, repo.base_branch)

    mock_gh.get_latest_workflow_run.return_value = FakeRun("completed", "success")
    mock_gh.find_pull_request.return_value = None
    pr = FakePR(number=1)
    mock_gh.create_pull_request.return_value = pr

    pipeline.step(test, repo)
    assert test.pipeline.state == "pr_analytics_open"
    assert test.pipeline.current_pr_head == test.branch
    mock_gh.approve_pull_request.assert_called_once_with(pr)

    mock_gh.find_pull_request.return_value = pr
    mock_gh.pull_request_is_merged.return_value = True
    pipeline.step(test, repo)
    assert test.pipeline.state == "pr_analytics_merged"

    pipeline.step(test, repo)
    assert test.pipeline.state == "done"


@patch("src.pipeline.gh")
def test_happy_path_to_dev_continues_after_analytics(mock_gh):
    repo = make_repo(skip_analytics=False)
    test = make_test(target="dev")
    test.pipeline.state = "pr_analytics_merged"

    mock_gh.find_pull_request.return_value = None
    dev_pr = FakePR(number=2)
    mock_gh.create_pull_request.return_value = dev_pr

    pipeline.step(test, repo)
    assert test.pipeline.state == "pr_dev_open"
    assert test.pipeline.current_pr_head == repo.branch_analytics
    mock_gh.approve_pull_request.assert_called_once_with(dev_pr)

    mock_gh.find_pull_request.return_value = dev_pr
    mock_gh.pull_request_is_merged.return_value = True
    pipeline.step(test, repo)
    assert test.pipeline.state == "pr_dev_merged"

    pipeline.step(test, repo)
    assert test.pipeline.state == "done"


@patch("src.pipeline.gh")
def test_skip_analytics_goes_straight_to_dev(mock_gh):
    repo = make_repo(skip_analytics=True)
    test = make_test(target="dev")
    test.pipeline.state = "branch_ready"

    mock_gh.get_latest_workflow_run.return_value = FakeRun("completed", "success")
    mock_gh.find_pull_request.return_value = None
    pr = FakePR(number=3)
    mock_gh.create_pull_request.return_value = pr

    pipeline.step(test, repo)
    assert test.pipeline.state == "pr_dev_open"
    assert test.pipeline.current_pr_head == test.branch
    assert any("manualmente" in e["event"] for e in test.pipeline.history)


@patch("src.pipeline.gh")
def test_feature_workflow_failure_marks_failed(mock_gh):
    repo = make_repo()
    test = make_test()
    test.pipeline.state = "branch_ready"

    mock_gh.get_latest_workflow_run.return_value = FakeRun("completed", "failure")

    pipeline.step(test, repo)

    assert test.pipeline.state == "failed"
    assert "failure" in test.pipeline.error


@patch("src.pipeline.gh")
def test_feature_workflow_still_running_sets_intermediate_state(mock_gh):
    repo = make_repo()
    test = make_test()
    test.pipeline.state = "branch_ready"

    mock_gh.get_latest_workflow_run.return_value = FakeRun("in_progress", None)

    pipeline.step(test, repo)

    assert test.pipeline.state == "feature_running"
    mock_gh.find_pull_request.assert_not_called()
