"""Metodologia: como o sistema funciona, com diagramas (Mermaid) e o passo a passo ilustrado."""
import os
from typing import Any

from django.conf import settings

from commercial.propostas.constantes import ETAPAS, PROBABILIDADE_PADRAO
from commercial.propostas.web import com_empresa

# Passo a passo: (arquivo em media/metodologia/, título, explicação). Os prints são gerados por
# documents/prints/capturar.mjs sobre uma base com os dados reais do SharePoint.
PASSOS = [
    ("01-painel.png", "Painel comercial",
     "Ao entrar, o painel mostra o pipeline com os clientes, a previsão ponderada, o vendido, a conversão, o ticket médio e o "
     "ciclo de venda do período, os alertas do dia e os gráficos de funil, vendas por mês, resultado por responsável e motivos de perda."),
    ("02-propostas.png", "Lista de propostas",
     "O funil em abas (abertas, com o cliente, a acompanhar, fechadas, todas), com filtros por etapa e responsável, busca pelo "
     "número da equipe (021/26), título ou cliente, e exportação para Excel. Clique na linha para abrir a proposta."),
    ("03-nova-proposta.png", "Nova proposta",
     "Cliente, contato, responsável, condições e acompanhamento, em seções. Nos itens, escolha do catálogo (descrição, unidade e "
     "preço vêm dele) ou digite um item avulso; o total e o aviso de desconto acima da alçada aparecem enquanto você digita."),
    ("04-rascunho.png", "Rascunho salvo e alçada de desconto",
     "A proposta recebe o número. Com desconto acima do limite da empresa, o sistema pede aprovação antes do envio: o botão "
     "“Marcar como enviada” dá lugar a “Pedir aprovação”."),
    ("05-aprovacao.png", "Aprovação pelo gestor",
     "Na etapa “Em aprovação”, um Master vê o desconto pedido e aprova ou devolve ao rascunho. Tudo fica no histórico."),
    ("06-detalhe-importada.png", "Proposta importada do SharePoint",
     "Número original, documento e pedido de compra com link para o SharePoint, histórico da importação e a etapa deduzida "
     "(ganha, pelo pedido de compra na pasta do cliente)."),
    ("07-perda.png", "Fechamento com motivo",
     "Ao registrar a perda, o motivo é obrigatório e alimenta o gráfico de motivos de perda do painel."),
    ("08-impressao.png", "Proposta para o cliente",
     "Versão para imprimir ou PDF, com dados da empresa, cliente, escopo, itens, condições, validade, termos e campo de aceite. "
     "Preço de tabela e observações internas não aparecem."),
    ("09-clientes.png", "Clientes",
     "Contas e contatos, com quantas propostas cada cliente tem, quantas estão abertas e quanto já comprou; as pastas do "
     "SharePoint ligadas a cada cliente ficam no cadastro."),
    ("10-catalogo.png", "Produtos e serviços",
     "Preços de tabela usados como referência dos descontos. Só gestores alteram; propostas já feitas mantêm o preço da época."),
    ("11-sincronizacao.png", "Sincronização com o SharePoint",
     "Configuração, teste de conexão, simulação, execução e histórico de cada rodada, com os avisos e conflitos encontrados."),
    ("12-historico.png", "Histórico",
     "Propostas de 2016 em diante, ano a ano: emitidas, proposto, ganhas, vendido, conversão, ticket e clientes; a matriz de "
     "clientes ao longo dos anos e as linhas de serviço por ano. Os anos e clientes levam à lista de propostas filtrada."),
    ("13-contratos.png", "Contratos e documentos",
     "Documentos da empresa (cartão CNPJ com aviso de validade), contratos fechados por ano com pedidos e contratos de cada um, "
     "e o acervo do SharePoint por categoria: pedidos, contratos, NDAs, cadastros, fiscais e dados."),
]


@com_empresa
def view(context, request, empresa) -> dict[str, Any]:
    pasta = os.path.join(settings.MEDIA_ROOT, "metodologia")
    context.update(
        {
            "passos": [
                {"imagem": f"metodologia/{arquivo}", "titulo": titulo, "texto": texto, "numero": i}
                for i, (arquivo, titulo, texto) in enumerate(PASSOS, start=1)
                if os.path.exists(os.path.join(pasta, arquivo))
            ],
            "probabilidades": [(rotulo, PROBABILIDADE_PADRAO[chave]) for chave, rotulo in ETAPAS],
        }
    )
    return {"request": request, "context": context}
