import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
rmSync(dist, { recursive: true, force: true });
mkdirSync(dist, { recursive: true });

for (const name of ["assets", "login", "receipts", "upload"]) cpSync(join(root, name), join(dist, name), { recursive: true });
for (const name of ["favicon.svg", "index.html", "og.png", "server.js", "package.json"]) cpSync(join(root, name), join(dist, name));

for (const page of ["index.html", "login/index.html", "upload/index.html", "receipts/index.html", "receipts/detail.html"]) {
  const path = join(dist, page);
  if (!existsSync(path) || !/<!doctype html>/i.test(readFileSync(path, "utf8"))) throw new Error(`Build thiếu HTML hợp lệ: ${page}`);
}

console.log(`Production build: ${readdirSync(dist).length} top-level entries written to dist/`);
