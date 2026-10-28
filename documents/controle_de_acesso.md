# Controle de acesso — quem consegue entrar no CommercialProposal

**Resposta curta:** no deploy, só entram **leao@**, **hiro@**, **lucas@**, **rubens@**, **victor@** e **vitor@estatcamp.com.br** (Victor Vasconcelos e Vitor Cezareto são pessoas diferentes). A lista está fixa no código, e cada pessoa precisa também ter usuário no Keycloak. No ambiente local (com `DEBUG` ligado), o usuário `admin` do Keycloak local também entra. Depois de entrar, os **grupos** do usuário decidem quais empresas ele vê e com que papel.

Situação conferida no código em 28/10/2026.

## 1. Quem pode entrar

A lista fica em `EMAILS_PERMITIDOS`, em [src/proposal/sso.py](../src/proposal/sso.py):

```python
EMAILS_PERMITIDOS = frozenset(
    {
        "leao@estatcamp.com.br",  # Dorival Leão
        "hiro@estatcamp.com.br",  # Hiro Watanabe
        "lucas@estatcamp.com.br",  # Lucas Farias
        "rubens@estatcamp.com.br",  # Rubens
        "victor@estatcamp.com.br",  # Victor Vasconcelos
        "vitor@estatcamp.com.br",  # Vitor Cezareto
    }
)
```

- **Não existe variável de ambiente para a lista.** `.env`, docker-compose, ConfigMap ou Secret não liberam ninguém. Assim, ninguém amplia o acesso mudando a configuração do servidor.
- Maiúsculas, minúsculas e espaços nas pontas não importam. O resto do e-mail precisa ser idêntico: `hiro@estatcamp.com.br.outro.io` não entra.
- **Admin local:** com `DEBUG` ligado, o usuário `admin` do realm local (`local-admin@mail.com`) também entra. O `DEBUG` está ligado no [docker-compose.yml](../docker-compose.yml) (`DEBUG=true`) e desligado no [k8s/commercialproposal.yaml](../k8s/commercialproposal.yaml) (`DEBUG: "false"`). Portanto, no deploy esse usuário recebe 403.
- O superusuário do Django (`DJANGO_SUPERUSER_*`), que entra com senha pelo `/admin/`, não passa pela lista, nem localmente nem no deploy.

| Quero… | Faça |
| --- | --- |
| Liberar uma pessoa | Acrescente o e-mail em `EMAILS_PERMITIDOS`, ajuste o teste `test_so_os_emails_fixos_podem_entrar` em [tests/test_sso.py](../tests/test_sso.py), gere uma imagem nova e faça o deploy. A pessoa também precisa de usuário no Keycloak (realm `commercialproposal`) com esse e-mail e com nome |
| Bloquear uma pessoa | Tire o e-mail da lista e faça o deploy. A sessão aberta cai na próxima página que ela abrir. Para bloquear na hora, sem esperar o deploy, desative o usuário no Keycloak e apague as sessões dele no `/admin/` |
| Dar papel Admin, Tech ou Limited | Atribua o papel de mesmo nome no Keycloak (client `account`); veja o item 4.1 |
| Limitar uma empresa a um grupo | *Administração → Acessos às empresas*; veja o item 4.2 |

## 2. Fluxo de login

```text
/login ──► página com keycloak.js ──► login no Keycloak (realm commercialproposal)
                                            │
                       token de acesso gravado no cookie SSOToken
                                            │
                                            ▼
                         /auth/complete/  (proposal/sso.py: auth_complete)
                           ├─ valida o token (assinatura, emissor, client, validade)
                           ├─ confere o e-mail do token em EMAILS_PERMITIDOS
                           ├─ define os grupos a partir dos papéis do token
                           └─ cria/atualiza o User do Django e faz login

a cada página: EmailPermitidoMiddleware derruba a sessão se o e-mail saiu da lista
```

| Etapa | Arquivo |
| --- | --- |
| Página de login (realm, client e host do Keycloak) | [src/proposal/views.py](../src/proposal/views.py) (`login`) |
| Login no Keycloak e cookie `SSOToken` | [src/commercial/static/sso/keycloak.js](../src/commercial/static/sso/keycloak.js) (`setSSOInfo`) |
| Validação do token, lista de e-mails e middleware | [src/proposal/sso.py](../src/proposal/sso.py) |
| Empresas e papel de cada usuário | [src/commercial/propostas/empresas.py](../src/commercial/propostas/empresas.py) |
| Realm importado na subida do Keycloak | [data/keycloak/realm/realm-export.json](../data/keycloak/realm/realm-export.json) |
| Testes | [tests/test_sso.py](../tests/test_sso.py) |

### 2.1 Validação do token

O servidor não confia em nada que o navegador mande além do token, e o token precisa:

- ter a assinatura de uma chave do realm. As chaves são baixadas em `<KEYCLOAK_INTERNAL_URL ou KEYCLOAK_HOST>/realms/<KEYCLOAK_REALM>/protocol/openid-connect/certs`;
- ter o emissor (`iss`) igual a `<KEYCLOAK_HOST>/realms/<KEYCLOAK_REALM>`;
- ter sido emitido para o client `KEYCLOAK_CLIENT_ID` (`azp`);
- estar dentro da validade (`exp`).

E-mail, nome e papéis são lidos do token validado. Um token inválido ou vencido recebe 400. Um e-mail fora da lista recebe 403.

| Variável | Para que serve | Valor no docker-compose |
| --- | --- | --- |
| `KEYCLOAK_HOST` | Endereço público do Keycloak; define o emissor esperado | `https://keycloak-propostas.docker.localhost/` |
| `KEYCLOAK_INTERNAL_URL` | Endereço do Keycloak dentro da rede do Docker, usado para baixar as chaves. Se ficar em branco, usa `KEYCLOAK_HOST` | `http://propostas-keycloak:8080/` |
| `KEYCLOAK_REALM` / `KEYCLOAK_CLIENT_ID` | Realm e client do sistema | `commercialproposal` / `commercialproposal` |
| `DEBUG` | Ligado, também libera o admin local (`local-admin@mail.com`) | `true` (no k8s: `false`) |

Em outro ambiente (produção), `KEYCLOAK_HOST` precisa ser exatamente o endereço que aparece no `iss` dos tokens, e `KEYCLOAK_INTERNAL_URL` precisa ser alcançável pelo container.

### 2.2 Sessões já abertas

O `EmailPermitidoMiddleware` confere, a cada requisição, o e-mail de quem entrou pelo Keycloak. Se o e-mail não estiver mais na lista (por exemplo, depois de um deploy que tirou alguém), a sessão é encerrada e a resposta é 403. A conferência vale para as contas do login corporativo, que não têm senha no Django. O superusuário local, que entra com senha pelo `/admin/`, não passa por ela.

### 2.3 Conta do usuário

A conta do Django é encontrada pelo **e-mail**. Uma conta nova recebe o nome exibido como `username`. Se esse nome já pertencer a outra pessoa, o `username` passa a ser o próprio e-mail. Assim, pessoas com o mesmo nome não dividem a mesma conta.

## 3. Keycloak

O realm `commercialproposal` está com **auto-cadastro desligado** (`registrationAllowed: false`) e **sem provedor externo** (sem login Microsoft/Google). Por isso, os usuários são criados por um administrador no console do Keycloak, com e-mail e nome preenchidos. Ter usuário no Keycloak **não basta**: o e-mail também precisa estar em `EMAILS_PERMITIDOS`.

## 4. Grupos e papéis

### 4.1 Grupo definido no login

O token traz os papéis do client `account` (`resource_access.account.roles`). O sistema aproveita só os que tiverem o nome de um destes grupos: `Admin`, `Master`, `Tech`, `Limited` e `Missing`. Maiúsculas e minúsculas não importam.

- **Se nenhum papel bater, o usuário entra como `Master`.** Os papéis padrão do Keycloak (`manage-account`, `view-profile`) não batem. Então, na prática, todo usuário novo é Master.
- **Os grupos são substituídos a cada login.** Um grupo dado à mão em *Administração* ou no `/admin/` do Django some no próximo login. Para mudar o papel de alguém de forma duradoura, atribua o papel no Keycloak.

### 4.2 Empresas visíveis

Um `AcessoEmpresa` liga um **grupo** a uma **empresa** com um papel. As telas são editadas em *Administração → Empresas / Acessos às empresas*.

- O grupo `Admin` e os superusuários veem **todas** as empresas ativas, como Admin.
- Na criação, cada empresa recebe acesso dos grupos `Master`, `Tech` e `Limited`, cada um com o papel de mesmo nome. Isso é feito por `empresas_padrao.configurar` (comando `configurar_empresas`, que roda no entrypoint). Somado ao padrão `Master` do item 4.1, **os e-mails liberados viram Master em todas as empresas**, a não ser que receba outro papel no Keycloak.
- Quem não tem nenhum acesso consegue entrar, mas vê só o aviso "sem acesso a nenhuma empresa".

Para restringir uma empresa a um time: crie um grupo próprio (ex.: `vendas-analytics`), dê a ele o papel desejado na empresa e remova da empresa os acessos dos grupos genéricos. Lembre do item 4.1: o vínculo do usuário a esse grupo próprio é apagado no próximo login, enquanto os grupos vierem só do token.

### 4.3 O que cada papel pode fazer

Veja a tabela de papéis na seção 1 do [README](../README.md#1-acesso).

## 5. Pontos ainda em aberto

- **Master por padrão:** um padrão mais seguro seria `Limited` ou `Missing` (sem acesso), com a promoção feita de forma explícita.
- **Grupos sobrescritos no login:** veja o item 4.1.
- **Dependência:** a validação usa `pyjwt` com `cryptography`, declarados no `pyproject.toml` como `pyjwt[crypto]`.

## 6. Deploy no Kubernetes

### 6.1 De onde o sistema lê a configuração

A lista de e-mails vai **dentro da imagem**, porque está no código: não há nada a configurar no cluster para ela. Para mudar a lista, é preciso gerar uma imagem nova (`make build` e push) e atualizar o Deployment.

As demais configurações (`KEYCLOAK_*`, `DEBUG`, banco) são lidas **só das variáveis de ambiente do processo** (`os.environ`). Nenhum código lê o arquivo `.env`:

- no `docker compose`, quem transforma o `.env` em variáveis de ambiente é o próprio compose (`env_file: .env`);
- no Kubernetes, isso **não acontece**: o `.env` não vai para a imagem.

Portanto, no cluster, essas variáveis precisam estar declaradas no Deployment, no ConfigMap e no Secret abaixo.

### 6.2 Manifestos e comandos

Os manifestos ficam em [k8s/commercialproposal.yaml](../k8s/commercialproposal.yaml). O pod recebe a configuração de duas fontes, nesta ordem (numa chave repetida, vale a última):

| Fonte | O que tem | Quem cria |
| --- | --- | --- |
| ConfigMap `commercialproposal-config` | Endereços e opções sem segredo: `HOST`, `DEBUG=false`, `KEYCLOAK_*`, banco, SharePoint (sem o segredo) | O próprio `k8s/commercialproposal.yaml` |
| Secret `commercialproposal-segredos` | `SHAREPOINT_CLIENT_SECRET`, `DJANGO_DATABASE_PASSWORD`, `DJANGO_SUPERUSER_*` | Você, à mão, fora do repositório (veja abaixo) |

Os valores marcados com `AJUSTAR` no manifesto (endereço do sistema, do Keycloak e do banco) dependem do cluster e precisam ser revistos antes do primeiro deploy.

Para aplicar: `make k8s-deploy K8S_NAMESPACE=<namespace>` (o padrão é `default`). O comando aplica `k8s/commercialproposal.yaml`: ConfigMap, Deployment e Service.

**Mantenha `DEBUG: "false"` no ConfigMap.** Com `DEBUG` ligado, o admin local passaria a entrar no deploy, e o Django mostraria páginas de erro com detalhes internos.

Criar o Secret, uma vez, com os valores reais:

```bash
kubectl -n <namespace> create secret generic commercialproposal-segredos \
  --from-literal=SHAREPOINT_CLIENT_SECRET='...' \
  --from-literal=DJANGO_DATABASE_PASSWORD='...' \
  --from-literal=DJANGO_SUPERUSER_USERNAME='admin' \
  --from-literal=DJANGO_SUPERUSER_EMAIL='admin@estatcamp.com.br' \
  --from-literal=DJANGO_SUPERUSER_PASSWORD='...'
```

O Ingress (ou a IngressRoute do Traefik) com o domínio e o TLS não está no manifesto, porque depende do domínio de cada ambiente. Siga o mesmo padrão das outras aplicações do cluster.

Sobre os endereços do Keycloak:

- **`KEYCLOAK_HOST`** precisa ser o endereço público que o navegador usa para fazer login e que aparece no campo `iss` dos tokens, por exemplo `https://keycloak.estatcamp.com.br/realms/commercialproposal`. A barra no final não faz diferença. Se o endereço não bater, todo login recebe 400 ("Login inválido ou expirado").
- **`KEYCLOAK_INTERNAL_URL`** é opcional. Ele serve para o pod baixar as chaves pelo Service interno do Keycloak, sem sair do cluster. Se o Keycloak estiver em outro cluster ou fora dele, deixe em branco: o pod vai usar o `KEYCLOAK_HOST` e precisa conseguir acessar esse endereço por HTTPS. Se o pod não alcançar o Keycloak, o login responde 400 com "Não foi possível falar com o Keycloak".

### 6.3 Mudar a lista de e-mails

1. Edite `EMAILS_PERMITIDOS` em [src/proposal/sso.py](../src/proposal/sso.py) e o teste correspondente.
2. Gere e publique a imagem: `make build` e o push para o registry.
3. Recrie os pods para baixar a imagem nova: `kubectl -n <namespace> rollout restart deployment/commercialproposal`. O manifesto usa `imagePullPolicy: Always`.

Depois do restart, o login já usa a lista nova. Quem saiu da lista perde a sessão na próxima página que abrir. As sessões ficam no banco e continuam válidas depois do restart, mas o middleware confere o e-mail a cada requisição.

### 6.4 Cuidados

- **Não coloque o `.env` na imagem.** O [Dockerfile](../Dockerfile) não copia mais o `.env`: segredos dentro da imagem podem ser lidos por qualquer pessoa com acesso ao registry. Passe tudo por ConfigMap e Secret.
- **`DJANGO_SUPERUSER_*`:** o superusuário do Django entra sem passar pela lista. No cluster, use uma senha forte (pelo Secret), não a `estatcamp` do docker-compose.
- **Primeiro deploy desta versão:** revise os `AJUSTAR` do manifesto, principalmente o `KEYCLOAK_HOST`. Se ele estiver errado, ninguém consegue entrar.

## 7. Histórico

Até 26/10/2026, o `/auth/complete/` lia o e-mail, o nome e os grupos de cookies gravados pelo JavaScript, sem validar o token. Quem montasse esses cookies entrava sem passar pelo Keycloak, até como Admin. A única barreira era o primeiro pedaço do domínio do e-mail (`ALLOWED_USER_DOMAINS=estatcamp,admin,mail`), que aceitava também `x@estatcamp.qualquercoisa.io`. A variável `ALLOWED_USER_EMAILS` já existia no `.env`, mas não era lida por nenhum código. A validação do token e a lista de e-mails fixa no código (`EMAILS_PERMITIDOS`) substituíram esse esquema. `ALLOWED_USER_DOMAINS` e `ALLOWED_USER_EMAILS` deixaram de existir.
