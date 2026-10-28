# CommercialProposal — Manual do usuário

O CommercialProposal controla as propostas comerciais das empresas do grupo (MBRL, Estatcamp e Estat Analytics), do rascunho ao fechamento. Cada empresa tem clientes, catálogo, numeração e propostas independentes. O sistema guarda os itens com o preço de tabela, pede aprovação quando o desconto passa da alçada, controla validade e próxima ação, mantém o histórico e as revisões de cada proposta, gera o PDF para o cliente e mostra os indicadores de venda no painel.

## Sumário

1. [Acesso](#1-acesso)
2. [Primeiros passos](#2-primeiros-passos)
3. [As telas](#3-as-telas)
4. [O funil de uma proposta](#4-o-funil-de-uma-proposta)
5. [Criar e editar uma proposta](#5-criar-e-editar-uma-proposta)
6. [Desconto e aprovação](#6-desconto-e-aprovação)
7. [Envio, validade e follow-up](#7-envio-validade-e-follow-up)
8. [Revisões](#8-revisões)
9. [Fechamento: ganha, perdida ou cancelada](#9-fechamento-ganha-perdida-ou-cancelada)
10. [Painel e indicadores](#10-painel-e-indicadores)
11. [Perguntas frequentes](#11-perguntas-frequentes)
12. [Administração e instalação](#12-administração-e-instalação)
13. [SharePoint](#13-sharepoint)
14. [Histórico e contratos](#14-histórico-e-contratos)

---

## 1. Acesso

Entre pelo endereço do sistema e clique em **Entrar com a conta corporativa**. O login é feito pela conta da empresa (Keycloak). Só entram os e-mails liberados no código (veja [documents/controle_de_acesso.md](documents/controle_de_acesso.md)).

Você vê as empresas liberadas para os seus grupos, e em cada uma tem um papel. O menu lateral e os botões mostram só o que esse papel permite:

| Papel | O que pode fazer |
| --- | --- |
| **Limited** | Consultar painel, propostas (inclusive PDF e Excel), clientes e catálogo |
| **Tech** (vendedor) | Tudo do Limited, mais cadastrar clientes e criar, enviar, acompanhar e fechar propostas |
| **Master** (gestor) | Tudo do Tech, mais aprovar descontos acima da alçada e manter o catálogo de preços |
| **Admin** | Tudo, em todas as empresas, mais a área de Administração |

O papel pode mudar de uma empresa para outra. Com acesso a mais de uma, troque a empresa no seletor do menu lateral.

## 2. Primeiros passos

1. Um **Admin** confere a empresa em *Administração → Empresas*: razão social, CNPJ, endereço e contatos (saem no PDF), **prefixo da numeração**, **validade padrão**, **desconto máximo sem aprovação**, condições de pagamento padrão e **termos e condições gerais**.
2. Um **Master** cadastra os produtos e serviços em **Produtos e serviços**, com o preço de tabela.
3. Cadastre os **clientes** e seus contatos.
4. Crie a primeira **proposta** e acompanhe o **painel**.

## 3. As telas

| Tela | Para que serve |
| --- | --- |
| **Painel comercial** | Pipeline, previsão ponderada, vendido no período, conversão, ticket médio, ciclo de venda, funil, motivos de perda, resultado por responsável e alertas (aprovação pendente, follow-up atrasado, propostas vencendo) |
| **Propostas** | Lista do funil com filtros (etapa, responsável, busca por número, título ou cliente) e exportação para Excel. Clique numa linha para abrir o detalhe |
| **Clientes** | Contas e contatos, com quantas propostas cada cliente tem e quanto já comprou. Clientes com histórico são inativados, nunca apagados |
| **Produtos e serviços** | Catálogo com preço de tabela, a referência dos descontos |

## 4. O funil de uma proposta

```text
Rascunho ──► (Em aprovação ──► Aprovada) ──► Enviada ──► Em negociação ──► Ganha
   ▲              │ devolvida                   │               │
   │              ▼                             ├───────────────┴──► Perdida (com motivo)
   └──── Criar revisão ◄────────────────────────┤
                                                └── validade vencida ──► Expirada
Qualquer etapa aberta ──► Cancelada
```

| Etapa | Probabilidade sugerida | Observação |
| --- | --- | --- |
| Rascunho | 10% | Única etapa editável |
| Em aprovação | 10% | Desconto acima da alçada, esperando um Master |
| Aprovada internamente | 20% | Pronta para enviar |
| Enviada ao cliente | 40% | Conta no pipeline e expira na validade |
| Em negociação | 60% | Conta no pipeline e expira na validade |
| Ganha | 100% | Entra no vendido do painel |
| Perdida / Expirada / Cancelada | 0% | Fechadas |

A probabilidade muda sozinha com a etapa; o vendedor pode ajustá-la no rascunho se souber mais.

## 5. Criar e editar uma proposta

Em **Propostas → + Nova proposta** (ou **+ Proposta** na lista de clientes):

- **Cliente, contato, responsável e origem** (indicação, site, prospecção, evento, cliente da base, parceiro).
- **Condições:** validade (sugerida pela empresa), condições de pagamento, prazo de entrega e o texto de **apresentação e escopo**, que sai no PDF antes dos itens.
- **Acompanhamento:** probabilidade, previsão de fechamento, **próxima ação** e data, e observações internas (não saem no PDF).
- **Itens:** escolha um item do catálogo (descrição, unidade e preço vêm dele) ou digite um item avulso. Informe quantidade, preço unitário e desconto da linha. O total e o aviso de desconto acima da alçada aparecem enquanto você digita. Valores aceitam o formato brasileiro (`1.234,56`).

A proposta recebe o número na hora de salvar: `<prefixo>-<ano>-<sequência>`, por exemplo `EST-2026-0007`. A sequência é por empresa e recomeça a cada ano.

**Duplicar** cria uma proposta nova (outro número, rascunho) com os mesmos dados e itens. Use para propostas parecidas ou para reaproveitar uma perdida.

## 6. Desconto e aprovação

O desconto é medido sobre o **preço de tabela** do catálogo, não sobre o preço digitado: baixar o preço unitário conta como desconto, assim como o desconto da linha. Itens avulsos (sem catálogo) usam o próprio preço como referência.

- Até o **desconto máximo** da empresa, o vendedor envia direto.
- Acima dele, o botão **Marcar como enviada** dá lugar a **Pedir aprovação**. Um Master **aprova** (a proposta fica *Aprovada internamente* e pode ser enviada) ou **devolve ao rascunho**.
- O preço de tabela é copiado para a proposta quando o item entra. Mudar o catálogo depois não altera propostas já feitas.

## 7. Envio, validade e follow-up

- **Imprimir** abre a proposta pronta para imprimir; **PDF** gera o arquivo para enviar ao cliente. Os dois trazem dados da empresa, cliente, escopo, itens, condições, validade, termos e campo de aceite. Preço de tabela e observações internas não aparecem.
- **Marcar como enviada** registra a data de envio. Se a validade estiver vazia ou vencida, ela é renovada pela validade padrão da empresa.
- Propostas enviadas ou em negociação cuja validade passou viram **Expirada** sozinhas (ao abrir as telas e pelo comando `expirar_propostas`).
- No detalhe, **Acompanhamento** registra anotações e a **próxima ação** com data. O painel lista follow-ups atrasados, propostas que vencem em até 7 dias e propostas com o cliente sem próxima ação. A visão **A acompanhar** da lista mostra as próximas ações de hoje e as atrasadas.

## 8. Revisões

Depois que sai do rascunho, a proposta não é mais editada. Para mudar preço, itens ou condições, use **Criar revisão** (disponível também para propostas expiradas):

- a versão atual (cliente, itens, valores, condições) fica guardada em **Revisões anteriores**, com o motivo informado;
- a proposta volta ao rascunho com o código seguinte: `EST-2026-0007-R1`, `-R2`…;
- aprovação e data de envio são zeradas, e o fluxo recomeça.

## 9. Fechamento: ganha, perdida ou cancelada

- **Ganha:** registra a data e um comentário (pedido, contrato, fator decisivo).
- **Perdida:** exige o **motivo** (preço, concorrente, prazo, escopo, sem orçamento, projeto adiado, sem resposta, outro) e aceita o concorrente que ganhou e o que aprendemos. Os motivos alimentam o painel.
- **Cancelada:** decisão interna (proposta feita por engano, oportunidade que deixou de existir). Não conta na conversão.

Todo fechamento limpa a próxima ação. Cada mudança de etapa, edição, revisão e anotação fica no **histórico** da proposta, com data e usuário.

## 10. Painel e indicadores

Filtre por período de fechamento e por responsável.

| Indicador | Cálculo |
| --- | --- |
| Pipeline com clientes | Soma das propostas enviadas e em negociação (hoje) |
| Previsão ponderada | Soma de valor × probabilidade de todas as abertas (hoje) |
| Vendido no período | Soma das ganhas com fechamento no período |
| Taxa de conversão | Ganhas ÷ (ganhas + perdidas + expiradas) fechadas no período, em quantidade e em valor. Canceladas ficam de fora |
| Ticket médio | Vendido ÷ quantidade de ganhas |
| Ciclo de venda | Média de dias entre o envio e o ganho |

## 11. Perguntas frequentes

**Errei o valor de uma proposta já enviada. Edito?** Não: crie uma revisão. A versão enviada fica guardada para consulta.

**Por que não consigo enviar?** O desconto passou do limite da empresa (peça aprovação) ou a proposta não tem itens.

**O cliente voltou depois da validade.** Abra a proposta expirada e use **Criar revisão**; ao enviar de novo, a validade é renovada.

**Como apago um cliente?** Clientes com propostas não são apagados, para não perder o histórico: inative-os. Um Admin pode apagar pelo `/admin/` um cliente sem propostas.

**Posso mudar o número de uma proposta?** Não. A numeração é sequencial por empresa e ano; mudanças depois do envio geram revisões (`-R1`, `-R2`…) do mesmo número.

## 12. Administração e instalação

Esta seção é para quem instala e mantém o sistema.

### Subir o ambiente

```bash
make compose            # ou: docker compose up -d
```

Ao iniciar, o container `commercialproposal` roda as migrações, cria as empresas do grupo que faltarem (`configurar_empresas`) e expira as propostas vencidas. Endereços locais: sistema em `https://propostas.docker.localhost`, Keycloak em `https://keycloak-propostas.docker.localhost` (importa o realm `commercialproposal` de `data/keycloak/realm/`) e Adminer em `https://adminer-propostas.docker.localhost`.

Os serviços têm o prefixo `propostas-` e o banco fica só na rede interna da stack. A rede `proxy` é compartilhada com outros sistemas (como o CostManage); nomes iguais nela se misturam no DNS do Docker. Com as duas stacks no ar, basta um Traefik (`reverse-proxy`), porque ele enxerga os containers de todas.

### Empresas e acessos

Em **Administração → Empresas**, além dos dados impressos e das regras comerciais (seção 2), a lista **Grupos com acesso** dá aos membros de um grupo um papel (Limited, Tech ou Master) na empresa. Quem está em mais de um grupo com acesso fica com o maior papel. O grupo **Admin** e os superusuários veem todas as empresas. Desmarcar **Ativa** esconde a empresa de todos, sem apagar dados.

O admin do Django também permite correções pontuais em propostas (texto, itens). Etapa, numeração e aprovação só mudam pelo sistema, que registra o histórico; criar propostas pelo admin está bloqueado.

### Comandos úteis

Rode dentro do container (`docker compose exec commercialproposal poetry run python src/manage.py <comando>`):

| Comando | O que faz |
| --- | --- |
| `configurar_empresas` | Cria as empresas do grupo que faltam e o acesso dos grupos de papel (não altera o que já existe) |
| `expirar_propostas [--empresa <slug>]` | Marca como expiradas as propostas com validade vencida; bom para agendar diariamente |
| `anexar_documento <link> [--tipo cartao_cnpj] [--empresa <slug>]` | Anexa à empresa um documento do SharePoint pelo link de compartilhamento (ex.: cartão CNPJ); do cartão, preenche CNPJ, razão social, endereço e telefone em branco |
| `sincronizar_sharepoint [--empresa <slug>] [--simular]` | Importa e atualiza as propostas da biblioteca do SharePoint (seção 13); `--simular` mostra o resultado sem gravar |

### Desenvolvimento

```bash
make install            # dependências (inclui as de desenvolvimento)
make test               # pytest; precisa de SECRET_KEY no ambiente ou no .env
```

### Onde está cada coisa

- Regras de negócio: `src/commercial/propostas/` (`models.py`, `servicos.py` com o funil, `indicadores.py` com o painel)
- Telas: `src/commercial/screens/<tela>/view.py` e `src/commercial/templates/<tela>.html`
- Menu: `src/commercial/screens/config/aside.py`
- Login e lista de e-mails: `src/proposal/sso.py`
- Estilos: `media/css/app.css` (moldura) e `media/css/ui.css` (telas)
- Regras e decisões de negócio: [documents/propostas.md](documents/propostas.md)
- Mapa do SharePoint e regras da sincronização: [documents/sharepoint.md](documents/sharepoint.md)
- Testes: `tests/`

## 13. SharePoint

As propostas feitas em Word na biblioteca do SharePoint (`01 - Propostas/<ano>/<cliente>/Proposta 021 26.docx`) são importadas para o sistema, com o número original, cliente, contato, valor, validade e a lista de arquivos (versões e pedidos de compra), cada um com link para o SharePoint. Propostas com pedido de compra na pasta entram como **ganhas**; as demais com validade vencida, como **expiradas**.

- **Automática:** o container sincroniza ao subir e depois a cada `SHAREPOINT_INTERVALO_MINUTOS` (padrão 60; 0 desliga).
- **Tela Sincronização** (menu *Integração e ajuda*): configuração da empresa, **Testar conexão**, **Simular**, **Sincronizar agora** (papel Master) e o histórico de cada rodada com avisos e conflitos. Também pelo comando `sincronizar_sharepoint`. A primeira vez leva alguns minutos; depois, só o que mudou é baixado. Só uma rodada por empresa roda de cada vez.
- **O que não é desfeito:** etapas decididas no sistema (negociação, ganha, perdida, cancelada) e itens editados aqui.
- **Numeração:** propostas novas no sistema continuam a sequência do ano. Use o número gerado (ex.: `035/26`) no nome do arquivo do SharePoint; um número usado pelos dois lados aparece como conflito no relatório.
- **Configuração:** *Administração → Empresas → SharePoint* (site, pastas e primeiro ano) e as variáveis `SHAREPOINT_TENANT_ID`, `SHAREPOINT_CLIENT_ID` e `SHAREPOINT_CLIENT_SECRET` no `.env` (ou no Secret do Kubernetes).

Detalhes, o mapa da biblioteca e os próximos passos em [documents/sharepoint.md](documents/sharepoint.md). A tela **Metodologia** explica o sistema inteiro com diagramas e o passo a passo ilustrado; os prints são gerados por `documents/prints/capturar.cjs` (Playwright).

## 14. Histórico e contratos

- **Histórico** (menu *Comercial*): propostas de 2016 em diante, ano a ano pelo ano de emissão. Mostra emitidas, valor proposto, ganhas, vendido, conversão, ticket médio, clientes, clientes novos e documentos. Inclui a matriz **clientes × anos** (os 25 com mais propostas) e as **linhas de serviço por ano**. Filtros: período, linha de serviço e cliente. O histórico de 2016–2020 vem de `Propostas_antigas`; de 2021 em diante, de `01 - Propostas` e das planilhas de controle.
- **Contratos**: propostas fechadas (ganhas) com os pedidos de compra e contratos de cada uma, um resumo por ano e o **acervo** do SharePoint. O acervo cataloga todos os arquivos das pastas de clientes e das pastas de contratos, classificados pelo nome: proposta, pedido de compra, contrato, NDA, cadastro de fornecedor, fiscal, dados e outros.
- **Documentos da empresa**: o cartão CNPJ e outros documentos ficam anexados à empresa e aparecem em *Contratos*. Para anexar, use *Administração → Empresas* ou o comando `anexar_documento`. Com o link do SharePoint, a sincronização baixa de novo o arquivo quando ele muda. O sistema avisa quando o cartão CNPJ tem mais de 90 dias, prazo que cadastros de fornecedor costumam exigir.
