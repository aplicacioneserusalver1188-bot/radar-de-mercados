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
 console.log("PASS: NVIDIA FY2026 live 10-K, sections present and plausible");
})().catch(e=>{console.error("FAIL:",e.message);process.exitCode=1});
