#!/bin/sh
# Roda na VM antiga (README_migracao_vm.md, passo 1 + caminho A ou B).
# Descobre onde o Keycloak guarda os dados e gera o arquivo da migração:
#   KC_DB=postgres           → keycloak.dump  (caminho B: cópia fiel, sem parar nada)
#   H2 (start-dev) ou outro  → kc-export.tgz  (caminho A; com H2 o container fica parado ~1 min)
#
# Uso:  sh exportar_vm.sh <container-do-keycloak> [--realms]
#       --realms força o caminho A mesmo com Postgres (ex.: para trazer só alguns realms)
#       PG_CONTAINER=<nome> sh exportar_vm.sh ...  se o container do Postgres não for achado sozinho
set -eu

KC="${1:?Uso: sh $0 <container-do-keycloak> [--realms]}"
MODO="${2:-}"

IMG=$(docker inspect "$KC" --format '{{.Config.Image}}')
CMD=$(docker inspect "$KC" --format '{{json .Config.Cmd}}')
ENVS=$(docker inspect "$KC" --format '{{range .Config.Env}}{{println .}}{{end}}')
MOUNTS=$(docker inspect "$KC" --format '{{json .Mounts}}')
valor() { printf '%s\n' "$ENVS" | sed -n "s/^$1=//p" | head -n 1; }
DB=$(valor KC_DB)

echo "Imagem: $IMG"
echo "Comando: $CMD"
echo "KC_DB: ${DB:-(vazio: H2 embutido)}"
case "$IMG" in
    *jboss/keycloak*) echo "❌ Imagem jboss/keycloak (Keycloak 16 ou anterior, WildFly): não é coberta."; exit 1 ;;
esac

# ------------------------------------------------------------------ caminho B
if [ "$DB" = postgres ] && [ "$MODO" != --realms ]; then
    URL=$(valor KC_DB_URL)                       # jdbc:postgresql://<host>:5432/<banco>
    HOST_PG=$(printf '%s' "$URL" | sed -E 's#^jdbc:postgresql://([^:/]+).*#\1#')
    BANCO=$(printf '%s' "$URL" | sed -E 's#^jdbc:postgresql://[^/]+/([^?]+).*#\1#')
    USUARIO=$(valor KC_DB_USERNAME)
    SCHEMA=$(valor KC_DB_SCHEMA)
    PG="${PG_CONTAINER:-}"
    if [ -z "$PG" ]; then
        # O host do JDBC é o nome do container ou um alias dele na rede do Docker
        for c in $(docker ps --format '{{.Names}}'); do
            nomes=$(docker inspect "$c" --format '{{.Name}} {{range .NetworkSettings.Networks}}{{range .Aliases}}{{.}} {{end}}{{end}}')
            case " $nomes " in *" /$HOST_PG "*|*" $HOST_PG "*) PG="$c"; break ;; esac
        done
    fi
    [ -n "$PG" ] || { echo "❌ Não achei o container do Postgres ($HOST_PG). Rode de novo com PG_CONTAINER=<nome>."; exit 1; }
    echo "➡️  pg_dump de $BANCO no container $PG (usuário $USUARIO), com tudo no ar"
    docker exec "$PG" pg_dump -U "$USUARIO" -d "$BANCO" -Fc --no-owner --no-acl ${SCHEMA:+-n "$SCHEMA"} > keycloak.dump
    echo "✅ $(pwd)/keycloak.dump ($(du -h keycloak.dump | cut -f1))"
    [ -n "$SCHEMA" ] && echo "⚠️  Schema $SCHEMA: use o mesmo KC_DB_SCHEMA no destino."
    echo "   Na sua máquina: scp <vm>:$(pwd)/keycloak.dump .  &&  make restaurar-dump  (ou make k8s-restaurar-dump)"
    exit 0
fi

# ------------------------------------------------------------------ caminho A
rm -rf kc-export
if [ -z "$DB" ] || [ "$DB" = dev-file ] || [ "$DB" = dev-mem ]; then
    # O arquivo do H2 fica travado com o servidor no ar: para, copia e exporta num container temporário.
    [ "$MOUNTS" = "[]" ] && echo "⚠️  H2 sem volume: os dados só existem dentro do container. Não rode docker rm/compose down nele."
    echo "➡️  H2: parando $KC (volta sozinho no fim, ~1 min)"
    docker stop "$KC" >/dev/null
    trap 'docker start "$KC" >/dev/null && echo "▶️  $KC de volta no ar"' EXIT
    rm -rf h2 && docker cp "$KC":/opt/keycloak/data/h2 ./h2
    docker rm -f kc-export >/dev/null 2>&1 || true
    docker run --name kc-export -u 0 -v "$PWD/h2:/opt/keycloak/data/h2" "$IMG" export --dir /tmp/kc-export --users realm_file
    docker cp kc-export:/tmp/kc-export ./kc-export
    docker rm kc-export >/dev/null
    rm -rf h2
else
    # Com banco externo, o export roda com o servidor no ar. A 9001 evita disputar a 9000 (não existe antes do Keycloak 25).
    docker exec "$KC" /opt/keycloak/bin/kc.sh export --dir /tmp/kc-export --users realm_file --http-management-port=9001 \
        || docker exec "$KC" /opt/keycloak/bin/kc.sh export --dir /tmp/kc-export --users realm_file
    docker cp "$KC":/tmp/kc-export ./kc-export
fi
tar czf kc-export.tgz kc-export && rm -rf kc-export
echo "✅ $(pwd)/kc-export.tgz (um <realm>-realm.json por realm, inclusive o master)"
echo "   Na sua máquina: scp <vm>:$(pwd)/kc-export.tgz .  &&  make importar-realms  (ou make k8s-importar-realms)"
echo "   O arquivo tem hashes de senha e secrets: apague aqui depois da migração."
