"""Modelos de dados do painel: configuração de repositórios e casos de teste."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Literal

PipelineState = Literal[
    "not_started",
    "branch_ready",
    "committed",
    "feature_running",
    "pr_analytics_open",
    "pr_analytics_merged",
    "pr_dev_open",
    "pr_dev_merged",
    "done",
    "failed",
]

TestTarget = Literal["analytics", "dev"]
SubtestResult = Literal["pending", "success", "fail"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class RepoConfig:
    key: str
    full_name: str
    base_branch: str = "develop"
    skip_analytics: bool = False
    branch_analytics: str = "analytics"
    branch_develop: str = "develop"
    branch_main: str = "main"
    workflow_feature: str = "1 - Feature"
    workflow_analytics: str = "2 - Analytics"
    workflow_dev: str = "3 - Dev"

    def to_dict(self) -> dict:
        return {
            "full_name": self.full_name,
            "base_branch": self.base_branch,
            "skip_analytics": self.skip_analytics,
            "branches": {
                "analytics": self.branch_analytics,
                "develop": self.branch_develop,
                "main": self.branch_main,
            },
            "workflows": {
                "feature": self.workflow_feature,
                "analytics": self.workflow_analytics,
                "dev": self.workflow_dev,
            },
        }

    @staticmethod
    def from_dict(key: str, data: dict) -> RepoConfig:
        branches = data.get("branches", {})
        workflows = data.get("workflows", {})
        return RepoConfig(
            key=key,
            full_name=data["full_name"],
            base_branch=data.get("base_branch", "develop"),
            skip_analytics=data.get("skip_analytics", False),
            branch_analytics=branches.get("analytics", "analytics"),
            branch_develop=branches.get("develop", "develop"),
            branch_main=branches.get("main", "main"),
            workflow_feature=workflows.get("feature", "1 - Feature"),
            workflow_analytics=workflows.get("analytics", "2 - Analytics"),
            workflow_dev=workflows.get("dev", "3 - Dev"),
        )


@dataclass
class Subtest:
    id: str = field(default_factory=new_id)
    name: str = ""
    done: bool = False
    result: SubtestResult = "pending"
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> Subtest:
        return Subtest(**data)


@dataclass
class PipelineInfo:
    state: PipelineState = "not_started"
    error: str | None = None
    history: list[dict] = field(default_factory=list)
    current_pr_head: str | None = None

    def add_event(self, event: str) -> None:
        self.history.append({"ts": now_iso(), "event": event})

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "error": self.error,
            "history": self.history,
            "current_pr_head": self.current_pr_head,
        }

    @staticmethod
    def from_dict(data: dict) -> PipelineInfo:
        return PipelineInfo(
            state=data.get("state", "not_started"),
            error=data.get("error"),
            history=data.get("history", []),
            current_pr_head=data.get("current_pr_head"),
        )


@dataclass
class TestCase:
    id: str = field(default_factory=new_id)
    name: str = ""
    objective: str = ""
    repo: str = ""
    branch: str = ""
    target: TestTarget = "analytics"
    subtests: list[Subtest] = field(default_factory=list)
    pipeline: PipelineInfo = field(default_factory=PipelineInfo)
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "objective": self.objective,
            "repo": self.repo,
            "branch": self.branch,
            "target": self.target,
            "subtests": [s.to_dict() for s in self.subtests],
            "pipeline": self.pipeline.to_dict(),
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(data: dict) -> TestCase:
        return TestCase(
            id=data["id"],
            name=data.get("name", ""),
            objective=data.get("objective", ""),
            repo=data.get("repo", ""),
            branch=data.get("branch", ""),
            target=data.get("target", "analytics"),
            subtests=[Subtest.from_dict(s) for s in data.get("subtests", [])],
            pipeline=PipelineInfo.from_dict(data.get("pipeline", {})),
            created_at=data.get("created_at", now_iso()),
        )
