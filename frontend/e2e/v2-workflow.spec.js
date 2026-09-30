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
 const state={record:receipt(options.status||"NEEDS_REVIEW",Boolean(options.pdf)),gets:0,patches:0};
 await page.route(/\/api\/v2\/receipts/,async(route)=>{
  const request=route.request(),method=request.method(),url=new URL(request.url()),part=url.pathname.replace("/api/v2/receipts","");
  const send=(data,status=200)=>route.fulfill({status,contentType:"application/json",body:JSON.stringify(data)});
  if(method==="POST"&&part===""){if(options.uploadError)return send({error:{code:"STORAGE_FAILED",message:"Storage unavailable"}},503);state.record.status="UPLOADED";return send(state.record,201);}
  if(method==="GET"&&part==="")return send({items:[],limit:50,offset:0});
  if(method==="GET"&&part===`/${RID}`){state.gets++;if(options.progress)state.record.status=state.gets===1?"PROCESSING":"NEEDS_REVIEW";return send(state.record);}
  if(method==="GET"&&part.endsWith("/source"))return options.missingSource?send({error:{code:"STORAGE_FAILED",message:"missing source"}},503):route.fulfill({status:200,contentType:options.pdf?"application/pdf":"image/jpeg",body:options.pdf?pdf:photo});
  if(method==="GET"&&part.endsWith("/evidence"))return options.missingEvidence?send({error:{code:"NOT_FOUND",message:"missing evidence"}},404):send(options.pdf?{schema_version:"document-2.0",pages:[{page_index:0,evidence:{blocks:[block("b1")]}},{page_index:1,evidence:{blocks:[block("p1")]}}]}:{schema_version:"1.3",blocks:[block("b1")]});
  if(method==="POST"&&part.endsWith("/retry")){expect(request.postDataJSON().expected_version).toBe(state.record.version);state.record.status="UPLOADED";state.record.version++;state.record.processing_error=null;return send(state.record,202);}
  if(method==="PATCH"&&part.endsWith("/correction")){
   state.patches++;if(options.conflict)return send({error:{code:"CONFLICT",message:"stale"}},409);
   const data=request.postDataJSON();expect(data.expected_version).toBe(state.record.version);
   const field=part.split("/").at(-2),target=part.includes("/fields/")?state.record.fields[field]:part.includes("/line-items/")?state.record.line_items[0][field]:state.record.tax_breakdown[0][field];
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
 for(const id of ["header||seller_name","line|row/1|description","tax|0|rate"]){const card=page.locator(`[data-cell="${id}"]`);await card.locator("[data-input]").fill("Đã kiểm tra");await card.getByRole("button",{name:"Lưu"}).click();await expect(card.getByText("Đã lưu")).toBeVisible();}
 await page.getByRole("button",{name:"Xác nhận hóa đơn"}).click();
 await expect(page.getByText("Hóa đơn đã được backend xác nhận. Dữ liệu chỉ đọc.")).toBeVisible();
 for(const [name,extension] of [["Tải JSON",".json"],["Tải CSV (ZIP)",".zip"],["Tải Excel",".xlsx"]]){const promise=page.waitForEvent("download");await page.getByRole("button",{name}).click();expect((await promise).suggestedFilename()).toContain(extension);}
});
test("PDF nhiều trang: evidence ở trang 2",async({page})=>{
 await provider(page,{pdf:true,progress:true});await page.goto(`${ORIGIN}/upload/`);await page.locator("#file-input").setInputFiles({name:"demo.pdf",mimeType:"application/pdf",buffer:pdf});await page.getByRole("button",{name:"Tải lên và xử lý"}).click();
 await expect(page.locator('[data-view="page"]')).toHaveText("Trang 1 / 2",{timeout:15000});
 await page.locator('[data-cell="header||seller_name"] [data-evidence]').click();
 await expect(page.locator('[data-view="page"]')).toHaveText("Trang 2 / 2");
 await expect(page.locator('polygon[data-block="p1"].is-active')).toHaveCount(1);await page.screenshot({path:"test-results/v2-pdf-evidence.png"});
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
 await expect(page.locator("#stale-banner")).toBeVisible();expect(state.patches).toBe(1);
 await page.getByRole("button",{name:"Tải phiên bản mới"}).click();await expect(page.locator("#stale-banner")).toBeHidden();
});
test("export lỗi không làm mất trang",async({page})=>{
 await provider(page,{status:"VERIFIED",exportError:true});await page.goto(`${ORIGIN}/receipts/${RID}/`);
 await page.getByRole("button",{name:"Tải Excel"}).click();await expect(page.locator("#action-message")).toContainText("Không thể xuất tệp");
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
 await expect(page.getByText("Bạn chưa tải hóa đơn nào.")).toBeVisible();
});
test("màn hình nhỏ và phím tắt lưu correction",async({page})=>{
 await page.setViewportSize({width:390,height:844});await provider(page);await page.goto(`${ORIGIN}/receipts/${RID}/`);
 await expect(page.locator(".source-panel")).toBeVisible();
 const card=page.locator('[data-cell="header||seller_name"]');await card.locator("[data-input]").fill("Bản sửa bằng bàn phím");
 await card.locator("[data-input]").press("Control+Enter");
 await expect(card.getByText("Đã lưu")).toBeVisible();
 expect(await page.evaluate(()=>(window.scrollTo(999,0),window.scrollX<=2&&document.body.scrollWidth<=window.innerWidth+2))).toBe(true);
});
