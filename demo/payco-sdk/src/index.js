// PayCo webhooks SDK: sign and verify the `PayCo-Signature` header.
//
// Header format: `t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<payload>">`.
const crypto = require("node:crypto");

const DEFAULT_TOLERANCE_SEC = 300;

class SignatureVerificationError extends Error {
  constructor(message) {
    super(message);
    this.name = "SignatureVerificationError";
  }
}

function hmac(secret, timestamp, payload) {
  return crypto.createHmac("sha256", secret).update(`${timestamp}.${payload}`).digest("hex");
}

/** @returns {string} the PayCo-Signature header for a payload. */
function sign(payload, secret, timestamp = Math.floor(Date.now() / 1000)) {
  return `t=${timestamp},v1=${hmac(secret, timestamp, payload)}`;
}

function parseHeader(header) {
  const parts = Object.fromEntries(
    String(header || "")
      .split(",")
      .map((kv) => kv.split("=").map((s) => s.trim()))
      .filter((kv) => kv.length === 2),
  );
  return { timestamp: Number(parts.t), signature: parts.v1 };
}

/**
 * Verify a webhook. `payload` must be the raw request body (string or Buffer).
 * @returns {object} the parsed event
 */
function verify(payload, header, secret, { toleranceSec = DEFAULT_TOLERANCE_SEC, now } = {}) {
  if (typeof payload !== "string" && !Buffer.isBuffer(payload)) {
    throw new SignatureVerificationError("verify() needs the raw request body (string or Buffer)");
  }
  const body = payload.toString();
  const { timestamp, signature } = parseHeader(header);
  if (!timestamp || !signature) {
    throw new SignatureVerificationError("Unable to extract timestamp and signatures from header");
  }
  const current = now ?? Math.floor(Date.now() / 1000);
  if (Math.abs(current - timestamp) > toleranceSec) {
    throw new SignatureVerificationError("Timestamp outside the tolerance zone");
  }
  const expected = hmac(secret, timestamp, body);
  const ok =
    expected.length === signature.length && crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
  if (!ok) {
    throw new SignatureVerificationError("No signatures found matching the expected signature for payload");
  }
  return JSON.parse(body);
}

module.exports = { sign, verify, SignatureVerificationError, DEFAULT_TOLERANCE_SEC };
