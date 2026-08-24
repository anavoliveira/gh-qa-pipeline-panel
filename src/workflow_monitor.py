"""Thread de acompanhamento por teste: chama pipeline.step() periodicamente e persiste o estado.

As threads vivem num dicionário em nível de módulo, então sobrevivem a reruns do
Streamlit dentro do mesmo processo (cada `streamlit run` é um processo único).
"""
from __future__ import annotations

import threading

from src import config_store, github_client, pipeline, test_store

POLL_INTERVAL_SECONDS = 30

_monitors: dict[str, TestMonitor] = {}
_lock = threading.Lock()


class TestMonitor:
    def __init__(self, test_id: str):
        self.test_id = test_id
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:  # noqa: BLE001 - queremos registrar qualquer falha no histórico
                test = test_store.load_test(self.test_id)
                if test is not None:
                    test.pipeline.state = "failed"
                    test.pipeline.error = str(exc)
                    test.pipeline.add_event(f"Erro no acompanhamento: {exc}")
                    test_store.save_test(test)
                self._stop_event.set()
                break

            test = test_store.load_test(self.test_id)
            if test is None or test.pipeline.state in ("done", "failed"):
                self._stop_event.set()
                break
            self._stop_event.wait(POLL_INTERVAL_SECONDS)

    def _tick(self) -> None:
        test = test_store.load_test(self.test_id)
        if test is None:
            self._stop_event.set()
            return
        repos = config_store.load_repos()
        repo_cfg = repos.get(test.repo)
        if repo_cfg is None:
            raise github_client.GitHubClientError(
                f"Repositório '{test.repo}' não encontrado na configuração."
            )
        pipeline.step(test, repo_cfg)
        test_store.save_test(test)


def start_monitor(test_id: str) -> None:
    with _lock:
        existing = _monitors.get(test_id)
        if existing is not None and existing.is_alive():
            return
        monitor = TestMonitor(test_id)
        _monitors[test_id] = monitor
        monitor.start()


def stop_monitor(test_id: str) -> None:
    with _lock:
        monitor = _monitors.get(test_id)
        if monitor is not None:
            monitor.stop()


def is_monitoring(test_id: str) -> bool:
    with _lock:
        monitor = _monitors.get(test_id)
        return monitor is not None and monitor.is_alive()
