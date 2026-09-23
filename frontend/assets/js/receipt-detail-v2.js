import { invoiceApi, ApiError, HEADER_GROUPS, LINE_FIELDS, TAX_FIELDS, VALUE_LABELS, STATUS_LABELS, correctionValue, unresolvedCells, errorText } from "./api-v2.js";
import { escapeHtml, formatDate, formatVnd, getReceiptIdFromLocation, renderNavigation } from "./common.js";
import { createSourceViewer } from "./source-v2.js";
renderNavigation();
const main=document.querySelector("#main-content"), receiptId=getReceiptIdFromLocation();
let detail=null, viewer=null, timer=null, pollCount=0, stale=false, saving=false, verifying=false, exporting=false;
const drafts=new Map(), saved=new Set(), errors=new Map();
const key=(section,row,field)=>`${section}|${row}|${field}`;
const moneyFields=new Set(["subtotal","tax_amount","total_amount","unit_price","amount","taxable_amount"]);
const labelMap=Object.fromEntries([...HEADER_GROUPS.flatMap(([,items])=>items),...LINE_FIELDS,...TAX_FIELDS]);
function display(value,field){return value===null||value===undefined||value===""?"—":moneyFields.has(field)&&typeof value==="number"?formatVnd(value):String(value);}
function safe(value){return escapeHtml(value);}
function statusCell(cell){const status=cell?.effective_status||"UNKNOWN";return `<span class="value-status value-${status.toLowerCase()}">${VALUE_LABELS[status]||safe(status)}</span>`;}
function sourceIds(cell){return Array.isArray(cell?.source_block_ids)?cell.source_block_ids:[];}
function renderCell(section,row,field,cell,compact=false){
  const id=key(section,row,field), draft=drafts.get(id),status=draft?.status||cell.effective_status||"UNKNOWN";
  const value=draft?.text??(cell.effective_value===null?"":String(cell.effective_value??""));
  const needs=cell.effective_needs_review, readOnly=detail.status==="VERIFIED";
  const state=stale?"Dữ liệu cũ":saving&&draft?.saving?"Đang lưu":errors.has(id)?"Lỗi lưu":draft?"Chưa lưu":saved.has(id)?"Đã lưu":"";
  const reasons=(cell.review_reasons||[]).map((r)=>`<li>${safe(r)}</li>`).join("");
  return `<div class="review-cell ${needs?"needs-review":""} ${compact?"compact":""}" data-cell="${safe(id)}">
    <div class="cell-top"><strong>${safe(labelMap[field]||field)}</strong>${statusCell(cell)}</div>
    <div class="cell-values"><div><small>Máy đọc · ${safe(VALUE_LABELS[cell.value_status]||"Chưa xác định")}</small><span>${safe(display(cell.normalized_value,field))}</span></div>
    <div><small>Người sửa${cell.has_correction?` · ${safe(VALUE_LABELS[cell.corrected_status]||cell.corrected_status)}`:""}</small><span>${cell.has_correction?safe(display(cell.corrected_value,field)):"—"}</span></div>
    <div><small>Hiệu lực</small><b>${safe(display(cell.effective_value,field))}</b></div></div>
    ${cell.raw_text&&cell.raw_text!==String(cell.normalized_value??"")?`<p class="raw-text">Văn bản gốc: ${safe(cell.raw_text)}</p>`:""}
    ${needs?`<p class="review-warning">Cần kiểm tra${reasons?` · ${safe((cell.review_reasons||[]).join("; "))}`:""}</p>`:""}
    <button type="button" class="evidence-link" data-evidence="${safe(id)}" ${sourceIds(cell).length?"":"disabled"}>${sourceIds(cell).length?`Xem ${sourceIds(cell).length} vùng nguồn`:"Không có vị trí nguồn"}</button>
    ${readOnly?"":`<div class="edit-row"><label><span class="sr-only">Giá trị ${safe(labelMap[field]||field)}</span><input class="v2-input" data-input="${safe(id)}" value="${safe(value)}" ${status==="PRESENT"?"":"disabled"}></label><label><span class="sr-only">Trạng thái ${safe(labelMap[field]||field)}</span><select class="v2-input" data-status="${safe(id)}">${Object.entries(VALUE_LABELS).map(([code,text])=>`<option value="${code}" ${status===code?"selected":""}>${text}</option>`).join("")}</select></label><button type="button" class="v2-button small" data-save="${safe(id)}" ${saving||stale?"disabled":""}>Lưu</button></div>`}
    <p class="cell-state ${errors.has(id)||stale?"v2-error":""}" role="status">${errors.has(id)?safe(errors.get(id)):state}</p>
  </div>`;
}
function renderTables(){
  const rows=detail.line_items.map((row,index)=>`<tr><th scope="row">${index+1}</th>${LINE_FIELDS.map(([field])=>`<td>${renderCell("line",row.line_id,field,row[field],true)}</td>`).join("")}</tr>`).join("");
  const taxes=detail.tax_breakdown.map((row,index)=>`<tr><th scope="row">${index+1}</th>${TAX_FIELDS.map(([field])=>`<td>${renderCell("tax",row.tax_id,field,row[field],true)}</td>`).join("")}</tr>`).join("");
  return `<section class="review-group"><h2>Dòng hàng</h2>${rows?`<div class="table-scroll"><table class="review-table"><thead><tr><th>STT</th>${LINE_FIELDS.map(([,label])=>`<th>${safe(label)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`:'<p class="v2-muted">Backend chưa cung cấp dòng hàng.</p>'}</section>
  <section class="review-group"><h2>Nhóm thuế</h2>${taxes?`<div class="table-scroll"><table class="review-table"><thead><tr><th>STT</th>${TAX_FIELDS.map(([,label])=>`<th>${safe(label)}</th>`).join("")}</tr></thead><tbody>${taxes}</tbody></table></div>`:'<p class="v2-muted">Backend chưa cung cấp nhóm thuế.</p>'}</section>`;
}
function renderReview(){
  const unresolved=unresolvedCells(detail),readOnly=detail.status==="VERIFIED";
  const groups=HEADER_GROUPS.map(([title,fields])=>`<section class="review-group"><h2>${title}</h2><div class="field-grid">${fields.map(([field])=>renderCell("header","",field,detail.fields[field]||{},false)).join("")}</div></section>`).join("");
  document.querySelector("#detail-body").innerHTML=`${readOnly?'<div class="v2-success">Hóa đơn đã được backend xác nhận. Dữ liệu chỉ đọc.</div>':unresolved.length?`<div class="v2-warning"><strong>Còn ${unresolved.length} ô cần kiểm tra.</strong><details><summary>Xem các ô chưa xử lý</summary><ul>${unresolved.map(([group,name])=>`<li>${safe(group)} · ${safe(labelMap[name]||name)}</li>`).join("")}</ul></details></div>`:'<div class="v2-success">Các ô backend đánh dấu đã được xử lý. Bạn có thể xác nhận.</div>'}
  ${groups}${renderTables()}
  <section class="review-actions">${readOnly?`<h2>Xuất dữ liệu đã xác nhận</h2><div class="button-row"><button type="button" class="v2-button" data-export="json">Tải JSON</button><button type="button" class="v2-button" data-export="csv">Tải CSV (ZIP)</button><button type="button" class="v2-button" data-export="xlsx">Tải Excel</button></div>`:`<button type="button" id="verify" class="v2-button" ${unresolved.length||drafts.size||stale||saving?"disabled":""}>Xác nhận hóa đơn</button><p>${unresolved.length?`Cần kiểm tra ${unresolved.length} ô trước khi xác nhận.`:drafts.size?"Hãy lưu các thay đổi đang soạn trước khi xác nhận.":stale?"Hãy tải phiên bản mới.":"Backend sẽ quyết định kết quả xác nhận cuối cùng."}</p>`}<p id="action-message" role="status"></p></section>`;
}
function renderShell(){
  main.innerHTML=`<div class="v2-container wide"><header class="v2-heading v2-heading-row"><div><p class="eyebrow">Bước 2 · Đối chiếu và xác nhận</p><h1>${safe(detail.original_filename)}</h1><p>${safe(STATUS_LABELS[detail.status])} · phiên bản ${detail.version} · tải lên ${formatDate(detail.created_at)}</p></div><a class="v2-button secondary" href="/receipts/">Danh sách hóa đơn</a></header>
  <div id="stale-banner" class="v2-error-panel" hidden><strong>Dữ liệu đã cũ.</strong> Tải phiên bản mới trước khi tiếp tục; các thay đổi chưa lưu vẫn nằm trong ô soạn thảo. <button type="button" id="reload-detail" class="v2-button secondary">Tải phiên bản mới</button></div>
  <div id="top-message" role="status"></div><div class="review-layout"><section class="v2-card source-panel"><h2>Tài liệu nguồn</h2><div id="source-viewer"></div></section><section class="v2-card data-panel"><div id="detail-body"></div></section></div></div>`;
  main.querySelector("#reload-detail").addEventListener("click",reload);
  viewer=createSourceViewer(main.querySelector("#source-viewer"),receiptId,(blockId)=>{
    const refs=allCells().filter(([, , ,cell])=>sourceIds(cell).includes(blockId));
    const target=refs[0];if(target){const id=key(...target.slice(0,3));main.querySelectorAll("[data-cell]").forEach((node)=>node.classList.toggle("source-selected",node.dataset.cell===id));const el=[...main.querySelectorAll("[data-cell]")].find((node)=>node.dataset.cell===id);el?.scrollIntoView({block:"center",behavior:"smooth"});el?.querySelector("input")?.focus();}
  });
  viewer.load().catch((error)=>{main.querySelector("#top-message").textContent=errorText(error);});
}
function allCells(){
  return [...Object.entries(detail.fields).map(([field,cell])=>["header","",field,cell]),
    ...detail.line_items.flatMap((row)=>LINE_FIELDS.map(([field])=>["line",row.line_id,field,row[field]])),
    ...detail.tax_breakdown.flatMap((row)=>TAX_FIELDS.map(([field])=>["tax",row.tax_id,field,row[field]]))];
}
function getCell(id){return allCells().find(([section,row,field])=>key(section,row,field)===id);}
function render(){
  if(!detail)return;
  if(!main.querySelector("#detail-body"))renderShell();
  const banner=main.querySelector("#stale-banner");banner.hidden=!stale;
  main.querySelector(".v2-heading h1").textContent=detail.original_filename;
  main.querySelector(".v2-heading p:last-child").textContent=`${STATUS_LABELS[detail.status]} · phiên bản ${detail.version} · tải lên ${formatDate(detail.created_at)}`;
  if(["UPLOADED","PROCESSING"].includes(detail.status)){
    document.querySelector("#detail-body").innerHTML=`<div class="processing-state"><h2>Đang xử lý hóa đơn…</h2><p>Trạng thái: ${safe(STATUS_LABELS[detail.status])}</p><p>${detail.processing_stage?`Bước: ${safe(detail.processing_stage)}`:"Đang chờ worker nhận tài liệu."}</p><p>Trang sẽ kiểm tra trạng thái định kỳ. <button type="button" id="refresh-now" class="v2-button secondary">Kiểm tra ngay</button></p><p id="poll-message" role="status"></p></div>`;
    schedulePoll();return;
  }
  clearTimeout(timer);
  if(detail.status==="FAILED"){
    const failure=detail.processing_error;
    document.querySelector("#detail-body").innerHTML=`<div class="v2-error-panel"><h2>Xử lý thất bại</h2><p>${safe(failure?.message||"Backend không cung cấp chi tiết lỗi.")}</p><p>Bước: ${safe(failure?.stage||"không rõ")} · mã: ${safe(failure?.code||"không rõ")}</p>${failure?.retryable?'<button type="button" id="retry-processing" class="v2-button">Thử xử lý lại</button>':"<p>Lỗi này không thể thử lại từ giao diện.</p>"}<p id="retry-message" role="status"></p></div>`;return;
  }
  renderReview();
}
function schedulePoll(){
  clearTimeout(timer);
  if(!["UPLOADED","PROCESSING"].includes(detail.status))return;
  if(pollCount>=120){const p=main.querySelector("#poll-message");if(p)p.textContent="Đã dừng kiểm tra tự động sau 120 lần. Bạn có thể kiểm tra thủ công.";return;}
  timer=setTimeout(async()=>{
    if(document.hidden){schedulePoll();return;}
    pollCount++;
    try{detail=await invoiceApi.detail(receiptId);render();}
    catch(error){const p=main.querySelector("#poll-message");if(p)p.textContent=errorText(error);schedulePoll();}
  },Math.min(10000,2500+pollCount*250));
}
async function reload(){
  try{detail=await invoiceApi.detail(receiptId);stale=false;errors.clear();saved.clear();render();main.querySelector("#top-message").textContent="Đã tải phiên bản mới. Kiểm tra lại bản soạn trước khi lưu.";}
  catch(error){main.querySelector("#top-message").textContent=errorText(error);}
}
async function save(id){
  if(saving||stale||detail.status!=="NEEDS_REVIEW")return;
  const match=getCell(id);if(!match)return;
  const [section,row,field]=match;
  const input=[...main.querySelectorAll("[data-input]")].find((node)=>node.dataset.input===id);
  const select=[...main.querySelectorAll("[data-status]")].find((node)=>node.dataset.status===id);
  if(!input||!select)return;
  let value;const status=select.value;
  try{value=correctionValue(field,input.value,status);}
  catch(error){errors.set(id,errorText(error));renderReview();return;}
  drafts.set(id,{text:input.value,status,saving:true});errors.delete(id);saving=true;renderReview();
  try{
    detail=await invoiceApi.correction(receiptId,section,row,field,value,status,detail.version);
    drafts.delete(id);saved.add(id);render();
  }catch(error){errors.set(id,errorText(error));if(error instanceof ApiError&&error.status===409)stale=true;render();}
  finally{saving=false;render();}
}
async function retry(){
  const p=main.querySelector("#retry-message");if(p)p.textContent="Đang gửi yêu cầu thử lại…";
  try{detail=await invoiceApi.retry(receiptId,detail.version);pollCount=0;render();}
  catch(error){if(error instanceof ApiError&&error.status===409)stale=true;render();const target=main.querySelector("#retry-message")||main.querySelector("#top-message");target.textContent=errorText(error);}
}
async function verify(){
  if(verifying||stale||drafts.size||unresolvedCells(detail).length)return;
  verifying=true;const p=main.querySelector("#action-message");p.textContent="Đang chờ backend xác nhận…";
  try{detail=await invoiceApi.verify(receiptId,detail.version);render();}
  catch(error){if(error instanceof ApiError&&error.status===409)stale=true;render();main.querySelector("#action-message").textContent=errorText(error);}
  finally{verifying=false;}
}
async function download(format){
  if(exporting||detail.status!=="VERIFIED")return;
  exporting=true;const p=main.querySelector("#action-message");p.textContent=`Đang tạo tệp ${format.toUpperCase()}…`;
  try{
    const result=await invoiceApi.export(receiptId,format),url=URL.createObjectURL(result.blob),a=document.createElement("a");
    a.href=url;a.download=result.filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
    p.textContent=`Đã nhận tệp ${result.filename} từ backend.`;
  }catch(error){if(error instanceof ApiError&&error.status===409){stale=true;main.querySelector("#stale-banner").hidden=false;}p.textContent=`Không thể xuất tệp: ${errorText(error)}`;}
  finally{exporting=false;}
}
main.addEventListener("click",async(event)=>{
  const evidence=event.target.closest("[data-evidence]");
  if(evidence){const match=getCell(evidence.dataset.evidence);if(match){await viewer?.highlight(sourceIds(match[3]));main.querySelectorAll("[data-cell]").forEach((node)=>node.classList.toggle("source-selected",node.dataset.cell===evidence.dataset.evidence));}return;}
  const saveButton=event.target.closest("[data-save]");if(saveButton){save(saveButton.dataset.save);return;}
  const exportButton=event.target.closest("[data-export]");if(exportButton){download(exportButton.dataset.export);return;}
  if(event.target.id==="verify")verify();
  else if(event.target.id==="retry-processing")retry();
  else if(event.target.id==="refresh-now")reload();
});
main.addEventListener("input",(event)=>{
  const id=event.target.dataset.input;if(!id)return;
  const status=[...main.querySelectorAll("[data-status]")].find((node)=>node.dataset.status===id)?.value||"PRESENT";
  drafts.set(id,{text:event.target.value,status});saved.delete(id);errors.delete(id);
  const state=event.target.closest(".review-cell")?.querySelector(".cell-state");if(state)state.textContent="Chưa lưu";
  const verifyButton=main.querySelector("#verify");if(verifyButton)verifyButton.disabled=true;
});
main.addEventListener("change",(event)=>{
  const id=event.target.dataset.status;if(!id)return;
  const input=[...main.querySelectorAll("[data-input]")].find((node)=>node.dataset.input===id);
  if(input)input.disabled=event.target.value!=="PRESENT";
  drafts.set(id,{text:input?.value||"",status:event.target.value});saved.delete(id);
  const state=event.target.closest(".review-cell")?.querySelector(".cell-state");if(state)state.textContent="Chưa lưu";
  const verifyButton=main.querySelector("#verify");if(verifyButton)verifyButton.disabled=true;
});
main.addEventListener("focusin",(event)=>{
  const cell=event.target.closest("[data-cell]");if(!cell||!viewer)return;
  const match=getCell(cell.dataset.cell);if(match)viewer.highlight(sourceIds(match[3])).catch(()=>{});
});
main.addEventListener("keydown",(event)=>{
  if((event.ctrlKey||event.metaKey)&&event.key==="Enter"){const id=event.target.closest("[data-cell]")?.dataset.cell;if(id){event.preventDefault();save(id);}}
  if(event.key==="Escape"){const id=event.target.closest("[data-cell]")?.dataset.cell;if(id){drafts.delete(id);errors.delete(id);renderReview();}}
});
window.addEventListener("pagehide",()=>{clearTimeout(timer);viewer?.destroy();},{once:true});
document.addEventListener("visibilitychange",()=>{if(document.hidden)clearTimeout(timer);else if(detail&&["UPLOADED","PROCESSING"].includes(detail.status))schedulePoll();});
if(!receiptId){main.innerHTML='<div class="v2-container"><div class="v2-error-panel">Không tìm thấy mã hóa đơn. <a href="/receipts/">Về danh sách</a></div></div>';}
else{
  main.innerHTML='<div class="v2-container"><p role="status">Đang tải hóa đơn…</p></div>';
  try{detail=await invoiceApi.detail(receiptId);render();}
  catch(error){main.innerHTML=`<div class="v2-container"><div class="v2-error-panel"><h1>Không mở được hóa đơn</h1><p>${safe(errorText(error))}</p><button type="button" id="retry-initial" class="v2-button">Thử lại</button></div></div>`;main.querySelector("#retry-initial").addEventListener("click",()=>location.reload());}
}
