const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync('worker/template.mjs','utf8'),c=vm.createContext({});
vm.runInContext(src.slice(src.indexOf('function nvidiaInlineInvestments('),src.indexOf('async function secCompany(')),c);
const filing={reportDate:'2026-01-25',accession:'annual',url:'https://www.sec.gov/example'};
const fixture=(extra='',unit='iso4217:USD',date='2026-01-25')=>`<xbrli:context id="consolidated"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0001045810</xbrli:identifier>${extra}</xbrli:entity><xbrli:period><xbrli:instant>${date}</xbrli:instant></xbrli:period></xbrli:context><xbrli:unit id="usd"><xbrli:measure>${unit}</xbrli:measure></xbrli:unit><ix:nonFraction name="nvda:MarketableSecuritiesAndEquitySecuritiesFVNI" contextRef="consolidated" unitRef="usd" format="ixt:num-dot-decimal" scale="6">51,951</ix:nonFraction>`;
test('issuer extension scales USD and retains provenance',()=>{
 const r=c.nvidiaInlineInvestments(fixture(),filing);assert.equal(r.value,51951000000);assert.equal(r.sourceUrl,filing.url);assert.equal(r.extraction,'inline-xbrl');
});
test('rejects dimensional contexts, foreign currencies and wrong dates',()=>{
 assert.equal(c.nvidiaInlineInvestments(fixture('<xbrli:segment/>'),filing),null);
 assert.equal(c.nvidiaInlineInvestments(fixture('','iso4217:EUR'),filing),null);
 assert.equal(c.nvidiaInlineInvestments(fixture('','iso4217:USD','2025-01-26'),filing),null);
});
test('conflicting consolidated values are unavailable',()=>{
 const html=fixture()+fixture().replace('51,951','99,999');assert.equal(c.nvidiaInlineInvestments(html,filing),null);
});
