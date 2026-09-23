import test from "node:test";
import assert from "node:assert/strict";
import { invoiceApi, ApiError, HEADER_FIELDS, correctionValue, unresolvedCells, validateFile, v2Paths } from "../assets/js/api-v2.js";
import { evidencePages } from "../assets/js/source-v2.js";
const id="00000000-0000-4000-8000-000000000051";
const cell=(value="x",needs=false)=>({raw_text:String(value),normalized_value:value,value_status:"PRESENT",source_block_ids:["b1"],corrected_value:null,corrected_status:null,has_correction:false,effective_value:value,effective_status:"PRESENT",reviewed:!needs,effective_needs_review:needs,review_reasons:needs?["LOW_CONFIDENCE"]:[]});
const detail=(version=1)=>({receipt_id:id,version,status:"NEEDS_REVIEW",fields:Object.fromEntries(HEADER_FIELDS.map((field)=>[field,cell()])),line_items:[{line_id:"a/b",description:cell(),unit:cell(),quantity:cell(1),unit_price:cell(2),amount:cell(2)}],tax_breakdown:[{tax_id:"0",rate:cell("10%"),taxable_amount:cell(2),tax_amount:cell(1)}]});
test("V2 dùng 13 header canonical và mã hóa line_id có dấu slash",()=>{
  assert.equal(HEADER_FIELDS.length,13);
  assert.equal(v2Paths.line(id,"a/b","amount").includes("a%2Fb"),true);
  assert.equal(v2Paths.detail(id),`/api/v2/receipts/${id}`);
});
test("validation JPEG/PNG/PDF và giá trị correction",()=>{
  assert.equal(validateFile(new File(["x"],"a.pdf",{type:"application/pdf"})),null);
  assert.match(validateFile(new File(["x"],"a.webp",{type:"image/webp"})),/Chỉ hỗ trợ/);
  assert.match(validateFile(new File([],"a.png",{type:"image/png"})),/rỗng/);
  assert.equal(correctionValue("amount","00120","PRESENT"),120);
  assert.equal(correctionValue("seller_tax_id","00120","PRESENT"),"00120");
  assert.equal(correctionValue("amount","","UNREADABLE"),null);
  assert.throws(()=>correctionValue("amount","12.5","PRESENT"));
});
test("unresolved phân biệt header, line và tax",()=>{
  const record=detail();record.fields.seller_name.effective_needs_review=true;record.line_items[0].description.effective_needs_review=true;record.tax_breakdown[0].rate.effective_needs_review=true;
  assert.deepEqual(unresolvedCells(record),[["Header","seller_name"],["Dòng 1","description"],["Thuế 1","rate"]]);
});
test("evidence nhiều trang giữ block theo đúng trang",()=>{
  const evidence={schema_version:"document-2.0",pages:[{page_index:0,evidence:{blocks:[{block_id:"p0"}]}},{page_index:1,evidence:{blocks:[{block_id:"p1"}]}}]};
  assert.deepEqual(evidencePages(evidence).map((blocks)=>blocks[0].block_id),["p0","p1"]);
});
test("upload chỉ trả success sau HTTP 201 và multipart file",async()=>{
  const original=globalThis.fetch;let calls=0;
  globalThis.fetch=async(url,init)=>{calls++;assert.equal(url,"/api/v2/receipts");assert.equal(init.method,"POST");assert.equal(init.body.get("file").name,"a.pdf");return Response.json({...detail(),status:"UPLOADED"},{status:201});};
  try{assert.equal((await invoiceApi.upload(new File(["%PDF-1.4"],"a.pdf",{type:"application/pdf"}))).receipt_id,id);assert.equal(calls,1);}finally{globalThis.fetch=original;}
});
test("correction và verify truyền expected_version, dùng response version mới",async()=>{
  const original=globalThis.fetch, bodies=[];
  globalThis.fetch=async(url,init)=>{bodies.push({url,body:JSON.parse(init.body)});return Response.json({...detail(bodies.length+4),status:url.endsWith("/verify")?"VERIFIED":"NEEDS_REVIEW"});};
  try{
    const saved=await invoiceApi.correction(id,"header","","seller_name","ABC","PRESENT",4);
    await invoiceApi.verify(id,saved.version);
    assert.equal(saved.version,5);assert.equal(bodies[0].body.expected_version,4);assert.equal(bodies[1].body.expected_version,5);
  }finally{globalThis.fetch=original;}
});
test("409 không tự gửi lại correction với version cũ",async()=>{
  const original=globalThis.fetch;let count=0;
  globalThis.fetch=async()=>{count++;return Response.json({error:{code:"CONFLICT",message:"stale"}},{status:409});};
  try{await assert.rejects(invoiceApi.correction(id,"line","a/b","amount",5,"PRESENT",1),(error)=>error instanceof ApiError&&error.status===409);assert.equal(count,1);}finally{globalThis.fetch=original;}
});
test("export đòi đúng MIME JSON, CSV ZIP và XLSX; lỗi backend không tạo file",async()=>{
  const original=globalThis.fetch;
  try{
    for(const [format,type] of Object.entries({json:"application/json",csv:"application/zip",xlsx:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})){
      globalThis.fetch=async()=>new Response("content",{status:200,headers:{"content-type":type}});
      const result=await invoiceApi.export(id,format);assert.equal(result.blob.size,7);assert.match(result.filename,format==="csv"?/-csv.zip$/:new RegExp(`\\.${format}$`));
    }
    globalThis.fetch=async()=>Response.json({error:{code:"EXPORT_FAILED",message:"bad"}},{status:503});
    await assert.rejects(invoiceApi.export(id,"xlsx"),(error)=>error instanceof ApiError&&error.code==="EXPORT_FAILED");
  }finally{globalThis.fetch=original;}
});
