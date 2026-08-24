# QA Pipeline Panel

Painel local (Streamlit) para acompanhar e automatizar o fluxo de promoção de
testes em repositórios com esteiras GitHub Actions no padrão
`feature -> analytics -> dev -> hom -> prod`, disparado por aprovação de PRs.

O painel cadastra testes com subtestes, cria a branch `feature/*` se necessário,
dispara o commit gatilho (um espaço em `config.yml`) e acompanha sozinho os
workflows, aprovando os PRs intermediários até o alvo definido (`analytics` ou
`dev`), avisando na própria tela quando o pipeline terminar com sucesso ou falha.

## Pré-requisitos

- Python 3.11+
- [GitHub CLI](https://cli.github.com/) instalado e autenticado: `gh auth login`
  (o painel reutiliza o token via `gh auth token`, não guarda credenciais próprias)
- Permissão de escrita/aprovação nos repositórios cadastrados

## Instalação

```bash
pip install -r requirements.txt
```

## Uso

```bash
streamlit run app.py
```

1. Na aba **Repositórios**, cadastre cada repositório com seu nome completo
   (`org/repo`), branch base, se pula analytics, e os nomes dos workflows de
   cada ambiente (eles variam entre repositórios).
2. Na aba **Testes**, crie um teste informando nome, objetivo, repositório,
   branch e alvo (`analytics` ou `dev`).
3. Quebre o teste em subtestes e marque conclusão/resultado conforme for
   executando manualmente.
4. Use **Commit** para disparar a mudança gatilho em `config.yml` na branch
   (cria a branch se ainda não existir).
5. Use **Iniciar acompanhamento** para a automação assumir: ela espera o
   workflow de feature, aprova os PRs que forem abertos (ou cria o PR quando a
   esteira não abre sozinha para develop) até o alvo escolhido, e mostra um
   banner de sucesso/falha no painel.

## Limitações conhecidas

- **Auto-aprovação do próprio PR**: se o token do `gh auth token` pertence à
  mesma conta que abriu o PR, o GitHub pode recusar a aprovação
  (`422 Can not approve your own pull request`) quando a branch protection
  exige um revisor diferente do autor. Nesse caso o painel marca o teste como
  falho com a mensagem de erro — pode ser necessário um token/conta de bot
  separada para aprovação.
- O acompanhamento roda em threads dentro do processo do Streamlit: se você
  fechar o `streamlit run`, o acompanhamento em andamento é perdido (o estado
  do teste fica salvo em `data/tests/*.json`, mas a thread não sobrevive).

## Desenvolvimento

```bash
pip install -r requirements-dev.txt
pytest
ruff check .
```

Os testes usam mocks para `src.github_client` — não fazem chamadas reais à
API do GitHub.
