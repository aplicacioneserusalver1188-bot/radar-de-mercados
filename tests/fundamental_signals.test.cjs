const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('consultor.html','utf8');
const ctx=vm.createContext({n:String,h:String,latest:x=>x?.at(-1),previous:x=>x?.at(-2),usd:String,fmtPct:String});
vm.runInContext(html.slice(html.indexOf('function fundamentalSignals('),html.indexOf('function fundamentalQualityGate(')),ctx);
const fact=(value,year='2026')=>({value,fiscalYear:year,end:year+'-06-30'});
function fixture(){return {operatingCashFlow:[fact(50,'2025'),fact(70)],capitalExpenditures:[fact(100,'2025'),fact(100)],cash:[fact(200)],debtCurrent:[fact(20)],debtNoncurrent:[fact(80)]};}
test('improving negative cash flow remains under watch',()=>{
 const out=ctx.fundamentalSignals(fixture(),fact(100),10,20,-30);
 assert.match(out,/Generación de caja<\/small><b class="signal-status">Vigilancia/);
});
test('missing debt is unavailable rather than zero',()=>{
 const s=fixture();delete s.debtCurrent;
 assert.match(ctx.fundamentalSignals(s,fact(100),10,20,-30),/Solvencia<\/small><b class="signal-status">Sin datos/);
});
test('cash coverage requires matching dates and uses bank-specific scope',()=>{
 const s=fixture();
 assert.match(ctx.fundamentalSignals(s,fact(100),10,20,-30),/Cobertura de efectivo/);
 s.debtCurrent[0].end='2026-03-31';
 assert.doesNotMatch(ctx.fundamentalSignals(s,fact(100),10,20,-30),/>Cobertura de efectivo</);
 assert.match(ctx.fundamentalSignals(fixture(),fact(100),10,20,-30,true),/Revisión bancaria/);
});
