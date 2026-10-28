from decimal import Decimal

import pytest


@pytest.fixture
def empresa(db):
    from commercial.propostas.models import Empresa

    return Empresa.objects.create(nome="Empresa Teste", slug="teste", prefixo="PC", desconto_maximo=Decimal("10"))


@pytest.fixture
def cliente(empresa):
    from commercial.propostas.models import Cliente, Contato

    cliente = Cliente.objects.create(empresa=empresa, nome="Cliente Ltda", documento="12.345.678/0001-90")
    Contato.objects.create(cliente=cliente, nome="Ana Compras", email="ana@cliente.com", principal=True)
    return cliente


@pytest.fixture
def consultoria(empresa):
    from commercial.propostas.models import ItemCatalogo

    return ItemCatalogo.objects.create(empresa=empresa, codigo="CONS", nome="Consultoria", unidade="h", preco=Decimal("200"))


@pytest.fixture
def usuario(db):
    from django.contrib.auth.models import Group, User

    def criar(*grupos, **extras):
        # Contas do login corporativo (sem senha) só passam pelo middleware com e-mail da lista liberada.
        extras.setdefault("email", "hiro@estatcamp.com.br")
        user = User.objects.create_user(f"u{User.objects.count()}", **extras)
        user.groups.add(*(Group.objects.get_or_create(name=nome)[0] for nome in grupos))
        return user

    return criar


@pytest.fixture
def nova_proposta(empresa, cliente, consultoria):
    """Rascunho com um item do catálogo: ``nova_proposta(quantidade=10, preco=..., desconto=...)``."""
    from commercial.propostas.models import ItemProposta, Proposta
    from commercial.propostas.servicos import salvar_proposta

    def criar(quantidade=Decimal("10"), preco=None, desconto=Decimal("0"), usuario=None, **campos):
        proposta = Proposta(empresa=empresa, cliente=cliente, titulo=campos.pop("titulo", "Implantação"), **campos)
        item = ItemProposta(
            item_catalogo=consultoria, descricao="Consultoria", unidade="h", quantidade=quantidade,
            preco_unitario=consultoria.preco if preco is None else preco, desconto=desconto,
        )
        return salvar_proposta(proposta, [item], [], usuario)

    return criar


@pytest.fixture(autouse=True)
def estaticos_sem_manifesto(settings):
    """O manifesto dos estáticos só existe depois do collectstatic (feito no entrypoint do Docker)."""
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
