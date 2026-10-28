# Keycloak + assistente

Keycloak 26 com Postgres próprio, publicado no Traefik em `https://keycloak.docker.localhost`, e o **assistente**: um app Django que faz pela Admin API os passos do [README_sso.md](README_sso.md) e do [README_migracao_vm.md](README_migracao_vm.md), sem cliques no console. No primeiro boot, o Keycloak cria o realm `automateflow`, que já traz os clients do `mongo/` (`atlas-insights`), do `akamai/` (`linode-insights`) e do `migrate_mongo/` (`mongo-migrator`).

## Subindo

```bash
make compose     # cria o .env a partir do .env.example, a SECRET_KEY, a rede proxy, e sobe tudo
make logs
```

| Serviço | Função |
|---|---|
| `keycloak` | Keycloak em modo `start` (produção), HTTP na 8080 atrás do Traefik, health/metrics na 9000. Na rede `proxy`, os outros apps o alcançam como `http://keycloak:8080` |
| `keycloak-db` | Postgres 17 do Keycloak, no volume `keycloak-db`, só na rede da stack |
| `assistente` | O assistente, em `https://keycloak-assistente.docker.localhost` (`ASSISTENTE_HOST`) |
| `assistente-db` | Postgres 17 do assistente (sessões e histórico), no volume `assistente-db` |
| `reverse-proxy` | Traefik 3 com `~/.traefik` e `~/.certs`; **só sobe se nenhum container estiver publicando a porta 443** (profile `traefik`) |

| Onde | Quem entra |
|---|---|
| Console do Keycloak: `https://keycloak.docker.localhost/admin` | o admin do realm **master** (`KC_ADMIN_USER`/`KC_ADMIN_PASSWORD`) |
| Assistente: `https://keycloak-assistente.docker.localhost` | um usuário do realm `KC_REALM` com e-mail liberado (veja [Acesso ao assistente](#acesso-ao-assistente)). Localmente, o `KC_REALM_ADMIN_USER`/`KC_REALM_ADMIN_PASSWORD` |

Outros alvos: `make down`, `make ps`, `make realm-export`, `make reset` e `make test`.

## O assistente

Cada etapa é um formulário que vale para o realm escolhido no menu lateral. **Simular** mostra o plano (o que será criado, atualizado ou removido) sem gravar nada; **Aplicar** grava no Keycloak. Rodar de novo uma etapa já aplicada não duplica nada: o plano sai com 0 mudanças. Toda simulação e aplicação fica no **Histórico**, com quem fez e o plano completo.

| Tela | O que faz | Guia |
|---|---|---|
| **Painel** | Versão do Keycloak, realms, andamento das etapas do realm ativo e as últimas ações | |
| **1 · Realm e apps** | Cria ou acerta o realm (SSL, cadastro e "esqueci a senha" desligados, login com e-mail, pt-BR, força bruta), a role `ADMIN`, um client OIDC público com PKCE `S256` por app e uma role de acesso com o nome de cada client | SSO 1.1–1.7, 3.1 |
| **2 · Grupos e roles** | Matriz grupo × role, já preenchida com a estrutura sugerida (`<realm>-admins` e um grupo por app) | SSO 3.2 |
| **3 · SSO corporativo** | URLs para o time do SSO (Entity ID, ACS, metadata do SP) com botão de copiar, roteiro do Entra/Google/Okta, e o provedor SAML cadastrado a partir da URL ou do XML de metadata, com assinaturas, `Sync mode Force`, os mappers de e-mail, nome, sobrenome e username e, se quiser, o login direto pelo SSO | SSO 2 |
| **4 · Grupos do SSO** | Um mapper *Advanced Attribute to Group* por grupo (Key `groups` ou o URI longo do Entra; Value com o nome ou o GUID do grupo) | SSO 4.4 |
| **5 · Conferir** | Checklist do realm contra o guia, roles efetivas e vínculo com o SSO de um usuário, `.env` de cada app e o **JSON para versionar** (sem usuários, ids, secrets nem chaves) | SSO 1.8, 3.3, 4.5 |
| **Migração da VM** | Comandos prontos para a VM e o destino, troca do host antigo (Frontend URL e URLs dos clients) e usuários sem e-mail ou nome | Migração |
| **Histórico** | Cada simulação e aplicação, com filtro por realm | |

O que acontece **dentro do SSO** (criar a aplicação SAML, os grupos e o claim de grupos no Entra, no Google ou no Okta) continua sendo feito no portal de cada um. A tela 3 mostra o roteiro.

### Acesso ao assistente

O login segue o padrão dos apps: `keycloak.js` no client `keycloak-assistente` do realm `KC_REALM`, com o token validado em [src/system/sso.py](src/system/sso.py).

- Só entram os e-mails de `EMAILS_PERMITIDOS`, fixos no código. Com `DEBUG` ligado (compose), entra também o `admin@automateflow.local` (o `KC_REALM_ADMIN_USER` do JSON).
- Quem tem a role de realm **`ADMIN`** fica no grupo *Admin*: simula, aplica e acessa o `/admin/` do Django. Os demais ficam no *Limited*: veem tudo e simulam, mas não aplicam.
- O client `keycloak-assistente` é criado (ou acertado) pelo entrypoint (`manage.py preparar_login`), porque um realm importado antes não o tem.
- Na Admin API, o assistente usa o admin do master (`KEYCLOAK_ADMIN_USER`/`KEYCLOAK_ADMIN_PASSWORD`, que no compose vêm de `KC_ADMIN_USER`/`KC_ADMIN_PASSWORD`). Se a senha desse admin for trocada no console, troque também no `.env`/`secrets.env`, ou o assistente mostra "O Keycloak não respondeu". Para não usar senha, crie no master um client com service account e role `admin` e passe `KEYCLOAK_ADMIN_CLIENT_ID`/`KEYCLOAK_ADMIN_CLIENT_SECRET`.

Para configurar outro Keycloak (ex.: o de produção) a partir da sua máquina, rode o assistente apontando para ele: `KEYCLOAK_HOST` e `KEYCLOAK_INTERNAL_URL` com a URL pública e as credenciais do admin do master.

### Código

```text
src/
├── system/                  # projeto Django: settings, URLs, login (sso.py)
└── keycloak/                # o app
    ├── automacao/           # Admin API e as etapas, sem Django (dá para usar num script)
    │   ├── api.py           #   cliente da Admin REST API (token do master)
    │   ├── plano.py         #   Plano/Passo: simular x aplicar, diff
    │   ├── realm.py         #   etapa 1
    │   ├── grupos.py        #   etapa 2
    │   ├── saml.py          #   etapas 3 e 4
    │   ├── conferir.py      #   etapa 5 e export
    │   ├── manutencao.py    #   host novo e usuários incompletos
    │   └── web.py           #   utilitários das telas (realm ativo, permissões, histórico)
    ├── screens/<tela>/view.py   # uma pasta por tela; o menu fica em screens/config/aside.py
    ├── templates/<tela>.html
    └── management/commands/preparar_login.py
scripts/exportar_vm.sh       # roda na VM antiga (migração)
```

### Testes

```bash
make test                                                                       # unitários
KEYCLOAK_TESTE_URL=https://keycloak.docker.localhost KEYCLOAK_VERIFY_TLS=false make test   # + integração
```

Com `KEYCLOAK_TESTE_URL`, [tests/test_integracao.py](tests/test_integracao.py) percorre as cinco etapas e a troca de host pelas telas, contra o Keycloak de verdade, num realm descartável que é apagado no fim. Ele confere também que reaplicar não muda nada e que o perfil Limited não grava.

## Realm `automateflow`

O arquivo [realm/automateflow-realm.json](realm/automateflow-realm.json) é importado com `--import-realm`, mas **só quando o realm ainda não existe** no banco. Os `${...}` do arquivo vêm das variáveis de ambiente do container. Ele contém:

- role de realm `ADMIN`, que vira superuser nos apps (`KEYCLOAK_ADMIN_ROLE`);
- usuário `KC_REALM_ADMIN_USER`/`KC_REALM_ADMIN_PASSWORD`, com a role `ADMIN`;
- clients públicos com PKCE (`S256`): `atlas-insights`, `linode-insights` e `mongo-migrator`. Os redirects são `<URL>/oidc/callback/`, em que a URL vem de `ATLAS_INSIGHTS_URL`, `LINODE_INSIGHTS_URL` e `MONGO_MIGRATOR_URL`.

Para mudar o realm:

- **Pelo assistente ou pelo console**: as mudanças ficam no banco. Para versionar, use **5 · Conferir → JSON para versionar** (ou `make realm-export`, que grava o realm completo em `./export/`, no `.gitignore` porque contém hashes de senha) e copie para `realm/` o que quiser versionar.
- **Pelo JSON**: edite `realm/*.json` e rode `make reset`. **Atenção:** o `reset` apaga os bancos inteiros (usuários, sessões, o que foi feito no console e o histórico do assistente).

## Usando nos apps (`mongo/`, `akamai/`)

Os apps apontam por padrão para o realm `pseudo658`. Para usar este Keycloak, coloque no `.env` de cada app o trecho que a tela **5 · Conferir** monta, ou:

```bash
KEYCLOAK_HOST=https://keycloak.docker.localhost/
KEYCLOAK_INTERNAL_URL=http://keycloak:8080
KEYCLOAK_REALM=automateflow
KEYCLOAK_REQUIRED_ROLE=atlas-insights   # sem ela, qualquer usuário do realm entra no app
```

Como os clients já vêm no realm, não é preciso rodar o `make keycloak-client` dos apps. Se rodar, passe a senha do admin do master: `make keycloak-client KC_ADMIN_PASSWORD=...`.

**Conflito com o pseudo658:** o Keycloak do pseudo658 usa o mesmo host (`keycloak.docker.localhost`), o mesmo hostname (`keycloak`) e o mesmo router no Traefik. Suba só um dos dois. Se precisar dos dois ao mesmo tempo, troque `KC_HOST` aqui e o nome do router nas labels do `docker-compose.yml`. Nos apps, aponte `KEYCLOAK_INTERNAL_URL` para o nome do container (`http://keycloak-keycloak-1:8080`).

## Migração de uma VM

Para trazer os realms de um Keycloak que roda em outra VM:

```bash
scp scripts/exportar_vm.sh usuario@vm: && ssh usuario@vm sh exportar_vm.sh <container-do-keycloak>
scp usuario@vm:kc-export.tgz .  && make importar-realms     # se saiu kc-export.tgz (caminho A)
scp usuario@vm:keycloak.dump .  && make restaurar-dump      # se saiu keycloak.dump (caminho B: apaga o banco daqui)
```

O script descobre sozinho se a VM usa H2 ou Postgres. No cluster, use `make k8s-importar-realms` / `make k8s-restaurar-dump`. Depois, termine na tela **Migração da VM**. O passo a passo explicado, com figuras, está no [README_migracao_vm.md](README_migracao_vm.md).

## Deploy no Kubernetes

Os manifests ficam em [k8s/](k8s/) e são montados pelo [kustomization.yaml](kustomization.yaml). Ele fica na raiz porque o kustomize não lê arquivos acima dela, e precisa empacotar o mesmo `realm/automateflow-realm.json` usado no compose.

```bash
make build         # imagem estat/keycloak-assistente (precisa do GITHUB_PAT); publique no registry
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
| `Deployment/assistente` | O assistente (`estat/keycloak-assistente`), com o histórico num SQLite no PVC `assistente-data` (1 réplica). Fala com o Keycloak pelo Service `http://keycloak:8080` |
| `Ingress/keycloak`, `Ingress/assistente` | Traefik no entrypoint `websecure`, com `certresolver: default` (mesmo padrão do `akamai.yaml`). Só HTTPS |
| `ConfigMap/keycloak-config` | gerado de [k8s/config.env](k8s/config.env): hosts, realm e URLs dos apps (versionado) |
| `Secret/keycloak-secrets` | gerado de `k8s/secrets.env` (no `.gitignore`): admin do master, usuário do banco, senha do admin do realm e a `SECRET_KEY` do assistente |

Os hosts públicos ficam só em `KC_HOSTNAME` e `ASSISTENTE_HOSTNAME` (`k8s/config.env`). O kustomize copia esses valores para os Ingress. Os ConfigMaps e o Secret ganham um hash no nome, então mudar `config.env` ou `secrets.env` e rodar `make k8s-apply` reinicia os pods sozinho.

Como no compose, as senhas do admin do master e do Postgres só valem no primeiro boot, com o volume vazio. Depois disso, trocá-las no `secrets.env` não altera o banco. A exceção é o assistente, que lê a senha do admin do master desse Secret: se ela mudar no console, atualize o `secrets.env`.

Nos apps do cluster:

```yaml
- name: KEYCLOAK_HOST
  value: https://keycloak.actionstat.app/
- name: KEYCLOAK_INTERNAL_URL        # back-channel sem sair do cluster
  value: http://keycloak.keycloak.svc.cluster.local:8080
- name: KEYCLOAK_REALM
  value: automateflow
```

`make k8s-delete` apaga o namespace inteiro, **inclusive os PVCs** do banco e do assistente.

## Variáveis

| Variável | Descrição |
|---|---|
| `KC_HOST` | host público do Keycloak no Traefik (padrão `keycloak.docker.localhost`) |
| `KC_ADMIN_USER` / `KC_ADMIN_PASSWORD` | admin do realm master. Só valem no primeiro boot; depois, a senha é trocada pelo console. O assistente usa os mesmos na Admin API |
| `KC_DB_NAME` / `KC_DB_USER` / `KC_DB_PASSWORD` | Postgres do Keycloak |
| `KC_REALM` | nome do realm importado (padrão `automateflow`); é também o realm do login no assistente |
| `KC_REALM_ADMIN_USER` / `KC_REALM_ADMIN_PASSWORD` | usuário com a role `ADMIN` criado no realm |
| `ATLAS_INSIGHTS_URL` / `LINODE_INSIGHTS_URL` / `MONGO_MIGRATOR_URL` | URLs públicas dos apps, usadas nos redirect URIs |
| `KC_LOG_LEVEL` | `info` (padrão), `debug`, `warn`… |
| `ASSISTENTE_HOST` | host público do assistente (padrão `keycloak-assistente.docker.localhost`) |
| `ASSISTENTE_DB_PASSWORD` | Postgres do assistente |
| `SECRET_KEY` | do Django do assistente (criada pelo `make secret`) |
| `KEYCLOAK_ADMIN_CLIENT_ID` / `KEYCLOAK_ADMIN_CLIENT_SECRET` | opcional: service account do master no lugar do usuário e senha |
| `KEYCLOAK_VERIFY_TLS` | `false` para aceitar certificado próprio ao rodar o assistente fora do Docker contra o host HTTPS |
