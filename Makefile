REGISTRY_OWNER:=estat
PROJECT_NAME:=commercialproposal
PROJECT_TAG:=latest

ifneq (,$(wildcard ./.env))
	include .env
	export
endif

all: install compose

install:
	@poetry install --with dev
	@poetry config virtualenvs.in-project true

migrate:
	@poetry run python src/manage.py collectstatic --noinput
	@poetry run python src/manage.py makemigrations
	@poetry run python src/manage.py migrate

createsuperuser:
	@poetry run python src/manage.py createsuperuser

startapp:
	@cd src; poetry run python manage.py startapp $(app); cd ..

runserver: migrate
	@poetry run python src/manage.py runserver

test:
	@poetry run pytest

gunicorn:
	@poetry run gunicorn \
		--log-level debug \
		--bind localhost:8000 \
		src.proposal.wsgi:application

clean:
	@sudo rm prof/*.prof

secret:
	@if [ ! -f .env ] || ! grep -q '^SECRET_KEY=' .env 2>/dev/null; then \
		echo "SECRET_KEY='$$(poetry run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")'" >> .env; \
		echo "✅ SECRET_KEY added to .env"; \
	else \
		echo "⚠️  .env already exists and contains SECRET_KEY (not modified)"; \
	fi

compose: secret
	@docker-compose up --build --remove-orphans

build:
	@docker buildx build \
		--secret id=github_pat,env=GITHUB_PAT \
		--load \
		--tag \
		${REGISTRY_OWNER}/${PROJECT_NAME}:${PROJECT_TAG} \
		.

K8S_NAMESPACE?=default

k8s-deploy:
	@kubectl -n ${K8S_NAMESPACE} apply -f k8s/commercialproposal.yaml

interact: build
	@docker run \
		--rm \
		--workdir /usr/src \
		--volume $(shell pwd)/src:/usr/src/src \
		-it \
		--entrypoint /bin/sh \
		${REGISTRY_OWNER}/${PROJECT_NAME}:${PROJECT_TAG}

shell:
	docker-compose exec \
		commercialproposal \
		python src/manage.py shell_plus

der:
	@if pacman -Qq graphviz >/dev/null 2>&1; then \
		echo "Generating diagrams for ${PROJECT_NAME}..."; \
		poetry run python src/manage.py graph_models commercial -o ${PROJECT_NAME}_clean_diagram.svg; \
		poetry run python src/manage.py graph_models -a -g -o ${PROJECT_NAME}_complete_diagram.svg; \
	else \
		echo "❌ Graphviz not found."; \
		echo "➡️  Install graphviz: sudo pacman -S graphviz"; \
		exit 1; \
	fi

down:
	@docker-compose down

tunel:
	@cloudflared tunnel \
		--url https://propostas.docker.localhost \
		--no-tls-verify \
		--http-host-header propostas.docker.localhost \
		--origin-server-name propostas.docker.localhost
