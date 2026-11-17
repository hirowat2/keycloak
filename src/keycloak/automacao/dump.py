"""Restaurar um dump do banco do Keycloak (k8s/sql_db.md, seção 2), pelo assistente.

O fluxo nunca restaura direto no banco em uso: um Keycloak conectado a um banco vazio cria
as tabelas na hora e o ``pg_restore`` falha com ``already exists``. Então:

1. restaura num banco temporário (``<banco>_new``) e confere ``migration_model`` e realms;
2. troca os nomes: o banco atual vira ``<banco>_antes_<data>`` (cópia de segurança, sem
   conexões) e o temporário assume o nome do banco do Keycloak;
3. reinicia o Keycloak, para ele largar o cache com os dados antigos.

A conexão vem de ``KEYCLOAK_DB_*`` e precisa poder criar, renomear e apagar bancos
(no Akamai Managed PostgreSQL, o ``akmadmin``; no compose, o usuário do keycloak-db).
"""

import json
import re
import ssl
import subprocess
import urllib.request
from contextlib import contextmanager
import base64
import hashlib
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from os import environ
from pathlib import Path

import psycopg2
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from psycopg2 import sql

SUFIXO_TEMPORARIO = "_new"
SUFIXO_COPIA = "_antes_"
# pg_restore 17+ envia "SET transaction_timeout", que um servidor <= 16 não conhece: inofensivo.
ERROS_IGNORADOS = ("transaction_timeout",)
CHAVE_SESSAO = "banco_keycloak"
CONTA_K8S = Path("/var/run/secrets/kubernetes.io/serviceaccount")


class ErroDump(Exception):
    pass


@dataclass
class Banco:
    host: str
    porta: str
    usuario: str
    senha: str
    nome: str
    administrativo: str
    sslmode: str

    @classmethod
    def da_sessao(cls, sessao) -> "Banco | None":
        """A conexão escolhida na tela (guardada na sessão, com a senha cifrada) ou, sem ela, a do ambiente."""
        salvo = sessao.get(CHAVE_SESSAO)
        if salvo:
            try:
                return cls(**{**salvo, "senha": _cifra().decrypt(salvo["senha"].encode()).decode()})
            except (InvalidToken, TypeError, KeyError):
                sessao.pop(CHAVE_SESSAO, None)
        return cls.do_ambiente()

    def guardar(self, sessao) -> None:
        sessao[CHAVE_SESSAO] = {**asdict(self), "senha": _cifra().encrypt(self.senha.encode()).decode()}

    @staticmethod
    def esquecer(sessao) -> None:
        sessao.pop(CHAVE_SESSAO, None)

    @classmethod
    def do_ambiente(cls) -> "Banco | None":
        if not environ.get("KEYCLOAK_DB_HOST"):
            return None
        return cls(
            host=environ["KEYCLOAK_DB_HOST"],
            porta=environ.get("KEYCLOAK_DB_PORT", "5432"),
            usuario=environ.get("KEYCLOAK_DB_USER", ""),
            senha=environ.get("KEYCLOAK_DB_PASSWORD", ""),
            nome=environ.get("KEYCLOAK_DB_NAME", "keycloak"),
            # Banco usado para criar/renomear os outros (Akamai: defaultdb)
            administrativo=environ.get("KEYCLOAK_DB_ADMIN_DB", "postgres"),
            sslmode=environ.get("KEYCLOAK_DB_SSLMODE", "prefer"),
        )

    @property
    def temporario(self) -> str:
        return f"{self.nome}{SUFIXO_TEMPORARIO}"

    @property
    def descricao(self) -> str:
        return f"{self.usuario}@{self.host}:{self.porta}/{self.nome}"

    @contextmanager
    def cursor(self, banco: str | None = None):
        """Cursor em autocommit (CREATE/DROP/ALTER DATABASE não rodam em transação); fecha a conexão no fim."""
        conexao = self._conectar(banco)
        try:
            with conexao.cursor() as cursor:
                yield cursor
        finally:
            conexao.close()

    def _conectar(self, banco: str | None):
        try:
            conexao = psycopg2.connect(
                host=self.host, port=self.porta, user=self.usuario, password=self.senha,
                dbname=banco or self.administrativo, sslmode=self.sslmode, connect_timeout=10,
                application_name="keycloak-assistente",
            )
        except psycopg2.OperationalError as erro:
            raise ErroDump(f"Sem conexão com o banco {self.host}:{self.porta}: {str(erro).strip()}") from erro
        conexao.autocommit = True
        return conexao

    def ambiente_pg(self) -> dict[str, str]:
        """Variáveis do libpq para o pg_restore (a senha não aparece na linha de comando)."""
        return {
            **environ, "PGHOST": self.host, "PGPORT": self.porta, "PGUSER": self.usuario, "PGPASSWORD": self.senha,
            "PGSSLMODE": self.sslmode, "PGAPPNAME": "keycloak-assistente", "PGCONNECT_TIMEOUT": "10",
        }


@dataclass
class Arquivo:
    """O que o ``pg_restore --list`` diz do dump, antes de restaurar."""

    cabecalho: dict[str, str]
    objetos: int
    tem_keycloak: bool


@dataclass
class Conferencia:
    """Estado do banco restaurado: as mesmas consultas da seção 2.2 do sql_db.md."""

    banco: str
    migracoes: list[tuple[str, str]] = field(default_factory=list)
    realms: list[str] = field(default_factory=list)
    usuarios: int = 0
    admins_master: list[str] = field(default_factory=list)

    @property
    def versao(self) -> str:
        return self.migracoes[-1][1] if self.migracoes else ""

    @property
    def problemas(self) -> list[str]:
        problemas = []
        if not self.migracoes:
            problemas.append("Não há migration_model: isto não parece um banco do Keycloak.")
        if "master" not in self.realms:
            problemas.append("Falta o realm master.")
        return problemas

    @property
    def avisos(self) -> list[str]:
        # Uma linha por versão por que o banco passou: várias é normal num Keycloak atualizado (21 → 26).
        # Contaminação (um Keycloak criou as tabelas antes do restore) aparece como erros "already exists".
        if len(self.migracoes) > 1:
            versoes = " → ".join(v for _, v in self.migracoes)
            return [f"migration_model tem {len(self.migracoes)} linhas ({versoes}). Normal se este Keycloak já foi "
                    "atualizado; se o pg_restore relatou \"already exists\", um Keycloak criou tabelas antes: restaure de novo."]
        return []


def versao_numerica(versao: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", versao)[:3])


def listar(caminho: str) -> Arquivo:
    """Confere o formato do arquivo sem tocar em banco nenhum."""
    resultado = _rodar(["pg_restore", "--list", caminho])
    if resultado.returncode != 0:
        raise ErroDump(f"O arquivo não é um dump válido do PostgreSQL (formato custom, pg_dump -Fc): {resultado.stderr.strip()}")
    cabecalho, objetos = {}, 0
    for linha in resultado.stdout.splitlines():
        if linha.startswith(";"):
            texto = linha[1:].strip()
            # "; Archive created at 2026-11-12 20:49:36 -03" é o único sem "chave: valor"
            if texto.startswith("Archive created at "):
                cabecalho["Archive created at"] = texto.removeprefix("Archive created at ")
            elif ": " in texto:
                chave, _, valor = texto.partition(": ")
                cabecalho[chave.strip()] = valor.strip()
        elif linha.strip():
            objetos += 1
    tem_keycloak = re.search(r"\bTABLE( DATA)? \S+ migration_model\b", resultado.stdout) is not None
    return Arquivo(cabecalho, objetos, tem_keycloak)


def erros_relevantes(saida: str) -> list[str]:
    """Linhas de erro do pg_restore, sem as inofensivas."""
    return [
        linha.strip() for linha in saida.splitlines()
        if "error:" in linha.lower() and not any(i in linha for i in ERROS_IGNORADOS)
    ]


def restaurar_temporario(banco: Banco, caminho: str) -> list[str]:
    """Recria ``<banco>_new`` vazio e restaura o dump nele. Devolve os erros que importam."""
    with banco.cursor() as cursor:
        cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(banco.temporario)))
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(banco.temporario)))
    resultado = _rodar(
        ["pg_restore", "--no-owner", "--no-privileges", "--dbname", banco.temporario, caminho],
        env=banco.ambiente_pg(), timeout=1800,
    )
    return erros_relevantes(resultado.stderr)


def existe(banco: Banco, nome: str) -> bool:
    with banco.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", [nome])
        return cursor.fetchone() is not None


def copias(banco: Banco) -> list[str]:
    """Bancos ``<banco>_antes_*`` deixados pelas trocas anteriores (mais novo primeiro)."""
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT datname FROM pg_database WHERE starts_with(datname, %s) ORDER BY datname DESC",
            [f"{banco.nome}{SUFIXO_COPIA}"],
        )
        return [linha[0] for linha in cursor.fetchall()]


def conferir(banco: Banco, nome: str) -> Conferencia:
    conferencia = Conferencia(nome)
    with banco.cursor(nome) as cursor:
        cursor.execute("SELECT to_regclass('migration_model') IS NOT NULL")
        if not cursor.fetchone()[0]:
            return conferencia
        cursor.execute("SELECT id, version FROM migration_model ORDER BY update_time")
        conferencia.migracoes = [(str(i), str(v)) for i, v in cursor.fetchall()]
        cursor.execute("SELECT name FROM realm ORDER BY name <> 'master', name")
        conferencia.realms = [linha[0] for linha in cursor.fetchall()]
        cursor.execute("SELECT count(*) FROM user_entity WHERE service_account_client_link IS NULL")
        conferencia.usuarios = cursor.fetchone()[0]
        cursor.execute(
            "SELECT u.username FROM user_entity u JOIN realm r ON r.id = u.realm_id "
            "WHERE r.name = 'master' AND u.service_account_client_link IS NULL ORDER BY u.username"
        )
        conferencia.admins_master = [linha[0] for linha in cursor.fetchall()]
    return conferencia


def trocar(banco: Banco) -> str:
    """O temporário assume o nome do banco do Keycloak; o atual vira cópia. Devolve o nome da cópia.

    ``ALLOW_CONNECTIONS false`` antes de derrubar as conexões impede que o Keycloak reconecte
    no meio da troca. Ele volta a conectar sozinho quando o banco novo assume o nome.
    """
    copia = f"{banco.nome}{SUFIXO_COPIA}{datetime.now():%Y%m%d_%H%M%S}"
    nome, temporario = sql.Identifier(banco.nome), sql.Identifier(banco.temporario)
    with banco.cursor() as cursor:
        cursor.execute("SELECT datname FROM pg_database WHERE datname IN (%s, %s)", [banco.nome, banco.temporario])
        existentes = {linha[0] for linha in cursor.fetchall()}
        if banco.temporario not in existentes:
            raise ErroDump(f"Não há banco {banco.temporario}: envie o dump de novo.")
        if banco.nome in existentes:
            cursor.execute(sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS false").format(nome))
            _derrubar_conexoes(cursor, banco.nome)
            cursor.execute(sql.SQL("ALTER DATABASE {} RENAME TO {}").format(nome, sql.Identifier(copia)))
        _derrubar_conexoes(cursor, banco.temporario)
        cursor.execute(sql.SQL("ALTER DATABASE {} RENAME TO {}").format(temporario, nome))
    return copia if banco.nome in existentes else ""


def descartar_temporario(banco: Banco) -> None:
    with banco.cursor() as cursor:
        cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(banco.temporario)))


def _derrubar_conexoes(cursor, nome: str) -> None:
    cursor.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()", [nome]
    )


def _rodar(comando: list[str], timeout: int = 120, **kwargs) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(comando, capture_output=True, text=True, timeout=timeout, check=False, **kwargs)
    except FileNotFoundError as erro:
        raise ErroDump(f"{comando[0]} não está instalado no assistente (pacote postgresql-client).") from erro
    except subprocess.TimeoutExpired as erro:
        raise ErroDump(f"{comando[0]} passou de {timeout} s e foi interrompido.") from erro


def _cifra() -> Fernet:
    """A senha do banco fica na sessão cifrada com uma chave derivada da SECRET_KEY."""
    chave = hashlib.sha256(f"banco-keycloak:{settings.SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(chave))


# --- Diagnóstico (sql_db.md, seções 1 e 3) ---------------------------------------------------------


def testar(banco: Banco) -> dict:
    """``select 1`` no banco administrativo, mais a versão do servidor e os bancos que existem."""
    with banco.cursor() as cursor:
        cursor.execute("SHOW server_version")
        versao = cursor.fetchone()[0]
        cursor.execute(
            "SELECT datname, pg_size_pretty(pg_database_size(datname)), datallowconn FROM pg_database "
            "WHERE NOT datistemplate ORDER BY datname"
        )
        bancos = [{"nome": n, "tamanho": t, "aceita": a} for n, t, a in cursor.fetchall()]
    return {"versao": versao.split(" ")[0], "bancos": bancos}


def conexoes(banco: Banco) -> list[dict]:
    """Quem está conectado no banco do Keycloak e no temporário (descobrir quem cria tabelas antes do restore)."""
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT datname, host(client_addr), application_name, usename, state, backend_start "
            "FROM pg_stat_activity WHERE datname IN (%s, %s) AND pid <> pg_backend_pid() ORDER BY datname, backend_start",
            [banco.nome, banco.temporario],
        )
        campos = ["banco", "origem", "aplicacao", "usuario", "estado", "desde"]
        return [dict(zip(campos, linha)) for linha in cursor.fetchall()]


# --- Senha de admin direto no banco (sql_db.md, seção 4.3) ----------------------------------------

ITERACOES_PBKDF2 = 27500


def hash_senha(senha: str) -> tuple[str, str]:
    """``secret_data`` e ``credential_data`` no formato pbkdf2-sha256 do Keycloak (21 e 26 leem)."""
    sal = os.urandom(16)
    chave = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, ITERACOES_PBKDF2, 32)
    secreto = {"value": base64.b64encode(chave).decode(), "salt": base64.b64encode(sal).decode(), "additionalParameters": {}}
    dados = {"hashIterations": ITERACOES_PBKDF2, "algorithm": "pbkdf2-sha256", "additionalParameters": {}}
    return json.dumps(secreto, separators=(",", ":")), json.dumps(dados, separators=(",", ":"))


def trocar_senha(banco: Banco, usuario: str, senha: str, realm: str = "master") -> int:
    """Grava a senha nova do usuário. Devolve quantas credenciais mudaram (0 = usuário sem senha ou inexistente)."""
    secreto, dados = hash_senha(senha)
    with banco.cursor(banco.nome) as cursor:
        cursor.execute(
            "UPDATE credential c SET secret_data = %s, credential_data = %s, "
            "created_date = (extract(epoch from now()) * 1000)::bigint "
            "FROM user_entity u JOIN realm r ON r.id = u.realm_id "
            "WHERE c.user_id = u.id AND c.type = 'password' AND r.name = %s AND u.username = %s",
            [secreto, dados, realm, usuario],
        )
        return cursor.rowcount


def usuarios_com_senha(banco: Banco, realm: str = "master") -> list[str]:
    with banco.cursor(banco.nome) as cursor:
        cursor.execute(
            "SELECT u.username FROM user_entity u JOIN realm r ON r.id = u.realm_id "
            "WHERE r.name = %s AND EXISTS (SELECT 1 FROM credential c WHERE c.user_id = u.id AND c.type = 'password') "
            "ORDER BY u.username",
            [realm],
        )
        return [linha[0] for linha in cursor.fetchall()]


# --- Gerar dump (sql_db.md, seção 5) --------------------------------------------------------------


def gerar_dump(banco: Banco):
    """``pg_dump -Fc`` do banco do Keycloak num arquivo temporário; devolve o arquivo aberto (já sem nome no disco)."""
    descritor, caminho = tempfile.mkstemp(prefix="keycloak-", suffix=".dump")
    os.close(descritor)
    try:
        resultado = _rodar(
            ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--dbname", banco.nome, "--file", caminho],
            env=banco.ambiente_pg(), timeout=1800,
        )
        if resultado.returncode != 0:
            raise ErroDump(f"pg_dump falhou: {resultado.stderr.strip()}")
        return open(caminho, "rb")  # noqa: SIM115 - o FileResponse fecha
    finally:
        os.unlink(caminho)


# --- Reiniciar o Keycloak --------------------------------------------------------------------------


def comando_reiniciar() -> str:
    """O que rodar à mão quando o assistente não pode reiniciar o Keycloak sozinho."""
    if CONTA_K8S.exists():
        return f"kubectl -n {_namespace()} rollout restart deploy/{_deployment()}"
    return "docker compose restart keycloak"


def pode_reiniciar() -> bool:
    return (CONTA_K8S / "token").exists() and bool(environ.get("KUBERNETES_SERVICE_HOST"))


def reiniciar_keycloak() -> None:
    """O mesmo que ``kubectl rollout restart``: muda uma anotação do template do Deployment.

    Precisa da Role ``assistente-reinicia-keycloak`` (k8s/assistente.yaml).
    """
    if not pode_reiniciar():
        raise ErroDump(f"O assistente não roda no Kubernetes; reinicie à mão: {comando_reiniciar()}")
    url = (
        f"https://{environ['KUBERNETES_SERVICE_HOST']}:{environ.get('KUBERNETES_SERVICE_PORT', '443')}"
        f"/apis/apps/v1/namespaces/{_namespace()}/deployments/{_deployment()}"
    )
    corpo = {"spec": {"template": {"metadata": {"annotations": {"kubectl.kubernetes.io/restartedAt": datetime.now().astimezone().isoformat()}}}}}
    pedido = urllib.request.Request(
        url, data=json.dumps(corpo).encode(), method="PATCH",
        headers={
            "Authorization": f"Bearer {(CONTA_K8S / 'token').read_text().strip()}",
            "Content-Type": "application/strategic-merge-patch+json",
        },
    )
    contexto = ssl.create_default_context(cafile=str(CONTA_K8S / "ca.crt"))
    try:
        with urllib.request.urlopen(pedido, context=contexto, timeout=15):
            pass
    except OSError as erro:
        raise ErroDump(f"O Kubernetes recusou o reinício ({erro}); reinicie à mão: {comando_reiniciar()}") from erro


def _namespace() -> str:
    arquivo = CONTA_K8S / "namespace"
    return arquivo.read_text().strip() if arquivo.exists() else "keycloak"


def _deployment() -> str:
    return environ.get("KEYCLOAK_DEPLOYMENT", "keycloak")
