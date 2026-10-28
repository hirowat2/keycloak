"""Propostas: lista do funil, cadastro com itens, detalhe com ações, histórico e impressão."""
import re
from typing import Any

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.utils import timezone

from commercial.propostas.constantes import (
    ETAPAS,
    ETAPAS_ABERTAS,
    ETAPAS_COM_CLIENTE,
    GANHA,
    PERDIDA,
    ROTULOS_ETAPA,
    ZERO,
)
from commercial.propostas.empresas import papel_ativo
from commercial.propostas.exportacao import planilha_xlsx
from commercial.propostas.models import Cliente, ItemCatalogo, Proposta
from commercial.propostas.servicos import (
    acoes_disponiveis,
    anotar,
    duplicar,
    executar,
    expirar_vencidas,
    salvar_proposta,
)
from commercial.propostas.web import GRUPOS_EDICAO, com_empresa, exigir, pode, responsaveis

from .forms import AnotacaoForm, ItensFormSet, PerdaForm, PropostaForm

VISOES = [
    ("abertas", "Abertas"),
    ("com_cliente", "Com o cliente"),
    ("acompanhar", "A acompanhar"),
    ("fechadas", "Fechadas"),
    ("todas", "Todas"),
]
PARAMETROS_DA_TELA = ("id", "novo", "editar", "cliente_novo", "imprimir")
NAO_ENCONTRADA = "Proposta não encontrada."


def _buscar(empresa, pk):
    """Proposta da empresa pelo id da URL ou do formulário; None se não existir (ou se o id não for número)."""
    pk = str(pk or "")
    return Proposta.objects.filter(empresa=empresa, pk=pk).first() if pk.isdigit() else None


def _erros(erro: ValidationError) -> str:
    return " ".join(erro.messages)


def _voltar(request, proposta: Proposta | None = None) -> str:
    return f"{request.path}?id={proposta.pk}" if proposta else request.path


def _formularios(request, empresa, proposta: Proposta):
    dados = request.POST if request.method == "POST" else None
    form = PropostaForm(dados, instance=proposta, empresa=empresa)
    itens = ItensFormSet(dados, instance=proposta, prefix="itens", form_kwargs={"empresa": empresa})
    return form, itens


def _salvar(request, empresa):
    """POST do cadastro. Devolve o redirect ou, com erro, os formulários para mostrar de novo."""
    pk = request.POST.get("id")
    proposta = _buscar(empresa, pk) if pk else Proposta(empresa=empresa)
    if proposta is None:
        messages.error(request, NAO_ENCONTRADA)
        return redirect(request.path), None
    form, itens = _formularios(request, empresa, proposta)
    if form.is_valid() and itens.is_valid():
        proposta = form.save(commit=False)
        novos = [f.instance for f in itens.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]
        removidos = [f.instance for f in itens.deleted_forms]
        try:
            proposta = salvar_proposta(proposta, novos, removidos, request.user)
        except ValidationError as erro:
            form.add_error(None, erro)
        else:
            messages.success(request, f"Proposta {proposta.codigo} salva.")
            return redirect(_voltar(request, proposta)), None
    return None, (form, itens)


def _executar(request, proposta: Proposta) -> Proposta:
    chave = request.POST.get("acao", "")
    dados = {"comentario": request.POST.get("comentario", ""), "motivo": request.POST.get("motivo", "")}
    if chave == "perder":
        perda = PerdaForm(request.POST)
        if not perda.is_valid():
            raise ValidationError("Informe o motivo da perda.")
        dados.update(perda.cleaned_data)
    proposta = executar(proposta, chave, request.user, papel_ativo(request), **dados)
    messages.success(request, f"{proposta.codigo}: {proposta.rotulo_etapa}.")
    return proposta


def _anotar(request, proposta: Proposta) -> Proposta:
    nota = AnotacaoForm(request.POST)
    if not nota.is_valid():
        raise ValidationError("Confira a data da próxima ação.")
    dados = nota.cleaned_data
    anotar(proposta, dados["texto"], request.user, dados["proxima_acao"], dados["proxima_acao_em"])
    messages.success(request, "Anotação registrada.")
    return proposta


def _duplicar(request, proposta: Proposta) -> Proposta:
    copia = duplicar(proposta, request.user)
    messages.success(request, f"Proposta {copia.codigo} criada como cópia de {proposta.codigo}.")
    return copia


ACOES_DO_DETALHE = {"executar": _executar, "anotar": _anotar, "duplicar": _duplicar}


def _post(request, empresa):
    """Ações do detalhe e do cadastro; devolve o redirect ou os formulários com erro."""
    if not exigir(request, GRUPOS_EDICAO):
        return redirect(request.get_full_path()), None
    acao = request.POST.get("action", "")
    if acao == "salvar":
        return _salvar(request, empresa)

    proposta = _buscar(empresa, request.POST.get("id"))
    tratar = ACOES_DO_DETALHE.get(acao)
    if proposta is None or tratar is None:
        messages.error(request, NAO_ENCONTRADA if proposta is None else "Ação desconhecida.")
        return redirect(request.path), None
    try:
        proposta = tratar(request, proposta)
    except ValidationError as erro:
        messages.error(request, _erros(erro))
    return redirect(_voltar(request, proposta)), None


def _impressao(request, proposta: Proposta) -> HttpResponse:
    """Proposta para o cliente: PDF (WeasyPrint) ou, sem ele no servidor, a página pronta para imprimir."""
    html = render_to_string("proposta_impressao.html", {"p": proposta, "hoje": timezone.localdate()}, request)
    if request.GET.get("imprimir") == "pdf":
        try:
            from weasyprint import HTML
        except (ImportError, OSError):
            messages.warning(request, "Gerador de PDF indisponível no servidor; use Imprimir → Salvar como PDF.")
        else:
            pdf = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
            resposta = HttpResponse(pdf, content_type="application/pdf")
            resposta["Content-Disposition"] = f'inline; filename="{proposta.codigo}.pdf"'
            return resposta
    return HttpResponse(html)


def _detalhe(context, request, proposta: Proposta) -> None:
    papel = papel_ativo(request)
    hoje = timezone.localdate()
    context.update(
        {
            "modo": "detalhe",
            "p": proposta,
            "itens": list(proposta.itens.select_related("item_catalogo")),
            "arquivos": proposta.arquivos.all(),
            "acoes": acoes_disponiveis(proposta, papel) if pode(request, GRUPOS_EDICAO) else [],
            "eventos": proposta.eventos.select_related("usuario"),
            "revisoes": proposta.revisoes.select_related("criada_por"),
            "perda_form": PerdaForm(),
            "nota_form": AnotacaoForm(initial={"proxima_acao": proposta.proxima_acao, "proxima_acao_em": proposta.proxima_acao_em}),
            "dias_para_vencer": proposta.dias_para_vencer(hoje),
            "acao_atrasada": proposta.acao_atrasada(hoje),
            "hoje": hoje,
        }
    )


def _filtrar(request, empresa, hoje):
    propostas = Proposta.objects.filter(empresa=empresa).select_related("cliente", "responsavel", "empresa")
    visao = request.GET.get("ver", "abertas")
    visao = visao if visao in dict(VISOES) else "abertas"
    if visao == "abertas":
        propostas = propostas.filter(etapa__in=ETAPAS_ABERTAS)
    elif visao == "com_cliente":
        propostas = propostas.filter(etapa__in=ETAPAS_COM_CLIENTE)
    elif visao == "acompanhar":
        propostas = propostas.filter(etapa__in=ETAPAS_ABERTAS, proxima_acao_em__lte=hoje)
    elif visao == "fechadas":
        propostas = propostas.exclude(etapa__in=ETAPAS_ABERTAS)
    etapa = request.GET.get("etapa", "")
    if etapa in ROTULOS_ETAPA:
        propostas = propostas.filter(etapa=etapa)
    responsavel = request.GET.get("responsavel", "")
    if responsavel.isdigit():
        propostas = propostas.filter(responsavel_id=responsavel)
    cliente = request.GET.get("cliente", "")
    if cliente.isdigit():
        propostas = propostas.filter(cliente_id=cliente)
    ano = request.GET.get("ano", "")
    if ano.isdigit():
        propostas = propostas.filter(ano=int(ano))
    busca = request.GET.get("q", "").strip()
    if busca:
        filtro = Q(titulo__icontains=busca) | Q(cliente__nome__icontains=busca) | Q(cliente__nome_fantasia__icontains=busca)
        partes = busca.upper().replace(empresa.prefixo.upper(), "").strip("-").split("-")
        curto = re.fullmatch(r"(\d{1,4})\s*[/ ]\s*(\d{2})", busca)  # como a equipe escreve: 021/26
        if len(partes) >= 2 and partes[0].isdigit() and partes[1].isdigit():
            filtro |= Q(ano=int(partes[0]), numero=int(partes[1]))
        elif curto:
            filtro |= Q(ano=2000 + int(curto.group(2)), numero=int(curto.group(1)))
        elif busca.isdigit():
            filtro |= Q(numero=int(busca))
        propostas = propostas.filter(filtro)
    return propostas, {"visao": visao, "etapa": etapa, "responsavel": responsavel, "cliente": cliente, "busca": busca, "ano": ano}


def _exportar(propostas: list[Proposta]):
    cabecalho = [
        "Número", "Título", "Cliente", "Etapa", "Responsável", "Valor total", "Desconto (%)", "Probabilidade (%)",
        "Valor ponderado", "Criada em", "Enviada em", "Válida até", "Fechada em", "Motivo da perda", "Origem",
    ]
    linhas = [
        [
            p.codigo, p.titulo, str(p.cliente), p.rotulo_etapa,
            (p.responsavel.get_full_name() or p.responsavel.username) if p.responsavel else "",
            p.valor_total, p.desconto, p.probabilidade, p.valor_ponderado, timezone.localtime(p.criada_em).date(),
            p.enviada_em, p.validade, p.fechada_em, p.get_motivo_perda_display(), p.get_origem_display(),
        ]
        for p in propostas
    ]
    return planilha_xlsx(f"propostas_{timezone.localdate():%Y%m%d}", [("Propostas", cabecalho, linhas)])


def _lista(context, request, empresa) -> HttpResponse | None:
    hoje = timezone.localdate()
    consulta, filtros = _filtrar(request, empresa, hoje)
    propostas = list(consulta)
    if request.GET.get("exportar") == "xlsx":
        return _exportar(propostas)
    parametros = request.GET.copy()
    for chave in ("ver", "exportar", *PARAMETROS_DA_TELA):
        parametros.pop(chave, None)
    abertas = [p for p in propostas if p.aberta]
    context.update(
        {
            "modo": "lista",
            "propostas": propostas,
            "visoes": VISOES,
            "etapas": ETAPAS,
            "responsaveis": responsaveis(empresa),
            "cliente_filtro": Cliente.objects.filter(empresa=empresa, pk=filtros["cliente"]).first() if filtros["cliente"] else None,
            "parametros": parametros.urlencode(),
            "total_valor": sum((p.valor_total for p in propostas), ZERO),
            "total_ponderado": sum((p.valor_ponderado for p in abertas), ZERO),
            "ganhas_valor": sum((p.valor_total for p in propostas if p.etapa == GANHA), ZERO),
            "perdidas_qtd": sum(1 for p in propostas if p.etapa == PERDIDA),
            "sem_clientes": not Cliente.objects.filter(empresa=empresa).exists(),
            "tem_sharepoint": bool(empresa.sharepoint_site),
            "hoje": hoje,
            **filtros,
        }
    )
    return None


def _cadastro(context, request, empresa, forms=None) -> bool:
    """Formulário de nova proposta ou de edição de rascunho; False se a proposta pedida não pode ser editada."""
    if forms is None:
        pk = request.GET.get("editar")
        proposta = _buscar(empresa, pk) if pk else Proposta(empresa=empresa)
        if proposta is None or (proposta.pk and not proposta.editavel):
            messages.error(request, "Só o rascunho pode ser editado. Crie uma revisão para mudar uma proposta enviada.")
            return False
        if not proposta.pk:
            proposta.responsavel = request.user
            cliente = request.GET.get("cliente_novo", "")
            if cliente.isdigit():
                proposta.cliente = Cliente.objects.filter(empresa=empresa, pk=cliente).first()
        forms = _formularios(request, empresa, proposta)
    form, itens = forms
    catalogo = ItemCatalogo.objects.filter(empresa=empresa, ativo=True)
    context.update(
        {
            "modo": "form",
            "form": form,
            "itens": itens,
            "editando": form.instance if form.instance.pk else None,
            # Preço, unidade e descrição de cada item do catálogo, para preencher a linha ao escolher.
            "catalogo_js": {str(i.pk): {"nome": i.nome, "unidade": i.unidade, "preco": f"{i.preco:.2f}".replace(".", ",")} for i in catalogo},
            "desconto_maximo": empresa.desconto_maximo,
        }
    )
    return True


@com_empresa
def view(context, request, empresa) -> dict[str, Any] | HttpResponse:
    context["pode_editar"] = pode(request, GRUPOS_EDICAO)
    if request.method == "POST":
        resposta, forms = _post(request, empresa)
        if resposta is not None:
            return resposta
        _cadastro(context, request, empresa, forms)
        return {"request": request, "context": context}

    for proposta in expirar_vencidas(empresa):
        messages.info(request, f"{proposta.codigo} expirou: a validade ({proposta.validade:%d/%m/%Y}) passou sem resposta.")

    if request.GET.get("novo") or request.GET.get("editar"):
        if context["pode_editar"] and _cadastro(context, request, empresa):
            return {"request": request, "context": context}
        if not context["pode_editar"]:
            messages.error(request, "Você não tem permissão para esta operação.")
        return redirect(request.path)

    pk = request.GET.get("id")
    if pk:
        proposta = _buscar(empresa, pk)
        if proposta is None:
            messages.error(request, NAO_ENCONTRADA)
            return redirect(request.path)
        if request.GET.get("imprimir"):
            return _impressao(request, proposta)
        _detalhe(context, request, proposta)
        return {"request": request, "context": context}

    resposta = _lista(context, request, empresa)
    return resposta or {"request": request, "context": context}
