const test = require("node:test");
const assert = require("node:assert");
const { sign, verify, SignatureVerificationError } = require("../src");

const SECRET = "test-secret";
const RAW = '{"id": "evt_1", "type": "payment.succeeded", "amount": 4200}';

test("verifies a raw string body", () => {
  const header = sign(RAW, SECRET);
  assert.deepStrictEqual(verify(RAW, header, SECRET).id, "evt_1");
});

test("verifies a raw Buffer body", () => {
  const header = sign(RAW, SECRET);
  assert.strictEqual(verify(Buffer.from(RAW), header, SECRET).amount, 4200);
});

test("rejects a tampered body", () => {
  const header = sign(RAW, SECRET);
  assert.throws(() => verify(RAW.replace("4200", "9999"), header, SECRET), SignatureVerificationError);
});

test("rejects a stale timestamp", () => {
  const header = sign(RAW, SECRET, 1000);
  assert.throws(() => verify(RAW, header, SECRET, { now: 5000 }), /tolerance/);
});
