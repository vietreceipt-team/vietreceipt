// No HTTP interception or test providers. Run only against the isolated synthetic stack.
import { expect, test } from "@playwright/test";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { resolve, join } from "node:path";
import { createHash } from "node:crypto";

const root = resolve(process.env.TV6_DEMO_ROOT || "../.data/tv6-demo");
const manifest = JSON.parse(readFileSync(join(root, "manifest.json"), "utf8"));
if (manifest.synthetic !== true || manifest.split !== "demo" || manifest.dataset !== "tv6-synthetic-review-demo") throw new Error("Only the generated TV6 synthetic demo is allowed");
const mime = {jpg: "image/jpeg", pdf: "application/pdf"};
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const dump = (path, data) => writeFileSync(path, JSON.stringify(data, null, 2));

async function edit(page, section, row, field, value, status = "PRESENT") {
  await page.getByRole("tab", {name: section === "line" ? "Dòng hàng" : section === "tax" ? /^Thuế/ : "Thông tin"}).click();
  const cell = page.locator(`[data-cell="${section}|${row}|${field}"]`);
  if (section === "header") {
    await cell.locator("[data-inspect]").click();
    await page.getByRole("button", {name: "Sửa giá trị", exact: true}).click();
  } else await cell.locator("[data-edit]").click();
  await cell.locator("[data-status]").selectOption(status);
  if (status === "PRESENT") await cell.locator("[data-input]").fill(String(value));
  return cell;
}
async function save(cell) {
  await cell.getByRole("button", {name: "Lưu", exact: true}).click();
  await expect(cell.locator(".cell-state")).toContainText("Đã lưu");
}

for (const sample of manifest.samples) test(`${sample.condition}: real upload → review → conflict → verify → exports`, async ({page, request}, info) => {
  const folder = resolve("real-results", sample.id); mkdirSync(folder, {recursive: true});
  const source = readFileSync(join(root, sample.path)); expect(hash(source)).toBe(sample.sha256);
  const record = {sample: sample.id, condition: sample.condition, source_sha256: sample.sha256, commit: process.env.GITHUB_SHA || null, accuracy: null, status: "STARTED"};
  dump(join(folder, "result.json"), record);
  let rid;
  const get = async suffix => {
    const response = await request.get(`http://127.0.0.1:3104/api/v2/receipts/${rid}${suffix}`);
    expect(response.ok()).toBe(true); return response.json();
  };
  try {
    await page.goto("/upload/");
    await page.locator("#file-input").setInputFiles({name: sample.path, mimeType: mime[sample.path.split(".").pop()], buffer: source});
    const uploaded = page.waitForResponse(r => r.request().method() === "POST" && /\/api\/v2\/receipts$/.test(r.url()));
    await page.getByRole("button", {name: "Tải lên và xử lý"}).click();
    const response = await uploaded; expect(response.status()).toBe(201);
    // Upload immediately navigates; Chromium can discard that response body.
    await expect(page).toHaveURL(/\/receipts\/[0-9a-f-]{36}\/$/);
    rid = new URL(page.url()).pathname.split("/").filter(Boolean).at(-1);
    record.receipt_id = rid;
    await expect.poll(async () => (await get("")).status, {timeout: 840_000, intervals: [2000, 5000]}).toMatch(/NEEDS_REVIEW|FAILED/);
    let detail = await get(""); expect(detail.status).toBe("NEEDS_REVIEW");
    // Processing may already have removed its refresh button; reconcile with a GET.
    await page.reload();
    await expect(page.locator('[data-cell="header||seller_name"]')).toBeVisible({timeout: 20_000});
    await expect(page.locator(".viewer-page canvas")).toBeVisible();
    const before = await get("/machine-results"); dump(join(folder, "machine-before.json"), before); dump(join(folder, "detail-before.json"), detail);
    const attempt = before.attempts.find(a => a.status === "SUCCEEDED" && a.kie_run_id === detail.latest_kie_run_id);
    expect(attempt.provenance.config.providers).toEqual({V2_DOCUMENT_READER_CALLABLE: "ai.document_reader.backend:read_document", V2_KIE_CALLABLE: "ai.kie.v2:extract_invoice"});
    expect(attempt.provenance.config.callables).toEqual({reader: "backend.app.v2.providers:configured_reader", kie: "backend.app.v2.providers:configured_kie"});
    const evidence = await get("/evidence"); dump(join(folder, "evidence.json"), evidence);
    await page.screenshot({path: join(folder, "01-machine.png"), fullPage: true});

    if (sample.id === "challenge") {
      expect(detail.fields.invoice_number.effective_status).toBe("PRESENT");
      expect(detail.fields.invoice_number.effective_value).not.toBe("00001234");
      expect(detail.fields.invoice_symbol.effective_status).toBe("UNREADABLE");
      await save(await edit(page, "header", "", "invoice_symbol", null, "UNREADABLE"));
      record.unreadable_preserved = true;
    }
    const number = await edit(page, "header", "", "invoice_number", "00001234");
    // A second editor advances the real backend version while this browser retains its draft.
    detail = await get("");
    const concurrent = await request.patch(`http://127.0.0.1:3104/api/v2/receipts/${rid}/fields/seller_address/correction`, {data: {value: "1 Sample Street", status: "PRESENT", expected_version: detail.version}});
    expect(concurrent.ok()).toBe(true);
    const conflict = page.waitForResponse(r => r.status() === 409 && r.request().method() === "PATCH");
    await number.getByRole("button", {name: "Lưu", exact: true}).click(); await conflict;
    await expect(page.locator("#stale-banner")).toBeVisible(); await expect(page.locator("#verify")).toBeDisabled();
    await page.screenshot({path: join(folder, "02-conflict.png"), fullPage: true});
    await page.locator("#reload-detail").click(); await expect(page.locator("#stale-banner")).toBeHidden();
    await save(await edit(page, "header", "", "invoice_number", "00001234"));
    await page.locator('[data-cell="header||invoice_number"] [data-inspect]').click();
    await expect(page.locator(".inspector")).toContainText("Máy đọc"); await expect(page.locator(".inspector")).toContainText("Người sửa");
    await page.screenshot({path: join(folder, "03-corrected.png"), fullPage: true});
    await page.locator("#close-inspector").click();
    detail = await get(""); expect(detail.line_items.length).toBeGreaterThan(0);
    const row = detail.line_items[0];
    await save(await edit(page, "line", row.line_id, "description", sample.id === "challenge" ? "Office paper 1" : "Office paper A4"));
    if (row.description.source_block_ids.length) {
      await page.locator(`[data-cell="line|${row.line_id}|description"] [data-edit]`).click();
      await expect(page.locator("polygon.is-active").first()).toBeVisible();
      if (sample.id === "challenge") await expect(page.locator('[data-view="page"]')).toHaveText("Trang 2 / 2");
      await page.screenshot({path: join(folder, "04-source-row.png"), fullPage: true});
      await page.locator(`[data-cell="line|${row.line_id}|description"]`).getByRole("button", {name: "Hủy", exact: true}).click();
    }
    detail = await get("");
    if (detail.tax_breakdown.length) await save(await edit(page, "tax", detail.tax_breakdown[0].tax_id, "rate", "10%"));
    const remaining = page.locator("#review-remaining");
    if (await remaining.count()) {
      await remaining.click(); await page.locator("#batch-all").check(); await page.locator("#batch-apply").click();
    }
    await expect(page.locator("#verify")).toBeEnabled({timeout: 30_000});
    await page.locator("#verify").click(); await expect(page.locator(".verified-label")).toBeVisible();
    const reviewed = await get(""); expect(reviewed.fields.invoice_number.effective_value).toBe("00001234");
    if (sample.id === "challenge") { expect(reviewed.fields.invoice_symbol.effective_status).toBe("UNREADABLE"); expect(reviewed.fields.invoice_symbol.effective_value).toBeNull(); }
    await page.locator(".export-menu summary").click();
    for (const format of ["json", "csv", "xlsx"]) {
      const waiting = page.waitForEvent("download"); await page.locator(`[data-export="${format}"]`).click();
      const download = await waiting; await download.saveAs(join(folder, `reviewed.${format === "csv" ? "zip" : format}`));
      if (format === "json") expect(JSON.parse(readFileSync(join(folder, "reviewed.json"))).header.invoice_number).toBe("00001234");
    }
    const after = await get("/machine-results"); dump(join(folder, "machine-after.json"), after); expect(after).toEqual(before);
    dump(join(folder, "detail-reviewed.json"), reviewed); dump(join(folder, "history.json"), await get("/history"));
    await page.screenshot({path: join(folder, "05-verified.png"), fullPage: true});
    record.status = "PASSED"; record.machine_snapshot_unchanged = true; record.exports = ["json", "csv", "xlsx"];
  } catch (error) {
    record.status = "FAILED"; record.error = String(error.message).slice(0, 1500);
    if (rid) { try { dump(join(folder, "machine-failure.json"), await get("/machine-results")); } catch {} }
    throw error;
  } finally { dump(join(folder, "result.json"), record); await info.attach("result", {path: join(folder, "result.json"), contentType: "application/json"}); }
});
