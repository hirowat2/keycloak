"""Telas sem Keycloak de verdade: permissões, aviso de conexão e histórico."""

import pytest

from keycloak.automacao import web
from keycloak.automacao.api import ErroKeycloak
from keycloak.models import Aplicacao

pytestmark = pytest.mark.django_db

TELAS = ["painel", "realm", "grupos", "sso", "mapeamento", "conferir", "migracao"]


class SemKeycloak:
    url = "http://keycloak:8080"

    def get(self, *args, **kwargs):
        raise ErroKeycloak("Sem conexão com o Keycloak em http://keycloak:8080: recusada")


@pytest.fixture
def sem_keycloak(monkeypatch):
    monkeypatch.setattr(web, "_api", SemKeycloak())


def test_login_exigido(client) -> None:
    resposta = client.get("/app/painel/")
    assert resposta.status_code == 302 and resposta["Location"].startswith("/login")


@pytest.mark.parametrize("tela", TELAS)
def test_keycloak_fora_do_ar_mostra_o_aviso(entrar, sem_keycloak, tela) -> None:
    resposta = entrar().get(f"/app/{tela}/")
    assert resposta.status_code == 502 and "O Keycloak não respondeu" in resposta.content.decode()


def test_inicio_e_tela_inexistente(entrar) -> None:
    client = entrar("Limited")
    assert client.get("/app/").status_code == 200
    assert client.get("/app/nao-existe/").status_code == 404
    assert client.get("/app/config/").status_code == 404


def test_menu_esconde_administracao_de_quem_so_consulta(entrar) -> None:
    assert "/admin/" not in entrar("Limited").get("/app/").content.decode()
    assert "/admin/" in entrar("Admin").get("/app/").content.decode()


def test_historico_mostra_o_plano(entrar) -> None:
    registro = Aplicacao.objects.create(
        servidor="http://kc", realm="automateflow", etapa=Aplicacao.GRUPOS, simulacao=True, mudancas=1,
        passos=[{"situacao": "criar", "tipo": "grupo", "alvo": "automateflow-admins", "detalhe": ""}],
    )
    html = entrar("Limited").get(f"/app/historico/?id={registro.pk}").content.decode()
    assert "automateflow-admins" in html and "Simulação" in html


def test_limited_simula_mas_nao_aplica(usuario, monkeypatch) -> None:
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.test import RequestFactory

    from keycloak.automacao.plano import Plano

    request = RequestFactory().post("/app/grupos/", {"acao": "aplicar"})
    request.user, request.session = usuario("Limited"), {}
    request._messages = FallbackStorage(request)
    monkeypatch.setattr(web, "_api", SemKeycloak())
    chamado = []
    assert web.executar(request, "automateflow", Aplicacao.GRUPOS, lambda simular: chamado.append(simular) or Plano(simular)) is None
    assert chamado == [] and not Aplicacao.objects.exists()


def test_metodologia_tem_uma_secao_por_etapa(entrar) -> None:
    from keycloak.screens.metodologia.view import ETAPAS

    html = entrar("Limited").get("/app/metodologia/").content.decode()
    for etapa in ["realm", "grupos", "sso", "mapeamento", "conferir", "migracao", "banco"]:
        assert f'id="{etapa}"' in html and f'href="#{etapa}"' in html
    # Diagramas com "{{" seriam lidos como variável do Django e quebrariam o Mermaid
    assert all("{{" not in e["diagrama"] for e in ETAPAS) and 'T(["Teste de login' in html
    # Todo print citado existe em media/metodologia (make prints)
    assert html.count('class="ct-card mt-passo"') == sum(len(e["passos"]) for e in ETAPAS)


def test_manual_tem_um_caso_por_tarefa(entrar) -> None:
    from keycloak.screens.manual.view import CASOS

    html = entrar("Limited").get("/app/manual/").content.decode()
    for caso in CASOS:
        assert f'id="{caso["id"]}"' in html and f'href="#{caso["id"]}"' in html
        assert "{{" not in caso["diagrama"]
    assert 'id="problemas"' in html and 'id="glossario"' in html


def test_prints_e_telas_citados_existem() -> None:
    """Todo print citado na Metodologia e no Manual existe, e todo "Abrir a tela" leva a uma tela de verdade."""
    import os

    from django.conf import settings

    from keycloak.screens.manual.view import CASOS, TELAS as TELAS_MANUAL
    from keycloak.screens.metodologia.view import ETAPAS

    pasta = os.path.join(settings.MEDIA_ROOT, "metodologia")
    prints = {arquivo for e in ETAPAS for arquivo, _, _ in e["passos"]}
    prints |= {imagem for c in CASOS for _, _, imagem in c["passos"] if imagem}
    assert sorted(p for p in prints if not os.path.exists(os.path.join(pasta, p))) == []

    telas = os.path.join(settings.BASE_DIR.parent, "src", "keycloak", "screens")
    links = {tela for c in CASOS for _, tela, _ in c["passos"] if tela} | {url for url, *_ in TELAS_MANUAL} | {e["tela"] for e in ETAPAS}
    nomes = {link.split("/")[2] for link in links}
    assert sorted(n for n in nomes if not os.path.isfile(os.path.join(telas, n, "view.py"))) == []
