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
function annualFactSeries(facts, names, annualFilings, isFlow = true, unit = "USD") {
  const result = [];
  for (const filing of annualFilings) {
    let selected = null;
    for (const name of names) {
      const entries = facts?.["us-gaap"]?.[name]?.units?.[unit] || [];
      const match = entries.find((item) => {
        if (item.accn !== filing.accession || item.form !== "10-K" || item.end !== filing.reportDate || !Number.isFinite(item.val)) return false;
        if (!isFlow) return !item.start; // Balance-sheet facts must be instant observations, not duration facts.
        if (!item.start || !item.end) return false;
        const days = (Date.parse(item.end) - Date.parse(item.start)) / 86400000;
        return days >= 300 && days <= 400;
      });
      if (match) { selected = { ...match, label: facts["us-gaap"][name].label || name, concept: name }; break; }
    }
    if (selected) result.push({ fiscalYear: String(filing.reportDate || selected.end).slice(0, 4), end: filing.reportDate || selected.end, filed: filing.filingDate, value: selected.val, form: "10-K", accession: filing.accession, label: selected.label, unit, concept: selected.concept, sourceUrl: filing.url || null });
  }
  return result.sort((a, b) => String(a.end).localeCompare(String(b.end))).slice(-5);
}
function cleanFilingText(value) {
  return String(value || "").replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>|<ix:header[\s\S]*?<\/ix:header>/gi," ")
    .replace(/<\/(?:p|div|tr|h[1-6]|table|li|section)>/gi,"\n").replace(/<[^>]+>/g," ")
    .replace(/&nbsp;|&#160;/gi," ").replace(/&amp;/gi,"&").replace(/&quot;/gi,'"')
    .replace(/&#39;|&apos;/gi,"'").replace(/[ \t\r\f]+/g," ").replace(/\n\s*\n+/g,"\n").trim();
}
const FILING_HEADINGS = [
 {key:"business",re:/^\s*ITEM\s*1\s*[.:-]?\s*BUSINESS\b[^\n]{0,100}$/gim},
 {key:"risks",re:/^\s*ITEM\s*1\s*A\s*[.:-]?\s*RISK\s*FACTORS\b[^\n]{0,100}$/gim},
 {key:"discussion",re:/^\s*ITEM\s*7\s*[.:-]?\s*MANAGEMENT.{0,150}DISCUSSION[^\n]{0,150}$/gim},
 {key:"discussionEnd",re:/^\s*ITEM\s*(?:7\s*A|8)\s*[.:-]?[^\n]{0,150}$/gim},
 {key:"risksEnd",re:/^\s*ITEM\s*(?:1\s*B|1\s*C|2)\s*[.:-]?[^\n]{0,150}$/gim}
];
function filingSections(text) {
 const positions={};
 for(const {key,re} of FILING_HEADINGS)positions[key]=[...text.matchAll(re)].map(m=>({at:m.index,after:m.index+m[0].length}));
 const result={};
 for(const [key,ends] of [["business",["risks"]],["risks",["risksEnd","discussion"]],["discussion",["discussionEnd"]]]) {
  const candidates=[];
  for(const heading of positions[key]||[]) {
   const following=ends.flatMap(name=>positions[name]||[]).filter(p=>p.at>heading.after).sort((a,b)=>a.at-b.at)[0];
   if(!following)continue;
   const body=text.slice(heading.after,following.at).trim();
   if(body.length>=700)candidates.push({body,length:body.length});
  }
  result[key]=candidates.sort((a,b)=>b.length-a.length)[0]||null;
 }
 return result;
}
function filingEvidence(section,patterns,maxItems=8) {
  if(!section) return [];
  const results=[];
  for(const pattern of patterns) {
    const flags=pattern.flags.replace(/g/g,"");
    const matcher=new RegExp(pattern.source,flags);
    const match=matcher.exec(section.body);
    if(!match) continue;
    const from=Math.max(0,match.index-300),to=Math.min(section.body.length,match.index+match[0].length+650);
    const excerpt=section.body.slice(from,to).replace(/\s+/g," ").trim();
    if(!results.some(x=>x.text===excerpt)) results.push({text:excerpt,sourceSection:section.name,sourceUrl:section.url,offset:match.index});
    if(results.length>=maxItems) break;
  }
  return results;
}
async function filingNarrative(env,filing) {
  if(!filing?.url) return {available:false};
  try {
    const html=await cachedSec("filing:"+filing.accession,async()=>{
      const response=await fetch(filing.url,{headers:{"User-Agent":env.SEC_USER_AGENT,"Accept-Encoding":"gzip, deflate","Accept":"text/html,application/xhtml+xml"}});
      if(!response.ok) throw new Error("SEC EDGAR devolvió HTTP "+response.status+".");
      return response.text();
    });
    const cleaned=cleanFilingText(html); const sections=filingSections(cleaned.replace(/ITEM[ ]+(1A|1B|7A|1|7|8)[. ]+(?=BUSINESS|RISK|MANAGEMENT|FINANCIAL)/gi,'\nITEM $1. '));
    const annotate=(key,name)=>sections[key]?{...sections[key],name,url:filing.url}:null;
    const business=annotate("business","Item 1. Business"),risks=annotate("risks","Item 1A. Risk Factors"),discussion=annotate("discussion","Item 7. MD&A");
    const evidence={
      customers:[...filingEvidence(discussion,[/concentration of revenue/i,/direct customer.{0,120}(revenue|sales)/i,/customer.{0,100}\d{1,2}%/i]),...filingEvidence(risks,[/customer.{0,100}concentrat/i,/customer.{0,100}revenue/i])],
      segments:filingEvidence(discussion||business,[/compute.{0,40}networking/i,/graphics.{0,60}revenue/i,/data center.{0,80}revenue/i]),
      supply:filingEvidence(risks||discussion,[/supply.{0,80}(constraint|capacity|chain)/i,/inventory.{0,80}(risk|commitment)/i,/purchase.{0,50}commitment/i]),
      exportControls:filingEvidence(risks||discussion,[/export.{0,40}(control|restriction)/i,/\bH20\b/i])
    };
    return {
      available:!!(business||risks||discussion),filingDate:filing.filingDate,reportDate:filing.reportDate,url:filing.url,
      business:business?.body.slice(0,10000)||null,risks:risks?.body.slice(0,10000)||null,discussion:discussion?.body.slice(0,10000)||null,
      sections:Object.fromEntries([["business",business],["risks",risks],["discussion",discussion]].map(([key,s])=>[key,s?{heading:s.name,length:s.length,sourceUrl:s.url,found:true}:{found:false}])),
      evidence,warnings:["Extractos documentales, no verificación de cifras XBRL; comprobar unidades y período antes de usarlos en una valoración."]
    };
  } catch(error) {return {available:false,error:error.message||"No se pudo leer el informe anual."};}
}
function quarterlyRevenueSeries(facts,filings){
 const concepts=["RevenueFromContractWithCustomerExcludingAssessedTax","SalesRevenueNet","Revenues"];
 return filings.filter(f=>f.form==="10-Q").slice(0,4).map(f=>{
  for(const concept of concepts){
   const entries=facts?.["us-gaap"]?.[concept]?.units?.USD||[];
   const match=entries.find(e=>e.accn===f.accession&&e.form==="10-Q"&&e.end===f.reportDate&&e.start&&Number.isFinite(e.val)&&((Date.parse(e.end)-Date.parse(e.start))/86400000>=70)&&((Date.parse(e.end)-Date.parse(e.start))/86400000<=105));
   if(match)return {value:match.val,start:match.start,end:match.end,filed:f.filingDate,form:"10-Q",sourceUrl:f.url,concept};
  }
  return null;
 }).filter(Boolean).sort((a,b)=>a.end.localeCompare(b.end));
}
function makeFundamentalSeries(facts, annualFilings) { return { revenue: annualFactSeries(facts, ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenues"], annualFilings), netIncome: annualFactSeries(facts, ["NetIncomeLoss"], annualFilings), assets: annualFactSeries(facts, ["Assets"], annualFilings, false), liabilities: annualFactSeries(facts, ["Liabilities"], annualFilings, false), equity: annualFactSeries(facts, ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"], annualFilings, false), operatingCashFlow: annualFactSeries(facts, ["NetCashProvidedByUsedInOperatingActivities"], annualFilings), capitalExpenditures: annualFactSeries(facts, ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"], annualFilings), grossProfit: annualFactSeries(facts, ["GrossProfit"], annualFilings), operatingIncome: annualFactSeries(facts, ["OperatingIncomeLoss"], annualFilings), eps: annualFactSeries(facts, ["EarningsPerShareDiluted"], annualFilings, true, "USD/shares"), cash: annualFactSeries(facts, ["CashAndCashEquivalentsAtCarryingValue"], annualFilings, false), shortTermInvestments: annualFactSeries(facts, ["ShortTermInvestments", "MarketableSecuritiesCurrent"], annualFilings, false), debtCurrent: annualFactSeries(facts, ["LongTermDebtCurrent", "ShortTermBorrowings"], annualFilings, false), debtNoncurrent: annualFactSeries(facts, ["LongTermDebtNoncurrent"], annualFilings, false), dilutedShares: annualFactSeries(facts, ["WeightedAverageNumberOfDilutedSharesOutstanding"], annualFilings, true, "shares"), debtProceeds: annualFactSeries(facts, ["ProceedsFromIssuanceOfLongTermDebt", "ProceedsFromLongTermDebt"], annualFilings), debtRepayments: annualFactSeries(facts, ["RepaymentsOfLongTermDebt", "RepaymentsOfLongTermDebtAndCapitalSecurities"], annualFilings), netInterestIncome: annualFactSeries(facts, ["InterestIncomeExpenseNet"], annualFilings) }; }
function nvidiaInlineInvestments(html, filing) {
  // NVIDIA's consolidated current-investment total uses an issuer extension
  // absent from companyfacts. Never substitute debt securities alone.
  const attribute = (tag, name) => tag.match(new RegExp('\\b' + name + '="([^"]+)"', 'i'))?.[1];
  const contexts = new Set();
  for (const match of html.matchAll(/<xbrli:context\b([^>]*)>([\s\S]*?)<\/xbrli:context>/gi)) {
    const body = match[2];
    if (/<(?:\w+:)?(?:segment|scenario|explicitMember|typedMember)\b/i.test(body)) continue;
    if (!/<xbrli:identifier\b[^>]*>0*1045810<\/xbrli:identifier>/i.test(body)) continue;
    if (body.match(/<xbrli:instant>([^<]+)<\/xbrli:instant>/i)?.[1] === filing.reportDate) contexts.add(attribute(match[1], 'id'));
  }
  const units = new Set();
  for (const match of html.matchAll(/<xbrli:unit\b([^>]*)>([\s\S]*?)<\/xbrli:unit>/gi)) {
    if (/^\s*<xbrli:measure>iso4217:USD<\/xbrli:measure>\s*$/i.test(match[2])) units.add(attribute(match[1], 'id'));
  }
  const values = [];
  for (const match of html.matchAll(/<ix:nonFraction\b([^>]*)>([\s\S]*?)<\/ix:nonFraction>/gi)) {
    const tag = match[1];
    if (attribute(tag, 'name') !== 'nvda:MarketableSecuritiesAndEquitySecuritiesFVNI' || !contexts.has(attribute(tag, 'contextRef')) || !units.has(attribute(tag, 'unitRef'))) continue;
    if (attribute(tag, 'format') !== 'ixt:num-dot-decimal' || attribute(tag, 'sign') === '-') continue;
    const raw = match[2].trim(), scale = Number(attribute(tag, 'scale') || 0);
    if (!/^[\d,]+(?:\.\d+)?$/.test(raw) || !Number.isInteger(scale) || Math.abs(scale) > 12) continue;
    const value = Number(raw.replaceAll(',', '')) * 10 ** scale;
    if (Number.isFinite(value) && value >= 0) values.push(value);
  }
  if (!values.length || new Set(values).size !== 1) return null;
  return { fiscalYear: filing.reportDate.slice(0, 4), end: filing.reportDate, filed: filing.filingDate, value: values[0], form: '10-K', accession: filing.accession, unit: 'USD', concept: 'nvda:MarketableSecuritiesAndEquitySecuritiesFVNI', label: 'Marketable securities', sourceUrl: filing.url, extraction: 'inline-xbrl' };
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
  const allFilings = (recent.form || []).map((form, index) => ({ form, filingDate: recent.filingDate?.[index], reportDate: recent.reportDate?.[index], accession: recent.accessionNumber?.[index], document: recent.primaryDocument?.[index], description: recent.primaryDocDescription?.[index] })).filter((item) => forms.includes(item.form)).map((item) => ({ ...item, url: item.accession && item.document ? `https://www.sec.gov/Archives/edgar/data/${Number(cik)}/${item.accession.replaceAll("-", "")}/${item.document}` : null }));
  const annualFilings = allFilings.filter((item) => item.form === "10-K").slice(0, 5), annual = annualFilings[0], filings = allFilings.slice(0, 8);
  const narrative = await filingNarrative(env, annual);
  const series = makeFundamentalSeries(facts.facts, annualFilings);
  const quarterly = {revenue:quarterlyRevenueSeries(facts.facts,allFilings)};
  if (cik === '0001045810' && annual?.url && !series.shortTermInvestments.some(item => item.end === annual.reportDate)) {
    const document = secCache.get('filing:' + annual.accession)?.value;
    const investment = typeof document === 'string' ? nvidiaInlineInvestments(document, annual) : null;
    if (investment) series.shortTermInvestments.push(investment);
  }
  const sector = submissions.sicDescription || null, bank = /bank|savings|credit/i.test(sector || "");
  return { ticker, cik, name: submissions.name || match.title, sic: sector, isBank: bank, updated: submissions.filingDate || null, filings, annual, narrative, series, quarterly, fundamentals: { revenue: secFact(facts.facts, ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenues"]), netIncome: secFact(facts.facts, ["NetIncomeLoss"]), assets: secFact(facts.facts, ["Assets"]), liabilities: secFact(facts.facts, ["Liabilities"]), equity: secFact(facts.facts, ["StockholdersEquity"]) } };
}
function tradingViewExchange(exchange) {
  const value = String(exchange || "").toUpperCase();
  if (value.includes("NASDAQ")) return "NASDAQ";
  if (value.includes("NYSE AMERICAN") || value.includes("NYSE ARCA") || value === "AMEX") return "AMEX";
  if (value === "NYSE") return "NYSE";
  if (value.includes("CBOE")) return "CBOE";
  return null;
}
async function secTradingViewSymbol(env, ticker) {
  const directory = await cachedSec("ticker-exchanges", () => secJson(env, "https://www.sec.gov/files/company_tickers_exchange.json"));
  const fields = directory.fields || [], tickerIndex = fields.indexOf("ticker"), exchangeIndex = fields.indexOf("exchange");
  const row = (directory.data || []).find((item) => String(item[tickerIndex] || "").toUpperCase() === ticker);
  const exchange = row && tradingViewExchange(row[exchangeIndex]);
  if (!exchange) return { ticker, error: "La asociación de bolsa no está disponible en el directorio oficial de la SEC." };
  return { ticker, exchange, symbol: `${exchange}:${ticker}`, source: "SEC company_tickers_exchange.json" };
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
  if (path === "/api/tradingview-symbol") {
    if (request.method !== "GET") return json({ error: "Método no permitido." }, 405);
    const ticker = (url.searchParams.get("ticker") || "").toUpperCase();
    if (!/^[A-Z0-9.\-]{1,12}$/.test(ticker)) return json({ error: "Símbolo inválido." }, 400);
    try { return json(await secTradingViewSymbol(env, ticker)); } catch (error) { return json({ ticker, error: error.message || "No se pudo resolver la bolsa." }, 502); }
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
