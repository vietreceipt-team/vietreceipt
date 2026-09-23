import { APP_CONFIG } from "./config.js";
/** @type {Array<[string, Array<[string, string]>]>} */
export const HEADER_GROUPS = [
  ["Thông tin hóa đơn",[["invoice_template_number","Mẫu số"],["invoice_symbol","Ký hiệu"],["invoice_number","Số hóa đơn"],["invoice_date","Ngày hóa đơn"]]],
  ["Người bán",[["seller_name","Tên người bán"],["seller_tax_id","Mã số thuế"],["seller_address","Địa chỉ"]]],
  ["Người mua",[["buyer_name","Tên người mua"],["buyer_tax_id","Mã số thuế"]]],
  ["Tiền và thuế",[["subtotal","Tạm tính"],["tax_amount","Tiền thuế"],["total_amount","Tổng tiền"],["currency","Tiền tệ"]]]
];
export const HEADER_FIELDS=HEADER_GROUPS.flatMap(([,fields])=>fields.map(([key])=>key));
export const LINE_FIELDS=[["description","Tên hàng/dịch vụ"],["unit","Đơn vị"],["quantity","Số lượng"],["unit_price","Đơn giá"],["amount","Thành tiền"]];
export const TAX_FIELDS=[["rate","Thuế suất"],["taxable_amount","Tiền chịu thuế"],["tax_amount","Tiền thuế"]];
export const VALUE_LABELS={PRESENT:"Có dữ liệu",NOT_PRESENT:"Không có trên hóa đơn",UNREADABLE:"Không đọc được",AMBIGUOUS:"Mơ hồ",UNKNOWN:"Chưa xác định"};
export const STATUS_LABELS={UPLOADED:"Đã tải lên",PROCESSING:"Đang xử lý",NEEDS_REVIEW:"Cần kiểm tra",VERIFIED:"Đã xác nhận",FAILED:"Xử lý thất bại"};
const BASE="/api/v2/receipts", url=(p)=>APP_CONFIG.apiBaseUrl+p, path=(id)=>`${BASE}/${encodeURIComponent(id)}`;
export class ApiError extends Error { constructor(message,status=0,code="NETWORK_ERROR",requestId=null){super(message);this.status=status;this.code=code;this.requestId=requestId;} }
export function validateFile(file) {
  if (!file) return "Hãy chọn một tệp.";
  const extension=file.name.split(".").pop()?.toLowerCase();
  const mime={jpg:"image/jpeg",jpeg:"image/jpeg",png:"image/png",pdf:"application/pdf"};
  if (!mime[extension] || mime[extension]!==file.type) return "Chỉ hỗ trợ JPEG, PNG hoặc PDF với loại tệp khớp phần mở rộng.";
  if (!file.size) return "Tệp rỗng.";
  if (file.size>10*1024*1024) return "Tệp vượt giới hạn 10 MiB.";
  return null;
}
export function correctionValue(field,text,status){
  if (!Object.hasOwn(VALUE_LABELS,status)) throw new Error("Trạng thái giá trị không hợp lệ.");
  if(status!=="PRESENT") return null;
  const value=text.trim();
  if(["subtotal","tax_amount","total_amount","unit_price","amount","taxable_amount"].includes(field)){
    if(!/^\d+$/.test(value)||!Number.isSafeInteger(Number(value))) throw new Error("Số tiền phải là số nguyên không âm.");
    return Number(value);
  }
  if(field==="quantity"){
    if(!/^\d+(?:\.\d+)?$/.test(value)||!Number.isFinite(Number(value))) throw new Error("Số lượng phải là số không âm, dùng dấu chấm thập phân.");
    return Number(value);
  }
  if(!value||value.length>10000) throw new Error("Văn bản không được để trống và tối đa 10.000 ký tự.");
  if(field==="invoice_date"){
    const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if(!m||new Date(Date.UTC(+m[1],+m[2]-1,+m[3])).toISOString().slice(0,10)!==value) throw new Error("Ngày phải đúng dạng YYYY-MM-DD.");
  }
  return value;
}
export function unresolvedCells(detail){
  if(Object.keys(detail.fields||{}).length!==13) return [["Kết quả","Chưa đủ 13 trường header"]];
  return [
    ...Object.entries(detail.fields).map(([name,cell])=>["Header",name,cell]),
    ...detail.line_items.flatMap((row,i)=>LINE_FIELDS.map(([name])=>[`Dòng ${i+1}`,name,row[name]])),
    ...detail.tax_breakdown.flatMap((row,i)=>TAX_FIELDS.map(([name])=>[`Thuế ${i+1}`,name,row[name]]))
  ].filter(([, ,cell])=>cell?.effective_needs_review).map(([group,name])=>[group,name]);
}
export const v2Paths={
  receipts:BASE,detail:path,source:(id)=>`${path(id)}/source`,evidence:(id)=>`${path(id)}/evidence`,
  retry:(id)=>`${path(id)}/retry`,verify:(id)=>`${path(id)}/verify`,
  header:(id,field)=>`${path(id)}/fields/${encodeURIComponent(field)}/correction`,
  line:(id,row,field)=>`${path(id)}/line-items/${encodeURIComponent(row)}/${encodeURIComponent(field)}/correction`,
  tax:(id,row,field)=>`${path(id)}/tax-groups/${encodeURIComponent(row)}/${encodeURIComponent(field)}/correction`,
  export:(id,format)=>`${path(id)}/export?format=${encodeURIComponent(format)}`
};
async function request(p,init={}){
  let response;
  try{response=await fetch(url(p),{credentials:APP_CONFIG.requestCredentials,...init});}
  catch{throw new ApiError("Không thể kết nối backend. Kiểm tra mạng và thử lại.");}
  if(!response.ok){
    let envelope;try{envelope=await response.json();}catch{envelope=null;}
    const e=envelope?.error||{};
    throw new ApiError(response.status===409?"Dữ liệu đã thay đổi hoặc trạng thái không còn hợp lệ. Hãy tải phiên bản mới.":e.message||`Backend trả lỗi HTTP ${response.status}.`,response.status,e.code||`HTTP_${response.status}`,e.request_id||null);
  }
  return response;
}
async function json(p,init){return (await request(p,init)).json();}
function body(value){return {headers:{"content-type":"application/json",accept:"application/json"},body:JSON.stringify(value)};}
export function assertDetail(detail){
  if(!detail||typeof detail.receipt_id!=="string"||!Number.isInteger(detail.version)||!STATUS_LABELS[detail.status]||!detail.fields||!Array.isArray(detail.line_items)||!Array.isArray(detail.tax_breakdown)) throw new Error("Backend trả InvoiceDetail V2 không hợp lệ.");
  return detail;
}
function mutationDetail(value,id,version,status){const next=assertDetail(value);if(next.receipt_id!==id||next.version<=version||(status&&next.status!==status))throw new Error("Backend đã trả 2xx nhưng kết quả mutation không hợp lệ. Hãy tải lại hóa đơn.");return next;}
export const invoiceApi={
  async upload(file,sourceGroup){
    const error=validateFile(file);if(error) throw new Error(error);
    const form=new FormData();form.set("file",file);if(sourceGroup)form.set("source_group",sourceGroup);
    const uploaded=assertDetail(await json(BASE,{method:"POST",body:form}));if(uploaded.status!=="UPLOADED")throw new Error("Backend không xác nhận trạng thái đã tải lên.");return uploaded;
  },
  async list(limit=50,offset=0){const page=await json(`${BASE}?limit=${limit}&offset=${offset}`);if(!Array.isArray(page?.items))throw new Error("Backend trả danh sách không hợp lệ.");return page;},
  async detail(id){return assertDetail(await json(path(id)));},
  async source(id){const response=await request(v2Paths.source(id));const type=response.headers.get("content-type")?.split(";")[0]||"";if(!["image/jpeg","image/png","application/pdf"].includes(type))throw new Error("Backend trả nguồn tài liệu không hợp lệ.");return {blob:await response.blob(),type};},
  async evidence(id){return json(v2Paths.evidence(id));},
  async correction(id,section,row,field,value,status,version){
    const allowed=section==="header"?HEADER_FIELDS:section==="line"?LINE_FIELDS.map(([name])=>name):section==="tax"?TAX_FIELDS.map(([name])=>name):[];
    if(!allowed.includes(field)||!Object.hasOwn(VALUE_LABELS,status))throw new Error("Ô hoặc trạng thái không hợp lệ.");
    const target=section==="header"?v2Paths.header(id,field):section==="line"?v2Paths.line(id,row,field):v2Paths.tax(id,row,field);
    return mutationDetail(await json(target,{method:"PATCH",...body({value,status,expected_version:version})}),id,version,"NEEDS_REVIEW");
  },
  async retry(id,version){return mutationDetail(await json(v2Paths.retry(id),{method:"POST",...body({expected_version:version})}),id,version,"UPLOADED");},
  async verify(id,version){return mutationDetail(await json(v2Paths.verify(id),{method:"POST",...body({expected_version:version})}),id,version,"VERIFIED");},
  async export(id,format){
    if(!["json","csv","xlsx"].includes(format))throw new Error("Định dạng xuất không hợp lệ.");
    const response=await request(v2Paths.export(id,format));
    const type=response.headers.get("content-type")?.split(";")[0]||"";
    const expected={json:"application/json",csv:"application/zip",xlsx:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}[format];
    if(type!==expected)throw new Error("Backend trả định dạng export không đúng.");
    return {blob:await response.blob(),filename:`${id}${format==="csv"?"-csv.zip":"."+format}`};
  }
};
export function errorText(error){if(error instanceof ApiError){const labels={STORAGE_FAILED:"Không thể truy cập nơi lưu tài liệu.",BACKEND_NOT_CONFIGURED:"Backend V2 chưa được cấu hình.",REVIEW_REQUIRED:"Còn dữ liệu cần kiểm tra trước khi xác nhận.",INVALID_VALUE:"Giá trị chỉnh sửa không hợp lệ.",NOT_VERIFIED:"Chỉ hóa đơn đã xác nhận mới được xuất.",PROVIDER_NOT_CONFIGURED:"Bộ đọc tài liệu hoặc trích xuất chưa được cấu hình.",EXPORT_FAILED:"Không thể tạo tệp xuất."};const lead=labels[error.code]||error.message;return `${lead}${lead!==error.message?` Chi tiết: ${error.message}`:""}${error.requestId?` (mã yêu cầu ${error.requestId})`:""}`;}return error instanceof Error?error.message:"Có lỗi không xác định.";}
