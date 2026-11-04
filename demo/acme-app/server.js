// Acme's checkout service: receives PayCo payment webhooks.
const fs = require("node:fs");
const path = require("node:path");
const express = require("express");
const { verify } = require("@payco/webhooks");

const LOG = path.join(__dirname, "logs", "webhooks.log");

function log(line) {
  fs.mkdirSync(path.dirname(LOG), { recursive: true });
  fs.appendFileSync(LOG, `${new Date().toISOString()} ${line}\n`);
}

/** @param {{ secret: string }} options */
function createApp({ secret }) {
  if (!secret) throw new Error("PAYCO_WEBHOOK_SECRET is not set");
  const app = express();

  // Raw bytes on the webhook route: the signature covers exactly what PayCo sent.
  app.post("/webhooks/payco", express.raw({ type: "application/json" }), (req, res) => {
    const sig = String(req.headers["payco-signature"] || "");
    const region = req.headers["payco-region"] || "?";
    try {
      const event = verify(req.body, sig, secret);
      log(`INFO accepted event=${event.id} region=${region} sig=${sig}`);
      res.status(200).json({ received: event.id });
    } catch (err) {
      let customer = "?";
      try {
        customer = JSON.parse(req.body.toString()).customer_email ?? "?";
      } catch {
        // body wasn't JSON; nothing to log
      }
      log(`WARN rejected reason="${err.message}" region=${region} customer=${customer} sig=${sig}`);
      res.status(400).json({ error: err.message });
    }
  });
  return app;
}

if (require.main === module) {
  const port = Number(process.env.PORT || 4242);
  createApp({ secret: process.env.PAYCO_WEBHOOK_SECRET }).listen(port, "127.0.0.1", () => {
    process.stdout.write(`acme checkout listening on ${port}\n`);
  });
}

module.exports = { createApp };
