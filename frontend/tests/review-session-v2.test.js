import test from "node:test";
import assert from "node:assert/strict";
import { createReviewSession } from "../assets/js/review-session-v2.js";

test("V2 pilot thu số liệu chỉ sau đồng ý, phân biệt sửa và xác nhận, rút đồng ý xóa hết", () => {
  let clock = 0;
  const session = createReviewSession(() => clock);
  session.saved("header", "seller_name", true);
  assert.equal(session.snapshot(), null);
  session.start(); clock = 100;
  session.saved("header", "seller_name", true);
  session.saved("line", "description", false);
  session.complete(); clock = 999;
  assert.deepEqual(session.snapshot(), {
    schema_version: "tv6-pilot-1.0", condition: "ASSISTED", synthetic_only: true,
    active_review_ms: 100, outcome: "VERIFIED",
    counts: {"header.seller_name": {corrections: 1, confirmations: 0}, "line.description": {corrections: 0, confirmations: 1}},
  });
  session.withdraw(); assert.equal(session.snapshot(), null);
  session.start(); assert.deepEqual(session.snapshot().counts, {});
});

test("V2 pilot loại thời gian tab ẩn và các request chồng nhau kể cả lỗi", async () => {
  let clock = 0, resolveFirst, resolveSecond;
  const session = createReviewSession(() => clock);
  session.start(); clock = 10;
  const first = session.waiting(() => new Promise(resolve => { resolveFirst = resolve; }));
  const second = session.waiting(() => new Promise(resolve => { resolveSecond = resolve; }));
  clock = 100; resolveFirst(); await first;
  assert.equal(session.snapshot().active_review_ms, 10);
  session.visibility(true); clock = 200; resolveSecond(); await second;
  clock = 300; assert.equal(session.snapshot().active_review_ms, 10);
  session.visibility(false); clock = 310;
  await assert.rejects(session.waiting(async () => { clock = 500; throw new Error("failed"); }));
  clock = 510; assert.equal(session.snapshot().active_review_ms, 30);
});
