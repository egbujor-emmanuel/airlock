// PayCo's webhook dispatcher: signs an event and delivers it to a merchant endpoint.
const { sign } = require("../src");
const { signingTimestamp } = require("./clock");

/**
 * Build the request PayCo sends for an event.
 * @param {object} event
 * @param {{ secret: string, region: string }} merchant
 * @returns {{ body: string, headers: Record<string, string> }}
 */
function buildDelivery(event, merchant) {
  // Pretty-printed on purpose: merchants must verify the raw bytes, not re-serialise.
  const body = JSON.stringify(event, null, 1);
  const timestamp = signingTimestamp(merchant.region);
  return {
    body,
    headers: {
      "content-type": "application/json",
      "payco-signature": sign(body, merchant.secret, timestamp),
      "payco-region": merchant.region,
      "payco-event-id": event.id,
    },
  };
}

/** Deliver an event to a merchant's endpoint. @returns {Promise<number>} HTTP status */
async function deliver(url, event, merchant) {
  const { body, headers } = buildDelivery(event, merchant);
  const res = await fetch(url, { method: "POST", headers, body });
  return res.status;
}

module.exports = { buildDelivery, deliver };
