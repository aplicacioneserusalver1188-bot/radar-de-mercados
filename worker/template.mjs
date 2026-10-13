const indexPage = __INDEX_PAGE__;
const consultorPage = __CONSULTOR_PAGE__;
const marketData = __MARKET_DATA__;
const bursts = new Map();
let usageStoreReady;
const htmlHeaders = { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff", "content-security-policy": "default-src 'self'; connect-src 'self' https://raw.githubusercontent.com; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src https://www.cmegroup.com" };

function burstLimited(ip) {
  const now = Date.now(), previous = (bursts.get(ip) || []).filter((t) => now - t < 60000);
  if (previous.length >= 12) return true;
  previous.push(now); bursts.set(ip, previous); return false;
}
function json(value, status = 200) { return new Response(JSON.stringify(value), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" } }); }
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
