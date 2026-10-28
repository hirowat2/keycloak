#!/bin/sh
set -eu

python src/manage.py collectstatic --noinput
if [ "${RUN_MAKEMIGRATIONS:-0}" = "1" ]; then
    python src/manage.py makemigrations --noinput
fi
python src/manage.py migrate --noinput
# Propostas com a validade vencida viram "Expirada" (as telas também conferem ao abrir).
python src/manage.py expirar_propostas

# Empresas do grupo e o acesso dos grupos de papel: só cria/completa o que falta.
if [ "${CONFIGURAR_EMPRESAS:-1}" = "1" ]; then
    python src/manage.py configurar_empresas
fi

if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && \
   [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ] && \
   [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    python src/manage.py createsuperuser --noinput 2>/dev/null || \
        echo "[entrypoint] Superusuário já existe; continuando."
fi

# Sincronização com o SharePoint em segundo plano: logo ao subir e depois a cada
# SHAREPOINT_INTERVALO_MINUTOS (0 desliga). Um erro numa rodada não derruba o servidor.
INTERVALO="${SHAREPOINT_INTERVALO_MINUTOS:-0}"
if [ "$INTERVALO" -gt 0 ] 2>/dev/null; then
    (
        sleep 30
        while true; do
            python src/manage.py sincronizar_sharepoint || echo "[sharepoint] rodada falhou; nova tentativa em ${INTERVALO} min"
            sleep $((INTERVALO * 60))
        done
    ) &
    echo "[entrypoint] Sincronização com o SharePoint a cada ${INTERVALO} min (em segundo plano)"
fi

DEBUG_FLAG="${DEBUG:-False}"

if [ "$DEBUG_FLAG" = "true" ] || [ "$DEBUG_FLAG" = "True" ] || [ "$DEBUG_FLAG" = "1" ]; then
    echo "[entrypoint] DEBUG ligado → rodando runserver"
    exec python src/manage.py runserver 0.0.0.0:80 --nothreading --noreload
else
    echo "[entrypoint] DEBUG desligado → rodando gunicorn"
    exec gunicorn \
        --workers "${GUNICORN_WORKERS:-3}" \
        --timeout "${GUNICORN_TIMEOUT:-600}" \
        --bind 0.0.0.0:80 \
        proposal.wsgi:application
fi

