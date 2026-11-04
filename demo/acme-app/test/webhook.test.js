const test = require("node:test");
const assert = require("node:assert");
const { sign } = require("@payco/webhooks");
const { createApp } = require("../server");

const SECRET = "test-only-secret";
const BODY = '{\n "id": "evt_1042",\n "type": "payment.succeeded",\n "amount": 4200\n}';

function post(app, body, headers) {
  return new Promise((resolve, reject) => {
    const server = app.listen(0, async () => {
      try {
        const res = await fetch(`http://127.0.0.1:${server.address().port}/webhooks/payco`, {
          method: "POST",
          headers: { "content-type": "application/json", "payco-region": "test", ...headers },
          body,
        });
        resolve({ status: res.status, json: await res.json() });
      } catch (err) {
        reject(err);
      } finally {
        server.close();
      }
    });
  });
}

test("accepts a genuine PayCo webhook", async () => {
  const res = await post(createApp({ secret: SECRET }), BODY, { "payco-signature": sign(BODY, SECRET) });
  assert.strictEqual(res.status, 200, `rejected: ${res.json.error}`);
  assert.strictEqual(res.json.received, "evt_1042");
});

test("rejects a forged webhook", async () => {
  const res = await post(createApp({ secret: SECRET }), BODY, { "payco-signature": sign(BODY, "wrong-secret") });
  assert.strictEqual(res.status, 400);
});

test("rejects a replayed (stale) webhook", async () => {
  const stale = Math.floor(Date.now() / 1000) - 3600;
  const res = await post(createApp({ secret: SECRET }), BODY, { "payco-signature": sign(BODY, SECRET, stale) });
  assert.strictEqual(res.status, 400);
  assert.match(res.json.error, /tolerance/);
});
