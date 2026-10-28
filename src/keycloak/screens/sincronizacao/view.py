"""Sincronização com o SharePoint: configuração da empresa, teste de conexão, execução e histórico."""
import logging
import os
import threading
from typing import Any

from django.contrib import messages
from django.db import connection
from django.shortcuts import redirect

from commercial.propostas.empresas import empresas_do_usuario
from commercial.propostas.models import ExecucaoSincronizacao
from commercial.propostas.sharepoint import SharePointClient, SharePointErro
from commercial.propostas.sincronizacao import em_andamento, pastas_propostas, sincronizar
from commercial.propostas.web import GRUPOS_GESTAO, com_empresa, exigir, pode

CREDENCIAIS = ("SHAREPOINT_TENANT_ID", "SHAREPOINT_CLIENT_ID", "SHAREPOINT_CLIENT_SECRET")


def intervalo_automatico() -> int:
    """Minutos entre as sincronizações automáticas do container (0: desligadas)."""
    try:
        return max(int(os.environ.get("SHAREPOINT_INTERVALO_MINUTOS", "0")), 0)
    except ValueError:
        return 0


def _testar(request, empresa) -> None:
    try:
        cliente = SharePointClient.criar(empresa.sharepoint_site)
        partes = []
        for pasta, inicio, fim in pastas_propostas(empresa.sharepoint_pasta):
            anos = sorted(
                int(i.nome) for i in cliente.listar(pasta)
                if i.pasta and i.nome.isdigit() and max(inicio or 0, empresa.sharepoint_desde) <= int(i.nome) <= (fim or 9999)
            )
            partes.append(f"“{pasta}”: {f'{anos[0]}–{anos[-1]}' if anos else 'nenhum ano'}")
        planilhas = [i.nome for i in cliente.listar(empresa.sharepoint_controle) if i.nome.lower().endswith(".xlsx")]
    except SharePointErro as erro:
        messages.error(request, f"Conexão falhou: {erro}")
        return
    messages.success(request, f"Conexão ok. Anos lidos — {'; '.join(partes)}. Planilhas de controle: {len(planilhas)}.")


def _rodar(empresa, simular: bool, usuario) -> None:
    """Corpo da thread: o resultado (ou o erro) fica registrado na execução."""
    try:
        sincronizar(empresa, simular=simular, usuario=usuario)
    except Exception:  # registrado na execução; aqui só não deixa a thread morrer em silêncio
        logging.getLogger(__name__).exception("Sincronização com o SharePoint falhou")
    finally:
        connection.close()


def _executar(request, empresa, simular: bool) -> None:
    """Dispara a sincronização em segundo plano: a primeira carga do histórico leva dezenas de minutos."""
    if em_andamento(empresa):
        messages.warning(request, "Já há uma sincronização em andamento; acompanhe abaixo.")
        return
    threading.Thread(target=_rodar, args=(empresa, simular, request.user), daemon=True).start()
    tipo = "Simulação iniciada (nada será gravado)" if simular else "Sincronização iniciada"
    messages.success(request, f"{tipo} em segundo plano. Recarregue a página para acompanhar; o resultado aparece no histórico.")


@com_empresa
def view(context, request, empresa) -> dict[str, Any]:
    pode_executar = pode(request, GRUPOS_GESTAO) and bool(empresa.sharepoint_site)
    if request.method == "POST":
        if exigir(request, GRUPOS_GESTAO):
            acao = request.POST.get("action")
            if not empresa.sharepoint_site:
                messages.error(request, "Esta empresa não tem site do SharePoint configurado.")
            elif acao == "testar":
                _testar(request, empresa)
            elif acao in ("simular", "sincronizar"):
                _executar(request, empresa, simular=acao == "simular")
        return redirect(request.path)

    execucoes = list(ExecucaoSincronizacao.objects.filter(empresa=empresa).select_related("usuario")[:20])
    ultima = next((e for e in execucoes if not e.em_andamento), None)
    context.update(
        {
            "credenciais": [(nome, bool(os.environ.get(nome))) for nome in CREDENCIAIS],
            "credenciais_ok": all(os.environ.get(nome) for nome in CREDENCIAIS),
            "intervalo": intervalo_automatico(),
            "execucoes": execucoes,
            "ultima": ultima,
            "andamento": em_andamento(empresa),
            "pode_executar": pode_executar,
            "outras_com_site": [e for e in empresas_do_usuario(request.user).order_by("nome") if e.sharepoint_site and e.pk != empresa.pk],
            "importadas": empresa.propostas.exclude(sharepoint_item="").count(),
        }
    )
    return {"request": request, "context": context}
