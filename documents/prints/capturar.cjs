// Gera os prints do passo a passo da Metodologia (media/metodologia/*.png).
//
// Uso (com o sistema no ar e uma sessão de um usuário Admin):
//   BASE=http://127.0.0.1:8765 SESSAO=<sessionid> GANHA=<id> ENVIADA=<id> \
//   PLAYWRIGHT=<caminho do pacote playwright> node documents/prints/capturar.cjs
//
// GANHA: uma proposta importada com pedido de compra; ENVIADA: uma proposta enviada ao cliente.
// O roteiro cria uma proposta de demonstração (passos 3 a 5): rode numa base de demonstração.
const path = require("path");
const { chromium } = require(process.env.PLAYWRIGHT || "playwright");

const BASE = process.env.BASE || "http://127.0.0.1:8765";
const DESTINO = path.join(__dirname, "..", "..", "media", "metodologia");
const { SESSAO, GANHA, ENVIADA } = process.env;

async function print(pagina, arquivo, inteira = false) {
  await pagina.waitForLoadState("networkidle");
  // Página inteira: a janela cresce até o conteúdo (com fullPage, o menu e o topo fixos se repetem no meio).
  const tamanho = pagina.viewportSize();
  if (inteira) {
    const altura = await pagina.evaluate(() => document.documentElement.scrollHeight);
    await pagina.setViewportSize({ width: tamanho.width, height: Math.max(altura, tamanho.height) });
  }
  await pagina.screenshot({ path: path.join(DESTINO, arquivo) });
  await pagina.setViewportSize(tamanho);
  console.log("ok", arquivo);
}

(async () => {
  const navegador = await chromium.launch();
  const contexto = await navegador.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light", locale: "pt-BR" });
  await contexto.addCookies([{ name: "sessionid", value: SESSAO, url: BASE }]);
  const p = await contexto.newPage();

  await p.goto(`${BASE}/app/painel/?inicio=2021-01-01&fim=2026-12-31`);
  await print(p, "01-painel.png", true);

  await p.goto(`${BASE}/app/propostas/?ver=todas`);
  await print(p, "02-propostas.png");

  // 3. Nova proposta com dois itens do catálogo e desconto acima da alçada.
  await p.goto(`${BASE}/app/propostas/?novo=1`);
  await p.fill("#id_titulo", "Perfil de dissolução comparativo — 2 produtos");
  await p.selectOption("#id_cliente", { label: "MERCK" });
  await p.selectOption("#id_origem", "cliente");
  await p.fill("#id_prazo_entrega", "15 dias após o recebimento dos dados");
  await p.fill("#id_escopo", "Análise do perfil de dissolução comparativo pelo fator de similaridade f2 via bootstrap, com protocolo e relatório estatístico.");
  await p.selectOption("#id_itens-0-item_catalogo", { label: "PDC — Análise do Perfil de Dissolução Comparativo" });
  await p.fill("#id_itens-0-quantidade", "2");
  await p.fill("#id_itens-0-desconto", "15");
  await p.click("[data-adicionar-item]");
  await p.selectOption("#id_itens-1-item_catalogo", { label: "HT — Hora técnica de consultoria estatística" });
  await p.fill("#id_itens-1-quantidade", "8");
  await p.locator("#id_itens-1-quantidade").blur();
  await print(p, "03-nova-proposta.png", true);

  // 4. Rascunho salvo: desconto acima da alçada pede aprovação.
  await Promise.all([p.waitForNavigation(), p.click("text=Salvar rascunho")]);
  await print(p, "04-rascunho.png");

  // 5. Pedido de aprovação; o gestor vê aprovar / devolver.
  await Promise.all([p.waitForNavigation(), p.click("button:has-text('Pedir aprovação')")]);
  await print(p, "05-aprovacao.png");

  await p.goto(`${BASE}/app/propostas/?id=${GANHA}`);
  await print(p, "06-detalhe-importada.png", true);

  // 7. Diálogo de perda (sem confirmar).
  await p.goto(`${BASE}/app/propostas/?id=${ENVIADA}`);
  await p.click("[data-abrir-dialogo='dialogo-perder']");
  await p.selectOption("#dialogo-perder select[name=motivo_perda]", "concorrente");
  await p.fill("#dialogo-perder input[name=concorrente]", "Concorrente X");
  await print(p, "07-perda.png");

  await p.goto(`${BASE}/app/propostas/?id=${GANHA}&imprimir=html`);
  await p.addStyleTag({ content: ".imprimir{display:none}" });
  await print(p, "08-impressao.png", true);

  await p.goto(`${BASE}/app/clientes/`);
  await print(p, "09-clientes.png");

  await p.goto(`${BASE}/app/catalogo/`);
  await print(p, "10-catalogo.png");

  await p.goto(`${BASE}/app/sincronizacao/`);
  await print(p, "11-sincronizacao.png", true);

  await p.goto(`${BASE}/app/historico/`);
  await print(p, "12-historico.png", true);

  await p.goto(`${BASE}/app/contratos/`);
  await print(p, "13-contratos.png", true);

  await navegador.close();
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
