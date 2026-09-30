import { invoiceApi, errorText, STATUS_LABELS } from "./api-v2.js";
import { escapeHtml, formatDate, formatVnd, receiptUrl, renderNavigation } from "./common.js";
renderNavigation();
const main=document.querySelector("#main-content");
let offset=0, loading=false;
main.innerHTML=`<div class="v2-container"><header class="v2-heading v2-heading-row"><div><p class="eyebrow">Không gian hóa đơn</p><h1>Danh sách hóa đơn</h1><p>Theo dõi xử lý và mở hóa đơn để đối chiếu với tài liệu nguồn.</p></div><a class="v2-button" href="/upload/">+ Tải hóa đơn</a></header><section class="v2-card"><div id="list-message" role="status" aria-live="polite">Đang tải danh sách…</div><div id="invoice-list"></div><div class="list-actions"><button type="button" id="previous-page" class="v2-button secondary">Trang trước</button><button type="button" id="next-page" class="v2-button secondary">Trang sau</button><button type="button" id="reload-list" class="v2-button secondary">Tải lại</button></div></section></div>`;
const list=main.querySelector("#invoice-list"),message=main.querySelector("#list-message");
async function load(){
  if(loading)return;loading=true;message.textContent="Đang tải danh sách…";
  try{
    const page=await invoiceApi.list(50,offset),items=page.items;
    if(!items.length && offset===0){list.innerHTML='<div class="empty-state"><h2>Bạn chưa tải hóa đơn nào.</h2><p>Bắt đầu bằng một ảnh hoặc PDF.</p><a class="v2-button" href="/upload/">Tải hóa đơn đầu tiên</a></div>';}
    else if(!items.length){offset=Math.max(0,offset-50);message.textContent="Không còn hóa đơn ở trang này.";return;}
    else list.innerHTML=`<div class="invoice-list">${items.map((item)=>`<a class="invoice-row" href="${receiptUrl(item.receipt_id)}"><span><strong>${escapeHtml(item.original_filename)}</strong><small>${escapeHtml(item.seller_name||"Chưa có tên người bán")} · ${escapeHtml(item.invoice_date||"Chưa có ngày")}</small></span><span>${item.total_amount==null?"—":formatVnd(item.total_amount)}</span><span class="status-pill status-${item.status.toLowerCase()}">${STATUS_LABELS[item.status]||escapeHtml(item.status)}</span><small>${formatDate(item.created_at)}</small><span aria-hidden="true">→</span></a>`).join("")}</div>`;
    message.textContent=items.length?`${items.length} hóa đơn · từ vị trí ${offset+1}`:"";
    main.querySelector("#previous-page").disabled=offset===0;
    main.querySelector("#next-page").disabled=items.length<50;
  }catch(error){message.innerHTML=`<span class="v2-error">${escapeHtml(errorText(error))}</span> <button type="button" id="retry-list" class="v2-button secondary">Thử lại</button>`;main.querySelector("#retry-list").addEventListener("click",load);}
  finally{loading=false;}
}
main.querySelector("#previous-page").addEventListener("click",()=>{offset=Math.max(0,offset-50);load();});
main.querySelector("#next-page").addEventListener("click",()=>{offset+=50;load();});
main.querySelector("#reload-list").addEventListener("click",load);
load();
