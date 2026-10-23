// Opt-in, memory-only counters. No document, receipt, row or participant identifiers.
export function createReviewSession(now = () => performance.now()) {
  let started = null, activeStart = null, elapsed = 0, hidden = false, waits = 0, outcome = "IN_PROGRESS", counts = {};
  function pause() {
    if (activeStart !== null) elapsed += Math.max(0, now() - activeStart);
    activeStart = null;
  }
  function resume() {
    if (started !== null && !hidden && !waits && outcome === "IN_PROGRESS" && activeStart === null) activeStart = now();
  }
  return {
    start() { if (started !== null) return; started = now(); resume(); },
    withdraw() { started = activeStart = null; elapsed = 0; counts = {}; outcome = "IN_PROGRESS"; },
    enabled() { return started !== null; },
    visibility(value) { pause(); hidden = value; resume(); },
    async waiting(action) { pause(); waits++; try { return await action(); } finally { waits--; resume(); } },
    saved(section, field, changed) {
      if (started === null || outcome !== "IN_PROGRESS") return;
      const key = `${section}.${field}`, entry = counts[key] ||= {corrections: 0, confirmations: 0};
      entry[changed ? "corrections" : "confirmations"]++;
    },
    complete() { if (started === null) return; pause(); outcome = "VERIFIED"; },
    snapshot() {
      if (started === null) return null;
      return {schema_version: "tv6-pilot-1.0", condition: "ASSISTED", synthetic_only: true,
        active_review_ms: Math.round(elapsed + (activeStart === null ? 0 : Math.max(0, now() - activeStart))),
        outcome, counts: structuredClone(counts)};
    },
  };
}
