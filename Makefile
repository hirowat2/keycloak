REGISTRY_OWNER:=estat
PROJECT_NAME:=keycloak-assistente
PROJECT_TAG:=latest
SERVICE:=keycloak

ifneq (,$(wildcard ./.env))
	include .env
	export
endif

.PHONY: all install migrate createsuperuser startapp runserver test gunicorn clean secret env network compose up down logs ps \
	build interact shell der realm-export reset importar-realms restaurar-dump \
	k8s-secrets k8s-render k8s-apply k8s-status k8s-logs k8s-delete k8s-importar-realms k8s-restaurar-dump

all: install compose

# --- Assistente (Django) ------------------------------------------------------------------------

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

# Integração contra um Keycloak de verdade: KEYCLOAK_TESTE_URL=https://keycloak.docker.localhost KEYCLOAK_VERIFY_TLS=false make test
test:
	@poetry run python src/manage.py collectstatic --noinput -v0
	@poetry run pytest

gunicorn:
	@poetry run gunicorn \
		--log-level debug \
		--bind localhost:8000 \
		src.system.wsgi:application

clean:
	@sudo rm prof/*.prof

secret:
	@if [ ! -f .env ] || ! grep -q '^SECRET_KEY=' .env 2>/dev/null; then \
		echo "SECRET_KEY='$$(poetry run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")'" >> .env; \
		echo "✅ SECRET_KEY added to .env"; \
	else \
		echo "⚠️  .env already exists and contains SECRET_KEY (not modified)"; \
	fi

build:
	@docker buildx build \
		--secret id=github_pat,env=GITHUB_PAT \
		--load \
		--tag \
		${REGISTRY_OWNER}/${PROJECT_NAME}:${PROJECT_TAG} \
		.

interact: build
	@docker run \
		--rm \
		--workdir /usr/src \
		--volume $(shell pwd)/src:/usr/src/src \
		-it \
		--entrypoint /bin/sh \
		${REGISTRY_OWNER}/${PROJECT_NAME}:${PROJECT_TAG}

shell:
	docker compose exec \
		assistente \
		python src/manage.py shell_plus

der:
	@if pacman -Qq graphviz >/dev/null 2>&1; then \
		echo "Generating diagrams for ${PROJECT_NAME}..."; \
		poetry run python src/manage.py graph_models keycloak -o ${PROJECT_NAME}_clean_diagram.svg; \
		poetry run python src/manage.py graph_models -a -g -o ${PROJECT_NAME}_complete_diagram.svg; \
	else \
		echo "❌ Graphviz not found."; \
		echo "➡️  Install graphviz: sudo pacman -S graphviz"; \
		exit 1; \
	fi

# --- docker compose (Keycloak + assistente) -----------------------------------------------------

env:
	@[ -f .env ] || { cp .env.example .env; echo "✅ .env criado a partir do .env.example (troque as senhas)"; }

network:
	@docker network inspect proxy >/dev/null 2>&1 || docker network create proxy

# Sobe o Traefik junto só se nenhum container já estiver publicando a porta 443
compose: env network secret
	@if [ -n "$$(docker ps -q --filter publish=443)" ]; then \
		echo "➡️  Traefik já rodando; registrando o Keycloak e o assistente nele"; \
		docker compose up --build; \
	else \
		echo "➡️  Nenhum Traefik encontrado; subindo o reverse-proxy junto"; \
		docker compose --profile traefik up --build; \
	fi
	@echo "✅ Keycloak:   https://$(or $(KC_HOST),keycloak.docker.localhost)/admin (o primeiro boot leva ~1 min; acompanhe com make logs)"
	@echo "✅ Assistente: https://$(or $(ASSISTENTE_HOST),keycloak-assistente.docker.localhost)"

up: compose

down:
	@docker compose --profile traefik down

logs:
	@docker compose logs -f $(SERVICE) assistente

ps:
	@docker compose ps

# Exporta o realm (com usuários) para ./export. A 9000 já é do servidor rodando.
realm-export:
	@docker compose exec $(SERVICE) /opt/keycloak/bin/kc.sh export \
		--http-management-port=9001 --dir /tmp/export --realm $(or $(KC_REALM),automateflow) --users realm_file
	@mkdir -p export
	@docker compose cp $(SERVICE):/tmp/export/. export/
	@echo "✅ Realm exportado em ./export"

# Apaga os bancos (usuários, sessões, clients, histórico do assistente) e reimporta realm/*.json no próximo boot
reset:
	@docker compose --profile traefik down -v
	@$(MAKE) --no-print-directory compose

# --- Migração da VM (README_migracao_vm.md) ----------------------------------------------------
# Na VM: sh scripts/exportar_vm.sh <container> → kc-export.tgz (caminho A) ou keycloak.dump (caminho B)
EXPORT_DIR?=export/kc-export
DUMP?=keycloak.dump

define confirmar_apagar
	@printf "⚠️  Isto APAGA o banco do Keycloak $(1) e põe o da VM no lugar. Digite 'apagar' para continuar: "; \
		read resposta; [ "$$resposta" = apagar ] || { echo "Cancelado."; exit 1; }
endef

$(EXPORT_DIR):
	@[ -f kc-export.tgz ] || { echo "❌ Falta kc-export.tgz (ou a pasta $(EXPORT_DIR)). Traga da VM: scp <vm>:kc-export.tgz ."; exit 1; }
	@mkdir -p $(dir $(EXPORT_DIR)) && tar xzf kc-export.tgz -C $(dir $(EXPORT_DIR))

# Caminho A no compose: --override false pula os realms que já existem (o master e o automateflow daqui)
importar-realms: $(EXPORT_DIR)
	@docker compose exec $(SERVICE) rm -rf /tmp/kc-import
	@docker compose cp $(EXPORT_DIR) $(SERVICE):/tmp/kc-import
	@docker compose exec $(SERVICE) /opt/keycloak/bin/kc.sh import --dir /tmp/kc-import --override false --http-management-port=9001
	@docker compose restart $(SERVICE)
	@echo "✅ Realms importados. Confira no assistente (Painel) e ajuste o host em Migração da VM."

# Caminho B no compose: dropdb + pg_restore; na subida o Keycloak migra o schema sozinho
restaurar-dump:
	@[ -f "$(DUMP)" ] || { echo "❌ Falta $(DUMP). Traga da VM: scp <vm>:keycloak.dump ."; exit 1; }
	$(call confirmar_apagar,do compose)
	@docker compose stop $(SERVICE)
	@docker compose up -d --wait keycloak-db
	@docker compose exec -T keycloak-db sh -c 'dropdb -U "$$POSTGRES_USER" --if-exists "$$POSTGRES_DB" && createdb -U "$$POSTGRES_USER" "$$POSTGRES_DB"'
	@docker compose exec -T keycloak-db sh -c 'pg_restore -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" --no-owner --no-acl' < "$(DUMP)"
	@docker compose up -d $(SERVICE)
	@echo "✅ Dump restaurado. O admin do console agora é o da VM; acompanhe a migração do schema com make logs."

# --- Kubernetes (kustomization.yaml + k8s/) -----------------------------------------------------
K8S_NS:=keycloak
K8S_POD=$$(kubectl -n $(K8S_NS) get pod -l application=keycloak -o name | head -1)

k8s-secrets:
	@[ -f k8s/secrets.env ] || { cp k8s/secrets.env.example k8s/secrets.env; echo "⚠️  k8s/secrets.env criado: troque as senhas antes do k8s-apply"; exit 1; }

k8s-render: k8s-secrets
	@kubectl kustomize .

k8s-apply: k8s-secrets
	@echo "➡️  Contexto: $$(kubectl config current-context)"
	@kubectl apply -k .
	@kubectl -n $(K8S_NS) rollout status deploy/keycloak --timeout=10m
	@kubectl -n $(K8S_NS) rollout status deploy/assistente --timeout=10m

k8s-status:
	@kubectl -n $(K8S_NS) get pods,svc,ingress,pvc

k8s-logs:
	@kubectl -n $(K8S_NS) logs -f deploy/keycloak

# Remove tudo, inclusive os PVCs (namespace inteiro)
k8s-delete:
	@kubectl delete -k .

# Caminho A no cluster: a imagem do Keycloak não tem tar, então os arquivos vão um a um por stdin
k8s-importar-realms: $(EXPORT_DIR)
	@echo "➡️  Contexto: $$(kubectl config current-context)"
	@POD=$(K8S_POD); \
		kubectl -n $(K8S_NS) exec $$POD -- sh -c 'rm -rf /tmp/kc-import && mkdir -p /tmp/kc-import' && \
		for f in $(EXPORT_DIR)/*.json; do \
			case "$$f" in */master-*) continue ;; esac; \
			kubectl -n $(K8S_NS) exec -i $$POD -- sh -c "cat > /tmp/kc-import/$$(basename $$f)" < "$$f"; \
		done && \
		kubectl -n $(K8S_NS) exec $$POD -- /opt/keycloak/bin/kc.sh import --dir /tmp/kc-import --override false --http-management-port=9001
	@kubectl -n $(K8S_NS) rollout restart deploy/keycloak
	@kubectl -n $(K8S_NS) rollout status deploy/keycloak --timeout=10m

# Caminho B no cluster: 0 réplicas (o dropdb falha com conexões abertas), restore, 1 réplica
k8s-restaurar-dump:
	@[ -f "$(DUMP)" ] || { echo "❌ Falta $(DUMP). Traga da VM: scp <vm>:keycloak.dump ."; exit 1; }
	@echo "➡️  Contexto: $$(kubectl config current-context)"
	$(call confirmar_apagar,no cluster)
	@kubectl -n $(K8S_NS) scale deploy/keycloak --replicas=0
	@kubectl -n $(K8S_NS) wait --for=delete pod -l application=keycloak --timeout=5m
	@kubectl -n $(K8S_NS) exec -i keycloak-db-0 -- sh -c 'dropdb -U "$$POSTGRES_USER" --if-exists "$$POSTGRES_DB" && createdb -U "$$POSTGRES_USER" "$$POSTGRES_DB"'
	@kubectl -n $(K8S_NS) exec -i keycloak-db-0 -- sh -c 'pg_restore -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" --no-owner --no-acl' < "$(DUMP)"
	@kubectl -n $(K8S_NS) scale deploy/keycloak --replicas=1
	@kubectl -n $(K8S_NS) rollout status deploy/keycloak --timeout=10m
