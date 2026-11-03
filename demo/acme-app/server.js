// Acme's checkout service: receives PayCo payment webhooks.
const fs = require("node:fs");
const path = require("node:path");
const express = require("express");
const { verify } = require("@payco/webhooks");

const LOG = path.join(__dirname, "logs", "webhooks.log");

/** @param {{ secret: string }} options */
function createApp({ secret }) {
  if (!secret) throw new Error("PAYCO_WEBHOOK_SECRET is not set");
  const app = express();
  app.use(express.json());

  app.post("/webhooks/payco", (req, res) => {
    try {
      const event = verify(req.body, req.headers["payco-signature"], secret);
      res.status(200).json({ received: event.id });
    } catch (err) {
      fs.appendFileSync(
        LOG,
        `${new Date().toISOString()} WARN webhook rejected: ${err.message} ` +
          `customer=${req.body?.customer_email ?? "?"} sig=${req.headers["payco-signature"]}\n`,
      );
      res.status(400).json({ error: err.message });
    }
  });
  return app;
}

if (require.main === module) {
  const port = Number(process.env.PORT || 4242);
  createApp({ secret: process.env.PAYCO_WEBHOOK_SECRET }).listen(port, () => {
    process.stdout.write(`acme checkout listening on ${port}\n`);
  });
}

module.exports = { createApp };
