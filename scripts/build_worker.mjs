import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const read = (name) => readFileSync(resolve(root, name), "utf8");
const template = read("worker/template.mjs")
  .replace("__INDEX_PAGE__", JSON.stringify(read("index.html")))
  .replace("__CONSULTOR_PAGE__", JSON.stringify(read("consultor.html")))
  .replace("__MARKET_DATA__", JSON.stringify(read("data/market.json")));
rmSync(resolve(root, "dist"), { recursive: true, force: true });
mkdirSync(resolve(root, "dist/server"), { recursive: true });
mkdirSync(resolve(root, "dist/.openai"), { recursive: true });
writeFileSync(resolve(root, "dist/server/index.js"), template);
writeFileSync(resolve(root, "dist/.openai/hosting.json"), read(".openai/hosting.json"));
