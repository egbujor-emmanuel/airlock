const test = require("node:test");
const assert = require("node:assert");
const { sign, verify, SignatureVerificationError } = require("../src");
const { buildDelivery } = require("../sender/dispatch");

const SECRET = "test-secret";
const RAW = '{"id": "evt_1", "type": "payment.succeeded", "amount": 4200}';

test("verifies a raw string body", () => {
  assert.strictEqual(verify(RAW, sign(RAW, SECRET), SECRET).id, "evt_1");
});

test("verifies a raw Buffer body", () => {
  assert.strictEqual(verify(Buffer.from(RAW), sign(RAW, SECRET), SECRET).amount, 4200);
});

test("rejects a parsed object", () => {
  assert.throws(() => verify(JSON.parse(RAW), sign(RAW, SECRET), SECRET), /raw request body/);
});

test("rejects a tampered body", () => {
  assert.throws(() => verify(RAW.replace("4200", "9999"), sign(RAW, SECRET), SECRET), SignatureVerificationError);
});

test("rejects a stale timestamp", () => {
  assert.throws(() => verify(RAW, sign(RAW, SECRET, 1000), SECRET, { now: 5000 }), /tolerance/);
});

test("a dispatched webhook verifies on the merchant side", () => {
  const { body, headers } = buildDelivery({ id: "evt_9", amount: 100 }, { secret: SECRET, region: "us-east" });
  assert.strictEqual(verify(body, headers["payco-signature"], SECRET).id, "evt_9");
});
