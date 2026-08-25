// @ts-check
import { CORE_FIELD_TYPES } from "./common.js";

export const DIRTY_FIELD_PHASES = new Set(["EDITING", "SAVING", "SAVE_ERROR", "STALE"]);

export function createFieldState(field, phase = "VIEW") {
  return {
    phase,
    value: field.effective_value,
    value_status: field.effective_status,
    resolved: !field.effective_needs_review,
    error: null,
  };
}

export function createFieldStates(fields) {
  return Object.fromEntries(CORE_FIELD_TYPES.filter((name) => fields?.[name]).map((name) => [name, createFieldState(fields[name])]));
}

export function editFieldValue(state, fieldName, rawValue) {
  const value = fieldName === "total_amount"
    ? rawValue === "" ? null : Number(rawValue)
    : rawValue === "" ? null : rawValue;
  return {
    ...state,
    phase: "EDITING",
    value,
    value_status: value === null ? "UNKNOWN" : "PRESENT",
    resolved: value !== null && (fieldName !== "total_amount" || Number.isInteger(value) && value >= 0),
    error: null,
  };
}

export function editFieldStatus(state, valueStatus) {
  const value = valueStatus === "PRESENT" ? state.value : null;
  return {
    ...state,
    phase: "EDITING",
    value,
    value_status: valueStatus,
    resolved: ["NOT_PRESENT", "UNREADABLE"].includes(valueStatus) || (valueStatus === "PRESENT" && value !== null),
    error: null,
  };
}

export function reconcileStatesAfterCorrection(current, latestFields, savedFieldName) {
  return Object.fromEntries(CORE_FIELD_TYPES.map((fieldName) => {
    const local = current[fieldName];
    if (fieldName !== savedFieldName && local && DIRTY_FIELD_PHASES.has(local.phase)) return [fieldName, local];
    return [fieldName, createFieldState(latestFields[fieldName], fieldName === savedFieldName ? "SAVED" : "VIEW")];
  }));
}

export function canVerifyReceipt(receipt, states) {
  return receipt?.status === "NEEDS_REVIEW"
    && Boolean(receipt.fields)
    && CORE_FIELD_TYPES.every((name) => receipt.fields[name] && !receipt.fields[name].effective_needs_review)
    && CORE_FIELD_TYPES.every((name) => !DIRTY_FIELD_PHASES.has(states[name]?.phase));
}

export function findFieldsForSourceBlock(fields, blockId) {
  return CORE_FIELD_TYPES.filter((name) => fields?.[name]?.source_block_ids.includes(blockId));
}

export function getAdjacentField(current, direction) {
  const index = CORE_FIELD_TYPES.indexOf(current);
  const next = Math.min(CORE_FIELD_TYPES.length - 1, Math.max(0, index + direction));
  return CORE_FIELD_TYPES[next];
}
