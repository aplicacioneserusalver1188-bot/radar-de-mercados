const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync('worker/template.mjs','utf8'),c=vm.createContext({});
vm.runInContext(src.slice(src.indexOf('function annualFactSeries('),src.indexOf('function cleanFilingText(')),c);
const filing={accession:'annual',reportDate:'2026-01-25',filingDate:'2026-02-25',url:'https://www.sec.gov/example'};
const annual={accn:'annual',form:'10-K',start:'2025-01-27',end:filing.reportDate,val:4.90};
test('EPS selects USD per share and records provenance',()=>{
 const facts={'us-gaap':{EPS:{units:{'USD/shares':[annual],USD:[{...annual,val:999}]}}}};
 const r=c.annualFactSeries(facts,['EPS'],[filing],true,'USD/shares')[0];
 assert.equal(r.value,4.90);assert.equal(r.unit,'USD/shares');assert.equal(r.concept,'EPS');assert.equal(r.sourceUrl,filing.url);
});
test('annual flows reject quarters, other accessions and nonfinite values',()=>{
 const facts={'us-gaap':{Revenue:{units:{USD:[{...annual,start:'2025-10-27',val:1},{...annual,accn:'other',val:2},{...annual,val:NaN},{...annual,val:215938000000}]}}}};
 const r=c.annualFactSeries(facts,['Revenue'],[filing]);assert.equal(r.length,1);assert.equal(r[0].value,215938000000);
});
test('balance sheet instants need no start date',()=>{
 const facts={'us-gaap':{Assets:{units:{USD:[{...annual,start:undefined,val:100}]}}}};
 assert.equal(c.annualFactSeries(facts,['Assets'],[filing],false)[0].value,100);
 assert.equal(c.annualFactSeries(facts,['Assets'],[filing],true).length,0);
});
