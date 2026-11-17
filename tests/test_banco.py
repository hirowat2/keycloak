"""Tela "Banco do Keycloak": conexão, restauração, senha e dump, com o PostgreSQL simulado."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from keycloak.automacao import dump
from keycloak.models import Aplicacao

pytestmark = pytest.mark.django_db


def test_erros_relevantes_ignora_transaction_timeout() -> None:
    saida = (
        "pg_restore: error: could not execute query: ERROR:  unrecognized configuration parameter \"transaction_timeout\"\n"
        "pg_restore: error: could not execute query: ERROR:  relation \"realm\" already exists\n"
        "pg_restore: warning: errors ignored on restore: 2\n"
    )
    assert dump.erros_relevantes(saida) == ['pg_restore: error: could not execute query: ERROR:  relation "realm" already exists']


def test_conferencia() -> None:
    assert len(dump.Conferencia("keycloak_new", realms=["demo"]).problemas) == 2
    # Keycloak atualizado (21 → 26): várias linhas em migration_model só geram aviso
    c = dump.Conferencia("x", migracoes=[("a", "21.1.2"), ("b", "26.8.1")], realms=["master"])
    assert not c.problemas and "21.1.2 → 26.8.1" in c.avisos[0] and c.versao == "26.8.1"
    assert not dump.Conferencia("x", migracoes=[("a", "21.1.2")], realms=["master"]).avisos


def test_sem_configuracao_mostra_as_variaveis(entrar, monkeypatch) -> None:
    monkeypatch.delenv("KEYCLOAK_DB_HOST", raising=False)
    html = entrar("Limited").get("/app/banco/").content.decode()
    assert "não configurada" in html and 'value="conectar"' not in html  # Limited não conecta


class Falso:
    """O PostgreSQL: banco atual em 21.1.2 e, se ``temporario``, um keycloak_new restaurado."""

    def __init__(self, monkeypatch, temporario=True, versao_dump="21.1.2"):
        self.chamadas: list[str] = []
        self.temporario = temporario
        monkeypatch.setenv("KEYCLOAK_DB_HOST", "db")
        monkeypatch.setenv("KEYCLOAK_ADMIN_USER", "admin")
        atual = dump.Conferencia("keycloak", [("a", "21.1.2")], ["master", "demo", "velho"], 3, ["admin"])
        novo = dump.Conferencia("keycloak_new", [("a", versao_dump)], ["master", "demo"], 5, ["estatcamp"])
        monkeypatch.setattr(dump, "existe", lambda b, nome: nome == "keycloak" or self.temporario)
        monkeypatch.setattr(dump, "conferir", lambda b, nome, *a: novo if nome.endswith("_new") else atual)
        monkeypatch.setattr(dump, "copias", lambda b: [])
        monkeypatch.setattr(dump, "listar", lambda caminho: dump.Arquivo({"dbname": "keycloak"}, 10, True))
        monkeypatch.setattr(dump, "restaurar_temporario", lambda b, c: self.chamadas.append("restaurar") or [])
        monkeypatch.setattr(dump, "trocar", lambda b: self.chamadas.append("trocar") or "keycloak_antes_x")
        monkeypatch.setattr(dump, "pode_reiniciar", lambda: False)
        monkeypatch.setattr(dump, "testar", self.testar)
        monkeypatch.setattr(dump, "conexoes", lambda b: [{"banco": "keycloak", "origem": "10.0.0.9", "aplicacao": "keycloak-x",
                                                          "usuario": "kc", "estado": "idle", "desde": None}])
        monkeypatch.setattr(dump, "usuarios_com_senha", lambda b, realm="master": ["admin", "estatcamp"])
        monkeypatch.setattr(dump, "trocar_senha", lambda b, u, s, realm="master": self.chamadas.append(f"senha:{u}") or 1)
        self.falhar_conexao = False

    def testar(self, banco):
        if self.falhar_conexao:
            raise dump.ErroDump("Sem conexão com o banco outro:5432: recusada")
        self.chamadas.append(f"testar:{banco.host}")
        return {"versao": "16.4", "bancos": [{"nome": "keycloak", "tamanho": "20 MB", "aceita": True}]}


def test_conferencia_mostra_avisos(entrar, monkeypatch) -> None:
    Falso(monkeypatch)
    html = entrar("Limited").get("/app/banco/").content.decode()
    assert "pronto para trocar" in html and "estatcamp" in html
    assert "não existe no master do dump" in html and "velho" in html
    assert 'value="trocar"' not in html and 'value="senha"' not in html  # Limited não vê os botões


def test_conexoes_ativas_aparecem(entrar, monkeypatch) -> None:
    Falso(monkeypatch)
    html = entrar("Limited").get("/app/banco/").content.decode()
    assert "10.0.0.9" in html and "PostgreSQL 16.4" in html


def _dados_conexao(**extra):
    return {"acao": "conectar", "host": "outro", "porta": "23159", "usuario": "akmadmin", "senha": "x",
            "nome": "keycloak", "administrativo": "defaultdb", "sslmode": "require", **extra}


def test_conectar_em_outro_banco_vale_na_sessao(entrar, monkeypatch) -> None:
    falso = Falso(monkeypatch)
    client = entrar()
    assert client.post("/app/banco/", _dados_conexao()).status_code == 302
    html = client.get("/app/banco/").content.decode()
    assert "akmadmin@outro:23159/keycloak" in html and "vale só para a sua sessão" in html
    # A senha não fica em texto puro na sessão
    assert client.session[dump.CHAVE_SESSAO]["senha"] != "x"
    assert "testar:outro" in falso.chamadas
    client.post("/app/banco/", {"acao": "padrao"})
    assert dump.CHAVE_SESSAO not in client.session


def test_conexao_que_falha_nao_e_salva(entrar, monkeypatch) -> None:
    falso = Falso(monkeypatch)
    falso.falhar_conexao = True
    client = entrar()
    html = client.post("/app/banco/", _dados_conexao(), follow=True).content.decode()
    assert "Nada foi salvo" in html and dump.CHAVE_SESSAO not in client.session


def test_trocar_senha_de_admin(entrar, monkeypatch) -> None:
    falso = Falso(monkeypatch)
    client = entrar()
    html = client.post("/app/banco/", {"acao": "senha", "usuario": "admin", "senha": "admin", "repetir": "outra"}).content.decode()
    assert "As senhas não conferem" in html and not any(c.startswith("senha") for c in falso.chamadas)
    client.post("/app/banco/", {"acao": "senha", "usuario": "admin", "senha": "admin", "repetir": "admin"})
    assert "senha:admin" in falso.chamadas and Aplicacao.objects.get().realm == "master"


def test_hash_de_senha_confere() -> None:
    import base64, hashlib, json
    secreto, dados = dump.hash_senha("admin")
    s = json.loads(secreto)
    esperado = hashlib.pbkdf2_hmac("sha256", b"admin", base64.b64decode(s["salt"]), 27500, 32)
    assert base64.b64decode(s["value"]) == esperado and json.loads(dados)["algorithm"] == "pbkdf2-sha256"


def test_gerar_dump_baixa_arquivo(entrar, monkeypatch, tmp_path) -> None:
    Falso(monkeypatch)
    arquivo = tmp_path / "x.dump"
    arquivo.write_bytes(b"PGDMP-teste")
    monkeypatch.setattr(dump, "gerar_dump", lambda b: arquivo.open("rb"))
    resposta = entrar().post("/app/banco/", {"acao": "dump"})
    assert resposta.status_code == 200 and b"".join(resposta.streaming_content) == b"PGDMP-teste"
    assert resposta["Content-Disposition"].startswith('attachment; filename="keycloak-')


def test_limited_nao_envia(entrar, monkeypatch) -> None:
    falso = Falso(monkeypatch)
    arquivo = SimpleUploadedFile("keycloak.dump", b"PGDMP")
    entrar("Limited").post("/app/banco/", {"acao": "enviar", "arquivo": arquivo})
    assert "restaurar" not in falso.chamadas and not Aplicacao.objects.exists()


def test_enviar_restaura_no_temporario(entrar, monkeypatch) -> None:
    falso = Falso(monkeypatch)
    arquivo = SimpleUploadedFile("keycloak.dump", b"PGDMP")
    resposta = entrar().post("/app/banco/", {"acao": "enviar", "arquivo": arquivo})
    assert resposta.status_code == 302 and "restaurar" in falso.chamadas
    registro = Aplicacao.objects.get()
    assert registro.etapa == Aplicacao.DUMP and registro.simulacao and registro.sucesso


def test_trocar_exige_confirmacao(entrar, monkeypatch) -> None:
    falso = Falso(monkeypatch)
    client = entrar()
    html = client.post("/app/banco/", {"acao": "trocar", "confirmacao": "errado"}).content.decode()
    assert "Digite exatamente keycloak" in html and "trocar" not in falso.chamadas
    assert client.post("/app/banco/", {"acao": "trocar", "confirmacao": "keycloak"}).status_code == 302
    assert "trocar" in falso.chamadas and not Aplicacao.objects.get().simulacao


def test_trocar_recusa_dump_mais_novo(entrar, monkeypatch) -> None:
    falso = Falso(monkeypatch, versao_dump="26.0.1")
    client = entrar()
    assert "não volta versão" in client.get("/app/banco/").content.decode()
    client.post("/app/banco/", {"acao": "trocar", "confirmacao": "keycloak"})
    assert "trocar" not in falso.chamadas
