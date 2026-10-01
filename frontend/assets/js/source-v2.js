// @ts-ignore Browser module URL carries a cache revision.
import { invoiceApi, errorText } from "./api-v2.js?v=20260930";
// @ts-ignore Browser module URL carries a cache revision.
import { escapeHtml } from "./common.js?v=20260930";
// @ts-ignore Browser module URL carries a cache revision.
import { icon } from "./ui.js?v=20260930";

export function evidencePages(evidence) {
  if (evidence?.schema_version === "document-2.0" && Array.isArray(evidence.pages))
    return evidence.pages.map((entry) => entry.evidence?.blocks || []);
  return Array.isArray(evidence?.blocks) ? [evidence.blocks] : [];
}
function blockPage(pages, id) { return pages.findIndex((blocks) => blocks.some((block) => block.block_id === id)); }
function polygonPoints(block, rotation = 0) {
  if (!Array.isArray(block.polygon) || block.polygon.length !== 4) return null;
  const points = block.polygon.map((p) => [Number(p.x), Number(p.y)]);
  const rotated = points.map(([x, y]) => rotation === 90 ? [1 - y, x] : rotation === 180 ? [1 - x, 1 - y] : rotation === 270 ? [y, 1 - x] : [x, y]);
  return points.every(([x, y]) => Number.isFinite(x) && Number.isFinite(y) && x >= 0 && x <= 1 && y >= 0 && y <= 1)
    ? rotated.map(([x, y]) => `${x * 100},${y * 100}`).join(" ") : null;
}
export function createSourceViewer(host, receiptId, onBlock) {
  let blobUrl = null, type = null, pdf = null, pdfTask = null, sourceImage = null, page = 0, zoom = 1, rotation = 0, pages = [], highlighted = new Set();
  let renderVersion = 0, renderTask = null, destroyed = false, resizeTimer, previousWidth = 0, sourceError = "", evidenceError = "", loading;
  host.innerHTML = `<div class="viewer-toolbar"><button type="button" data-view="previous" aria-label="Trang trước">${icon("back")}</button><span data-view="page">Trang 1 / 1</span><button type="button" data-view="next" aria-label="Trang sau">${icon("chevron")}</button><button type="button" data-view="zoom-out" aria-label="Thu nhỏ">−</button><span data-view="zoom">100%</span><button type="button" data-view="zoom-in" aria-label="Phóng to">+</button><button type="button" data-view="rotate" aria-label="Xoay 90 độ" title="Xoay 90 độ">${icon("rotate")}</button><button type="button" data-view="fit">Vừa chiều rộng</button></div><div class="viewer-scroll"><div class="viewer-surface"></div></div><p class="viewer-note" role="status"></p>`;
  const surface = host.querySelector(".viewer-surface"), note = host.querySelector(".viewer-note"), scroll = host.querySelector(".viewer-scroll");
  const total = () => pdf?.numPages || Math.max(1, pages.length);
  function updateToolbar() {
    host.querySelector('[data-view="page"]').textContent = `Trang ${page + 1} / ${total()}`;
    host.querySelector('[data-view="zoom"]').textContent = `${Math.round(zoom * 100)}%`;
    host.querySelector('[data-view="previous"]').disabled = page === 0;
    host.querySelector('[data-view="next"]').disabled = page >= total() - 1;
  }
  function drawBlocks() {
    const overlay = surface.querySelector(".evidence-layer"), blocks = pages[page] || [];
    if (overlay) overlay.innerHTML = blocks.map((block) => {
      const points = polygonPoints(block, rotation);
      return points ? `<polygon tabindex="0" role="button" aria-label="Vùng chữ ${escapeHtml(block.text)}" data-block="${escapeHtml(block.block_id)}" points="${points}" class="${highlighted.has(block.block_id) ? "is-active" : ""}"><title>${escapeHtml(block.text)}</title></polygon>` : "";
    }).join("");
    note.textContent = sourceError || evidenceError || (highlighted.size && !blocks.some((block) => highlighted.has(block.block_id)) ? "Không có vị trí nguồn cho ô này trên trang đang xem." : highlighted.size ? "Đang đánh dấu vùng chữ nguồn." : "Chọn một ô dữ liệu để xem vị trí nguồn.");
  }
  async function render() {
    const version = ++renderVersion;
    renderTask?.cancel(); renderTask = null; updateToolbar();
    if (destroyed) return;
    if (!blobUrl) { surface.innerHTML = '<p class="viewer-fallback">Chưa có tài liệu nguồn để xem.</p>'; return; }
    const available = Math.max(100, scroll.clientWidth - 24), wrap = document.createElement("div"); wrap.className = "viewer-page";
    const canvas = document.createElement("canvas"), context = canvas.getContext("2d"), pixelRatio = Math.min(2, window.devicePixelRatio || 1);
    if (type === "application/pdf") {
      if (!pdf) { surface.innerHTML = '<p class="viewer-fallback">Không thể mở PDF. Hãy tải lại tài liệu.</p>'; return; }
      const pdfPage = await pdf.getPage(page + 1);
      if (version !== renderVersion || destroyed) return;
      const base = pdfPage.getViewport({scale: 1, rotation}), viewport = pdfPage.getViewport({scale: available / base.width * zoom, rotation});
      canvas.width = Math.ceil(viewport.width * pixelRatio); canvas.height = Math.ceil(viewport.height * pixelRatio);
      canvas.style.width = `${viewport.width}px`; canvas.style.height = `${viewport.height}px`;
      wrap.append(canvas); surface.replaceChildren(wrap);
      const task = pdfPage.render({canvas, canvasContext: context, viewport, transform: [pixelRatio, 0, 0, pixelRatio, 0, 0]}); renderTask = task;
      try { await task.promise; } catch (error) { if (error.name === "RenderingCancelledException") return; throw error; }
    } else {
      if (!sourceImage) return;
      const turned = rotation === 90 || rotation === 270, width = available * zoom, ratio = sourceImage.naturalHeight / sourceImage.naturalWidth;
      const height = width * (turned ? 1 / ratio : ratio);
      canvas.width = Math.ceil(width * pixelRatio); canvas.height = Math.ceil(height * pixelRatio);
      canvas.style.width = `${width}px`; canvas.style.height = `${height}px`;
      context.scale(pixelRatio, pixelRatio); context.translate(width / 2, height / 2); context.rotate(rotation * Math.PI / 180);
      context.drawImage(sourceImage, -(turned ? height : width) / 2, -(turned ? width : height) / 2, turned ? height : width, turned ? width : height);
      canvas.setAttribute("role", "img"); canvas.setAttribute("aria-label", "Ảnh hóa đơn nguồn");
      wrap.append(canvas); surface.replaceChildren(wrap);
    }
    if (version !== renderVersion || destroyed) return;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 100 100"); svg.setAttribute("preserveAspectRatio", "none"); svg.setAttribute("class", "evidence-layer");
    wrap.append(svg); drawBlocks();
  }
  async function safeRender() { try { await render(); } catch (error) { if (!destroyed) note.textContent = errorText(error); } }
  function resize() { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (!destroyed) safeRender(); }, 100); }
  const observer = new ResizeObserver((entries) => { const width = entries[0]?.contentRect.width; if (width > 0 && Math.abs(width - previousWidth) > 1) { previousWidth = width; resize(); } });
  observer.observe(scroll);
  host.addEventListener("click", async (event) => {
    const block = event.target.closest("[data-block]"); if (block) { onBlock?.(block.dataset.block); return; }
    const action = event.target.closest("[data-view]")?.dataset.view;
    if (action === "previous") page = Math.max(0, page - 1);
    else if (action === "next") page = Math.min(total() - 1, page + 1);
    else if (action === "zoom-out") zoom = Math.max(0.5, zoom - 0.25);
    else if (action === "zoom-in") zoom = Math.min(3, zoom + 0.25);
    else if (action === "rotate") rotation = (rotation + 90) % 360;
    else if (action === "fit") zoom = 1;
    else return;
    await safeRender();
  });
  host.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key) && event.target.dataset.block) { event.preventDefault(); onBlock?.(event.target.dataset.block); } });
  return {
    async load() {
      note.textContent = "Đang tải tài liệu nguồn…";
      loading = (async () => {
        const [source, evidence] = await Promise.allSettled([invoiceApi.source(receiptId), invoiceApi.evidence(receiptId)]);
        if (destroyed) return;
        if (evidence.status === "fulfilled") pages = evidencePages(evidence.value);
        else evidenceError = "Không có evidence để đánh dấu.";
        if (source.status === "fulfilled") {
          type = source.value.type; blobUrl = URL.createObjectURL(source.value.blob);
          try {
            if (type === "application/pdf") {
              // @ts-ignore Browser absolute URL resolved by static server.
              const pdfjs = await import("/assets/vendor/pdf.mjs");
              pdfjs.GlobalWorkerOptions.workerSrc = "/assets/vendor/pdf.worker.mjs";
              pdfTask = pdfjs.getDocument({url: blobUrl});
              pdf = await pdfTask.promise;
            } else { sourceImage = new Image(); sourceImage.src = blobUrl; await sourceImage.decode(); }
          } catch (error) { sourceError = `Không mở được tài liệu: ${errorText(error)}`; }
        } else sourceError = "Không có tài liệu nguồn. Dữ liệu vẫn có thể được xem và sửa.";
        if (destroyed) { if (blobUrl) URL.revokeObjectURL(blobUrl); pdfTask?.destroy().catch(() => {}); return; }
        await safeRender(); drawBlocks();
      })();
      await loading;
    },
    async refreshEvidence() {
      await loading; if (destroyed) return;
      try { pages = evidencePages(await invoiceApi.evidence(receiptId)); evidenceError = ""; drawBlocks(); }
      catch { evidenceError = "Không có evidence để đánh dấu."; drawBlocks(); }
    },
    async highlight(ids) {
      highlighted = new Set(ids || []);
      const found = [...highlighted].map((id) => blockPage(pages, id)).find((index) => index >= 0);
      if (found !== undefined && found !== page) { page = found; await safeRender(); }
      else drawBlocks();
      if (highlighted.size && found === undefined && !sourceError) note.textContent = "Không có vị trí nguồn cho ô này.";
    },
    resize,
    destroy() { destroyed = true; renderVersion++; clearTimeout(resizeTimer); observer.disconnect(); renderTask?.cancel(); if (blobUrl) URL.revokeObjectURL(blobUrl); pdfTask?.destroy().catch(() => {}); }
  };
}
