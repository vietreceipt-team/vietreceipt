import { invoiceApi, validateFile, errorText } from "./api-v2.js";
import { escapeHtml, renderNavigation, receiptUrl } from "./common.js";
renderNavigation();
const main=document.querySelector("#main-content");
let selected=null, previewUrl=null, busy=false;
main.innerHTML=`<div class="v2-container"><header class="v2-heading"><p class="eyebrow">Bước 1 · Nguồn tài liệu</p><h1>Tải hóa đơn lên</h1><p>Chọn ảnh JPEG, PNG hoặc PDF (tối đa 10 MiB). Backend sẽ kiểm tra tệp và xử lý sau khi nhận.</p></header>
<section class="v2-card upload-card"><div id="dropzone" class="dropzone" tabindex="0" role="button" aria-label="Chọn hoặc thả tệp hóa đơn"><div class="drop-icon">↑</div><h2>Kéo tệp vào đây</h2><p>hoặc chọn tệp từ thiết bị</p><button type="button" id="pick-file" class="v2-button secondary">Chọn tệp</button><input id="file-input" type="file" accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf" hidden></div>
<div id="selection" class="upload-selection" hidden></div><label class="v2-label" for="source-group">Nguồn hóa đơn</label><select id="source-group" class="v2-input"><option value="">Tự nhận theo tệp</option><option value="PAPER_DIGITIZED">Hóa đơn giấy đã số hóa</option><option value="IMAGE">Ảnh có sẵn</option><option value="PDF">PDF</option></select>
<p id="upload-message" role="status" aria-live="polite"></p><button id="upload-submit" type="button" class="v2-button" disabled>Tải lên và xử lý</button></section></div>`;
const input=main.querySelector("#file-input"),zone=main.querySelector("#dropzone"),selection=main.querySelector("#selection"),message=main.querySelector("#upload-message"),submit=main.querySelector("#upload-submit");
function choose(file){
  if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null;}
  selected=file;const error=validateFile(file);submit.disabled=Boolean(error)||busy;
  message.textContent=error||"Tệp đã sẵn sàng. Chưa gửi lên backend.";
  message.className=error?"v2-error":"v2-muted";
  selection.hidden=!file;
  if(!file)return;
  const size=(file.size/1024/1024).toLocaleString("vi-VN",{maximumFractionDigits:2});
  if(!error&&file.type.startsWith("image/"))previewUrl=URL.createObjectURL(file);
  selection.innerHTML=`${previewUrl?`<img src="${previewUrl}" alt="Xem trước ảnh đã chọn">`:'<span class="pdf-icon" aria-hidden="true">PDF</span>'}<div><strong>${escapeHtml(file.name)}</strong><p>${size} MiB · ${file.type==="application/pdf"?"Tài liệu PDF":"Ảnh"}</p></div>`;
}
main.querySelector("#pick-file").addEventListener("click",()=>input.click());
zone.addEventListener("click",(event)=>{if(!event.target.closest("button"))input.click();});
zone.addEventListener("keydown",(event)=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();input.click();}});
input.addEventListener("change",()=>choose(input.files?.[0]||null));
for(const eventName of ["dragenter","dragover"])zone.addEventListener(eventName,(event)=>{event.preventDefault();zone.classList.add("dragging");});
for(const eventName of ["dragleave","drop"])zone.addEventListener(eventName,(event)=>{event.preventDefault();zone.classList.remove("dragging");});
zone.addEventListener("drop",(event)=>choose(event.dataTransfer?.files?.[0]||null));
submit.addEventListener("click",async()=>{
  if(busy||!selected)return;
  busy=true;submit.disabled=true;submit.textContent="Đang gửi tệp…";message.textContent="Đang chờ phản hồi từ backend.";message.className="v2-muted";
  try{
    const detail=await invoiceApi.upload(selected,main.querySelector("#source-group").value||null);
    message.textContent="Backend đã nhận tệp. Đang mở trạng thái xử lý.";
    window.location.assign(receiptUrl(detail.receipt_id));
  }catch(error){message.textContent=errorText(error);message.className="v2-error";busy=false;submit.disabled=false;submit.textContent="Thử tải lại";}
});
window.addEventListener("pagehide",()=>{if(previewUrl)URL.revokeObjectURL(previewUrl);},{once:true});
