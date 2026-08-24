"""Painel de acompanhamento de testes em esteiras GitHub Actions.

Rodar com: streamlit run app.py
Pré-requisito: `gh auth login` já feito (o painel reaproveita o token do GitHub CLI).
"""
from __future__ import annotations

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src import config_store, test_store, workflow_monitor
from src.models import RepoConfig, Subtest, TestCase

st.set_page_config(page_title="QA Pipeline Panel", layout="wide")

PIPELINE_STEPS = [
    ("branch_ready", "Branch pronta"),
    ("committed", "Commit disparado"),
    ("feature_running", "Workflow de Feature"),
    ("pr_analytics_open", "PR -> Analytics"),
    ("pr_analytics_merged", "Analytics mergeado"),
    ("pr_dev_open", "PR -> Develop"),
    ("pr_dev_merged", "Develop mergeado"),
    ("done", "Concluído"),
]

STATE_ORDER = ["not_started"] + [s for s, _ in PIPELINE_STEPS]


def page_repos() -> None:
    st.header("Repositórios e Workflows")
    repos = config_store.load_repos()

    if repos:
        for key, repo in repos.items():
            with st.expander(f"{key} — {repo.full_name}"):
                st.json(repo.to_dict())
                if st.button("Remover", key=f"del_{key}"):
                    config_store.delete_repo(key)
                    st.rerun()
    else:
        st.info("Nenhum repositório cadastrado ainda.")

    st.subheader("Adicionar / editar repositório")
    with st.form("repo_form", clear_on_submit=True):
        key = st.text_input("Chave curta (ex: meu-repo)")
        full_name = st.text_input("Nome completo no GitHub (org/repo)")
        base_branch = st.text_input("Branch base para criar features", value="develop")
        skip_analytics = st.checkbox("Feature pula analytics (PR direto para develop)")
        col1, col2, col3 = st.columns(3)
        branch_analytics = col1.text_input("Branch de analytics", value="analytics")
        branch_develop = col2.text_input("Branch de develop", value="develop")
        branch_main = col3.text_input("Branch main", value="main")
        col4, col5, col6 = st.columns(3)
        wf_feature = col4.text_input("Workflow Feature", value="1 - Feature")
        wf_analytics = col5.text_input("Workflow Analytics", value="2 - Analytics")
        wf_dev = col6.text_input("Workflow Dev", value="3 - Dev")

        submitted = st.form_submit_button("Salvar repositório")
        if submitted:
            if not key or not full_name:
                st.error("Chave e nome completo são obrigatórios.")
            else:
                config_store.upsert_repo(
                    RepoConfig(
                        key=key,
                        full_name=full_name,
                        base_branch=base_branch,
                        skip_analytics=skip_analytics,
                        branch_analytics=branch_analytics,
                        branch_develop=branch_develop,
                        branch_main=branch_main,
                        workflow_feature=wf_feature,
                        workflow_analytics=wf_analytics,
                        workflow_dev=wf_dev,
                    )
                )
                st.success(f"Repositório '{key}' salvo.")
                st.rerun()


def _status_badge(test: TestCase) -> str:
    state = test.pipeline.state
    if state == "done":
        return "🟢"
    if state == "failed":
        return "🔴"
    if state == "not_started":
        return "⚪"
    return "🟡"


def page_tests() -> None:
    st.header("Testes")
    repos = config_store.load_repos()
    tests = test_store.list_tests()

    with st.expander("➕ Novo teste"), st.form("new_test_form", clear_on_submit=True):
        name = st.text_input("Nome do teste")
        objective = st.text_area("Objetivo")
        repo_key = st.selectbox("Repositório", options=list(repos.keys()) or ["<cadastre um repositório>"])
        branch = st.text_input("Branch (ex: feature/minha-mudanca)")
        target = st.radio("Alvo do pipeline", options=["analytics", "dev"], horizontal=True)
        submitted = st.form_submit_button("Criar teste")
        if submitted:
            if not repos:
                st.error("Cadastre um repositório antes de criar um teste.")
            elif not name or not branch:
                st.error("Nome e branch são obrigatórios.")
            else:
                test = TestCase(name=name, objective=objective, repo=repo_key, branch=branch, target=target)
                test_store.save_test(test)
                st.success(f"Teste '{name}' criado.")
                st.rerun()

    if not tests:
        st.info("Nenhum teste cadastrado ainda.")
        return

    for test in tests:
        with st.expander(f"{_status_badge(test)} {test.name} — {test.repo}/{test.branch}"):
            render_test_detail(test, repos)


def render_test_detail(test: TestCase, repos: dict[str, RepoConfig]) -> None:
    st.write(f"**Objetivo:** {test.objective or '_(sem objetivo definido)_'}")
    st.write(f"**Alvo:** `{test.target}`  |  **Estado atual:** `{test.pipeline.state}`")

    if test.pipeline.state == "done":
        st.success("✅ Pipeline concluído com sucesso.")
    elif test.pipeline.state == "failed":
        st.error(f"❌ Pipeline falhou: {test.pipeline.error}")

    render_pipeline_track(test)

    st.subheader("Subtestes")
    for sub in test.subtests:
        cols = st.columns([4, 1, 2, 3])
        cols[0].write(sub.name)
        done = cols[1].checkbox("Feito", value=sub.done, key=f"done_{test.id}_{sub.id}")
        result = cols[2].selectbox(
            "Resultado",
            options=["pending", "success", "fail"],
            index=["pending", "success", "fail"].index(sub.result),
            key=f"result_{test.id}_{sub.id}",
            label_visibility="collapsed",
        )
        notes = cols[3].text_input(
            "Notas", value=sub.notes, key=f"notes_{test.id}_{sub.id}", label_visibility="collapsed"
        )
        if done != sub.done or result != sub.result or notes != sub.notes:
            sub.done, sub.result, sub.notes = done, result, notes
            test_store.save_test(test)

    with st.form(f"new_subtest_{test.id}", clear_on_submit=True):
        sub_name = st.text_input("Novo subteste")
        if st.form_submit_button("Adicionar subteste") and sub_name:
            test.subtests.append(Subtest(name=sub_name))
            test_store.save_test(test)
            st.rerun()

    st.subheader("Ações do pipeline")
    repo_cfg = repos.get(test.repo)
    col1, col2, col3 = st.columns(3)

    if col1.button("Commit (adicionar espaço no config.yml)", key=f"commit_{test.id}"):
        if repo_cfg is None:
            st.error("Repositório não encontrado na configuração.")
        else:
            from src import github_client, pipeline

            try:
                if test.pipeline.state == "not_started":
                    pipeline.step(test, repo_cfg)  # garante a branch antes do commit
                github_client.commit_config_touch(repo_cfg.full_name, test.branch)
                test.pipeline.state = "committed"
                test.pipeline.add_event("Commit disparado (espaço adicionado em config.yml).")
                test_store.save_test(test)
                st.rerun()
            except github_client.GitHubClientError as exc:
                st.error(str(exc))

    monitoring = workflow_monitor.is_monitoring(test.id)
    if not monitoring:
        if col2.button("Iniciar acompanhamento", key=f"start_{test.id}"):
            workflow_monitor.start_monitor(test.id)
            st.rerun()
    else:
        if col2.button("Parar acompanhamento", key=f"stop_{test.id}"):
            workflow_monitor.stop_monitor(test.id)
            st.rerun()
        col2.caption("🔄 Acompanhando...")

    if col3.button("Excluir teste", key=f"delete_{test.id}"):
        workflow_monitor.stop_monitor(test.id)
        test_store.delete_test(test.id)
        st.rerun()

    if test.pipeline.history:
        with st.expander("Histórico"):
            for event in reversed(test.pipeline.history):
                st.text(f"{event['ts']} — {event['event']}")


def render_pipeline_track(test: TestCase) -> None:
    current_index = STATE_ORDER.index(test.pipeline.state) if test.pipeline.state in STATE_ORDER else -1
    cols = st.columns(len(PIPELINE_STEPS))
    for i, (state_key, label) in enumerate(PIPELINE_STEPS):
        step_index = STATE_ORDER.index(state_key)
        if test.pipeline.state == "failed":
            icon = "⚪"
        elif step_index < current_index:
            icon = "✅"
        elif step_index == current_index:
            icon = "🟡"
        else:
            icon = "⚪"
        cols[i].markdown(f"{icon}\n\n{label}")


def main() -> None:
    st.sidebar.title("QA Pipeline Panel")
    page = st.sidebar.radio("Navegação", ["Testes", "Repositórios"])

    any_monitoring = any(
        workflow_monitor.is_monitoring(t.id) for t in test_store.list_tests()
    )
    if any_monitoring:
        st_autorefresh(interval=15_000, key="pipeline_autorefresh")

    if page == "Repositórios":
        page_repos()
    else:
        page_tests()


if __name__ == "__main__":
    main()
