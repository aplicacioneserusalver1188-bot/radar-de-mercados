const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const html=fs.readFileSync("consultor.html","utf8");
test("entire consultor inline script parses as JavaScript",()=>{
 const script=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
 assert.ok(script,"missing inline script");
 assert.doesNotThrow(()=>new vm.Script(script,{filename:"consultor-inline.js"}));
});

const start=html.indexOf("function dcfModel("),end=html.indexOf("function dcfReport(",start);
assert.ok(start>=0&&end>start);
const context=vm.createContext({});
vm.runInContext(html.slice(start,end),context);
const model=context.dcfModel;
test("DCF matches hand-calculated single-year perpetuity",()=>{
 const r=model(100,{fcf:100,growth:0,discount:.1,terminal:0,years:1});
 assert.ok(Math.abs(r.enterpriseValue-1000)<1e-6);
 assert.ok(Math.abs(r.pvFlows-100/1.1)<1e-6);
});
test("rejects non-positive FCF and discount below terminal growth",()=>{
 assert.equal(model(0,{fcf:0,growth:.1,discount:.1,terminal:.03}),null);
 assert.equal(model(100,{fcf:100,growth:.1,discount:.03,terminal:.04}),null);
});
test("five-year forecast has five rows and reconciles to EV",()=>{
 const r=model(100,{fcf:100,growth:.16,discount:.11,terminal:.03});
 assert.equal(r.rows.length,5);
 assert.ok(Math.abs(r.enterpriseValue-r.pvFlows-r.pvTerminal)<1e-6);
});
test("consultor uses matching annual CFO and CapEx periods",()=>{
 assert.match(html,/cfo\.fiscalYear===capex\.fiscalYear&&cfo\.end===capex\.end/);
});

test("unsupported bridge is excluded",()=>{assert.ok(html.includes("se omite el puente experimental"));assert.ok(!html.includes("equity/shares.value"));});
test("DCF annual SEC inputs are traceable",()=>{
 assert.ok(html.includes("10-K SEC"));
 assert.ok(html.includes("sourceYear=latest(s.operatingCashFlow)"));
});

test("NVIDIA investor brief includes sourced segment distinction and risks",()=>{
 assert.match(html,/function nvdaInvestorBrief\(/);
 assert.match(html,/Compute &amp; Networking/);
 assert.match(html,/Data Center: USD 193\.737 millones/);
 assert.match(html,/concentración en clientes/);
 assert.match(html,/nvdaInvestorBrief\(d,s,rev,revGrowth,grossMargin,opMargin,netMargin,fcf\)/);
});
test("executive scope does not deny the illustrative DCF",()=>{
 assert.doesNotMatch(html,/no es valoración ni recomendación/);
 assert.match(html,/incluye una valoración DCF ilustrativa/);
});

test("10-Q revenue section stays independent of annual DCF",()=>{
 assert.match(html,/function quarterlySecBrief\(/);
 assert.match(html,/No son acumulados semestrales/);
 assert.match(html,/El DCF anterior conserva su base anual histórica/);
});

test("DCF sensitivity matrix varies growth and discount with fixed terminal rate",()=>{
 assert.match(html,/function dcfSensitivity\(base\)/);
 assert.match(html,/const rates=\[\.09,\.11,\.13\],growthRates=\[\.10,\.16,\.22\],terminal=\.03/);
 assert.match(html,/dcfSensitivity\(fcf\)/);
});

test("FCFE model refuses missing debt financing facts and does not double adjust cash/debt",()=>{
 assert.match(html,/function fcfeAlternative\(s,fcf\)/);
 assert.match(html,/fcf\+proceeds\.value-Math\.abs\(repayments\.value\)/);
 assert.match(html,/La ausencia de una etiqueta XBRL no se interpreta como cero/);
 assert.match(html,/no se vuelve a sumar efectivo ni restar deuda/);
 assert.match(html,/fcfeAlternative\(s,fcf\)/);
});

test("Microsoft FY2026 analysis identifies actual businesses and SEC source",()=>{
 assert.match(html,/function microsoftInvestorAnalysis\(/);
 assert.match(html,/Productivity and Business Processes/);
 assert.match(html,/No se presentan tasas operativas específicas sin extraer y verificar/);
 assert.match(html,/d\.narrative\?\.reportDate==='2026-06-30'/);
 assert.match(html,/microsoftInvestorAnalysis\(d,s,rev,revGrowth,grossMargin,opMargin,netMargin,fcf\)/);
});

test("generic SEC investor diagnosis does not invent company-specific business claims",()=>{
 assert.match(html,/function generalInvestorAnalysis\(/);
 assert.match(html,/El extracto Business no se recuperó automáticamente/);
 assert.match(html,/no se afirma conocer segmentos, clientes o ventajas competitivas particulares/);
 assert.match(html,/generalInvestorAnalysis\(d,s,rev,revGrowth,grossMargin,opMargin,netMargin,fcf\)/);
});

test("generic issuer analysis connects SEC narrative evidence to risk implications",()=>{
 assert.match(html,/function secNarrativeSignals\(d\)/);
 assert.match(html,/Riesgos localizados en texto SEC y por qué importan/);
 assert.match(html,/Interpretación causal a comprobar/);
 assert.match(html,/No se recuperaron suficientes pasajes/);
});

test("report core uses financial interpretation",()=>{assert.ok(html.includes("executiveDiagnosis(d,rev,revGrowth,opMargin,fcf)"));assert.ok(html.includes("riskInterpretation(d)"));assert.ok(html.includes("fundamentalConclusion(d,revGrowth,opMargin,fcf)"));});

test('Microsoft FY2026 operational metrics require verified filing period',()=>{assert.match(html,/fy\?'El 10-K del ejercicio FY2026 está disponible/);assert.match(html,/Las métricas operativas específicas de FY2026 no se presentan/);});

test('multi-year analysis and period-matched margin comparison are rendered',()=>{assert.match(html,/function multiYearReading\(/);assert.match(html,/\$\{multiYearReading\(s\)\}/);assert.match(html,/function marginTrendReading\(/);assert.match(html,/\$\{marginTrendReading\(s\)\}/);assert.match(html,/x\.end===r\.end&&x\.fiscalYear===r\.fiscalYear/);});

test('risk interpretation identifies themes rather than claiming causal evidence',()=>{assert.match(html,/Temas detectados en el texto SEC/);assert.match(html,/no una atribución causal/);assert.match(html,/Ver documento SEC original/);});

test('ratios only divide SEC facts from matching fiscal periods',()=>{assert.match(html,/rev\.end===ni\.end&&rev\.fiscalYear===ni\.fiscalYear/);assert.match(html,/rev\.end===gross\.end&&rev\.fiscalYear===gross\.fiscalYear/);assert.match(html,/rev\.end===op\.end&&rev\.fiscalYear===op\.fiscalYear/);assert.match(html,/ni\.end===cfo\.end&&ni\.fiscalYear===cfo\.fiscalYear/);});

test('Microsoft FY2026 metrics require retrieved 10-K narrative and source URL',()=>{assert.match(html,/d\.narrative\?\.available===true&&!!d\.narrative\?\.url/);assert.match(html,/Riesgos para contrastar con el 10-K/);});

test('balance and growth comparisons respect matching dates and consecutive years',()=>{assert.match(html,/current\.fiscalYear===long\.fiscalYear/);assert.match(html,/assets\.fiscalYear===equity\.fiscalYear/);assert.match(html,/cash\.fiscalYear===current\.fiscalYear/);assert.match(html,/Number\(x\.fiscalYear\)-Number\(revenues\[i\]\.fiscalYear\)===1/);assert.match(html,/Number\(z\.year\)-Number\(a\.year\)!==1/);});

test('main financial metrics require aligned fiscal periods',()=>{assert.match(html,/Number\(rev\.fiscalYear\)-Number\(priorRev\.fiscalYear\)===1/);assert.match(html,/Number\(ni\.fiscalYear\)-Number\(priorNi\.fiscalYear\)===1/);assert.match(html,/ni\.end===equity\.end&&Number\(equity\.fiscalYear\)-Number\(priorEquity\.fiscalYear\)===1/);assert.match(html,/ni\.end===assets\.end&&Number\(assets\.fiscalYear\)-Number\(priorAssets\.fiscalYear\)===1/);assert.match(html,/equity\.end===assets\.end&&equity\.fiscalYear===assets\.fiscalYear/);});

test('SEC annual balance series select instant XBRL facts',()=>{const worker=fs.readFileSync('worker/template.mjs','utf8');assert.match(worker,/if \(!isFlow\) return !item\.start/);assert.match(worker,/item\.end !== filing\.reportDate/);});

test('Microsoft operating growth claims are not hardcoded without direct verification',()=>{assert.match(html,/Microsoft Cloud creció 27%/);assert.match(html,/Azure y otros servicios de nube crecieron 41%/);assert.match(html,/const verified=d.ticker==='MSFT'/);assert.match(html,/No se presentan tasas operativas específicas sin extraer y verificar/);});

test('reinvestment analysis links CapEx to operating cash and annual revenue',()=>{assert.match(html,/function investmentPressureReading\(s\)/);assert.match(html,/\$\{investmentPressureReading\(s\)\}/);assert.match(html,/rev\.end!==cfo\.end\|\|rev\.end!==cap\.end/);assert.match(html,/Number\(rev\.fiscalYear\)-Number\(prevRev\.fiscalYear\)===1/);});

test('annual SEC narrative evidence is shown with original source and missing-data guard',()=>{assert.match(html,/function secEvidenceReading\(d\)/);assert.match(html,/\$\{secEvidenceReading\(d\)\}/);assert.match(html,/no se extrajeron pasajes verificables del 10-K/);assert.match(html,/Consultar 10-K original/);assert.match(html,/h\(evidence\.trim\(\)\)/);});

test('SEC evidence requires verified annual report and rejects boilerplate',()=>{assert.match(html,/if\(!n\.url\|\|!n\.available\)return/);assert.match(html,/informe anual original no está verificado/);assert.match(html,/table of contents\|forward\.looking statements/);});

test('Microsoft report distinguishes verified results from unverified segment growth',()=>{assert.match(html,/Comprobación de indicadores operativos:/);assert.doesNotMatch(html,/Indicadores operativos FY2026 reportados:/);assert.match(html,/sin atribuir automáticamente el crecimiento agregado a esos productos/);});

test('integrated thesis is shared by Microsoft and NVIDIA and checks cash-flow periods',()=>{assert.match(html,/function integratedInvestmentThesis\(d,s,rev,revGrowth,opMargin,fcf\)/);assert.match(html,/\$\{integratedInvestmentThesis\(d,s,rev,revGrowth,opMargin,fcf\)\}/);assert.match(html,/rev\.end===cfo\.end&&rev\.end===cap\.end/);assert.match(html,/d\.ticker==='MSFT'/);assert.match(html,/d\.ticker==='NVDA'/);assert.match(html,/Sin estas verificaciones no se emite una recomendación/);});

test('integrated thesis derives cash remainder from aligned cash flow and capex',()=>{assert.match(html,/Number\.isFinite\(cfo\.value\)&&Number\.isFinite\(cap\.value\)/);assert.match(html,/cfo\.value-Math\.abs\(cap\.value\)/);});

test('Microsoft FY2026 operating evidence requires matching SEC year and cites original 10-K',()=>{assert.match(html,/function microsoft2026OperatingEvidence\(d,rev\)/);assert.match(html,/rev\?\.end==='2026-06-30'/);assert.match(html,/d\.narrative\?\.reportDate==='2026-06-30'/);assert.match(html,/Microsoft Cloud creció 27%/);assert.match(html,/Azure y otros servicios de nube crecieron 41%/);assert.match(html,/Microsoft 365 Commercial cloud creció 17%/);assert.match(html,/msft-20260630\.htm/);});

test('Microsoft operating evidence rejects NVIDIA and mismatched annual period',()=>{const a=html.indexOf('function microsoft2026OperatingEvidence('),z=html.indexOf('function microsoftInvestorAnalysis(',a);const ctx=vm.createContext({});vm.runInContext(html.slice(a,z),ctx);const d={ticker:'MSFT',narrative:{reportDate:'2026-06-30',available:true,url:'https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm'}};assert.match(ctx.microsoft2026OperatingEvidence(d,{end:'2026-06-30'}),/Microsoft Cloud creció 27%/);assert.doesNotMatch(ctx.microsoft2026OperatingEvidence({...d,ticker:'NVDA'},{end:'2026-06-30'}),/Microsoft Cloud creció 27%/);assert.doesNotMatch(ctx.microsoft2026OperatingEvidence(d,{end:'2025-06-30'}),/Microsoft Cloud creció 27%/);});

test('investment thesis rejects unmatched annual cash flow and CapEx',()=>{const a=html.indexOf('function integratedInvestmentThesis('),z=html.indexOf('function secEvidenceReading(',a);const ctx=vm.createContext({latest:v=>(v||[]).at(-1)||null,previous:v=>(v||[]).at(-2)||null,pct:(n,d)=>d?n/d*100:null,fmtPct:v=>String(v)+'%',usd:v=>'USD '+v,h:v=>String(v)});vm.runInContext(html.slice(a,z),ctx);const rev={end:'2026-06-30',fiscalYear:'2026',value:1000};const cfo={end:rev.end,fiscalYear:rev.fiscalYear,value:200};const cap={end:rev.end,fiscalYear:rev.fiscalYear,value:80};const fn=ctx.integratedInvestmentThesis;const good=fn({ticker:'MSFT'},{operatingCashFlow:[cfo],capitalExpenditures:[cap]},rev,10,20,120);assert.match(good,/USD 120/);const bad=fn({ticker:'MSFT'},{operatingCashFlow:[cfo],capitalExpenditures:[{...cap,end:'2025-06-30'}]},rev,10,20,120);assert.match(bad,/Sin flujo operativo y CapEx del mismo ejercicio/);assert.doesNotMatch(bad,/USD 120/);});

test('Microsoft operating evidence rejects non-Microsoft SEC archive URLs',()=>{const a=html.indexOf('function microsoft2026OperatingEvidence('),z=html.indexOf('function microsoftInvestorAnalysis(',a),ctx=vm.createContext({});vm.runInContext(html.slice(a,z),ctx);const d={ticker:'MSFT',narrative:{reportDate:'2026-06-30',available:true,url:'https://www.sec.gov/Archives/edgar/data/1045810/nvda.htm'}};assert.doesNotMatch(ctx.microsoft2026OperatingEvidence(d,{end:'2026-06-30'}),/Microsoft Cloud creció 27%/);});


test("SEC heading parser accepts conventional Microsoft 10-K headings",()=>{
 const worker=fs.readFileSync("worker/template.mjs","utf8");
 const start=worker.indexOf("const FILING_HEADINGS = ["),end=worker.indexOf("function filingEvidence(",start);
 assert.ok(start>=0&&end>start);
 const ctx=vm.createContext({});vm.runInContext(worker.slice(start,end),ctx);
 const sample=[
  "ITEM 1. BUSINESS","Microsoft cloud services ".repeat(80),
  "ITEM 1A. RISK FACTORS","Competition and security risks ".repeat(80),
  "ITEM 1B. UNRESOLVED STAFF COMMENTS",
  "ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS",
  "Operating results and cash flow ".repeat(80),
  "ITEM 7A. QUANTITATIVE AND QUALITATIVE DISCLOSURES"
 ].join(String.fromCharCode(10));
 const sections=ctx.filingSections(sample);
 assert.ok(sections.business?.body.includes("Microsoft cloud"));
 assert.ok(sections.risks?.body.includes("Competition"));
 assert.ok(sections.discussion?.body.includes("Operating results"));
});

test("SEC parser recognizes Microsoft FY2026 spaced headings",()=>{
 const worker=fs.readFileSync("worker/template.mjs","utf8");
 const a=worker.indexOf("const FILING_HEADINGS = ["),b=worker.indexOf("function filingEvidence(",a),ctx=vm.createContext({});
 vm.runInContext(worker.slice(a,b),ctx);
 const sample=["ITEM 1. B USINESS","Microsoft Azure and cloud subscriptions ".repeat(80),"ITEM 1A. RIS K FACTORS","Competition and datacenter costs ".repeat(80),"ITEM 1B. UNRESOLVE D STAFF COMMENTS","ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS","Cash flows and margins ".repeat(80),"ITEM 7A. QUANTITATIVE AND QUALITATIVE DISCLOSURES"].join(String.fromCharCode(10));
 const sections=ctx.filingSections(sample);
 assert.ok(sections.business?.body.includes("Microsoft Azure"));
 assert.ok(sections.risks?.body.includes("Competition"));
 assert.ok(sections.discussion?.body.includes("Cash flows"));
});

test("SEC filing parser handles Item numbers and titles on separate lines",()=>{
 const worker=fs.readFileSync("worker/template.mjs","utf8"),a=worker.indexOf("const FILING_HEADINGS = ["),b=worker.indexOf("function filingEvidence(",a),ctx=vm.createContext({});
 vm.runInContext(worker.slice(a,b),ctx);
 const sample=["ITEM 1","BUSINESS","Microsoft Azure and cloud subscriptions ".repeat(80),"ITEM 1A","RISK FACTORS","Competition and datacenter costs ".repeat(80),"ITEM 1B. UNRESOLVED STAFF COMMENTS","ITEM 7","MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS","Cash flows and margins ".repeat(80),"ITEM 7A. QUANTITATIVE AND QUALITATIVE DISCLOSURES"].join(String.fromCharCode(10));
 const sections=ctx.filingSections(sample);
 assert.ok(sections.business?.body.includes("Microsoft Azure"));
 assert.ok(sections.risks?.body.includes("Competition"));
 assert.ok(sections.discussion?.body.includes("Cash flows"));
});

test("SEC extractor excludes long numeric table-of-contents fragments",()=>{
 const worker=fs.readFileSync("worker/template.mjs","utf8"),a=worker.indexOf("const FILING_HEADINGS = ["),b=worker.indexOf("function filingEvidence(",a),ctx=vm.createContext({});
 vm.runInContext(worker.slice(a,b),ctx);
 const sample=["ITEM 1. BUSINESS",("1234 5678 9012 3456 ").repeat(60),"ITEM 1A. RISK FACTORS","Competition and cloud infrastructure risks ".repeat(80),"ITEM 1B. UNRESOLVED STAFF COMMENTS","ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS","Cash flow and investment discipline ".repeat(80),"ITEM 7A. QUANTITATIVE AND QUALITATIVE DISCLOSURES"].join(String.fromCharCode(10));
 const sections=ctx.filingSections(sample);
 assert.equal(sections.business,null);
 assert.ok(sections.risks?.body.includes("Competition"));
 assert.ok(sections.discussion?.body.includes("Cash flow"));
});

test("SEC narrative normalizes broken headings seen in real MSFT FY2026 filing",()=>{
 const worker=fs.readFileSync("worker/template.mjs","utf8");
 assert.ok(worker.includes('USINESS\\b/gi,"ITEM 1. BUSINESS"'));
 assert.ok(worker.includes('K\\s+FACTORS\\b/gi,"ITEM 1A. RISK FACTORS"'));
 assert.ok(worker.includes('OPERATIONS/gi,"ITEM 7. MANAGEMENT DISCUSSION'));
});

test("DCF blocks mixed fiscal years instead of modeling a misleading cash flow",()=>{
 const html=fs.readFileSync("consultor.html","utf8");
 assert.ok(html.includes("cashYear!==investmentYear"));
 assert.ok(html.includes("DCF bloqueado: el flujo operativo y las inversiones de capital no pertenecen al mismo ejercicio fiscal y fecha de cierre verificables"));
});

test("SEC parser selects substantive Microsoft FY2026 sections instead of contents",()=>{
 const worker=fs.readFileSync("worker/template.mjs","utf8"),a=worker.indexOf("const FILING_HEADINGS = ["),b=worker.indexOf("function filingEvidence(",a),ctx=vm.createContext({});
 vm.runInContext(worker.slice(a,b),ctx);
 const sample=[
  "ITEM 1. BUSINESS","ITEM 1A. RISK FACTORS","ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS",
  "ITEM 1. BUSINESS","GENERAL","Microsoft is a technology company committed to making digital technology and artificial intelligence available broadly. ".repeat(25),
  "ITEM 1A. RISK FACTORS","Our operations and financial results are subject to various risks and uncertainties. ".repeat(30),
  "ITEM 1B. UNRESOLVED STAFF COMMENTS",
  "ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS",
  "The following Management's Discussion and Analysis of Financial Condition and Results of Operations is intended to help the reader understand the results. ".repeat(25),
  "ITEM 7A. QUANTITATIVE AND QUALITATIVE DISCLOSURES"
 ].join(String.fromCharCode(10));
 const sections=ctx.filingSections(sample);
 assert.ok(sections.business?.body.startsWith("GENERAL"));
 assert.ok(sections.risks?.body.startsWith("Our operations"));
 assert.ok(sections.discussion?.body.startsWith("The following"));
});

test("DCF additionally requires identical SEC reporting end dates",()=>{
 const html=fs.readFileSync("consultor.html","utf8");
 assert.ok(html.includes("cashEnd!==investmentEnd"));
 assert.ok(html.includes("mismo ejercicio fiscal y fecha de cierre verificables"));
});
