# Keycloak

Keycloak 26 com Postgres próprio, publicado no Traefik em `https://keycloak.docker.localhost`. Ele cria no primeiro boot o realm `automateflow`, que já traz os clients do `mongo/` (`atlas-insights`), do `akamai/` (`linode-insights`) e do `migrate_mongo/` (`mongo-migrator`).

## Subindo

```bash
make compose     # cria o .env a partir do .env.example, a rede proxy, e sobe tudo
make logs
```

| Serviço | Função |
|---|---|
| `keycloak` | Keycloak em modo `start` (produção), HTTP na 8080 atrás do Traefik, health/metrics na 9000. Na rede `proxy`, os outros apps o alcançam como `http://keycloak:8080` |
| `keycloak-db` | Postgres 17 no volume `keycloak-db`, numa rede interna que não fica exposta na `proxy` |
| `reverse-proxy` | Traefik 3 com `~/.traefik` e `~/.certs`; **só sobe se nenhum container estiver publicando a porta 443** (profile `traefik`) |

O console fica em `https://keycloak.docker.localhost/admin` (usuário `KC_ADMIN_USER`/`KC_ADMIN_PASSWORD` do realm master).

Outros alvos: `make down`, `make ps`, `make export` e `make reset`.

Para trazer os realms de um Keycloak que roda em outra VM, veja [README_migracao_vm.md](README_migracao_vm.md).

Para criar realms, cadastrar o SSO corporativo via SAML e controlar o acesso por grupos, veja [README_sso.md](README_sso.md).

## Realm `automateflow`

O arquivo [realm/automateflow-realm.json](realm/automateflow-realm.json) é importado com `--import-realm`, mas **só quando o realm ainda não existe** no banco. Os `${...}` do arquivo vêm das variáveis de ambiente do container. Ele contém:

- role de realm `ADMIN`, que vira superuser nos apps (`KEYCLOAK_ADMIN_ROLE`);
- usuário `KC_REALM_ADMIN_USER`/`KC_REALM_ADMIN_PASSWORD`, com a role `ADMIN`;
- clients públicos com PKCE (`S256`): `atlas-insights`, `linode-insights` e `mongo-migrator`. Os redirects são `<URL>/oidc/callback/`, em que a URL vem de `ATLAS_INSIGHTS_URL`, `LINODE_INSIGHTS_URL` e `MONGO_MIGRATOR_URL`.

Para mudar o realm:

- **Pelo console**: as mudanças ficam no banco. Rode `make export` para gravar o realm em `./export/` (está no `.gitignore`, porque contém hashes de senha) e copie para `realm/` o que quiser versionar.
- **Pelo JSON**: edite `realm/*.json` e rode `make reset`. **Atenção:** o `reset` apaga o banco inteiro (usuários, sessões e o que foi feito no console).

## Usando nos apps (`mongo/`, `akamai/`)

Os apps apontam por padrão para o realm `pseudo658`. Para usar este Keycloak, coloque no `.env` de cada app:

```bash
KEYCLOAK_HOST=https://keycloak.docker.localhost/
KEYCLOAK_INTERNAL_URL=http://keycloak:8080
KEYCLOAK_REALM=automateflow
```

Como os clients já vêm no realm, não é preciso rodar o `make keycloak-client` dos apps. Se rodar, passe a senha do admin do master: `make keycloak-client KC_ADMIN_PASSWORD=...`.

**Conflito com o pseudo658:** o Keycloak do pseudo658 usa o mesmo host (`keycloak.docker.localhost`), o mesmo hostname (`keycloak`) e o mesmo router no Traefik. Suba só um dos dois. Se precisar dos dois ao mesmo tempo, troque `KC_HOST` aqui e o nome do router nas labels do `docker-compose.yaml`. Nos apps, aponte `KEYCLOAK_INTERNAL_URL` para o nome do container (`http://keycloak-keycloak-1:8080`).

## Deploy no Kubernetes

Os manifests ficam em [k8s/](k8s/) e são montados pelo [kustomization.yaml](kustomization.yaml). Ele fica na raiz desta pasta porque o kustomize não lê arquivos acima dela, e precisa empacotar o mesmo `realm/automateflow-realm.json` usado no compose.

```bash
make k8s-secrets   # cria k8s/secrets.env a partir do exemplo; troque as senhas
make k8s-apply     # kubectl apply -k . no contexto atual + espera o rollout
make k8s-status    # pods, svc, ingress e pvc
make k8s-logs
make k8s-render    # só mostra o YAML final
```

Tudo vai para o namespace `keycloak`:

| Recurso | Função |
|---|---|
| `Deployment/keycloak` | Keycloak 26 em modo `start`, com probes em `/health/*` na porta 9000. O realm é montado de um ConfigMap e importado com `--import-realm`. Para escalar, basta aumentar `replicas`: os pods se descobrem pelo banco (JDBC_PING) |
| `StatefulSet/keycloak-db` | Postgres 17 com PVC de 10Gi na StorageClass padrão do cluster |
| `Ingress/keycloak` | Traefik no entrypoint `websecure`, com `certresolver: default` (mesmo padrão do `akamai.yaml`). Só HTTPS |
| `ConfigMap/keycloak-config` | gerado de [k8s/config.env](k8s/config.env): host, realm e URLs dos apps (versionado) |
| `Secret/keycloak-secrets` | gerado de `k8s/secrets.env` (no `.gitignore`): admin do master, usuário do banco e senha do admin do realm |

O host público fica só em `KC_HOSTNAME` (`k8s/config.env`). O kustomize copia esse valor para o Ingress. Os ConfigMaps e o Secret ganham um hash no nome, então mudar `config.env` ou `secrets.env` e rodar `make k8s-apply` reinicia o Keycloak sozinho.

Como no compose, as senhas do admin do master e do Postgres só valem no primeiro boot, com o volume vazio. Depois disso, trocá-las no `secrets.env` não altera o banco.

Nos apps do cluster:

```yaml
- name: KEYCLOAK_HOST
  value: https://keycloak.actionstat.app/
- name: KEYCLOAK_INTERNAL_URL        # back-channel sem sair do cluster
  value: http://keycloak.keycloak.svc.cluster.local:8080
- name: KEYCLOAK_REALM
  value: automateflow
```

`make k8s-delete` apaga o namespace inteiro, **inclusive o PVC do banco**.

## Variáveis

| Variável | Descrição |
|---|---|
| `KC_HOST` | host público no Traefik (padrão `keycloak.docker.localhost`) |
| `KC_ADMIN_USER` / `KC_ADMIN_PASSWORD` | admin do realm master. Só valem no primeiro boot; depois, a senha é trocada pelo console |
| `KC_DB_NAME` / `KC_DB_USER` / `KC_DB_PASSWORD` | Postgres do Keycloak |
| `KC_REALM` | nome do realm importado (padrão `automateflow`) |
| `KC_REALM_ADMIN_USER` / `KC_REALM_ADMIN_PASSWORD` | usuário com a role `ADMIN` criado no realm |
| `ATLAS_INSIGHTS_URL` / `LINODE_INSIGHTS_URL` / `MONGO_MIGRATOR_URL` | URLs públicas dos apps, usadas nos redirect URIs |
| `KC_LOG_LEVEL` | `info` (padrão), `debug`, `warn`… |
