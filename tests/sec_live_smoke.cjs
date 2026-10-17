// Optional real-document smoke test. Run: SEC_USER_AGENT="Research App contact@yourdomain.com" node tests/sec_live_smoke.cjs
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const url="https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm";
(async()=>{
 const ua=process.env.SEC_USER_AGENT;
 if(!ua) throw new Error("Set SEC_USER_AGENT with an honest app name and contact email.");
 const response=await fetch(url,{headers:{"User-Agent":ua,"Accept":"text/html"}});
 if(!response.ok) throw new Error("SEC HTTP "+response.status+"; do not treat this as extraction failure.");
 const html=await response.text();
 assert.ok(html.length>100000,"Unexpectedly small SEC filing");
 const src=fs.readFileSync("worker/template.mjs","utf8"),a=src.indexOf("function cleanFilingText("),b=src.indexOf("async function filingNarrative(",a);
 const ctx=vm.createContext({});
 vm.runInContext(src.slice(a,b),ctx);
 const sections=ctx.filingSections(ctx.cleanFilingText(html));
 for(const key of ["business","risks","discussion"]) assert.ok(sections[key]?.length>1200,key+" missing");
 assert.match(sections.risks.body,/customer|export|supply/i);
 assert.match(sections.discussion.body,/revenue|gross margin/i);
 const factsResponse=await fetch('https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json',{headers:{'User-Agent':ua,'Accept':'application/json'}});
 if(!factsResponse.ok) throw new Error('SEC companyfacts HTTP '+factsResponse.status);
 const facts=await factsResponse.json();
 vm.runInContext(src.slice(src.indexOf('function annualFactSeries('),src.indexOf('function cleanFilingText(')),ctx);
 vm.runInContext(src.slice(src.indexOf('function makeFundamentalSeries('),src.indexOf('async function secCompany(')),ctx);
 const series=ctx.makeFundamentalSeries(facts.facts,[{accession:'0001045810-26-000021',reportDate:'2026-01-25',url}]);
 assert.equal(series.revenue[0]?.value,215938000000,'FY2026 revenue must match the official 10-K');
 assert.equal(series.netIncome[0]?.value,120067000000,'FY2026 net income must match the official 10-K');
 assert.equal(series.eps[0]?.value,4.90,'FY2026 diluted EPS must match the official 10-K');
 assert.equal(series.eps[0]?.unit,'USD/shares');
 vm.runInContext(src.slice(src.indexOf('function nvidiaInlineInvestments('),src.indexOf('async function secCompany(')),ctx);
 const investments=ctx.nvidiaInlineInvestments(html,{accession:'0001045810-26-000021',reportDate:'2026-01-25',url});
 assert.equal(investments?.value,51951000000,'NVIDIA marketable securities must match the consolidated balance sheet');
 series.shortTermInvestments=[investments];
 for(const key of ['cash','shortTermInvestments','debtCurrent','debtNoncurrent','dilutedShares','operatingCashFlow','capitalExpenditures']) {
  assert.ok(Number.isFinite(series[key][0]?.value),key+' missing for per-share DCF');
  assert.equal(series[key][0].end,'2026-01-25',key+' has a different fiscal closing date');
 }
 const page=fs.readFileSync('consultor.html','utf8');
 const reportContext=vm.createContext({Intl});
 vm.runInContext(page.slice(page.indexOf('function h('),page.indexOf('async function secAsset(')),reportContext);
 vm.runInContext('function n(v){return String(v)}',reportContext);
 const fcf=series.operatingCashFlow[0].value-Math.abs(series.capitalExpenditures[0].value);
 const report=reportContext.dcfReport({annual:{url}},series,fcf);
 for(const label of ['Conservador','Base','Optimista','Valor patrimonial por acción','Anexo técnico','10-K SEC']) assert.ok(report.includes(label),label+' missing');
 assert.ok(!report.includes('Valor por acción no disponible'));
 assert.ok(!/NaN|Infinity/.test(report));
 console.log('PASS: real NVIDIA SEC inputs render all three DCF scenarios, per-share valuation and technical appendix');
 console.log("PASS: NVIDIA FY2026 live 10-K, sections present and plausible");
})().catch(e=>{console.error("FAIL:",e.message);process.exitCode=1});
