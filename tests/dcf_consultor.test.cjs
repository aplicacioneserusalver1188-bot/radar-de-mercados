const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const html=fs.readFileSync("consultor.html","utf8");
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
