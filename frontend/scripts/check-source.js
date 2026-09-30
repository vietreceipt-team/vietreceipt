import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, extname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const excluded = new Set([".git", "dist", "node_modules"]);

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    if (entry.isDirectory() && excluded.has(entry.name)) return [];
    const path = join(directory, entry.name);
    return entry.isDirectory() ? walk(path) : [path];
  });
}

const files = walk(root);
const forbidden = files.filter((file) => [".ts", ".tsx"].includes(extname(file)));
if (forbidden.length) throw new Error(`Source vẫn còn TypeScript: ${forbidden.map((file) => relative(root, file)).join(", ")}`);

for (const file of files.filter((path) => extname(path) === ".js")) execFileSync(process.execPath, ["--check", file], { stdio: "pipe" });

if (process.argv.includes("--lint")) {
  const uiRoot = join(root, "assets", "js");
  const directFetch = files.filter((file) => file.startsWith(uiRoot) && extname(file) === ".js" && !["api.js", "api-v2.js"].some((name) => file.endsWith(join("assets", "js", name)))).filter((file) => /\bfetch\s*\(/.test(readFileSync(file, "utf8")));
  if (directFetch.length) throw new Error(`fetch() phải nằm trong API boundary: ${directFetch.map((file) => relative(root, file)).join(", ")}`);
  const telemetrySource = readFileSync(join(uiRoot, "review-telemetry.js"), "utf8");
  if (/raw_text|predicted_value|effective_value|field_value|ocr_text|image_data|credential|access_token/.test(telemetrySource)) throw new Error("Telemetry hook không được chứa ảnh, field value, OCR text, token hoặc credential.");
}

console.log(`${process.argv.includes("--lint") ? "Lint" : "Typecheck"}: ${files.length} files OK`);
