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
 assert.match(html,/Azure y otros servicios de nube crecieron 41%/);
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

test('Microsoft FY2026 operational metrics require verified filing period',()=>{assert.match(html,/fy\?'Microsoft Cloud creció/);assert.match(html,/Las métricas específicas de FY2026 no se presentan/);});

test('multi-year analysis and period-matched margin comparison are rendered',()=>{assert.match(html,/function multiYearReading\(/);assert.match(html,/\$\{multiYearReading\(s\)\}/);assert.match(html,/function marginTrendReading\(/);assert.match(html,/\$\{marginTrendReading\(s\)\}/);assert.match(html,/x\.end===r\.end&&x\.fiscalYear===r\.fiscalYear/);});

test('risk interpretation identifies themes rather than claiming causal evidence',()=>{assert.match(html,/Temas detectados en el texto SEC/);assert.match(html,/no una atribución causal/);assert.match(html,/Ver documento SEC original/);});

test('ratios only divide SEC facts from matching fiscal periods',()=>{assert.match(html,/rev\.end===ni\.end&&rev\.fiscalYear===ni\.fiscalYear/);assert.match(html,/rev\.end===gross\.end&&rev\.fiscalYear===gross\.fiscalYear/);assert.match(html,/rev\.end===op\.end&&rev\.fiscalYear===op\.fiscalYear/);assert.match(html,/ni\.end===cfo\.end&&ni\.fiscalYear===cfo\.fiscalYear/);});

test('Microsoft FY2026 metrics require retrieved 10-K narrative and source URL',()=>{assert.match(html,/d\.narrative\?\.available===true&&!!d\.narrative\?\.url/);assert.match(html,/Riesgos para contrastar con el 10-K/);});

test('balance and growth comparisons respect matching dates and consecutive years',()=>{assert.match(html,/current\.fiscalYear===long\.fiscalYear/);assert.match(html,/assets\.fiscalYear===equity\.fiscalYear/);assert.match(html,/cash\.fiscalYear===current\.fiscalYear/);assert.match(html,/Number\(x\.fiscalYear\)-Number\(revenues\[i\]\.fiscalYear\)===1/);assert.match(html,/Number\(z\.year\)-Number\(a\.year\)!==1/);});
