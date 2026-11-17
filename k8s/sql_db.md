# Banco do Keycloak (Akamai Managed PostgreSQL)

Como acessar o banco e restaurar o dump `keycloak.dump` no Keycloak que roda no LKE.

- Dump: `keycloak.dump`, formato custom do PostgreSQL, gerado pelo **Keycloak 21.1.2**.
  Só pode ser usado com a imagem `quay.io/keycloak/keycloak:21.1`.
- Os dados de conexão (host, porta, senha) ficam em Cloud Manager → Databases → Connection Details.
- O IP da sua máquina precisa estar liberado em Cloud Manager → Databases → Manage Access.

---

## 1. Preparar a sessão do terminal

Substitua `<HOST>` pelo host do banco. A senha é pedida no terminal e não fica no histórico.

```bash
DB="host=<HOST> port=23159 user=akmadmin sslmode=require"
read -s "PGPASSWORD?Senha do akmadmin: "; export PGPASSWORD

echo "$DB"                                   # confira: tem que começar com "host="
psql "$DB dbname=defaultdb" -c "select 1;"   # teste de conexão
```

> `read -s "VAR?texto"` é sintaxe do **zsh**. No bash use: `read -s -p "Senha: " PGPASSWORD; export PGPASSWORD`

Para abrir um console interativo:

```bash
psql "$DB dbname=defaultdb"   # banco administrativo
psql "$DB dbname=keycloak"    # banco do Keycloak
```

---

## 2. Restaurar o dump

**Nunca** restaure direto no banco `keycloak`. Quando o banco está vazio, qualquer Keycloak conectado
cria as tabelas na mesma hora. Aí o `pg_restore` falha com centenas de erros `already exists` e só sobra o realm `master`.

Restaure num banco temporário (`keycloak_new`), confira e troque os nomes no fim.

> **Pela tela do assistente:** *Manutenção → Banco do Keycloak* faz este guia inteiro sem terminal: conexão (seção 1,
> configurável na própria tela), restaurar com upload (seção 2), quem está conectado (seção 3), senha de admin direto
> no banco (seção 4.3) e gerar dump para baixar (seção 5). Na restauração, a tela:
> restaura em `keycloak_new`, mostra `migration_model`, realms e admins do master, e só troca depois que você
> digita o nome do banco. O banco anterior não é apagado: vira `keycloak_antes_<data>` (bloqueado para conexões).
> No Kubernetes o assistente reinicia o Keycloak sozinho; no compose, rode `docker compose restart keycloak`.
> Precisa das variáveis `KEYCLOAK_DB_*` no assistente. Para o Akamai:
> `KEYCLOAK_DB_HOST=<HOST> KEYCLOAK_DB_PORT=23159 KEYCLOAK_DB_USER=akmadmin KEYCLOAK_DB_ADMIN_DB=defaultdb KEYCLOAK_DB_SSLMODE=require`.

### 2.1 Restaurar no banco temporário

```bash
psql "$DB dbname=defaultdb" -c "DROP DATABASE IF EXISTS keycloak_new;"
psql "$DB dbname=defaultdb" -c "CREATE DATABASE keycloak_new;"

pg_restore -d "$DB dbname=keycloak_new" --no-owner --no-privileges \
  /home/hiro/Documentos/Github/Hiro/keycloak/keycloak.dump 2>&1 | tee restore.log

grep "error:" restore.log
```

- `--no-owner --no-privileges` são obrigatórias, porque os roles do banco de origem não existem na Akamai.
- Um erro sobre `transaction_timeout` pode ser ignorado: o `pg_restore` 17+ envia essa configuração e um servidor ≤ 16 não a conhece.
  Qualquer outro erro precisa ser investigado antes de continuar.

### 2.2 Conferir

```bash
psql "$DB dbname=keycloak_new" -c "select id, version from migration_model;"
psql "$DB dbname=keycloak_new" -c "select name from realm;"
```

Esperado:
- `migration_model`: **uma linha só** (`pvkxv | 21.1.2`). Duas linhas indicam que um Keycloak criou tabelas antes do restore.
- `realm`: `master` e os realms da aplicação.

### 2.3 Trocar os bancos

O Keycloak fica fora do ar por alguns segundos.

```bash
kubectl scale deploy/keycloak --replicas=0
kubectl wait --for=delete pod -l application=keycloak --timeout=120s

psql "$DB dbname=defaultdb" -c "DROP DATABASE IF EXISTS keycloak WITH (FORCE);"
psql "$DB dbname=defaultdb" -c "ALTER DATABASE keycloak_new RENAME TO keycloak;"

kubectl scale deploy/keycloak --replicas=1
kubectl rollout status deploy/keycloak
```

### 2.4 Validar

```bash
psql "$DB dbname=keycloak" -c "select id, version from migration_model;"   # continua 1 linha
kubectl logs deploy/keycloak | tail -5
```

No log, `KC-SERVICES0010: Failed to add user 'admin' ... user with username exists` é normal.
O admin vem do dump, então a senha de login é a do ambiente antigo, não a do `KEYCLOAK_ADMIN_PASSWORD`.

---

## 3. Problemas comuns

| Sintoma | Causa | Solução |
|---|---|---|
| `faltando "=" após "host..."` | `$DB` mal definido (marcador não substituído) | Refaça o passo 1 e confira com `echo "$DB"` |
| `multiple primary keys` / `already exists` no restore | O banco já tinha tabelas | Restaure num banco novo e vazio (seção 2) |
| `migration_model` com 2 linhas | Um Keycloak conectou antes do restore | Descubra quem conecta (abaixo) e refaça a seção 2 |
| `role "..." does not exist` | Faltou `--no-owner --no-privileges` | Rode o restore com essas opções |
| `psql` não conecta / timeout | IP não liberado | Libere o IP em Manage Access |

Para ver quem está conectado ao banco:

```bash
psql "$DB dbname=defaultdb" -c "select client_addr, application_name, backend_start from pg_stat_activity where datname='keycloak';"
kubectl get pods -A -o wide | grep -i keycloak
```

---

## 4. Trocar a senha de um admin

Os admins do console são os usuários do realm **master** (ex.: `estatcamp`).
No banco restaurado do dump **não existe** usuário `admin`. O `KEYCLOAK_ADMIN` do deploy só cria esse usuário
quando o realm `master` está vazio, e por isso o log mostra `Failed to add user 'admin'`.

### 4.1 Pelo console (sabendo a senha de algum admin)

1. Entre em `https://keycloak.actionstat.app/admin`.
2. Selecione o realm **master** (canto superior esquerdo).
3. Vá em **Users**, escolha o usuário e abra **Credentials** → **Reset password**.
4. Digite a nova senha e desmarque **Temporary**.

### 4.2 Pelo terminal, dentro do pod (sabendo a senha de algum admin)

```bash
kubectl exec -it deploy/keycloak -- bash
cd /opt/keycloak/bin
./kcadm.sh config credentials --server http://localhost:8080 --realm master --user estatcamp   # pede a senha atual
./kcadm.sh set-password -r master --username estatcamp --new-password 'NovaSenha'
```

### 4.3 Direto no banco (sem saber nenhuma senha)

Grava um novo hash no formato do Keycloak 21: `pbkdf2-sha256`, 27500 iterações, chave de 32 bytes e salt de 16 bytes.
Requer a sessão do passo 1 (`$DB` e `PGPASSWORD`) e o `python3`.

```bash
USUARIO=estatcamp
read -s "NOVA?Nova senha para $USUARIO: "; echo

SECRET=$(NOVA="$NOVA" python3 -I -c '
import os, hashlib, base64, json
salt = os.urandom(16)
dk = hashlib.pbkdf2_hmac("sha256", os.environ["NOVA"].encode(), salt, 27500, 32)
print(json.dumps({"value": base64.b64encode(dk).decode(), "salt": base64.b64encode(salt).decode(), "additionalParameters": {}}, separators=(",", ":")))
')
unset NOVA

psql "$DB dbname=keycloak" -v ON_ERROR_STOP=1 -v secret="$SECRET" -v usuario="$USUARIO" <<'SQL'
UPDATE credential c
   SET secret_data = :'secret',
       credential_data = '{"hashIterations":27500,"algorithm":"pbkdf2-sha256","additionalParameters":{}}',
       created_date = (extract(epoch from now()) * 1000)::bigint
  FROM user_entity u JOIN realm r ON r.id = u.realm_id
 WHERE c.user_id = u.id AND c.type = 'password'
   AND r.name = 'master' AND u.username = :'usuario';
SQL
```

- A saída deve ser `UPDATE 1`. `UPDATE 0` significa que o usuário não existe no `master` ou não tem senha cadastrada.
- Depois, reinicie **todos** os Keycloaks que usam esse banco, para limpar o cache: `kubectl rollout restart deploy/keycloak`.
  Sem o reinício, a senha antiga ainda pode valer por um tempo.
- Para ver os admins disponíveis:

  ```bash
  psql "$DB dbname=keycloak" -c "select u.username from user_entity u join realm r on r.id=u.realm_id where r.name='master';"
  ```

---

## 5. Gerar um novo dump

```bash
pg_dump -d "$DB dbname=keycloak" -Fc --no-owner --no-privileges -f keycloak-$(date +%F).dump
```

`*.dump` está no `.gitignore`. Não faça commit de dumps.
