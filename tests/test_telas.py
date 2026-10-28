"""Telas: acesso por empresa e papel, cadastro de proposta com itens, ações do funil, clientes e catálogo."""

from decimal import Decimal

import pytest
from django.test import Client

from commercial.propostas.constantes import ENVIADA, RASCUNHO
from commercial.propostas.models import AcessoEmpresa, Cliente, Empresa, ItemCatalogo, Proposta
from commercial.propostas.servicos import executar

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def entrar(empresa, usuario):
    """Cliente HTTP logado com um papel na empresa de teste."""

    def criar(papel: str) -> Client:
        user = usuario(papel, first_name="Vendedor")
        for grupo in user.groups.all():
            AcessoEmpresa.objects.get_or_create(empresa=empresa, grupo=grupo, defaults={"papel": papel})
        client = Client()
        client.force_login(user)
        return client

    return criar


def _post(client, empresa, url="/app/propostas/", **dados):
    return client.post(url, {"empresa_tela": empresa.pk, **dados})


def test_sem_acesso_a_empresa_ve_aviso(empresa, usuario) -> None:
    client = Client()
    client.force_login(usuario("Tech"))
    resposta = client.get("/app/propostas/")
    assert resposta.status_code == 403 and "Nenhuma empresa disponível" in resposta.content.decode()


@pytest.mark.parametrize("url", ["/app/", "/app/painel/", "/app/propostas/", "/app/propostas/?novo=1", "/app/clientes/", "/app/clientes/?novo=1", "/app/catalogo/"])
def test_telas_abrem(entrar, cliente, url) -> None:
    assert entrar("Master").get(url).status_code == 200


def test_tela_inexistente_e_config_dao_404(entrar) -> None:
    client = entrar("Master")
    assert client.get("/app/nao-existe/").status_code == 404
    assert client.get("/app/config/").status_code == 404


def test_cria_proposta_com_itens(entrar, empresa, cliente, consultoria) -> None:
    client = entrar("Tech")
    resposta = _post(
        client, empresa, action="salvar", titulo="Implantação", cliente=cliente.pk, probabilidade="10",
        **{
            "itens-TOTAL_FORMS": "2", "itens-INITIAL_FORMS": "0", "itens-MIN_NUM_FORMS": "1", "itens-MAX_NUM_FORMS": "1000",
            # Do catálogo: descrição, unidade e preço vêm dele.
            "itens-0-item_catalogo": consultoria.pk, "itens-0-quantidade": "10",
            "itens-1-descricao": "Deslocamento", "itens-1-quantidade": "1", "itens-1-preco_unitario": "1.500,00",
        },
    )
    proposta = Proposta.objects.get()
    assert resposta.status_code == 302 and resposta["Location"] == f"/app/propostas/?id={proposta.pk}"
    assert proposta.valor_total == D("3500.00") and proposta.etapa == RASCUNHO
    itens = list(proposta.itens.all())
    assert (itens[0].descricao, itens[0].unidade, itens[0].preco_tabela) == ("Consultoria", "h", D("200.00"))
    assert itens[1].preco_tabela == D("0") and itens[1].ordem == 2

    detalhe = client.get(f"/app/propostas/?id={proposta.pk}").content.decode()
    assert proposta.codigo in detalhe and "Marcar como enviada" in detalhe
    impressao = client.get(f"/app/propostas/?id={proposta.pk}&imprimir=html").content.decode()
    assert "R$ 3.500,00" in impressao and "Observações internas" not in impressao


def test_formulario_sem_item_volta_com_erro(entrar, empresa, cliente) -> None:
    resposta = _post(
        entrar("Tech"), empresa, action="salvar", titulo="Sem itens", cliente=cliente.pk, probabilidade="10",
        **{"itens-TOTAL_FORMS": "1", "itens-INITIAL_FORMS": "0", "itens-MIN_NUM_FORMS": "1", "itens-MAX_NUM_FORMS": "1000"},
    )
    assert resposta.status_code == 200 and "Descreva o item" in resposta.content.decode()
    assert not Proposta.objects.exists()


def test_acoes_do_funil_pela_tela(entrar, empresa, nova_proposta) -> None:
    client = entrar("Tech")
    proposta = nova_proposta()
    _post(client, empresa, action="executar", acao="enviar", id=proposta.pk)
    proposta.refresh_from_db()
    assert proposta.etapa == ENVIADA
    _post(client, empresa, action="executar", acao="perder", id=proposta.pk)  # sem motivo: recusada
    proposta.refresh_from_db()
    assert proposta.etapa == ENVIADA
    _post(client, empresa, action="anotar", id=proposta.pk, texto="Retornar", proxima_acao="Ligar", proxima_acao_em="2030-01-10")
    proposta.refresh_from_db()
    assert proposta.proxima_acao == "Ligar"


def test_limited_so_consulta(entrar, empresa, nova_proposta) -> None:
    client = entrar("Limited")
    proposta = nova_proposta()
    assert "Marcar como enviada" not in client.get(f"/app/propostas/?id={proposta.pk}").content.decode()
    _post(client, empresa, action="executar", acao="enviar", id=proposta.pk)
    proposta.refresh_from_db()
    assert proposta.etapa == RASCUNHO
    assert client.get("/app/propostas/?novo=1").status_code == 302


def test_proposta_de_outra_empresa_nao_aparece(entrar, nova_proposta) -> None:
    client = entrar("Master")
    outra = Empresa.objects.create(nome="Outra", slug="outra")
    cliente = Cliente.objects.create(empresa=outra, nome="Cliente da outra")
    alheia = Proposta.objects.create(empresa=outra, cliente=cliente, titulo="Alheia", ano=2026, numero=1)
    assert client.get(f"/app/propostas/?id={alheia.pk}").status_code == 302
    assert client.get("/app/propostas/?id=abc").status_code == 302


def test_exporta_excel(entrar, nova_proposta) -> None:
    nova_proposta()
    resposta = entrar("Limited").get("/app/propostas/?ver=todas&exportar=xlsx")
    assert resposta["Content-Type"].startswith("application/vnd.openxmlformats")


def test_cadastro_de_cliente_com_contato(entrar, empresa) -> None:
    resposta = _post(
        entrar("Tech"), empresa, "/app/clientes/", action="salvar", nome="Nova Conta SA", documento="1", uf="sp", ativo="on",
        **{
            "contatos-TOTAL_FORMS": "1", "contatos-INITIAL_FORMS": "0", "contatos-MIN_NUM_FORMS": "0",
            "contatos-MAX_NUM_FORMS": "1000", "contatos-0-nome": "Bruno", "contatos-0-email": "b@nova.com",
        },
    )
    assert resposta.status_code == 302
    cliente = Cliente.objects.get(nome="Nova Conta SA")
    assert cliente.uf == "SP" and cliente.contatos.get().nome == "Bruno"


def test_catalogo_so_master_altera(entrar, empresa) -> None:
    dados = {"nome": "Treinamento", "tipo": "treinamento", "unidade": "turma", "preco": "3.000,00", "ativo": "on"}
    _post(entrar("Tech"), empresa, "/app/catalogo/", **dados)
    assert not ItemCatalogo.objects.exists()
    _post(entrar("Master"), empresa, "/app/catalogo/", **dados)
    assert ItemCatalogo.objects.get().preco == D("3000.00")


def test_post_com_empresa_trocada_em_outra_aba_e_recusado(entrar, empresa, nova_proposta) -> None:
    client = entrar("Tech")
    proposta = nova_proposta()
    client.post("/app/propostas/", {"empresa_tela": empresa.pk + 99, "action": "executar", "acao": "enviar", "id": proposta.pk})
    proposta.refresh_from_db()
    assert proposta.etapa == RASCUNHO


def test_pdf_da_proposta(entrar, nova_proposta) -> None:
    pytest.importorskip("weasyprint", exc_type=ImportError)
    proposta = nova_proposta()
    resposta = entrar("Limited").get(f"/app/propostas/?id={proposta.pk}&imprimir=pdf")
    assert resposta["Content-Type"] == "application/pdf" and resposta.content.startswith(b"%PDF")


def test_tela_de_sincronizacao(entrar, empresa, monkeypatch) -> None:
    from commercial.propostas.sincronizacao import Relatorio

    client = entrar("Master")
    assert "não tem site do SharePoint" in client.get("/app/sincronizacao/").content.decode()
    empresa.sharepoint_site = "https://estatcamp.sharepoint.com/sites/propostasestatcamp"
    empresa.save()
    chamadas = []
    monkeypatch.setattr(
        "commercial.screens.sincronizacao.view.sincronizar",
        lambda emp, simular, usuario: chamadas.append((emp, simular, usuario)) or Relatorio(criadas=2),
    )

    class ThreadImediata:  # roda na hora, sem segundo plano, para o teste ver o efeito
        def __init__(self, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr("commercial.screens.sincronizacao.view.threading.Thread", ThreadImediata)
    monkeypatch.setattr("commercial.screens.sincronizacao.view.connection.close", lambda: None)
    assert "Sincronizar agora" in client.get("/app/sincronizacao/").content.decode()
    resposta = _post(client, empresa, "/app/sincronizacao/", action="simular")
    assert resposta.status_code == 302 and chamadas[0][1] is True
    _post(entrar("Tech"), empresa, "/app/sincronizacao/", action="sincronizar")
    assert len(chamadas) == 1


def test_metodologia_abre(entrar) -> None:
    html = entrar("Limited").get("/app/metodologia/").content.decode()
    assert "mermaid" in html and "Sincronização" in html


def test_empresa_padrao_e_a_com_propostas(entrar, nova_proposta) -> None:
    from commercial.propostas.models import Empresa

    Empresa.objects.create(nome="AAA sem propostas", slug="aaa")
    nova_proposta()
    client = entrar("Admin")
    assert "Empresa Teste" in client.get("/app/propostas/").content.decode().split("<title>")[1].split("</title>")[0]


def test_historico_e_contratos(entrar, empresa, nova_proposta) -> None:
    from commercial.propostas.models import ArquivoSharePoint

    ganha = executar(nova_proposta(), "enviar", None, "Tech")
    executar(ganha, "ganhar", None, "Tech")
    ArquivoSharePoint.objects.create(
        empresa=empresa, item_id="x1", nome="Acordo de Confidencialidade.pdf", caminho="a/Acordo.pdf",
        url="https://sp/a", pasta_raiz="01 - Propostas", ano=ganha.ano, categoria="nda",
    )
    client = entrar("Limited")
    historico = client.get("/app/historico/").content.decode()
    assert "Ano a ano" in historico and "R$ 2.000,00" in historico
    contratos = client.get("/app/contratos/").content.decode()
    assert ganha.numero_curto in contratos and "Acordo de Confidencialidade.pdf" in contratos
    assert client.get(f"/app/propostas/?ver=todas&ano={ganha.ano}").status_code == 200
