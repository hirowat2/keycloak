#!/bin/sh
set -eu

python src/manage.py collectstatic --noinput
python src/manage.py migrate --noinput

# Client de login do assistente e role ADMIN no realm do login: só cria/acerta o que falta.
# Num realm importado antes (ex.: produção), sem isso ninguém entra no assistente.
if [ "${PREPARAR_LOGIN:-1}" = "1" ]; then
    python src/manage.py preparar_login || echo "[entrypoint] preparar_login falhou; o login no assistente pode não funcionar"
fi

if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && \
   [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ] && \
   [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    python src/manage.py createsuperuser --noinput 2>/dev/null || \
        echo "[entrypoint] Superusuário já existe; continuando."
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
        system.wsgi:application
fi
