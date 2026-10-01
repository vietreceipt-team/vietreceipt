const paths = {
  receipt: '<path d="M6 3h9l4 4v14l-3-2-3 2-3-2-4 2V3Z"/><path d="M14 3v5h5M9 11h6M9 15h6"/>',
  upload: '<path d="M8 16H6a4 4 0 0 1-.6-8A6 6 0 0 1 17 6a5 5 0 0 1 1 10h-2M12 21V10m-4 4 4-4 4 4"/>',
  list: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 3v18M5 9h14M5 15h14"/>',
  file: '<path d="M6 3h8l4 4v14H6V3Z"/><path d="M14 3v5h4M9 12h6M9 16h6"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7"/>',
  back: '<path d="m14 5-7 7 7 7M7 12h14"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  warning: '<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3v.01"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.01"/>',
  edit: '<path d="m15 4 5 5-11 11-6 1 1-6L15 4Z"/><path d="m12 7 5 5"/>',
  download: '<path d="M12 3v12m-4-4 4 4 4-4M4 15v6h16v-6"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M10 4v16"/>',
  fit: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
  rotate: '<path d="M20 4v6h-6M20 10a8 8 0 1 0 0 5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
};

export function icon(name, className = "") {
  return `<svg class="ui-icon ${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.file}</svg>`;
}

export function invoiceDate(value) {
  if (!value) return "—";
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : value;
}

export function searchText(value) {
  return String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
}
