"""Importação do SharePoint: leitura dos .docx e da planilha, agrupamento dos arquivos e sincronização."""

import io
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal
from xml.sax.saxutils import escape

import pytest
from django.contrib.auth.models import User

from commercial.propostas.constantes import ENVIADA, EXPIRADA, GANHA, PERDIDA
from commercial.propostas.leitor_docx import ler
from commercial.propostas.models import Proposta
from commercial.propostas.servicos import executar
from commercial.propostas.sharepoint import ItemRemoto
from commercial.propostas.sincronizacao import agrupar, cita_numero, ler_controle, sincronizar

pytestmark = pytest.mark.django_db
D = Decimal
HOJE = date(2026, 10, 28)
RAIZ = "01 - Propostas"
CONTROLE = "02 - Controle de Propostas"


def docx(*paragrafos: str) -> bytes:
    corpo = "".join(f"<w:p><w:r><w:t>{escape(p)}</w:t></w:r></w:p>" for p in paragrafos)
    xml = f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{corpo}</w:body></w:document>'
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w") as z:
        z.writestr("word/document.xml", xml)
    return saida.getvalue()


def consultoria(numero="021/26", data="14/07/2026", vencimento="14/08/2026", valor="R$ 8.890,00", cliente="MERCK"):
    return docx(
        f"PROPOSTA DE SERVIÇO ENVIADA PARA {cliente}", "A/C: Fabiane Lisboa", "PROPOSTA", "NÚMERO:", numero,
        "Data:", data, "Vencimento:", vencimento, "Análise do Perfil de Dissolução Comparativo", "Descrição Geral",
        "Proposta comercial referente ao perfil de dissolução.", "ESCOPO", "Fase I", "VALOR",
        f"O valor cobrado será de {valor} (oito mil reais).", "FORMA DE PAGAMENTO", "Depósito, 90 ddl.",
        "CRONOGRAMA DE TRABALHO", "Prazo de 10 dias.", "A seu dispor para eventuais esclarecimentos,", "José Rubens Campanini",
    )


def xlsx(*linhas) -> bytes:
    from openpyxl import Workbook

    livro = Workbook()
    aba = livro.active
    aba.append(["\xa0", "SERVIÇO", "Nº", "EMPRESA", "DATA", "RESPONSAVEL", "FUP", "POSIÇÃO"])
    for linha in linhas:
        aba.append(["\xa0", *linha])
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()


def item(caminho: str, pasta=False, versao="v1", criado=datetime(2026, 7, 20, 15, tzinfo=timezone.utc)) -> ItemRemoto:
    return ItemRemoto(
        id=caminho, nome=caminho.rsplit("/", 1)[-1], caminho=caminho, pasta=pasta, versao=versao,
        url=f"https://sp/{caminho}", tamanho=10, criado=criado, modificado=criado,
    )


class SharePointFalso:
    """Biblioteca em memória: {caminho: conteúdo}; pastas são deduzidas dos caminhos."""

    def __init__(self, arquivos: dict[str, bytes], versoes: dict[str, str] | None = None) -> None:
        self.arquivos = arquivos
        self.versoes = versoes or {}
        self.baixados: list[str] = []

    def listar(self, caminho: str, profundidade: int = 1) -> list[ItemRemoto]:
        caminho = caminho.strip("/")
        pastas = {"/".join(c.split("/")[:i]) for c in self.arquivos for i in range(1, c.count("/") + 1)}
        todos = [item(p, pasta=True) for p in pastas] + [item(c, versao=self.versoes.get(c, "v1")) for c in self.arquivos]
        return sorted(
            (i for i in todos if i.caminho.startswith(caminho + "/") and i.caminho[len(caminho) + 1:].count("/") < profundidade),
            key=lambda i: i.caminho,
        )

    def baixar(self, remoto: ItemRemoto) -> bytes:
        self.baixados.append(remoto.caminho)
        return self.arquivos[remoto.caminho]


@pytest.fixture
def estatcamp(empresa):
    empresa.sharepoint_site = "https://estatcamp.sharepoint.com/sites/propostasestatcamp"
    empresa.save()
    return empresa


@pytest.fixture
def biblioteca():
    return {
        f"{RAIZ}/2026/MERCK/Proposta 021 26.docx": consultoria(vencimento="14/11/2026", valor="R$ 8.000,00"),
        f"{RAIZ}/2026/MERCK/Proposta 021 26 Rev 01.docx": consultoria(vencimento="14/11/2026"),
        f"{RAIZ}/2026/MERCK/Proposta 021 26 Rev 01.pdf": b"%PDF",
        f"{RAIZ}/2026/EUROFARMA/Proposta 002 26.docx": consultoria("002/26", "19/01/2026", "19/02/2026", "R$ 15.000,00", "EUROFARMA"),
        f"{RAIZ}/2026/EUROFARMA/Proposta 003 26.docx": consultoria("003/26", "03/02/2026", "03/03/2026", "R$ 9.000,00", "EUROFARMA"),
        f"{RAIZ}/2026/EUROFARMA/Pedido Compra 4100089244 - prop_002 26.pdf": b"%PDF",
        f"{RAIZ}/2026/EUROFARMA/Usuário e senha.docx": b"x",
        f"{RAIZ}/2020/ANTIGA/Proposta 001 20.docx": consultoria("001/20"),
        f"{CONTROLE}/Propostas Treinamento e consultoria2026.xlsx": xlsx(
            ["PERFIL", "002/26", "EUROFARMA", datetime(2026, 1, 19), "PATRÍCIA"],
            ["TESTE F2", "003/26", "EUROFARMA", "03/02/26", "LUCAS"],
            ["Perfil de Dissolução", "021 26", "MERCK", datetime(2026, 7, 14), "leão"],
        ),
        f"{CONTROLE}/Propostas Treinamento e consultoria2024-rubens-estat.xlsx": b"ignorada",
    }


def test_leitor_modelo_consultoria() -> None:
    dados = ler(consultoria())
    assert (dados.numero, dados.data, dados.validade) == ("021/26", date(2026, 7, 14), date(2026, 8, 14))
    assert dados.titulo == "Análise do Perfil de Dissolução Comparativo"
    assert (dados.cliente, dados.contato, dados.valor) == ("MERCK", "Fabiane Lisboa", D("8890.00"))
    assert dados.pagamento == "Depósito, 90 ddl." and dados.prazo == "Prazo de 10 dias."
    assert dados.assinante == "José Rubens Campanini" and not dados.valor_a_conferir


def test_leitor_modelo_action_stat() -> None:
    dados = ler(docx(
        "Proposta Comercial", "ACTION STAT", "Proposta No 017/21", "Entrega da Proposta: 22/02/2021",
        "Proposta válida até: 22.03.2021", "Preparada para:", "Alessandro Zacharias", "INDEMETAL", "Valor",
        "Licença", "R$ 2.500,00", "Forma de Pagamento: 28 ddl.", "A seu dispor para eventuais esclarecimentos,", "Rubens",
    ))
    assert (dados.numero, dados.data, dados.validade) == ("017/21", date(2021, 2, 22), date(2021, 3, 22))
    assert (dados.contato, dados.cliente, dados.valor, dados.pagamento) == ("Alessandro Zacharias", "INDEMETAL", D("2500.00"), "28 ddl.")


def test_leitor_prefere_o_total() -> None:
    dados = ler(docx("VALOR", "Hora técnica R$ 340,00", "Total do projeto: R$ 6.800,00", "Deslocamento R$ 9.000,00", "FORMA DE PAGAMENTO", "x"))
    assert dados.valor == D("6800.00") and dados.valor_a_conferir


def test_planilha_de_controle(biblioteca) -> None:
    linhas = ler_controle(biblioteca[f"{CONTROLE}/Propostas Treinamento e consultoria2026.xlsx"], 2026)
    assert set(linhas) == {2, 3, 21}
    assert linhas[3].data == date(2026, 2, 3) and linhas[21].servico == "Perfil de Dissolução"


def test_agrupamento(biblioteca) -> None:
    sp = SharePointFalso(biblioteca)
    grupos = agrupar(sp.listar(RAIZ, profundidade=4), RAIZ, 2021)
    assert set(grupos) == {(2026, 2), (2026, 3), (2026, 21)}
    assert grupos[(2026, 21)].revisao == 1 and grupos[(2026, 21)].principal.nome == "Proposta 021 26 Rev 01.docx"
    assert [p.nome for p in grupos[(2026, 2)].pedidos] == ["Pedido Compra 4100089244 - prop_002 26.pdf"]
    assert grupos[(2026, 3)].pedidos == []
    assert cita_numero("Pedido 4500761316 - 039 24.pdf", 39, 2024) and not cita_numero("Pedido 4500761316.pdf", 39, 2024)


def test_sincronizacao_completa(estatcamp, biblioteca) -> None:
    rubens = User.objects.create_user("rubens", "rubens@estatcamp.com.br")
    relatorio = sincronizar(estatcamp, SharePointFalso(biblioteca), hoje=HOJE)
    assert (relatorio.criadas, relatorio.ganhas, relatorio.expiradas) == (3, 1, 1)

    merck = Proposta.objects.get(ano=2026, numero=21)
    assert merck.numero_curto == "021/26" and merck.revisao == 1 and merck.importada
    assert merck.valor_total == D("8890.00") and merck.validade == date(2026, 11, 14)
    assert merck.cliente.nome == "MERCK" and merck.contato.nome == "Fabiane Lisboa"
    assert merck.responsavel == rubens and merck.servico == "Perfil de Dissolução"
    assert merck.etapa == ENVIADA and merck.enviada_em == date(2026, 7, 14)
    assert merck.arquivos.count() == 3

    ganha = Proposta.objects.get(ano=2026, numero=2)
    assert ganha.etapa == GANHA and ganha.fechada_em == date(2026, 7, 20)
    expirada = Proposta.objects.get(ano=2026, numero=3)
    assert expirada.etapa == EXPIRADA and expirada.fechada_em == date(2026, 3, 3)
    assert "LUCAS" in expirada.observacoes
    assert not Proposta.objects.filter(ano=2020).exists()


def test_sincronizar_de_novo_so_baixa_o_que_mudou(estatcamp, biblioteca) -> None:
    sincronizar(estatcamp, SharePointFalso(biblioteca), hoje=HOJE)
    sp = SharePointFalso(biblioteca)
    relatorio = sincronizar(estatcamp, sp, hoje=HOJE)
    assert (relatorio.criadas, relatorio.atualizadas, relatorio.sem_mudanca) == (0, 0, 3)
    assert not any(c.endswith(".docx") for c in sp.baixados)

    caminho = f"{RAIZ}/2026/MERCK/Proposta 021 26 Rev 01.docx"
    biblioteca[caminho] = consultoria(vencimento="14/11/2026", valor="R$ 9.500,00")
    relatorio = sincronizar(estatcamp, SharePointFalso(biblioteca, {caminho: "v2"}), hoje=HOJE)
    assert relatorio.atualizadas == 1
    assert Proposta.objects.get(ano=2026, numero=21).valor_total == D("9500.00")


def test_nao_desfaz_o_que_foi_decidido_no_sistema(estatcamp, biblioteca) -> None:
    sincronizar(estatcamp, SharePointFalso(biblioteca), hoje=HOJE)
    merck = Proposta.objects.get(ano=2026, numero=21)
    executar(merck, "perder", None, "Master", motivo_perda="preco")
    biblioteca[f"{RAIZ}/2026/MERCK/Pedido 123 - 021 26.pdf"] = b"%PDF"
    sincronizar(estatcamp, SharePointFalso(biblioteca), hoje=HOJE)
    assert Proposta.objects.get(pk=merck.pk).etapa == PERDIDA


def test_conflito_com_proposta_criada_no_sistema(estatcamp, cliente, biblioteca) -> None:
    Proposta.objects.create(empresa=estatcamp, cliente=cliente, titulo="Daqui", ano=2026, numero=21)
    relatorio = sincronizar(estatcamp, SharePointFalso(biblioteca), hoje=HOJE)
    assert len(relatorio.conflitos) == 1 and "021/26" in relatorio.conflitos[0]
    assert Proposta.objects.get(ano=2026, numero=21).titulo == "Daqui"


def test_simulacao_nao_grava(estatcamp, biblioteca) -> None:
    relatorio = sincronizar(estatcamp, SharePointFalso(biblioteca), simular=True, hoje=HOJE)
    assert relatorio.criadas == 3 and not Proposta.objects.exists()
    estatcamp.refresh_from_db()
    assert estatcamp.sincronizado_em is None


def test_proxima_proposta_do_sistema_continua_a_numeracao(estatcamp, biblioteca, nova_proposta) -> None:
    from django.utils import timezone as tz

    sincronizar(estatcamp, SharePointFalso(biblioteca), hoje=HOJE)
    ultimo = max(Proposta.objects.filter(ano=tz.localdate().year).values_list("numero", flat=True), default=0)
    assert nova_proposta().numero == ultimo + 1


def test_cliente_renomeado_continua_ligado_a_pasta(estatcamp, biblioteca) -> None:
    sincronizar(estatcamp, SharePointFalso(biblioteca), hoje=HOJE)
    eurofarma = Proposta.objects.get(ano=2026, numero=2).cliente
    assert eurofarma.nomes_sharepoint == "EUROFARMA"
    eurofarma.nome = "Eurofarma Laboratórios S.A."
    eurofarma.save()
    biblioteca[f"{RAIZ}/2026/EUROFARMA/Proposta 040 26.docx"] = consultoria("040/26", vencimento="14/11/2026", cliente="EUROFARMA")
    sincronizar(estatcamp, SharePointFalso(biblioteca), hoje=HOJE)
    assert Proposta.objects.get(ano=2026, numero=40).cliente == eurofarma


def test_responsavel_ligado_quando_o_usuario_aparece_depois(estatcamp, biblioteca) -> None:
    sincronizar(estatcamp, SharePointFalso(biblioteca), hoje=HOJE)
    merck = Proposta.objects.get(ano=2026, numero=21)
    assert merck.responsavel is None and merck.assinada_por == "José Rubens Campanini"
    rubens = User.objects.create_user("rubens", "rubens@estatcamp.com.br", first_name="José Rubens", last_name="Campanini")
    sincronizar(estatcamp, SharePointFalso(biblioteca), hoje=HOJE)
    assert Proposta.objects.get(pk=merck.pk).responsavel == rubens


def test_execucao_fica_registrada_e_bloqueia_outra_simultanea(estatcamp, biblioteca) -> None:
    from commercial.propostas.models import ExecucaoSincronizacao
    from commercial.propostas.sincronizacao import SincronizacaoEmAndamento

    usuario = User.objects.create_user("gestor")
    sincronizar(estatcamp, SharePointFalso(biblioteca), hoje=HOJE, usuario=usuario)
    execucao = ExecucaoSincronizacao.objects.get()
    assert (execucao.criadas, execucao.ganhas, execucao.usuario, execucao.situacao) == (3, 1, usuario, "concluída")

    ExecucaoSincronizacao.objects.create(empresa=estatcamp)  # outra rodando agora
    with pytest.raises(SincronizacaoEmAndamento):
        sincronizar(estatcamp, SharePointFalso(biblioteca), hoje=HOJE)


def test_erro_fica_registrado(estatcamp) -> None:
    from commercial.propostas.models import ExecucaoSincronizacao
    from commercial.propostas.sharepoint import SharePointErro

    class Fora:
        def listar(self, *args, **kwargs):
            raise SharePointErro("Acesso negado pelo Microsoft Graph (403).")

    with pytest.raises(SharePointErro):
        sincronizar(estatcamp, Fora())
    execucao = ExecucaoSincronizacao.objects.get()
    assert execucao.situacao == "erro" and "403" in execucao.erro


# ------------------------------------------------------------------ histórico, acervo e documentos

ANTIGAS = "Propostas_antigas"


@pytest.fixture
def com_historico(estatcamp, biblioteca):
    estatcamp.sharepoint_pasta = f"{ANTIGAS}: 2016-2020\n{RAIZ}: 2021-"
    estatcamp.sharepoint_contratos = "CONTRATOS_OUT 2023"
    estatcamp.sharepoint_desde = 2016
    estatcamp.save()
    biblioteca.update({
        f"{ANTIGAS}/2019/BRAINFARMA/Proposta 356 19 rev01.docx": docx(
            "A: BRAINFARMA", "A/C: Edgard Filho", "NÚMERO:", "356/19", "Data:", "20/12/2019", "Vencimento:", "20/01/2020",
            "Descrição Geral", "Proposta comercial referente à consultoria em estatística aplicada ao RPP. Total de 10 reuniões.",
            "ESCOPO", "x", "PREÇO", "O valor cobrado será de R$ 58.860,00 (cinquenta e oito mil).", "FORMA DE PAGAMENTO", "28 ddl",
        ),
        f"{ANTIGAS}/2019/BRAINFARMA/Acordo de Confidencialidade.pdf": b"%PDF",
        f"{ANTIGAS}/2019/BRAINFARMA/notas.xlsx": b"x",
        f"{RAIZ}/2019/BRAINFARMA/Proposta 356 19 rev01.docx": b"copia de 01 - Propostas: fora da faixa, ignorada",
        "CONTRATOS_OUT 2023/Contrato - Estatcamp & Marjan - assinado.pdf": b"%PDF",
    })
    return estatcamp


def test_pastas_com_faixa_de_anos() -> None:
    from commercial.propostas.sincronizacao import pastas_propostas

    assert pastas_propostas("Propostas_antigas: 2016-2020\n01 - Propostas: 2021-\n\nOutra") == [
        ("Propostas_antigas", 2016, 2020), ("01 - Propostas", 2021, None), ("Outra", None, None),
    ]


def test_classificacao_do_acervo() -> None:
    from commercial.propostas.sincronizacao import classificar

    assert classificar("Proposta 021 26.pdf") == "proposta"
    assert classificar("Pedido Compra 4100089244.pdf") == "pedido"
    assert classificar("PO-171382_v1_20260313.pdf") == "pedido"
    assert classificar("Acordo de Confidencialidade_BD.doc") == "nda"
    assert classificar("Contrato de Licença de Uso de Software - Template.docx") == "contrato"
    assert classificar("cnpj_estatcamp.pdf") == "cadastro"
    assert classificar("NF 1234.pdf") == "fiscal"
    assert classificar("dados.xlsx") == "dados"
    assert classificar("foto.png") == "outro"


def test_leitor_modelo_antigo() -> None:
    dados = ler(docx(
        "A: SAF-HOLLAND DO BRASIL", "A/C: Joice Garcia", "NÚMERO:", "169/16", "Data:", "26/07/2016", "Vencimento:",
        "26/08/2016", "Descrição Geral", "Proposta comercial referente à realização de um treinamento em MSA. Duração de 24 h.",
        "ESCOPO", "Estatística", "PREÇO", "O valor cobrado será de R$ 9.980,00 para 24 horas.", "FORMA DE PAGAMENTO", "28 ddl",
    ))
    assert (dados.cliente, dados.valor) == ("SAF-HOLLAND DO BRASIL", D("9980.00"))
    assert dados.titulo == "Realização de um treinamento em MSA"
    licenca = ler(docx("Proposta Comercial", "“ACTION STAT”", "Proposta No 141/16", "Entrega da Proposta: 26.08.2016"))
    assert licenca.titulo == "Licença ACTION STAT"


def test_historico_e_acervo(com_historico, biblioteca) -> None:
    from commercial.propostas.models import ArquivoSharePoint

    relatorio = sincronizar(com_historico, SharePointFalso(biblioteca), hoje=HOJE)
    antiga = Proposta.objects.get(ano=2019, numero=356)
    assert antiga.valor_total == D("58860.00") and antiga.revisao == 1 and antiga.etapa == EXPIRADA
    assert antiga.titulo.startswith("Consultoria em estatística aplicada ao RPP")
    assert antiga.arquivos.count() == 1  # a cópia em 01 - Propostas/2019 está fora da faixa

    acervo = {a.nome: a for a in ArquivoSharePoint.objects.all()}
    assert relatorio.arquivos == len(acervo)
    nda = acervo["Acordo de Confidencialidade.pdf"]
    assert (nda.categoria, nda.ano, nda.cliente, nda.pasta_raiz) == ("nda", 2019, antiga.cliente, ANTIGAS)
    assert acervo["Pedido Compra 4100089244 - prop_002 26.pdf"].proposta == Proposta.objects.get(ano=2026, numero=2)
    contrato = acervo["Contrato - Estatcamp & Marjan - assinado.pdf"]
    assert (contrato.categoria, contrato.ano, contrato.pasta_raiz) == ("contrato", 2023, "CONTRATOS_OUT 2023")

    del biblioteca[f"{ANTIGAS}/2019/BRAINFARMA/notas.xlsx"]
    sincronizar(com_historico, SharePointFalso(biblioteca), hoje=HOJE)
    assert not ArquivoSharePoint.objects.filter(nome="notas.xlsx").exists()


def test_proposta_so_na_planilha(estatcamp, biblioteca) -> None:
    caminho = f"{CONTROLE}/Propostas Treinamento e consultoria2026.xlsx"
    biblioteca[caminho] = xlsx(["VALIDAÇÃO", "040/26", "NCFARMA", datetime(2026, 10, 20), "CAROLINE"])
    sincronizar(estatcamp, SharePointFalso(biblioteca), hoje=HOJE)
    p = Proposta.objects.get(ano=2026, numero=40)
    assert (p.cliente.nome, p.titulo, p.valor_total, p.etapa) == ("NCFARMA", "VALIDAÇÃO", D("0"), ENVIADA)
    assert "Só na planilha" in p.observacoes and p.importada


TEXTO_CARTAO = """NÚMERO DE INSCRIÇÃO
02.195.435/0001-64
NOME EMPRESARIAL
ESTATCAMP CONSULTORIA ESTATISTICA EM QUALIDADE LTDA
LOGRADOURO
R MAESTRO JOAO SEPPE
NÚMERO
900
COMPLEMENTO
SALA 171
CEP
13.561-180
BAIRRO/DISTRITO
JARDIM PARAISO
MUNICÍPIO
SAO CARLOS
UF
SP
ENDEREÇO ELETRÔNICO
RUBENS@ESTATCAMP.COM.BR
TELEFONE
(16) 3376-2047
SITUAÇÃO CADASTRAL
DATA DA SITUAÇÃO CADASTRAL
ATIVA
Emitido no dia 09/09/2024 às 14:31:10 (data e hora de Brasília)."""


def test_cartao_cnpj_anexado_e_lido(estatcamp, monkeypatch, settings, tmp_path) -> None:
    from commercial.propostas.documentos import anexar_por_link, ler_cartao_cnpj
    from commercial.propostas.models import DocumentoEmpresa

    dados = ler_cartao_cnpj(TEXTO_CARTAO)
    assert dados["cnpj"] == "02.195.435/0001-64" and dados["emitido_em"] == "2024-09-09"
    assert dados["endereco"] == "R MAESTRO JOAO SEPPE, 900, SALA 171 — JARDIM PARAISO — SAO CARLOS/SP — CEP 13.561-180"

    settings.MEDIA_ROOT = str(tmp_path)
    monkeypatch.setattr("commercial.propostas.documentos.texto_pdf", lambda conteudo: TEXTO_CARTAO)

    class Compartilhado:
        versao = "c1"

        def por_link(self, link):
            return item("ALTERACAO_CONTRATO_CNPJ_ESTATCAMP/CNPJ.pdf", versao=self.versao)

        def baixar_link(self, link):
            return b"%PDF-1.4 cartao"

    sp = Compartilhado()
    link = "https://estatcamp.sharepoint.com/:b:/s/propostasestatcamp/IQAAYn5j"
    documento, mudou = anexar_por_link(estatcamp, link, DocumentoEmpresa.CARTAO_CNPJ, sp)
    estatcamp.refresh_from_db()
    assert mudou and documento.emitido_em == date(2024, 9, 9) and documento.vencido(HOJE)
    assert estatcamp.cnpj == "02.195.435/0001-64" and estatcamp.telefone == "(16) 3376-2047"
    assert (tmp_path / documento.arquivo.name).read_bytes() == b"%PDF-1.4 cartao"
    assert anexar_por_link(estatcamp, link, DocumentoEmpresa.CARTAO_CNPJ, sp) == (documento, False)
    sp.versao = "c2"
    assert anexar_por_link(estatcamp, link, DocumentoEmpresa.CARTAO_CNPJ, sp)[1] is True
    assert DocumentoEmpresa.objects.count() == 1
