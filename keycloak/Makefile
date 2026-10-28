PROJECT_NAME:=keycloak
SERVICE:=keycloak
KC_HOST:=$(shell grep -s '^KC_HOST=' .env | cut -d= -f2- | tr -d "'\"")
KC_REALM:=$(shell grep -s '^KC_REALM=' .env | cut -d= -f2- | tr -d "'\"")

.PHONY: env network compose up down logs ps export reset k8s-secrets k8s-render k8s-apply k8s-status k8s-logs k8s-delete

env:
	@[ -f .env ] || { cp .env.example .env; echo "✅ .env criado a partir do .env.example (troque as senhas)"; }

network:
	@docker network inspect proxy >/dev/null 2>&1 || docker network create proxy

# Sobe o Traefik junto só se nenhum container já estiver publicando a porta 443
compose: env network
	@if [ -n "$$(docker ps -q --filter publish=443)" ]; then \
		echo "➡️  Traefik já rodando; registrando o Keycloak nele"; \
		docker compose up -d --remove-orphans; \
	else \
		echo "➡️  Nenhum Traefik encontrado; subindo o reverse-proxy junto"; \
		docker compose --profile traefik up -d --remove-orphans; \
	fi
	@echo "✅ https://$(or $(KC_HOST),keycloak.docker.localhost) (o primeiro boot leva ~1 min; acompanhe com make logs)"

up: compose

down:
	@docker compose --profile traefik down

logs:
	@docker compose logs -f $(SERVICE)

ps:
	@docker compose ps

# Exporta o realm (com usuários) para ./export. A 9000 já é do servidor rodando.
export:
	@docker compose exec $(SERVICE) /opt/keycloak/bin/kc.sh export \
		--http-management-port=9001 --dir /tmp/export --realm $(or $(KC_REALM),automateflow) --users realm_file
	@mkdir -p export
	@docker compose cp $(SERVICE):/tmp/export/. export/
	@echo "✅ Realm exportado em ./export"

# Apaga o banco (usuários, sessões, clients) e reimporta realm/*.json no próximo boot
reset:
	@docker compose --profile traefik down -v
	@$(MAKE) --no-print-directory compose

# --- Kubernetes (kustomization.yaml + k8s/) -------------------------------------
K8S_NS:=keycloak

k8s-secrets:
	@[ -f k8s/secrets.env ] || { cp k8s/secrets.env.example k8s/secrets.env; echo "⚠️  k8s/secrets.env criado: troque as senhas antes do k8s-apply"; exit 1; }

k8s-render: k8s-secrets
	@kubectl kustomize .

k8s-apply: k8s-secrets
	@echo "➡️  Contexto: $$(kubectl config current-context)"
	@kubectl apply -k .
	@kubectl -n $(K8S_NS) rollout status deploy/keycloak --timeout=10m

k8s-status:
	@kubectl -n $(K8S_NS) get pods,svc,ingress,pvc

k8s-logs:
	@kubectl -n $(K8S_NS) logs -f deploy/keycloak

# Remove tudo, inclusive o PVC do banco (namespace inteiro)
k8s-delete:
	@kubectl delete -k .
