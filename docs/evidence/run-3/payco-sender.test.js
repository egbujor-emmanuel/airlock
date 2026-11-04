const test = require("node:test");
const assert = require("node:assert");
const { signingTimestamp, REGIONS } = require("../sender/clock");
const { nowSeconds } = require("../sender/hrclock");
const { buildDelivery } = require("../sender/dispatch");
const { verify } = require("../src");

const SECRET = "test-secret";
const EVENT = { id: "evt_1", type: "payment.succeeded", amount: 4200 };

test("the EU high-resolution clock reports whole Unix seconds", () => {
  const ts = nowSeconds();
  assert.ok(Number.isInteger(ts), `returned a non-integer timestamp: ${ts}`);
  assert.ok(Math.abs(Math.floor(Date.now() / 1000) - ts) <= 5, `not in seconds: ${ts}`);
});

test("every region signs in whole Unix seconds, not milliseconds", () => {
  const nowSec = Math.floor(Date.now() / 1000);
  for (const region of REGIONS) {
    const ts = signingTimestamp(region);
    assert.ok(Number.isInteger(ts), `${region} returned a non-integer timestamp`);
    assert.ok(Math.abs(nowSec - ts) <= 5, `${region} timestamp is not in seconds: ${ts}`);
  }
});

test("a delivery verifies in every region", () => {
  for (const region of REGIONS) {
    const { body, headers } = buildDelivery(EVENT, { secret: SECRET, region });
    assert.deepStrictEqual(verify(body, headers["payco-signature"], SECRET), EVENT);
  }
});
