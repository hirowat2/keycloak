# syntax=docker/dockerfile:1
#
# Dois estágios: o "builder" compila as dependências (compilador, cabeçalhos, git, poetry);
# a imagem final leva só o Python, as bibliotecas de execução e o .venv pronto.
#
# O token do GitHub (dependências privadas) entra como build secret, que não fica gravado
# na imagem nem no histórico: docker buildx build --secret id=github_pat,env=GITHUB_PAT .

ARG PYTHON_VERSION=3.13

# ------------------------------------------------------------------------------ builder
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# build-essential e libmariadb-dev: o mysqlclient (exigido pelo pseudoproject) é compilado na instalação.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        libmariadb-dev \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry

WORKDIR /usr/src
COPY pyproject.toml poetry.lock README.md ./

RUN --mount=type=secret,id=github_pat,env=GITHUB_PAT \
    if [ -n "${GITHUB_PAT:-}" ]; then \
        git config --global url."https://${GITHUB_PAT}@github.com/".insteadOf "https://github.com/"; \
    fi \
    && poetry install --only main --no-root --no-ansi \
    && rm -rf "${HOME}/.gitconfig" "${HOME}/.cache/pypoetry"

# ------------------------------------------------------------------------------ final
FROM python:${PYTHON_VERSION}-slim

LABEL author="hirowat2"
LABEL project="keycloak-assistente"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/src/.venv/bin:${PATH}" \
    PYTHONPATH="/usr/src/src"

# Só o necessário em execução: cliente MariaDB (mysqlclient, exigido pelo pseudoproject).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src

COPY --from=builder /usr/src/.venv .venv
COPY media/ media/
COPY prof/ prof/
COPY src/ src/
COPY --chmod=755 docker-entrypoint.sh .

EXPOSE 80

HEALTHCHECK --interval=60s --timeout=3s --retries=3 --start-interval=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1/health/', timeout=3)" || exit 1

ENTRYPOINT [ "./docker-entrypoint.sh" ]
