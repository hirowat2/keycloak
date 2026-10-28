# Propostas comerciais — regras de negócio

Referência técnica das regras implementadas em `src/commercial/propostas/`. O uso das telas está no [README](../README.md).

## 1. Práticas de mercado adotadas

| Prática | Como está no sistema | Onde |
| --- | --- | --- |
| Numeração única e rastreável | `<prefixo>-<ano>-<sequência>` por empresa, gerada no servidor com trava na linha da empresa | `servicos._proximo_numero` |
| Funil com etapas padronizadas e probabilidade | Nove etapas; probabilidade sugerida por etapa (`PROBABILIDADE_PADRAO`) e previsão ponderada | `constantes.py`, `indicadores.py` |
| Preço de tabela e alçada de desconto | Catálogo com preço de tabela; desconto medido sobre a tabela; acima do limite da empresa, aprovação de um Master | `ItemProposta.referencia`, `Proposta.precisa_aprovacao`, `ACOES` |
| Documento enviado é imutável | Só o rascunho é editável; mudança após o envio gera revisão com cópia da versão anterior | `salvar_proposta`, `executar("revisar")`, `RevisaoProposta` |
| Validade e expiração | Validade padrão por empresa, renovada no envio se vencida; expiração automática das propostas com o cliente | `executar("enviar")`, `expirar_vencidas` |
| Follow-up disciplinado | Próxima ação com data; alertas de atrasadas e de propostas com o cliente sem próxima ação | `anotar`, `indicadores.painel` |
| Motivo de perda obrigatório | Lista fechada de motivos e concorrente; análise no painel | `executar("perder")`, `indicadores.motivos_perda` |
| Trilha de auditoria | Histórico por proposta (`EventoProposta`) e `django-auditlog` em todos os modelos | `servicos.registrar` |
| Indicadores de vendas | Pipeline, previsão ponderada, conversão (quantidade e valor), ticket médio, ciclo de venda, resultado por responsável | `indicadores.py` |
| Separação por empresa e papel | Dados isolados por empresa; papéis Limited, Tech, Master e Admin | `empresas.py`, `web.com_empresa` |

## 2. Etapas e transições

As ações ficam em `servicos.ACOES`. Cada uma diz de quais etapas sai, para qual vai e quais papéis podem usá-la; `acoes_disponiveis` filtra pela etapa e pelo papel, e `executar` recusa (com `ValidationError`) qualquer ação fora disso.

| Ação | De | Para | Papéis |
| --- | --- | --- | --- |
| `solicitar_aprovacao` | Rascunho (só com desconto acima do limite) | Em aprovação | Tech, Master, Admin |
| `aprovar` | Em aprovação | Aprovada | Master, Admin |
| `reprovar` | Em aprovação | Rascunho | Master, Admin |
| `enviar` | Rascunho (só com desconto dentro do limite), Aprovada | Enviada | Tech, Master, Admin |
| `negociar` | Enviada | Em negociação | Tech, Master, Admin |
| `ganhar` | Enviada, Em negociação | Ganha | Tech, Master, Admin |
| `perder` | Qualquer aberta | Perdida | Tech, Master, Admin |
| `cancelar` | Qualquer aberta | Cancelada | Tech, Master, Admin |
| `revisar` | Em aprovação, Aprovada, Enviada, Em negociação, Expirada | Rascunho (revisão + 1) | Tech, Master, Admin |
| (automática) | Enviada, Em negociação com validade vencida | Expirada | — |

Enviar ou pedir aprovação exige ao menos um item. Ao entrar numa etapa, a probabilidade volta ao valor sugerido. Ganha, perdida e cancelada gravam `fechada_em` e limpam a próxima ação; a expiração grava `fechada_em` com o dia em que foi detectada.

## 3. Valores

- `ItemProposta.total = quantidade × preço unitário × (1 − desconto/100)`, arredondado a centavos (meio para cima).
- `ItemProposta.referencia = quantidade × max(preço de tabela, preço unitário)`. O preço de tabela é copiado do catálogo quando o item entra na proposta e não acompanha mudanças posteriores do catálogo. Item avulso tem preço de tabela zero, então a referência é o próprio preço.
- `Proposta.valor_total` e `Proposta.valor_referencia` são somas guardadas, recalculadas por `servicos.recalcular` sempre que os itens mudam (pelas telas ou pelo admin).
- `Proposta.desconto = (1 − valor_total / valor_referencia) × 100`. A aprovação é exigida quando ele passa de `Empresa.desconto_maximo`.

## 4. Indicadores

Todos em `indicadores.painel`, sobre as propostas da empresa (e do responsável, se filtrado):

- **Pipeline:** soma das propostas enviadas e em negociação, no momento da consulta.
- **Previsão ponderada:** soma de `valor_total × probabilidade` das propostas abertas.
- **Conversão:** propostas ganhas ÷ decididas pelo cliente (ganhas, perdidas e expiradas) com `fechada_em` no período, em quantidade e em valor. Canceladas são decisão interna e ficam fora.
- **Ticket médio:** valor ganho ÷ quantidade de ganhas no período.
- **Ciclo de venda:** média de dias entre `enviada_em` e `fechada_em` das ganhas no período.

## 5. Decisões e pontos em aberto

- **Revisão no mesmo registro.** A proposta revisada mantém o número e ganha o sufixo `-R<n>`; as versões anteriores ficam em `RevisaoProposta.dados` (JSON). Assim o funil e os indicadores contam a oportunidade uma vez só.
- **Expiração preguiçosa.** As telas de painel e propostas expiram o que venceu ao abrir; o comando `expirar_propostas` existe para agendar e manter os números em dia mesmo sem acesso.
- **Desconto por item, não global.** Um desconto geral na proposta pode ser feito aplicando o mesmo percentual em todos os itens.
- **Sem envio de e-mail pelo sistema.** O PDF é baixado e enviado pelo vendedor; "Marcar como enviada" registra o envio. Integrar com e-mail ou assinatura eletrônica é um próximo passo natural.
