import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { HEADER_FIELDS } from "../assets/js/api-v2.js";
const ORIGIN="http://127.0.0.1:3103", RID="00000000-0000-4000-8000-000000000051";
const photo=readFileSync("assets/fixtures/R001.jpg"), pdf=readFileSync("tests/fixtures/two-page.pdf");
const block=(id)=>({block_id:id,text:id,confidence:.9,reading_order:0,polygon:[{x:.1,y:.1},{x:.3,y:.1},{x:.3,y:.2},{x:.1,y:.2}]});
function cell(value,needs=false,source="b1"){return {raw_text:String(value),normalized_value:value,value_status:"PRESENT",source_block_ids:[source],corrected_value:null,corrected_status:null,has_correction:false,effective_value:value,effective_status:"PRESENT",reviewed:!needs,effective_needs_review:needs,machine_needs_review:needs,review_reasons:needs?["LOW_CONFIDENCE"]:[]};}
function receipt(status="NEEDS_REVIEW",pdfMode=false){
 const fields=Object.fromEntries(HEADER_FIELDS.map((name)=>[name,cell(name==="invoice_date"?"2026-09-23":["subtotal","tax_amount","total_amount"].includes(name)?1000:name==="currency"?"VND":"Mẫu",name==="seller_name",pdfMode&&name==="seller_name"?"p1":"b1")]));
 return {receipt_id:RID,original_filename:pdfMode?"demo.pdf":"demo.jpg",content_type:pdfMode?"application/pdf":"image/jpeg",source_group:pdfMode?"PDF":"IMAGE",status,version:1,created_at:"2026-09-23T08:00:00Z",updated_at:"2026-09-23T08:00:00Z",verified_at:null,source_url:`/api/v2/receipts/${RID}/source`,evidence_url:`/api/v2/receipts/${RID}/evidence`,latest_ocr_run_id:"ocr",latest_kie_run_id:"kie",processing_stage:null,processing_error:null,fields,line_items:[{line_id:"row/1",description:cell("Hàng",true),unit:cell("cái"),quantity:cell(1),unit_price:cell(1000),amount:cell(1000)}],tax_breakdown:[{tax_id:"0",rate:cell("10%",true),taxable_amount:cell(1000),tax_amount:cell(100)}]};
}
async function provider(page,options={}){
 const state={record:receipt(options.status||"NEEDS_REVIEW",Boolean(options.pdf)),gets:0,patches:0,history:[]};
 await page.route(/\/api\/v2\/receipts/,async(route)=>{
  const request=route.request(),method=request.method(),url=new URL(request.url()),part=url.pathname.replace("/api/v2/receipts","");
  const send=(data,status=200)=>route.fulfill({status,contentType:"application/json",body:JSON.stringify(data)});
  if(method==="POST"&&part===""){if(options.uploadError)return send({error:{code:"STORAGE_FAILED",message:"Storage unavailable"}},503);state.record.status="UPLOADED";return send(state.record,201);}
  if(method==="GET"&&part==="")return send({items:options.items||[],limit:100,offset:0});
  if(method==="GET"&&part.endsWith("/history"))return send(state.history);
  if(method==="GET"&&part===`/${RID}`){state.gets++;if(options.progress)state.record.status=state.gets===1?"PROCESSING":"NEEDS_REVIEW";return send(state.record);}
  if(method==="GET"&&part.endsWith("/source"))return options.missingSource?send({error:{code:"STORAGE_FAILED",message:"missing source"}},503):route.fulfill({status:200,contentType:options.pdf?"application/pdf":"image/jpeg",body:options.pdf?pdf:photo});
  if(method==="GET"&&part.endsWith("/evidence"))return options.missingEvidence?send({error:{code:"NOT_FOUND",message:"missing evidence"}},404):send(options.lateEvidence&&state.record.status==="PROCESSING"?{schema_version:"1.3",blocks:[]}:options.pdf?{schema_version:"document-2.0",pages:[{page_index:0,evidence:{blocks:[block("b1")]}},{page_index:1,evidence:{blocks:[block("p1")]}}]}:{schema_version:"1.3",blocks:[block("b1")]});
  if(method==="POST"&&part.endsWith("/retry")){expect(request.postDataJSON().expected_version).toBe(state.record.version);state.record.status="UPLOADED";state.record.version++;state.record.processing_error=null;return send(state.record,202);}
  if(method==="PATCH"&&part.endsWith("/correction")){
   state.patches++;if(options.conflict)return send({error:{code:"CONFLICT",message:"stale"}},409);
   const data=request.postDataJSON();expect(data.expected_version).toBe(state.record.version);
   const field=part.split("/").at(-2),target=part.includes("/fields/")?state.record.fields[field]:part.includes("/line-items/")?state.record.line_items[0][field]:state.record.tax_breakdown[0][field];
   state.history.push({kind:"CORRECTION",section:part.includes("/fields/")?"header":part.includes("/line-items/")?"line":"tax",field,old_value:{value:target.effective_value,status:target.effective_status},new_value:{value:data.value,status:data.status},created_at:"2026-09-30T15:00:00Z",actor:"Người dùng"});
   Object.assign(target,{corrected_value:data.value,corrected_status:data.status,has_correction:true,effective_value:data.value,effective_status:data.status,reviewed:true,effective_needs_review:false});
   state.record.version++;return send(state.record);
  }
  if(method==="POST"&&part.endsWith("/verify")){expect(request.postDataJSON().expected_version).toBe(state.record.version);state.record.status="VERIFIED";state.record.version++;return send(state.record);}
  if(method==="GET"&&part.endsWith("/export")){if(options.exportError)return send({error:{code:"EXPORT_FAILED",message:"Cannot export"}},503);const format=url.searchParams.get("format");return route.fulfill({status:200,contentType:{json:"application/json",csv:"application/zip",xlsx:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}[format],body:"file"});}
  return send({error:{code:"NOT_FOUND",message:"missing"}},404);
 });
 return state;
}
test("ảnh: upload, processing, sửa header/dòng/thuế, verify và export",async({page})=>{
 await provider(page,{progress:true});await page.goto(`${ORIGIN}/upload/`);
 await page.locator("#file-input").setInputFiles({name:"demo.jpg",mimeType:"image/jpeg",buffer:photo});
 await page.getByRole("button",{name:"Tải lên và xử lý"}).click();
 await expect(page.getByRole("heading",{name:"Đang xử lý hóa đơn…"})).toBeVisible();
 await expect(page.locator('[data-cell="header||seller_name"]')).toBeVisible({timeout:15000});await page.screenshot({path:"test-results/v2-review.png"});
 for(const id of ["header||seller_name","line|row/1|description","tax|0|rate"]){if(id.startsWith("line"))await page.getByRole("tab",{name:"Dòng hàng"}).click();if(id.startsWith("tax"))await page.getByRole("tab",{name:"Thuế",exact:false}).click();const card=page.locator(`[data-cell="${id}"]`);if(!id.startsWith("header"))await card.locator("[data-edit]").click();await card.locator("[data-input]").fill("Đã kiểm tra");await card.getByRole("button",{name:"Lưu"}).click();await expect(card.getByText("Đã lưu")).toBeVisible();}
 await page.getByRole("button",{name:"Xác nhận hóa đơn"}).click();
 await expect(page.locator("#review-help")).toContainText("Hóa đơn đã xác nhận");
 await page.locator(".export-menu summary").click();
 for(const [name,extension] of [["Tải JSON",".json"],["Tải CSV (ZIP)",".zip"],["Tải Excel",".xlsx"]]){const promise=page.waitForEvent("download");await page.getByRole("button",{name}).click();expect((await promise).suggestedFilename()).toContain(extension);}
});
test("PDF nhiều trang: evidence ở trang 2",async({page})=>{
 await provider(page,{pdf:true,progress:true,lateEvidence:true});await page.goto(`${ORIGIN}/upload/`);await page.locator("#file-input").setInputFiles({name:"demo.pdf",mimeType:"application/pdf",buffer:pdf});await page.getByRole("button",{name:"Tải lên và xử lý"}).click();
 await expect(page.locator('[data-view="page"]')).toHaveText("Trang 1 / 2",{timeout:15000});
 await page.locator('[data-cell="header||seller_name"] [data-evidence]').click();
 await expect(page.locator('[data-view="page"]')).toHaveText("Trang 2 / 2");
 await expect(page.locator('polygon[data-block="p1"].is-active')).toHaveCount(1);
 await page.getByRole("button",{name:"Xoay 90 độ",exact:true}).click();await expect(page.locator('polygon[data-block="p1"]')).toHaveAttribute("points","90,10 90,30 80,30 80,10");
 await page.getByRole("button",{name:"Phóng to",exact:true}).click();await expect(page.locator('[data-view="zoom"]')).toHaveText("125%");await page.getByRole("button",{name:"Vừa chiều rộng",exact:true}).click();await expect(page.locator('[data-view="zoom"]')).toHaveText("100%");
 await page.screenshot({path:"test-results/v2-pdf-evidence.png"});
});
test("file sai và lỗi upload",async({page})=>{
 await provider(page,{uploadError:true});await page.goto(`${ORIGIN}/upload/`);
 await page.locator("#file-input").setInputFiles({name:"bad.txt",mimeType:"text/plain",buffer:Buffer.from("bad")});
 await expect(page.locator("#upload-message")).toContainText("Chỉ hỗ trợ");
 await page.locator("#file-input").setInputFiles({name:"demo.jpg",mimeType:"image/jpeg",buffer:photo});
 await page.getByRole("button",{name:"Tải lên và xử lý"}).click();
 await expect(page.locator("#upload-message")).toContainText("Storage unavailable");
});
test("FAILED retry và 409 yêu cầu tải phiên bản mới",async({page})=>{
 const state=await provider(page,{status:"FAILED",conflict:true});
 state.record.processing_error={stage:"OCR",code:"READER_FAILED",message:"Không đọc được tài liệu",retryable:true};
 await page.goto(`${ORIGIN}/receipts/${RID}/`);await expect(page.getByRole("heading",{name:"Xử lý thất bại"})).toBeVisible();
 await page.getByRole("button",{name:"Thử xử lý lại"}).click();
 await expect(page.getByRole("heading",{name:"Đang xử lý hóa đơn…"})).toBeVisible();
 state.record.status="NEEDS_REVIEW";await page.getByRole("button",{name:"Kiểm tra ngay"}).click();
 const card=page.locator('[data-cell="header||seller_name"]');await card.locator("[data-input]").fill("ABC");await card.getByRole("button",{name:"Lưu"}).click();
 await expect(page.locator("#stale-banner")).toBeVisible();expect(state.patches).toBe(1);await expect(card.locator("[data-input]")).toHaveValue("ABC");
 await page.getByRole("button",{name:"Tải phiên bản mới"}).click();await expect(page.locator("#stale-banner")).toBeHidden();await expect(card.locator("[data-input]")).toHaveValue("ABC");
});
test("export lỗi không làm mất trang",async({page})=>{
 await provider(page,{status:"VERIFIED",exportError:true});await page.goto(`${ORIGIN}/receipts/${RID}/`);
 await page.locator(".export-menu summary").click();await page.getByRole("button",{name:"Tải Excel"}).click();await expect(page.locator("#action-message")).toContainText("Không thể xuất tệp");
});
test("thiếu source/evidence vẫn cho xem và sửa dữ liệu",async({page})=>{
 await provider(page,{missingSource:true,missingEvidence:true});await page.goto(`${ORIGIN}/receipts/${RID}/`);
 await expect(page.locator('[data-cell="header||seller_name"]')).toBeVisible();
 await expect(page.locator(".viewer-fallback")).toContainText("Chưa có tài liệu nguồn");
 await expect(page.locator(".viewer-note")).toContainText("Không có tài liệu nguồn");
});
test("danh sách rỗng và lỗi mạng có retry",async({page})=>{
 await page.route(/\/api\/v2\/receipts/,route=>route.abort());await page.goto(`${ORIGIN}/receipts/`);
 await expect(page.locator("#retry-list")).toBeVisible();
 await page.unrouteAll();
 await provider(page);
 await page.locator("#retry-list").click();
 await expect(page.getByText("Bạn chưa tải hóa đơn nào")).toBeVisible();
});
test("màn hình nhỏ và phím tắt lưu correction",async({page})=>{
 await page.setViewportSize({width:390,height:844});await provider(page);await page.goto(`${ORIGIN}/receipts/${RID}/`);
 await expect(page.locator(".source-panel")).toBeVisible();
 const card=page.locator('[data-cell="header||seller_name"]');await card.locator("[data-input]").fill("Bản sửa bằng bàn phím");
 await card.locator("[data-input]").press("Control+Enter");
 await expect(card.getByText("Đã lưu")).toBeVisible();
 expect(await page.evaluate(()=>(window.scrollTo(999,0),window.scrollX<=2&&document.body.scrollWidth<=window.innerWidth+2))).toBe(true);
});

test("đổi tab giữ bản sửa, hủy trả giá trị gốc và lịch sử đọc từ API",async({page})=>{
 const state=await provider(page);await page.goto(`${ORIGIN}/receipts/${RID}/`);
 const seller=page.locator('[data-cell="header||seller_name"]');await seller.locator("[data-input]").fill("Bản nháp người bán");
 await page.getByRole("tab",{name:"Dòng hàng"}).click();
 const row=page.locator('[data-cell="line|row/1|description"]');await row.locator("[data-edit]").click();await row.locator("[data-input]").fill("Bản nháp hàng hóa");
 await page.getByRole("tab",{name:"Thông tin"}).click();await expect(seller.locator("[data-input]")).toHaveValue("Bản nháp người bán");
 await page.getByRole("tab",{name:"Dòng hàng"}).click();await expect(row).toContainText("Bản nháp hàng hóa");await row.locator("[data-edit]").click();await row.getByRole("button",{name:"Hủy",exact:true}).click();await expect(row.locator("[data-edit]")).toContainText("Hàng");
 await page.getByRole("tab",{name:"Thông tin"}).click();await seller.locator("[data-input]").click();await seller.getByRole("button",{name:"Lưu",exact:true}).click();await expect(seller).toContainText("Đã lưu");expect(state.patches).toBe(1);
 await page.getByRole("tab",{name:"Lịch sử"}).click();await expect(page.locator(".history-list")).toContainText("Bản nháp người bán");
});
test("trường thiếu dữ liệu có thể mở sửa và đổi trạng thái",async({page})=>{
 const state=await provider(page);Object.assign(state.record.fields.seller_name,{effective_value:null,effective_status:"UNKNOWN",value_status:"UNKNOWN"});
 await page.goto(`${ORIGIN}/receipts/${RID}/`);const seller=page.locator('[data-cell="header||seller_name"]');
 await seller.locator("[data-inspect]").click();await page.getByRole("button",{name:"Sửa giá trị",exact:true}).click();
 await seller.locator("[data-status]").selectOption("PRESENT");await seller.locator("[data-input]").fill("Công ty đã đối chiếu");await seller.getByRole("button",{name:"Lưu",exact:true}).click();
 await expect(seller.locator("[data-input]")).toHaveValue("Công ty đã đối chiếu");expect(state.record.fields.seller_name.effective_needs_review).toBe(false);
});
test("ngày chưa đọc được hiện trống, không hiện ngày hiện tại",async({page})=>{
 const state=await provider(page);state.record.fields.invoice_date={...cell(null,true),effective_value:null,effective_status:"AMBIGUOUS",normalized_value:null};
 await page.goto(`${ORIGIN}/receipts/${RID}/`);
 const input=page.locator('[data-cell="header||invoice_date"] [data-input]');
 await expect(input).toHaveAttribute("type","text");await expect(input).toHaveValue("");await expect(input).toHaveAttribute("placeholder","Mơ hồ");
});
test("USD: lưu số tiền có phần lẻ và giữ đúng loại tiền",async({page})=>{
 const state=await provider(page);state.record.fields.currency=cell("USD");state.record.fields.total_amount=cell(349);
 await page.goto(`${ORIGIN}/receipts/${RID}/`);
 const total=page.locator('[data-cell="header||total_amount"]');
 await expect(total.locator(".amount-currency")).toHaveText("USD");
 await total.locator("[data-edit]").click();await total.locator("[data-input]").fill("349.25");
 await total.getByRole("button",{name:"Lưu",exact:true}).click();
 await expect(total).toContainText("Đã lưu");expect(state.record.fields.total_amount.effective_value).toBe(349.25);
 expect(state.record.fields.currency.effective_value).toBe("USD");
});
test("đối chiếu các mục còn lại giữ UNKNOWN và mở xác nhận hóa đơn",async({page})=>{
 const state=await provider(page);state.record.fields.invoice_symbol={...cell(null,true),normalized_value:null,value_status:"UNKNOWN",effective_value:null,effective_status:"UNKNOWN"};
 await page.goto(`${ORIGIN}/receipts/${RID}/`);await expect(page.locator("#verify")).toBeDisabled();
 await page.getByRole("button",{name:"Đối chiếu các mục còn lại",exact:true}).click();
 const dialog=page.getByRole("dialog",{name:"Đối chiếu các mục còn lại"});await expect(dialog).toContainText("Chưa xác định");
 await expect(dialog.getByRole("button",{name:"Lưu xác nhận đối chiếu"})).toBeDisabled();
 await dialog.getByRole("button",{name:"Quay lại sửa"}).click();expect(state.patches).toBe(0);await expect(page.locator("#verify")).toBeDisabled();
 await page.getByRole("button",{name:"Đối chiếu các mục còn lại",exact:true}).click();
 await dialog.locator("#batch-all").check();await dialog.getByRole("button",{name:"Lưu xác nhận đối chiếu"}).click();
 await expect(page.locator("#verify")).toBeEnabled();expect(state.record.fields.invoice_symbol.effective_status).toBe("UNKNOWN");expect(state.record.fields.invoice_symbol.effective_value).toBeNull();
 await page.locator("#verify").click();await expect(page.locator(".verified-label")).toContainText("Đã xác nhận");
 await page.locator(".export-menu summary").click();await expect(page.getByRole("button",{name:"Tải Excel"})).toBeEnabled();
});
test("đối chiếu hàng loạt gặp 409 dừng, không tự xác nhận hoặc gửi lại",async({page})=>{
 const state=await provider(page,{conflict:true});await page.goto(`${ORIGIN}/receipts/${RID}/`);
 await page.getByRole("button",{name:"Đối chiếu các mục còn lại",exact:true}).click();await page.locator("#batch-all").check();await page.getByRole("button",{name:"Lưu xác nhận đối chiếu"}).click();
 await expect(page.locator("#stale-banner")).toBeVisible();expect(state.patches).toBe(1);expect(state.record.status).toBe("NEEDS_REVIEW");await expect(page.locator("#verify")).toBeDisabled();
});
test("danh sách tìm kiếm không dấu, lọc ngày/trạng thái và phân trang",async({page})=>{
 const items=Array.from({length:12},(_,index)=>({receipt_id:RID,original_filename:`hoa_don_${index+1}.pdf`,status:index===0?"VERIFIED":"NEEDS_REVIEW",seller_name:index===0?"Công ty Văn Phòng Mẫu":"Công ty ABC",invoice_date:index===0?"2026-09-24":"2026-09-20",total_amount:143000,created_at:"2026-09-24T00:00:00Z"}));
 // Distinct records make pagination reflect real API records rather than duplicate IDs.
 items.forEach((item,index)=>{item.receipt_id=RID.slice(0,-2)+String(index+51).padStart(2,"0");});
 await provider(page,{items});await page.goto(`${ORIGIN}/receipts/`);
 await expect(page.locator(".invoice-table tbody tr")).toHaveCount(10);await page.getByRole("button",{name:"Trang sau",exact:true}).click();await expect(page.locator(".invoice-table tbody tr")).toHaveCount(2);
 await page.getByRole("searchbox",{name:"Tìm hóa đơn"}).fill("van phong");await expect(page.locator(".invoice-table tbody tr")).toHaveCount(1);await expect(page.locator(".invoice-table")).toContainText("Công ty Văn Phòng Mẫu");
 await page.getByRole("searchbox",{name:"Tìm hóa đơn"}).fill("");await page.getByLabel("Trạng thái",{exact:true}).selectOption("VERIFIED");await expect(page.locator(".invoice-table tbody tr")).toHaveCount(1);
 await page.getByLabel("Từ ngày",{exact:true}).fill("2026-09-25");await expect(page.getByText("Không tìm thấy hóa đơn phù hợp")).toBeVisible();await page.getByRole("button",{name:"Xóa bộ lọc"}).click();await expect(page.locator(".invoice-table tbody tr")).toHaveCount(10);
});

test("xem trước PDF nhiều trang, đóng và bỏ tệp đã chọn",async({page})=>{
 await provider(page);await page.goto(`${ORIGIN}/upload/`);
 await page.locator("#file-input").setInputFiles({name:"demo.pdf",mimeType:"application/pdf",buffer:pdf});
 await page.getByRole("button",{name:"Xem trước",exact:true}).click();await expect(page.getByRole("dialog",{name:"Xem trước hóa đơn"})).toBeVisible();
 await expect(page.locator("[data-preview-page]")).toHaveText("Trang 1 / 2");await expect(page.locator(".preview-document canvas")).toBeVisible();
 await page.getByRole("button",{name:"Trang PDF sau",exact:true}).click();await expect(page.locator("[data-preview-page]")).toHaveText("Trang 2 / 2");
 await page.getByRole("button",{name:"Đóng xem trước",exact:true}).click();await expect(page.getByRole("dialog",{name:"Xem trước hóa đơn"})).toBeHidden();
 await page.getByRole("button",{name:"Bỏ tệp",exact:true}).click();await expect(page.locator("#selection")).toBeHidden();await expect(page.getByRole("button",{name:"Tải lên và xử lý",exact:true})).toBeDisabled();
});
