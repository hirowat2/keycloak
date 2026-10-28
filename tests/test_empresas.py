"""Várias empresas: acesso e papel pelos grupos, troca de empresa, menu e configuração inicial."""

import pytest
from django.contrib.auth.models import Group
from django.test import Client

from commercial.propostas.empresas import SESSAO, empresas_do_usuario, papel
from commercial.propostas.empresas_padrao import EMPRESAS, configurar
from commercial.propostas.models import AcessoEmpresa, Empresa

pytestmark = pytest.mark.django_db


@pytest.fixture
def outra(db):
    return Empresa.objects.create(nome="Outra", slug="outra")


def test_maior_papel_entre_os_grupos(empresa, usuario) -> None:
    user = usuario("Limited", "vendas")
    AcessoEmpresa.objects.create(empresa=empresa, grupo=Group.objects.get(name="Limited"), papel="Limited")
    AcessoEmpresa.objects.create(empresa=empresa, grupo=Group.objects.get(name="vendas"), papel="Tech")
    assert papel(user, empresa) == "Tech"


def test_admin_ve_todas_e_os_demais_so_as_liberadas(empresa, outra, usuario) -> None:
    admin, tech = usuario("Admin"), usuario("Tech")
    AcessoEmpresa.objects.create(empresa=empresa, grupo=Group.objects.get(name="Tech"), papel="Tech")
    assert set(empresas_do_usuario(admin)) == {empresa, outra}
    assert list(empresas_do_usuario(tech)) == [empresa]
    assert papel(tech, outra) is None


def test_troca_de_empresa_so_para_liberada(empresa, outra, usuario) -> None:
    user = usuario("Tech")
    AcessoEmpresa.objects.create(empresa=empresa, grupo=Group.objects.get(name="Tech"), papel="Tech")
    client = Client()
    client.force_login(user)
    client.post("/app/empresa/", {"empresa": outra.pk, "next": "/app/propostas/"})
    assert client.session.get(SESSAO) != outra.pk
    resposta = client.post("/app/empresa/", {"empresa": empresa.pk, "next": "https://fora.com/"})
    assert client.session[SESSAO] == empresa.pk and resposta["Location"] == "/app/"


def test_menu_por_papel(empresa, usuario) -> None:
    user = usuario("Limited")
    AcessoEmpresa.objects.create(empresa=empresa, grupo=Group.objects.get(name="Limited"), papel="Limited")
    client = Client()
    client.force_login(user)
    html = client.get("/app/").content.decode()
    assert 'href="/app/propostas/"' in html and 'href="/admin/"' not in html


def test_configurar_empresas_e_idempotente(db) -> None:
    assert len(configurar()) == 2 * len(EMPRESAS)
    assert configurar() == []
    estatcamp = Empresa.objects.get(slug="estatcamp")
    assert estatcamp.prefixo == "EST" and estatcamp.acessos.count() == 3
    assert estatcamp.sharepoint_site.endswith("/sites/propostasestatcamp") and estatcamp.sharepoint_desde == 2016
    pharma = Empresa.objects.get(slug="mbrlproc-sistemas-ltda")
    assert pharma.nome == "PHARMA / MBRLPROC Sistemas" and pharma.sharepoint_site.endswith("/sites/actionpharma")
    assert pharma.sharepoint_controle_contratos == "Contratos de Clientes/Controle de Contratos.xlsx"
    assert Empresa.objects.get(slug="action-stat").sharepoint_site.endswith("/sites/actionstat")
    assert not Empresa.objects.filter(slug="estat-analytics").exists()


def test_empresa_existente_sem_site_recebe_a_configuracao(db) -> None:
    Empresa.objects.create(slug="mbrlproc-sistemas-ltda", nome="MBRLPROC SISTEMAS LTDA")
    configurar()
    pharma = Empresa.objects.get(slug="mbrlproc-sistemas-ltda")
    assert pharma.sharepoint_pasta == "02 - Propostas Clientes" and pharma.sharepoint_controle == "04 - Controle de Propostas"
