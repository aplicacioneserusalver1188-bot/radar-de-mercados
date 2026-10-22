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
