psql "host=a491511-akamai-prod-1361668-default.g2a.akamaidb.net \
  port=23159 \
  dbname=defaultdb \
  user=akmadmin \
  sslmode=require"


CREATE DATABASE keycloak;
DROP DATABASE keycloak;

# 0. Senha só nesta sessão do terminal (não fica salva no histórico de comandos)
read -s "PGPASSWORD?Senha do akmadmin: "; export PGPASSWORD
DB="hostescrever o host port=23159 user=akmadmin sslmode=require"


# 1. Parar o Keycloak, para ele não usar o banco durante a restauração
kubectl scale deploy/keycloak --replicas=0

# 2. Recriar o banco vazio (conectando no defaultdb)
psql "$DB dbname=defaultdb" -c "DROP DATABASE IF EXISTS keycloak WITH (FORCE);"
psql "$DB dbname=defaultdb" -c "CREATE DATABASE keycloak;"

# 3. Restaurar o dump
pg_restore -d "$DB dbname=keycloak" --no-owner --no-privileges -j 4 -v \
  /home/hiro/Documentos/Github/Hiro/keycloak/keycloak.dump

# 4. Conferir e subir o Keycloak de novo
psql "$DB dbname=keycloak" -c "select version from migration_model;"   # deve mostrar 21.1.2
kubectl scale deploy/keycloak --replicas=1
kubectl rollout status deploy/keycloak
