#!/usr/bin/env bash
# Banco do Keycloak de demonstração, para os prints da tela "Banco do Keycloak" (scripts/capturar_prints.cjs).
# Sem dados reais: um Keycloak 21.1 descartável cria o schema e importa realm/automateflow-realm.json.
#
#   scripts/demo_banco.sh subir <arquivo.dump>   # Postgres kc-demo-db na rede do compose + o dump dele
#   scripts/demo_banco.sh remover
#
# Conexão para a tela: host kc-demo-db, porta 5432, usuário keycloak, senha demo, banco keycloak,
# administrativo postgres, SSL disable.
set -euo pipefail

REDE=${COMPOSE_REDE:-keycloak_default}
BANCO=kc-demo-db
KEYCLOAK=kc-demo-keycloak
IMAGEM_KC=quay.io/keycloak/keycloak:${KC_VERSION:-21.1}
RAIZ=$(cd "$(dirname "$0")/.." && pwd)

remover() {
    docker rm -f "$KEYCLOAK" "$BANCO" >/dev/null 2>&1 || true
}

subir() {
    local saida=${1:?Uso: $0 subir <arquivo.dump>}
    remover
    docker run -d --name "$BANCO" --network "$REDE" \
        -e POSTGRES_USER=keycloak -e POSTGRES_PASSWORD=demo -e POSTGRES_DB=keycloak postgres:16-alpine >/dev/null
    until docker exec "$BANCO" pg_isready -U keycloak -d keycloak >/dev/null 2>&1; do sleep 1; done
    sleep 2

    # Um boot do Keycloak cria as tabelas, o admin do master e o realm de demonstração
    docker run -d --name "$KEYCLOAK" --network "$REDE" \
        -e KC_DB=postgres -e KC_DB_URL_HOST="$BANCO" -e KC_DB_URL_DATABASE=keycloak \
        -e KC_DB_USERNAME=keycloak -e KC_DB_PASSWORD=demo \
        -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin \
        -e KC_REALM=automateflow -e KC_REALM_ADMIN_USER=admin -e KC_REALM_ADMIN_PASSWORD=admin \
        -e ATLAS_INSIGHTS_URL=https://atlas-insights.exemplo.com.br \
        -e LINODE_INSIGHTS_URL=https://linode-insights.exemplo.com.br \
        -e MONGO_MIGRATOR_URL=https://mongo-migrator.exemplo.com.br \
        -v "$RAIZ/realm:/opt/keycloak/data/import:ro" \
        "$IMAGEM_KC" start-dev --import-realm >/dev/null
    for _ in $(seq 120); do
        docker logs "$KEYCLOAK" 2>&1 | grep -q "started in" && break
        sleep 2
    done
    docker logs "$KEYCLOAK" 2>&1 | grep -q "started in" || { docker logs "$KEYCLOAK" | tail -20; exit 1; }
    docker rm -f "$KEYCLOAK" >/dev/null

    docker exec "$BANCO" pg_dump -U keycloak -Fc --no-owner --no-privileges keycloak > "$saida"
    echo "✅ $BANCO no ar (rede $REDE) e $(du -h "$saida" | cut -f1) em $saida"
}

case "${1:-}" in
    subir) subir "${2:-}" ;;
    remover) remover ;;
    *) sed -n '2,9p' "$0"; exit 1 ;;
esac
