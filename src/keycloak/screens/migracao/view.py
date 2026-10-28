"""Migração da VM (README_migracao_vm.md): comandos prontos para a VM e o destino, host novo e usuários incompletos."""
from typing import Any

from django import forms

from keycloak.automacao import manutencao as servico
from keycloak.automacao.api import url_publica
from keycloak.automacao.web import api, com_realm, executar
from keycloak.models import Aplicacao


class VmForm(forms.Form):
    vm = forms.CharField(label="Acesso SSH à VM", max_length=200, initial="usuario@vm-antiga", required=False)
    container = forms.CharField(label="Container do Keycloak na VM", max_length=200, initial="keycloak", required=False,
                                help_text="docker ps --format '{{.Names}}\\t{{.Image}}' na VM")
    destino = forms.ChoiceField(label="Destino", choices=[("compose", "docker compose (esta máquina)"), ("k8s", "Kubernetes (contexto atual do kubectl)")])


class HostForm(forms.Form):
    antigo = forms.URLField(label="Host antigo", assume_scheme="https", help_text="ex.: https://sso.vm-antiga.local")
    novo = forms.URLField(label="Host novo", assume_scheme="https")


def comandos(vm: str, container: str, destino: str) -> dict[str, list[str]]:
    """Os passos 1, A e B do guia, já com os nomes preenchidos (o script decide entre H2 e Postgres)."""
    k8s = destino == "k8s"
    return {
        "vm": [
            f"scp scripts/exportar_vm.sh {vm}:",
            f"ssh {vm} sh exportar_vm.sh {container}",
        ],
        "a": [
            f"scp {vm}:kc-export.tgz .",
            "make k8s-importar-realms" if k8s else "make importar-realms",
        ],
        "b": [
            f"scp {vm}:keycloak.dump .",
            "make k8s-restaurar-dump" if k8s else "make restaurar-dump",
        ],
        "limpar": [f"ssh {vm} rm -f kc-export.tgz keycloak.dump", "rm -rf export/kc-export kc-export.tgz keycloak.dump"],
    }


@com_realm()
def view(context, request, realm) -> dict[str, Any]:
    vm_form = VmForm(request.GET if "vm" in request.GET else None)
    dados = vm_form.cleaned_data if vm_form.is_valid() else {"vm": "usuario@vm-antiga", "container": "keycloak", "destino": "compose"}
    plano = None
    if request.method == "POST":
        host_form = HostForm(request.POST)
        if host_form.is_valid():
            antigo, novo = host_form.cleaned_data["antigo"], host_form.cleaned_data["novo"]
            plano = executar(request, realm, Aplicacao.HOST, lambda simular: servico.trocar_host(api(), realm, antigo, novo, simular))
    else:
        host_form = HostForm(initial={"novo": url_publica()})
    context.update(
        {
            "vm_form": vm_form if vm_form.is_bound else VmForm(initial=dados),
            "comandos": comandos(dados["vm"] or "usuario@vm-antiga", dados["container"] or "keycloak", dados["destino"]),
            "host_form": host_form,
            "plano": plano,
            "incompletos": servico.usuarios_incompletos(api(), realm) if request.GET.get("incompletos") == "1" else None,
        }
    )
    return {"request": request, "context": context}
