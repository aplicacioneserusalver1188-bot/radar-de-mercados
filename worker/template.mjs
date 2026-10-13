const indexPage = __INDEX_PAGE__;
const consultorPage = __CONSULTOR_PAGE__;
const marketData = __MARKET_DATA__;
const bursts = new Map();
const secCache = new Map();
let usageStoreReady;
const htmlHeaders = { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff", "content-security-policy": "default-src 'self'; connect-src 'self' https://raw.githubusercontent.com; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' https://s3.tradingview.com; img-src 'self' data: https://s3.tradingview.com https://www.tradingview.com; frame-src https://www.cmegroup.com https://www.tradingview.com https://s.tradingview.com https://tradingview-widget.com https://www.tradingview-widget.com" };

function burstLimited(ip) {
  const now = Date.now(), previous = (bursts.get(ip) || []).filter((t) => now - t < 60000);
  if (previous.length >= 12) return true;
  previous.push(now); bursts.set(ip, previous); return false;
}
function json(value, status = 200) { return new Response(JSON.stringify(value), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" } }); }
async function cachedSec(key, load) {
  const hit = secCache.get(key), now = Date.now();
  if (hit && now - hit.at < 900000) return hit.value;
  const value = await load(); secCache.set(key, { at: now, value }); return value;
}
async function secJson(env, address) {
  if (!env.SEC_USER_AGENT) throw new Error("SEC_USER_AGENT no está configurado en el servidor.");
  const response = await fetch(address, { headers: { "User-Agent": env.SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate", "Accept": "application/json" } });
  if (!response.ok) throw new Error(`SEC EDGAR devolvió HTTP ${response.status}.`);
  return response.json();
}
function secFact(facts, names) {
  for (const name of names) {
    const entries = facts?.["us-gaap"]?.[name]?.units?.USD;
    if (!entries) continue;
    const selected = entries.filter((item) => item.form === "10-K" || item.form === "10-Q").sort((a, b) => String(b.end).localeCompare(String(a.end)) || String(b.filed).localeCompare(String(a.filed)))[0];
    if (selected) return { label: facts["us-gaap"][name].label || name, value: selected.val, end: selected.end, filed: selected.filed, form: selected.form, fiscalYear: selected.fy, fiscalPeriod: selected.fp };
  }
  return null;
}
async function secCompany(env, ticker) {
  const registry = await cachedSec("tickers", () => secJson(env, "https://www.sec.gov/files/company_tickers.json"));
  const match = Object.values(registry).find((item) => item.ticker === ticker);
  if (!match) return { error: "La SEC no asocia este símbolo con un emisor estadounidense.", ticker };
  const cik = String(match.cik_str).padStart(10, "0");
  const submissions = await cachedSec(`submissions:${cik}`, () => secJson(env, `https://data.sec.gov/submissions/CIK${cik}.json`));
  let facts = { facts: {} };
  try { facts = await cachedSec(`facts:${cik}`, () => secJson(env, `https://data.sec.gov/api/xbrl/companyfacts/CIK${cik}.json`)); } catch (error) { if (!String(error.message).includes("HTTP 404")) throw error; }
  const recent = submissions?.filings?.recent || {}, forms = ["10-K", "10-Q", "8-K"];
  const filings = (recent.form || []).map((form, index) => ({ form, filingDate: recent.filingDate?.[index], reportDate: recent.reportDate?.[index], accession: recent.accessionNumber?.[index], document: recent.primaryDocument?.[index], description: recent.primaryDocDescription?.[index] })).filter((item) => forms.includes(item.form)).slice(0, 8).map((item) => ({ ...item, url: item.accession && item.document ? `https://www.sec.gov/Archives/edgar/data/${Number(cik)}/${item.accession.replaceAll("-", "")}/${item.document}` : null }));
  return { ticker, cik, name: submissions.name || match.title, sic: submissions.sicDescription || null, updated: submissions.filingDate || null, filings, fundamentals: { revenue: secFact(facts.facts, ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenues"]), netIncome: secFact(facts.facts, ["NetIncomeLoss"]), assets: secFact(facts.facts, ["Assets"]), liabilities: secFact(facts.facts, ["Liabilities"]), equity: secFact(facts.facts, ["StockholdersEquity"]) } };
}
async function binanceQuote(symbol) {
  let source = "Binance Spot 24h", response = await fetch(`https://data-api.binance.vision/api/v3/ticker/24hr?symbol=${encodeURIComponent(symbol)}`);
  if (!response.ok && symbol === "BTCUSDT") { source = "Binance.US Spot 24h"; response = await fetch("https://api.binance.us/api/v3/ticker/24hr?symbol=BTCUSD"); }
  if (!response.ok) throw new Error(`Binance devolvió HTTP ${response.status}.`);
  const quote = await response.json();
  return { symbol: quote.symbol, price: quote.lastPrice, change: quote.priceChange, changePercent: quote.priceChangePercent, volume: quote.volume, quoteVolume: quote.quoteVolume, openTime: quote.openTime, closeTime: quote.closeTime, source };
}
function monthKey() { return new Date().toISOString().slice(0, 7); }
function monthlyCap(env) { const value = Number.parseInt(env.WOLFRAM_MONTHLY_CAP || "", 10); return Number.isSafeInteger(value) && value > 0 ? value : null; }
async function ensureUsageStore(env) {
  if (!env.DB) return;
  usageStoreReady ||= env.DB.prepare("CREATE TABLE IF NOT EXISTS wolfram_usage_monthly (month_key TEXT PRIMARY KEY, calls_used INTEGER NOT NULL DEFAULT 0)").run();
  await usageStoreReady;
}
async function usage(env, increment = false) {
  const month = monthKey();
  if (!env.DB) return { month, used: null, cap: monthlyCap(env), persistent: false };
  await ensureUsageStore(env);
  if (increment) {
    const row = await env.DB.prepare("INSERT INTO wolfram_usage_monthly (month_key, calls_used) VALUES (?, 1) ON CONFLICT(month_key) DO UPDATE SET calls_used = calls_used + 1 RETURNING calls_used").bind(month).first();
    return { month, used: row.calls_used, cap: monthlyCap(env), persistent: true };
  }
  const row = await env.DB.prepare("SELECT calls_used FROM wolfram_usage_monthly WHERE month_key = ?").bind(month).first();
  return { month, used: row?.calls_used || 0, cap: monthlyCap(env), persistent: true };
}

export default { async fetch(request, env) {
  const url = new URL(request.url), path = url.pathname;
  if (path === "/" || path === "/index.html") return new Response(indexPage, { headers: htmlHeaders });
  if (path === "/consultor" || path === "/consultor.html") return new Response(consultorPage, { headers: htmlHeaders });
  if (path === "/data/market.json") return new Response(marketData, { headers: { "content-type": "application/json; charset=utf-8", "cache-control": "public, max-age=900" } });
  if (path === "/api/wolfram-usage") return json(await usage(env));
  if (path === "/api/sec") {
    if (request.method !== "GET") return json({ error: "Método no permitido." }, 405);
    const ticker = (url.searchParams.get("ticker") || "").toUpperCase();
    if (!/^[A-Z0-9.\-]{1,12}$/.test(ticker)) return json({ error: "Símbolo inválido." }, 400);
    if (burstLimited(request.headers.get("cf-connecting-ip") || "anonymous")) return json({ error: "Demasiadas solicitudes seguidas. Espere un minuto." }, 429);
    try { return json(await secCompany(env, ticker)); } catch (error) { return json({ error: error.message || "No se pudo consultar SEC EDGAR." }, 502); }
  }
  if (path === "/api/binance") {
    if (request.method !== "GET") return json({ error: "Método no permitido." }, 405);
    const symbol = (url.searchParams.get("symbol") || "").toUpperCase();
    if (!/^[A-Z0-9]{5,20}$/.test(symbol)) return json({ error: "Par de criptoactivo inválido." }, 400);
    if (burstLimited(request.headers.get("cf-connecting-ip") || "anonymous")) return json({ error: "Demasiadas solicitudes seguidas. Espere un minuto." }, 429);
    try { return json(await binanceQuote(symbol)); } catch (error) { return json({ error: error.message || "No se pudo consultar Binance." }, 502); }
  }
  if (path !== "/api/wolfram") return new Response("Not found", { status: 404 });
  if (request.method !== "POST") return json({ error: "Método no permitido." }, 405);
  if (!env.WOLFRAM_APP_ID) return json({ error: "Wolfram no está configurado todavía en el servidor." }, 503);
  const ip = request.headers.get("cf-connecting-ip") || "anonymous";
  if (burstLimited(ip)) return json({ error: "Demasiadas solicitudes seguidas. Espere un minuto antes de continuar." }, 429);
  const current = await usage(env);
  if (current.cap && current.used >= current.cap) return json({ error: "Se alcanzó el cupo mensual configurado para Wolfram.", usage: current }, 429);
  let body; try { body = await request.json(); } catch { return json({ error: "Solicitud inválida." }, 400); }
  const expression = typeof body.expression === "string" ? body.expression.trim() : "";
  if (!/^[0-9+\-*/().\s]+$/.test(expression) || expression.length > 200) return json({ error: "Solo se permiten expresiones matemáticas numéricas." }, 400);
  const params = new URLSearchParams({ appid: env.WOLFRAM_APP_ID, input: expression, output: "json", format: "plaintext", includepodid: "Result", timeout: "3" });
  let upstream; try { upstream = await fetch("https://api.wolframalpha.com/v2/query?" + params); } catch { return json({ error: "No se pudo contactar Wolfram|Alpha." }, 502); }
  if (!upstream.ok) return json({ error: "Wolfram|Alpha rechazó el cálculo.", status: upstream.status }, 502);
  let payload; try { payload = await upstream.json(); } catch { return json({ error: "Respuesta inválida de Wolfram|Alpha." }, 502); }
  const result = payload?.queryresult, pod = result?.pods?.find((item) => item.id === "Result") || result?.pods?.[0], text = pod?.subpods?.[0]?.plaintext;
  if (!result?.success || !text) return json({ error: "Wolfram|Alpha no devolvió un resultado para esa expresión." }, 422);
  return json({ result: text, title: pod.title || "Resultado", engine: "Wolfram|Alpha Full Results API", expression, usage: await usage(env, true) });
} };
