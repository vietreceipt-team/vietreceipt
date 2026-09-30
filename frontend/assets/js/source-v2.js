import { invoiceApi, errorText } from "./api-v2.js";
import { escapeHtml } from "./common.js";

export function evidencePages(evidence) {
  if (evidence?.schema_version === "document-2.0" && Array.isArray(evidence.pages))
    return evidence.pages.map((entry) => entry.evidence?.blocks || []);
  return Array.isArray(evidence?.blocks) ? [evidence.blocks] : [];
}
function blockPage(pages, id) { return pages.findIndex((blocks) => blocks.some((block) => block.block_id === id)); }
function polygonPoints(block, rotation = 0) {
  if (!Array.isArray(block.polygon) || block.polygon.length !== 4) return null;
  const points=block.polygon.map((p)=>[Number(p.x),Number(p.y)]);
  const rotated=points.map(([x,y])=>rotation===90?[1-y,x]:rotation===180?[1-x,1-y]:rotation===270?[y,1-x]:[x,y]);
  return points.every(([x,y])=>Number.isFinite(x)&&Number.isFinite(y)&&x>=0&&x<=1&&y>=0&&y<=1)
    ? rotated.map(([x,y])=>`${x*100},${y*100}`).join(" ") : null;
}
export function createSourceViewer(host, receiptId, onBlock) {
  let blobUrl=null, type=null, pdf=null, page=0, zoom=1, rotation=0, pages=[], highlighted=new Set();
  host.innerHTML=`<div class="viewer-toolbar">
    <button type="button" data-view="previous" aria-label="Trang trước">←</button>
    <span data-view="page">Trang 1 / 1</span>
    <button type="button" data-view="next" aria-label="Trang sau">→</button>
    <button type="button" data-view="zoom-out" aria-label="Thu nhỏ">−</button>
    <span data-view="zoom">100%</span>
    <button type="button" data-view="zoom-in" aria-label="Phóng to">+</button>
    <button type="button" data-view="rotate" aria-label="Xoay 90 độ">↻</button>
  </div><div class="viewer-scroll"><div class="viewer-surface"></div></div><p class="viewer-note" role="status"></p>`;
  const surface=host.querySelector(".viewer-surface"), note=host.querySelector(".viewer-note");
  const total=()=>pdf?.numPages||Math.max(1,pages.length);
  function updateToolbar() {
    host.querySelector('[data-view="page"]').textContent=`Trang ${page+1} / ${total()}`;
    host.querySelector('[data-view="zoom"]').textContent=`${Math.round(zoom*100)}%`;
    host.querySelector('[data-view="previous"]').disabled=page===0;
    host.querySelector('[data-view="next"]').disabled=page>=total()-1;
  }
  function drawBlocks() {
    const overlay=surface.querySelector(".evidence-layer");
    if(!overlay)return;
    const blocks=pages[page]||[];
    overlay.innerHTML=blocks.map((block)=>{
      const points=polygonPoints(block,type==="application/pdf"?rotation:0);
      return points ? `<polygon tabindex="0" role="button" aria-label="Vùng chữ ${escapeHtml(block.text)}" data-block="${escapeHtml(block.block_id)}" points="${points}" class="${highlighted.has(block.block_id)?"is-active":""}"><title>${escapeHtml(block.text)}</title></polygon>` : "";
    }).join("");
    note.textContent=highlighted.size && !blocks.some((block)=>highlighted.has(block.block_id))
      ? "Vị trí OCR của ô này không có trên trang đang xem." : highlighted.size ? "Đang đánh dấu vùng chữ nguồn." : "Chọn một ô dữ liệu để xem vị trí nguồn.";
  }
  async function render() {
    updateToolbar();
    if(!blobUrl){surface.innerHTML='<p class="viewer-fallback">Chưa có tài liệu nguồn để xem.</p>';return;}
    surface.replaceChildren();
    const wrap=document.createElement("div");wrap.className="viewer-page";
    if(type==="application/pdf"){
      if(!pdf){surface.innerHTML='<p class="viewer-fallback">Không thể mở PDF. Hãy tải lại tài liệu.</p>';return;}
      const pdfPage=await pdf.getPage(page+1);
      const available=Math.max(280,host.querySelector(".viewer-scroll").clientWidth-32);
      const base=pdfPage.getViewport({scale:1,rotation});
      const viewport=pdfPage.getViewport({scale:available/base.width*zoom,rotation});
      const canvas=document.createElement("canvas");canvas.width=Math.ceil(viewport.width);canvas.height=Math.ceil(viewport.height);
      canvas.style.width=`${viewport.width}px`;canvas.style.height=`${viewport.height}px`;
      wrap.append(canvas);surface.append(wrap);
      await pdfPage.render({canvasContext:canvas.getContext("2d"),viewport,canvas}).promise;
    } else {
      const image=document.createElement("img");image.src=blobUrl;image.alt="Ảnh hóa đơn nguồn";
      image.style.width=`${Math.round(Math.max(280,host.querySelector(".viewer-scroll").clientWidth-32)*zoom)}px`;wrap.style.transform=`rotate(${rotation}deg)`;
      wrap.append(image);surface.append(wrap);
    }
    const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
    svg.setAttribute("viewBox","0 0 100 100");svg.setAttribute("preserveAspectRatio","none");svg.setAttribute("class","evidence-layer");
    wrap.append(svg);drawBlocks();
  }
  host.addEventListener("click",async(event)=>{
    const block=event.target.closest("[data-block]");
    if(block){onBlock?.(block.dataset.block);return;}
    const action=event.target.closest("[data-view]")?.dataset.view;
    if(action==="previous")page=Math.max(0,page-1);
    else if(action==="next")page=Math.min(total()-1,page+1);
    else if(action==="zoom-out")zoom=Math.max(0.5,zoom-0.25);
    else if(action==="zoom-in")zoom=Math.min(3,zoom+0.25);
    else if(action==="rotate")rotation=(rotation+90)%360;
    else return;
    try{await render();}catch(error){note.textContent=errorText(error);}
  });
  host.addEventListener("keydown",(event)=>{if((event.key==="Enter"||event.key===" ")&&event.target.dataset.block){event.preventDefault();onBlock?.(event.target.dataset.block);}});
  return {
    async load(){
      note.textContent="Đang tải tài liệu nguồn…";
      const [source,evidence]=await Promise.allSettled([invoiceApi.source(receiptId),invoiceApi.evidence(receiptId)]);
      if(evidence.status==="fulfilled")pages=evidencePages(evidence.value);
      else note.textContent="Không tải được evidence OCR; vẫn có thể xem tài liệu.";
      if(source.status==="fulfilled"){
        type=source.value.type;blobUrl=URL.createObjectURL(source.value.blob);
        if(type==="application/pdf"){
          try{
            // @ts-ignore Browser absolute URL resolved by static server.
            const pdfjs=await import("/assets/vendor/pdf.mjs");
            pdfjs.GlobalWorkerOptions.workerSrc="/assets/vendor/pdf.worker.mjs";
            pdf=await pdfjs.getDocument({url:blobUrl}).promise;
          }catch(error){note.textContent=`Không mở được PDF: ${errorText(error)}`;}
        }
      } else note.textContent=`Không tải được tài liệu nguồn: ${errorText(source.reason)}`;
      await render();
      if(source.status==="rejected"||evidence.status==="rejected")note.textContent=source.status==="rejected"?"Không có tài liệu nguồn. Dữ liệu vẫn có thể được xem và sửa.":"Không có evidence để đánh dấu.";
    },
    async highlight(ids){
      highlighted=new Set(ids||[]);
      const found=[...highlighted].map((id)=>blockPage(pages,id)).find((index)=>index>=0);
      if(found!==undefined && found!==page){page=found;await render();}
      else drawBlocks();
      if(highlighted.size && found===undefined)note.textContent="Không có vị trí nguồn cho ô này.";
    },
    destroy(){if(blobUrl)URL.revokeObjectURL(blobUrl);pdf?.destroy();}
  };
}
