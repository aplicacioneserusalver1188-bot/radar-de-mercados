const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('consultor.html','utf8'),ctx=vm.createContext({Intl,n:v=>String(Math.round(v*100)/100)});
vm.runInContext(html.slice(html.indexOf('function h(value)'),html.indexOf('async function secAsset(')),ctx);
const fact=(value,year)=>({value,fiscalYear:String(year),end:year+'-06-30'});
const series=()=>({revenue:[fact(100,2025),fact(120,2026)],operatingIncome:[fact(20,2025),fact(30,2026)],operatingCashFlow:[fact(40,2025),fact(50,2026)],capitalExpenditures:[fact(10,2025),fact(30,2026)],netIncome:[fact(15,2025),fact(25,2026)]});
test('synthesis quantifies margin expansion and explains the cash divergence',()=>{
 const s=series(),out=ctx.profitabilityReading({series:s},20,25,20,20);
 assert.match(out,/hay expansión/);assert.match(out,/\+20%.*\+25%/);assert.match(out,/variación de.*-10/);assert.match(out,/cambio del flujo operativo/);assert.match(out,/no se tradujo en más caja/);
 assert.doesNotMatch(out,/comparar con ejercicios|verificar si/);
 assert.match(ctx.fundamentalConclusion({series:s},20,25,20),/Crecimiento rentable con presión de caja/);
});
test('mismatched fiscal closes cannot yield a margin or cash diagnosis',()=>{
 const s=series();s.operatingIncome[1].end='2026-03-31';s.capitalExpenditures[1].end='2026-03-31';
 const a=ctx.annualAnalysis(s);assert.equal(a.now.margin,null);assert.equal(a.now.fcf,null);
 assert.doesNotMatch(ctx.fundamentalConclusion({series:s},20,25,20),/^Crecimiento rentable/);
});
test('risk assessment distinguishes measured reinvestment pressure from unquantified disruption',()=>{
 const d={series:series(),narrative:{risks:'Supply chain risk and data center capital expenditure'}};
 assert.match(ctx.riskInterpretation(d),/Presión de caja observada/);assert.match(ctx.riskInterpretation(d),/Impacto no cuantificado/);
 assert.doesNotMatch(ctx.riskMonitoringMatrix(d),/Por evaluar|Qué vigilar/);
});
test('segment contributions require reconciliation of both periods',()=>{
 const s=series();const group=(end,a,b)=>({axis:'us-gaap:StatementBusinessSegmentsAxis',concept:'us-gaap:Revenues',end,sourceUrl:'https://www.sec.gov/example',members:[{member:'x:CloudMember',value:a},{member:'x:DevicesMember',value:b}]});
 const d={narrative:{segmentRevenue:[group('2025-06-30',60,40),group('2026-06-30',80,40)]}};
 assert.match(ctx.segmentAnalysis(d,s),/Cloud aporta el mayor incremento/);assert.match(ctx.segmentAnalysis(d,s),/100% del cambio consolidado/);
 d.narrative.segmentRevenue[0].members[0].value=50;
 assert.match(ctx.segmentAnalysis(d,s),/no resuelta/);assert.doesNotMatch(ctx.segmentAnalysis(d,s),/aporta el mayor/);
});
const worker=fs.readFileSync('worker/template.mjs','utf8'),parser=vm.createContext({});
vm.runInContext(worker.slice(worker.indexOf('function segmentRevenue('),worker.indexOf('async function filingNarrative(')),parser);
function sample(extra='',value='60'){
 return '<xbrli:context id="seg"><xbrli:entity><xbrli:identifier>123</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">x:CloudMember</xbrldi:explicitMember>'+extra+'</xbrli:segment></xbrli:entity><xbrli:period><xbrli:startDate>2025-07-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context><xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit><ix:nonFraction name="us-gaap:Revenues" contextRef="seg" unitRef="usd" format="ixt:num-dot-decimal" scale="6">'+value+'</ix:nonFraction>';
}
const filing={reportDate:'2026-06-30',url:'https://www.sec.gov/Archives/edgar/data/123/filing.htm'};
test('inline segment revenue preserves annual period, USD scale and provenance',()=>{
 const out=parser.segmentRevenue(sample(),filing);assert.equal(out[0].members[0].value,60e6);assert.equal(out[0].sourceUrl,filing.url);
});
test('segment extraction rejects multiple dimensions, currency mismatch and conflicting facts',()=>{
 assert.equal(parser.segmentRevenue(sample('<xbrldi:explicitMember dimension="x:RegionAxis">x:USMember</xbrldi:explicitMember>'),filing).length,0);
 assert.equal(parser.segmentRevenue(sample().replace('iso4217:USD','iso4217:EUR'),filing).length,0);
 const extra='<ix:nonFraction name="us-gaap:Revenues" contextRef="seg" unitRef="usd" format="ixt:num-dot-decimal" scale="6">70</ix:nonFraction>';
 assert.equal(parser.segmentRevenue(sample()+extra,filing).length,0);
});
test('executive summary presents computed findings instead of assigning research',()=>{
 const s=series(),out=ctx.executiveDiagnosis({name:'Example',series:s,narrative:{business:'Business',risks:'Risk'}},s.revenue.at(-1),20,25,20);
 assert.match(out,/Crecimiento rentable con presión de caja/);assert.match(out,/se expandió/);assert.match(out,/disminuyó/);
 assert.doesNotMatch(out,/debe explicarse|para contrastar la tesis|requiere consultar/);
});
test('business analysis identifies documented monetization without inventing absent business',()=>{
 assert.match(ctx.businessReading({narrative:{business:'We offer subscription services and cloud infrastructure to enterprise customers.'}}),/Suscripciones e ingresos recurrentes/);
 assert.match(ctx.businessReading({ticker:'MSFT'}),/Modelo de negocio no documentado/);
 assert.doesNotMatch(ctx.businessReading({ticker:'MSFT'}),/Azure/);
});
test('balance diagnosis quantifies debt coverage and rejects mixed closes',()=>{
 const s=series();Object.assign(s,{assets:[fact(500,2026)],liabilities:[fact(300,2026)],equity:[fact(200,2026)],cash:[fact(40,2026)],debtCurrent:[fact(20,2026)],debtNoncurrent:[fact(80,2026)]});
 const out=ctx.balanceReading({},s);assert.match(out,/\+40%/);assert.match(out,/2 veces el flujo operativo/);assert.match(out,/no equivale por sí solo a insolvencia/);
 s.debtCurrent[0].end='2025-06-30';assert.match(ctx.balanceReading({},s),/no se calcula deuda neta/);
});
test('DCF interprets model dependence, preserves section number on unavailable and bank cases',()=>{
 const s=series();const out=ctx.dcfReport({},s,20);
 assert.match(out,/Resultado e interpretación del modelo/);assert.match(out,/del 11% al 13%/);assert.match(out,/período posterior al quinto año/);
 assert.match(ctx.dcfReport({}, {}, null),/<h3>8\./);
 assert.match(ctx.dcfReport({isBank:true},{},null),/DCF industrial no aplicable/);
});
test('falling investment intensity is not described as an increase',()=>{
 const s=series();s.capitalExpenditures=[fact(30,2025),fact(10,2026)];
 assert.match(ctx.investmentPressureReading(s),/menos inversión por unidad/);
 assert.doesNotMatch(ctx.investmentPressureReading(s),/necesita más inversión/);
});
test('complete reports retain all sections and do not delegate the analysis',async()=>{
 const payload={ticker:'EX',name:'Example',series:series(),narrative:{business:'We provide cloud subscription services to customers. '.repeat(5),risks:'We face intense competition and supply chain risk. '.repeat(5),discussion:'Revenue increased while capital expenditure expanded. '.repeat(5),available:true,url:'https://www.sec.gov/example'},annual:{url:'https://www.sec.gov/example'},filings:[]};
 const full=vm.createContext({Intl,n:String,fetch:async()=>({json:async()=>payload})});
 vm.runInContext(html.slice(html.indexOf('function h(value)'),html.indexOf('async function cryptoAsset(')),full);
 const out=await full.secAsset('EX');for(let i=1;i<=9;i++)assert.match(out,new RegExp('<h3>'+i+'\\.'));
 assert.doesNotMatch(out,/comparar con ejercicios|revisar disponibilidad|comparar inversión futura|la siguiente comprobación|debe comprobarse|hay que contrastarlo|requiere leer el MD&A|requiere consultar/);
 assert.match(out,/Modelo comercial identificado/);assert.match(out,/Resultado e interpretación del modelo/);
});
