# @payco/webhooks

Verify that a webhook really came from PayCo.

```js
const { verify } = require("@payco/webhooks");

app.post("/webhooks/payco", (req, res) => {
  const event = verify(req.body, req.headers["payco-signature"], process.env.PAYCO_WEBHOOK_SECRET);
  // handle event
  res.sendStatus(200);
});
```

`verify` throws `SignatureVerificationError` when the signature doesn't match or the
timestamp is more than 5 minutes old.

This repository is PayCo's (the vendor's) side of the Airlock demo. PayCo's agent works
here and never sees Acme's code, logs or keys.
