#!/usr/bin/env bash
# Banco do Keycloak num Akamai Managed PostgreSQL (cluster de banco), com o Keycloak no Kubernetes.
# É o k8s/sql_db.md automatizado, para a migração da VM (caminho B) e a manutenção.
#
#   AKAMAI_DB_HOST=<host primário> scripts/akamai_db.sh testar
#   AKAMAI_DB_HOST=<host primário> scripts/akamai_db.sh restaurar keycloak.dump
#   AKAMAI_DB_HOST=<host primário> scripts/akamai_db.sh conexoes | dump | psql
#
# Variáveis (com o padrão):
#   AKAMAI_DB_HOST   host PRIMÁRIO do cluster (Cloud Manager → Databases → Connection Details).
#                    Não use o host read-only/standby: ele recusa CREATE/ALTER DATABASE.
#   AKAMAI_DB_PORT   23159            AKAMAI_DB_USER  akmadmin
#   AKAMAI_DB_ADMIN  defaultdb        KC_DB_NAME      keycloak
#   K8S_NS           keycloak         K8S_DEPLOY      keycloak
#   PGPASSWORD       senha do akmadmin (sem ela, é pedida no terminal e não fica no histórico)
#
# O IP desta máquina precisa estar em Cloud Manager → Databases → Manage Access.
set -euo pipefail

: "${AKAMAI_DB_HOST:?Defina AKAMAI_DB_HOST com o host primário do cluster (Connection Details)}"
PORTA=${AKAMAI_DB_PORT:-23159}
USUARIO=${AKAMAI_DB_USER:-akmadmin}
ADMIN_DB=${AKAMAI_DB_ADMIN:-defaultdb}
BANCO=${KC_DB_NAME:-keycloak}
TEMP="${BANCO}_new"
NS=${K8S_NS:-keycloak}
DEPLOY=${K8S_DEPLOY:-keycloak}

export PGHOST=$AKAMAI_DB_HOST PGPORT=$PORTA PGUSER=$USUARIO PGSSLMODE=${AKAMAI_DB_SSLMODE:-require} PGAPPNAME=migracao-vm PGCONNECT_TIMEOUT=10

if [ -z "${PGPASSWORD:-}" ]; then
    read -r -s -p "Senha de $USUARIO@$AKAMAI_DB_HOST: " PGPASSWORD; echo
    export PGPASSWORD
fi

sql() { psql -X -v ON_ERROR_STOP=1 -At -d "$1" -c "$2"; }
titulo() { printf '\n\033[1m➡️  %s\033[0m\n' "$*"; }
confirmar() {
    local resposta
    read -r -p "$1 Digite '$2' para continuar: " resposta
    [ "$resposta" = "$2" ] || { echo "Cancelado. Nada mais foi feito."; exit 1; }
}

testar() {
    titulo "Conexão"
    echo "PostgreSQL $(sql "$ADMIN_DB" 'SHOW server_version') em $PGHOST:$PGPORT ($PGUSER)"
    sql "$ADMIN_DB" "SELECT datname || '  ' || pg_size_pretty(pg_database_size(datname)) || CASE WHEN datallowconn THEN '' ELSE '  (sem conexões)' END FROM pg_database WHERE NOT datistemplate ORDER BY 1"
    if [ "$(sql "$ADMIN_DB" 'SELECT pg_is_in_recovery()')" = t ]; then
        echo "❌ Este host é uma réplica (read-only). Use o host primário do cluster."; exit 1
    fi
}

conexoes() {
    titulo "Conexões em $BANCO e $TEMP"
    linhas_conexoes
}

linhas_conexoes() {
    sql "$ADMIN_DB" "SELECT datname || '  ' || coalesce(host(client_addr), 'local') || '  ' || coalesce(nullif(application_name, ''), '-') || '  desde ' || to_char(backend_start, 'DD/MM HH24:MI') FROM pg_stat_activity WHERE datname IN ('$BANCO', '$TEMP') AND pid <> pg_backend_pid() ORDER BY 1"
}

conferir() {
    titulo "Conferência de $1"
    echo "migration_model:"; sql "$1" "SELECT '  ' || id || ' | ' || version FROM migration_model ORDER BY update_time"
    echo "realms:         $(sql "$1" "SELECT string_agg(name, ', ' ORDER BY name <> 'master', name) FROM realm")"
    echo "admins (master): $(sql "$1" "SELECT string_agg(u.username, ', ') FROM user_entity u JOIN realm r ON r.id = u.realm_id WHERE r.name = 'master' AND u.service_account_client_link IS NULL")"
}

restaurar() {
    local dump=${1:?Uso: $0 restaurar <arquivo.dump>} log
    [ -f "$dump" ] || { echo "❌ Falta $dump. Traga da VM: scp <vm>:keycloak.dump ."; exit 1; }
    # Sem "| grep -q": com pipefail, o grep fecha o pipe cedo e o pg_restore morre por SIGPIPE
    [[ "$(pg_restore --list "$dump")" == *migration_model* ]] || { echo "❌ $dump não é um dump do Keycloak (sem migration_model)."; exit 1; }
    echo "➡️  Contexto do kubectl: $(kubectl config current-context) · deploy/$DEPLOY em $NS"
    kubectl -n "$NS" get deploy "$DEPLOY" >/dev/null
    testar

    # 1. Banco temporário: o Keycloak continua no ar, no banco atual
    titulo "Restaurando $dump em $TEMP (o Keycloak continua no ar)"
    sql "$ADMIN_DB" "DROP DATABASE IF EXISTS \"$TEMP\" WITH (FORCE)"
    sql "$ADMIN_DB" "CREATE DATABASE \"$TEMP\""
    log=$(mktemp)
    pg_restore -d "$TEMP" --no-owner --no-privileges "$dump" 2>"$log" || true
    if grep 'error:' "$log" | grep -v transaction_timeout; then
        echo "❌ O pg_restore teve os erros acima ($TEMP ficou como está; o $BANCO não foi tocado)."
        rm -f "$log"; exit 1
    fi
    rm -f "$log"
    conferir "$TEMP"
    [ "$(sql "$TEMP" 'SELECT count(*) FROM migration_model')" -gt 0 ] || { echo "❌ migration_model vazia."; exit 1; }

    # O Keycloak não volta versão: um dump mais novo que a imagem do Deployment não sobe
    local imagem versao_dump versao_kc
    imagem=$(kubectl -n "$NS" get deploy "$DEPLOY" -o jsonpath='{..image}')
    versao_kc=$(sed -nE 's/.*:([0-9]+(\.[0-9]+)*).*/\1/p' <<<"$imagem")
    versao_dump=$(sql "$TEMP" "SELECT version FROM migration_model ORDER BY update_time DESC LIMIT 1")
    echo "Keycloak do dump: $versao_dump · imagem do deploy: ${imagem:-?}"
    if [ -n "$versao_kc" ] && [ "$(printf '%s\n%s\n' "$versao_dump" "$versao_kc" | sort -V | tail -1)" != "$versao_kc" ] \
        && [[ "$versao_dump" != "$versao_kc".* ]]; then
        echo "❌ O dump ($versao_dump) é mais novo que o Keycloak do deploy ($versao_kc): atualize a imagem antes."
        echo "   $TEMP ficou restaurado; o $BANCO não foi tocado."
        exit 1
    fi

    # 2. Troca: o Keycloak para; o banco atual vira cópia (sem conexões) e o temporário assume o nome
    local copia="${BANCO}_antes_$(date +%Y%m%d_%H%M%S)"
    echo
    echo "A seguir: deploy/$DEPLOY vai a 0 réplicas, $BANCO vira $copia e $TEMP vira $BANCO."
    confirmar "O Keycloak fica fora do ar por 1 a 2 minutos." "$BANCO"
    local replicas
    replicas=$(kubectl -n "$NS" get deploy "$DEPLOY" -o jsonpath='{.spec.replicas}')
    kubectl -n "$NS" scale deploy/"$DEPLOY" --replicas=0
    kubectl -n "$NS" wait --for=delete pod -l application=keycloak --timeout=5m || true

    # Num cluster de banco compartilhado, outro Keycloak (outro ambiente) pode estar apontando para o mesmo banco
    if [ -n "$(linhas_conexoes)" ]; then
        conexoes
        confirmar "Ainda há conexões acima (outro Keycloak?). Elas serão derrubadas e passarão a usar o banco novo." "derrubar"
    fi
    if [ -n "$(sql "$ADMIN_DB" "SELECT 1 FROM pg_database WHERE datname = '$BANCO'")" ]; then
        sql "$ADMIN_DB" "ALTER DATABASE \"$BANCO\" ALLOW_CONNECTIONS false"
        sql "$ADMIN_DB" "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity WHERE datname = '$BANCO'" >/dev/null
        sql "$ADMIN_DB" "ALTER DATABASE \"$BANCO\" RENAME TO \"$copia\""
        echo "✅ Banco anterior guardado como $copia"
    fi
    sql "$ADMIN_DB" "ALTER DATABASE \"$TEMP\" RENAME TO \"$BANCO\""

    titulo "Subindo o Keycloak"
    kubectl -n "$NS" scale deploy/"$DEPLOY" --replicas="${replicas:-1}"
    kubectl -n "$NS" rollout status deploy/"$DEPLOY" --timeout=10m
    conferir "$BANCO"
    echo
    echo "✅ Dump restaurado. O admin do console agora é o da VM (senha da VM)."
    echo "   Voltar: pare o Keycloak e renomeie $copia de volta para $BANCO (ALLOW_CONNECTIONS true)."
    echo "   Depois: troque o host antigo na tela Migração da VM (passo 3)."
}

case "${1:-}" in
    testar) testar ;;
    conexoes) conexoes ;;
    conferir) conferir "${2:-$BANCO}" ;;
    restaurar) restaurar "${2:-keycloak.dump}" ;;
    dump)
        arquivo="${BANCO}-$(date +%F_%H%M).dump"
        pg_dump -d "$BANCO" -Fc --no-owner --no-privileges -f "$arquivo"
        echo "✅ $arquivo (tem hashes de senha: não faça commit)" ;;
    psql) exec psql -X -d "${2:-$BANCO}" ;;
    *) sed -n '2,17p' "$0"; exit 1 ;;
esac
