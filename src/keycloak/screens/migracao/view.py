"""Migração da VM (README_migracao_vm.md): comandos prontos para a VM e o destino, host novo e usuários incompletos."""
import re
from os import environ
from typing import Any

from django import forms

from keycloak.automacao import dump
from keycloak.automacao import manutencao as servico
from keycloak.automacao.api import url_publica
from keycloak.automacao.web import api, com_realm, executar
from keycloak.models import Aplicacao


DESTINOS = [
    ("akamai", "Kubernetes + Akamai Managed PostgreSQL (produção)"),
    ("k8s", "Kubernetes com Postgres no cluster (keycloak-db)"),
    ("compose", "docker compose (esta máquina)"),
]
ARGUMENTO_SEGURO = re.compile(r"^[A-Za-z0-9._@:-]*$")


class VmForm(forms.Form):
    vm = forms.CharField(label="Acesso SSH à VM", max_length=200, initial="usuario@vm-antiga", required=False)
    container = forms.CharField(label="Container do Keycloak na VM", max_length=200, initial="keycloak", required=False,
                                help_text="docker ps --format '{{.Names}}\\t{{.Image}}' na VM")
    destino = forms.ChoiceField(label="Destino", choices=DESTINOS)
    akamai = forms.CharField(label="Host do banco na Akamai", max_length=255, required=False,
                             help_text="Host primário do cluster (Connection Details); só no destino Akamai")
    namespace = forms.CharField(label="Namespace do Keycloak", max_length=63, required=False, initial="keycloak",
                                help_text="Kubernetes: onde está o deploy/keycloak")

    def clean_vm(self) -> str:
        # Aceita "ssh root@host" colado do terminal: o campo é só o destino (usuario@host)
        vm = self.cleaned_data["vm"].strip()
        if vm.startswith("ssh "):
            vm = vm[4:].strip()
        if " " in vm:
            raise forms.ValidationError("Use só usuario@host, sem espaços (ex.: root@170.187.168.183).")
        return vm

    def clean(self) -> dict:
        # Os valores vão para comandos de shell copiados pelo usuário: nada além de nomes e hosts
        dados = super().clean()
        for campo in ("vm", "container", "akamai", "namespace"):
            if not ARGUMENTO_SEGURO.match(dados.get(campo) or ""):
                self.add_error(campo, "Só letras, números e . _ @ : -")
        return dados


class HostForm(forms.Form):
    antigo = forms.URLField(label="Host antigo", assume_scheme="https", help_text="ex.: https://sso.vm-antiga.local")
    novo = forms.URLField(label="Host novo", assume_scheme="https")


def comandos(vm: str, container: str, destino: str, akamai: str = "", namespace: str = "keycloak") -> dict[str, list[str]]:
    """Os passos 1, A e B do guia, já com os nomes preenchidos (o script decide entre H2 e Postgres)."""
    ns = "" if namespace in ("", "keycloak") else f" K8S_NS={namespace}"
    if destino == "akamai":
        a = f"make k8s-importar-realms{ns}"
        b = [f"make akamai-testar AKAMAI_DB_HOST={akamai or '<host-primario>'}{ns}",
             f"make akamai-restaurar-dump AKAMAI_DB_HOST={akamai or '<host-primario>'}{ns}"]
    elif destino == "k8s":
        a, b = f"make k8s-importar-realms{ns}", [f"make k8s-restaurar-dump{ns}"]
    else:
        a, b = "make importar-realms", ["make restaurar-dump"]
    return {
        "vm": [
            f"scp scripts/exportar_vm.sh {vm}:",
            f"ssh {vm} sh exportar_vm.sh {container}",
        ],
        "a": [f"scp {vm}:kc-export.tgz .", a],
        "b": [f"scp {vm}:keycloak.dump .", *b],
        "limpar": [f"ssh {vm} rm -f kc-export.tgz keycloak.dump", "rm -rf export/kc-export kc-export.tgz keycloak.dump"],
    }


def padroes() -> dict[str, str]:
    """No cluster, o assistente já sabe o namespace e o host do banco (KEYCLOAK_DB_HOST): começa no destino certo."""
    host = environ.get("KEYCLOAK_DB_HOST", "")
    no_cluster = dump.pode_reiniciar()
    destino = "compose"
    if no_cluster:
        destino = "k8s" if host in ("", "keycloak-db") else "akamai"
    return {
        "vm": "usuario@vm-antiga", "container": "keycloak", "destino": destino,
        "akamai": host if destino == "akamai" else "",
        "namespace": dump._namespace() if no_cluster else "keycloak",
    }


@com_realm()
def view(context, request, realm) -> dict[str, Any]:
    vm_form = VmForm(request.GET if "vm" in request.GET else None)
    dados = {**padroes(), **{k: v for k, v in vm_form.cleaned_data.items() if v}} if vm_form.is_valid() else padroes()
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
            "comandos": comandos(dados["vm"], dados["container"], dados["destino"], dados["akamai"], dados["namespace"]),
            "destino": dados["destino"],
            "akamai": dados["akamai"],
            "host_form": host_form,
            "plano": plano,
            "incompletos": servico.usuarios_incompletos(api(), realm) if request.GET.get("incompletos") == "1" else None,
        }
    )
    return {"request": request, "context": context}
