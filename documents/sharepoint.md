# SharePoint — mapa da biblioteca de propostas e sincronização

Site: <https://estatcamp.sharepoint.com/sites/propostasestatcamp>, biblioteca **Documents** (a principal). Mapeada em 28/10/2026.

## 1. Mapa da biblioteca

| | |
| --- | --- |
| Tamanho | 27.301 arquivos em 3.682 pastas, 13,3 GB |
| Tipos | PDF (14.791), DOCX (8.376), XLS/XLSX (3.074), DOC (249), ZIP (161), outros |
| Outra biblioteca | `Teams Wiki Data` (do Teams, sem propostas) |

| Pasta | Arquivos | Conteúdo |
| --- | ---: | --- |
| `01 - Propostas/<ano>/<cliente>/` | 11.041 | Propostas de 2016 a 2026: o `.docx` editável, o `.pdf` enviado, revisões e anexos do cliente (pedidos de compra, NDAs, cadastros de fornecedor) |
| `02 - Controle de Propostas/` | 7 | Uma planilha por ano (`Propostas Treinamento e consultoria<ano>.xlsx`), de 2021 a 2026, mais uma cópia de 2024 (`…2024-rubens-estat.xlsx`) |
| `Propostas_antigas/` | 10.356 | Histórico de 2016–2020 (mesmos números de `01 - Propostas`, com alguns arquivos a mais); fonte do histórico |
| `Pedidos_propostas/pedidos_propostas.xlsx` | 1 | Pedidos e parcelas de 2020–2021 (não é importada) |
| `Financeiro/` | 5.541 | Financeiro da empresa (fora do escopo) |
| Demais (`CONTRATOS_OUT 2023`, `DocuSign`, `ciee…`, `marketing`, etc.) | ~400 | Contratos, estágio, marketing; fora do escopo |

### Propostas por ano (`01 - Propostas`)

| Ano | Arquivos | Propostas importáveis | Observação |
| --- | ---: | ---: | --- |
| 2016–2020 | 10.060 | — | Nomes e modelos mais variados; fora da sincronização por padrão |
| 2021 | 223 | 54 | Modelo "Action Stat" (licenças) e consultoria |
| 2022–2026 | 758 | 154 | Modelo de consultoria padronizado |

### Convenções encontradas

- **Arquivo da proposta:** `Proposta <NNN> <AA>[ Rev <NN>].docx|pdf` (ex.: `Proposta 023 26 Rev 01.pdf`). O número é sequencial por ano; `Rev` é a revisão.
- **Pasta do cliente:** o nome varia em caixa e acento entre os anos (`EUROFARMA`, `eurofarma`, `ACHÉ`, `Aché`), e há pastas por unidade (`eurofarma - rp`).
- **Pedido de compra:** salvo na pasta do cliente com nomes como `Pedido Compra 4100089244 - prop_002 26.pdf`, `PO-171382_v1_20260313.pdf` ou só o número do pedido. Nem sempre cita a proposta.
- **Planilha de controle:** colunas `SERVIÇO`, `Nº` (`001/26`), `EMPRESA`, `DATA`, `RESPONSAVEL` (quem pediu, do lado do cliente, na maioria das linhas), `FUP` e `POSIÇÃO`. **FUP e POSIÇÃO estão vazias em todos os anos**: hoje não há registro de follow-up nem do resultado das propostas.
- **Conteúdo do `.docx` (modelo de consultoria):** `NÚMERO`, `Data`, `Vencimento` (30 dias), título, `A/C` (contato), `Descrição Geral`, `VALOR` (em geral um só valor), `FORMA DE PAGAMENTO`, `CRONOGRAMA DE TRABALHO` (prazo) e a assinatura.
- **Atenção:** há documentos com credenciais de portais de clientes guardados na biblioteca (ex.: `Usuário e senha.docx` em pastas de cadastro de fornecedor). Não são importados, mas convém guardá-los num cofre de senhas.

## 2. Sincronização

Automática no container (ao subir e a cada `SHAREPOINT_INTERVALO_MINUTOS`, padrão 60), pela tela **Sincronização** (testar conexão, simular, sincronizar e histórico; papel Master) ou pelo comando `sincronizar_sharepoint`. Cada rodada fica registrada (`ExecucaoSincronizacao`) e só uma roda por empresa de cada vez. Só lê o SharePoint. Código em `src/commercial/propostas/sincronizacao.py`; leitura do `.docx` em `leitor_docx.py`.

Configuração em *Administração → Empresas → SharePoint*: site; pastas das propostas, uma por linha e com faixa de anos (`Propostas_antigas: 2016-2020` e `01 - Propostas: 2021-`); pasta das planilhas de controle (`02 - Controle de Propostas`, só 2021–2026); pastas de contratos (`CONTRATOS_OUT 2023`, `DocuSign`); e o primeiro ano (2016). As credenciais do app do Entra ID (`SHAREPOINT_TENANT_ID`, `SHAREPOINT_CLIENT_ID`, `SHAREPOINT_CLIENT_SECRET`) vêm do ambiente; o app precisa de `Sites.Read.All` e `Files.Read.All` com consentimento do administrador.

| Regra | Como funciona |
| --- | --- |
| Identidade | Cada número e ano (`021/26`) é uma proposta, com o número original. A próxima proposta criada no sistema continua a sequência |
| Documento principal | O `.docx` da maior revisão. Sem `.docx` nessa revisão, os dados vêm só da planilha |
| Dados | Do `.docx`: título, data (envio), vencimento (validade), contato, valor (vira um item avulso), pagamento, prazo, escopo e assinatura. Da planilha: serviço, cliente e data quando faltam, e o solicitante (nas observações) |
| Cliente | Pela pasta do ano; nomes iguais sem diferença de caixa ou acento são o mesmo cliente. As pastas ficam registradas no cliente (*Pastas no SharePoint*), então renomear o cliente no sistema não cria outro |
| Responsável | O usuário cujo nome ou início do e-mail aparece na assinatura (ex.: `rubens@…` ↔ "José Rubens Campanini"). Usuários que entrarem depois são ligados na sincronização seguinte |
| Ganha | Pedido de compra na pasta que cita o número (`prop_002 26`, `039 24`) ou numa pasta com uma só proposta. Data de fechamento: a do arquivo do pedido |
| Expirada | Sem pedido e com a validade vencida; data de fechamento: a validade |
| Arquivos | Todas as versões e os pedidos ficam listados na proposta, com link para o SharePoint |
| Atualização | Só quando o conteúdo do documento muda (`cTag`). Etapas decididas no sistema (negociação, ganha, perdida, cancelada) não são desfeitas; itens editados no sistema não são sobrescritos |
| Conflito | Se o número já foi usado por uma proposta criada no sistema, o SharePoint é ignorado e o conflito aparece no relatório |
| Só na planilha | Linha da planilha de controle sem documento no SharePoint: a proposta entra assim mesmo, sem valor, marcada nas observações |
| Acervo | Todo arquivo das pastas de propostas (na faixa de anos) e das pastas de contratos, classificado pelo nome e ligado ao cliente e à proposta que cita; arquivos apagados no SharePoint saem do acervo |
| Documentos da empresa | Anexados por link de compartilhamento (`anexar_documento`); baixados de novo quando mudam. Do cartão CNPJ são lidos CNPJ, razão social, endereço, telefone e data de emissão (`pypdf`) |
| Gravação | Cada proposta grava sozinha; a primeira carga do histórico (milhares de propostas) leva dezenas de minutos e roda em segundo plano |

### Resultado da primeira importação (base de teste, 28/10/2026)

208 propostas de 2021 a 2026, 62 clientes e 614 arquivos em 1min45; sincronizações seguintes sem mudança levam ~40 s (só listagem). 37 foram marcadas como ganhas por pedido de compra (R$ 392.730) e 168 como expiradas; 3 de 2026 seguem com o cliente. 11 avisos: 8 sem valor no documento (ficaram em R$ 0,00), 1 com mais de um valor e 2 sem `.docx` na última revisão.

**A taxa de conversão do histórico (18%) é um piso:** pedidos recebidos por e-mail e não salvos na pasta não são vistos. Marque como ganhas, no sistema, as propostas fechadas sem pedido na pasta; a sincronização não desfaz isso.

## 3. Próximos passos possíveis

- **Escrever no SharePoint** (exige `Sites.ReadWrite.All` ou `Sites.Selected` com escrita no site): ao criar uma proposta no sistema, criar a pasta do cliente, salvar o PDF e acrescentar a linha na planilha de controle. Sem isso, a numeração precisa ser combinada: a equipe deve usar o número gerado pelo sistema no nome do arquivo.
