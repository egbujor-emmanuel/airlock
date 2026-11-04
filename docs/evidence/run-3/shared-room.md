# Shared room `#acme-x-payco` (Discord), run 3

Everything the two companies saw of each other. Each crossing carries the signed footer that its ledger entry hashes to.

### 2026-11-04 21:34:55 · sim-acme-oncall

@envoy-payco Hi PayCo, Acme on-call here. Since around your platform 4.2.0 release a share of your webhooks to our checkout endpoint are being rejected by our signature verification. We haven't changed our verification code and our own tests pass. Can your team take a look?

### 2026-11-04 21:37:58 · envoy-payco

**From PayCo**
❓ Query Q-P-8: For the webhook deliveries rejected by signature verification since 4.2.0: how many deliveries and rejections, which verifier error, which regions, and what do the rejected t= values look like?
```json
{
 "query": "Q-P-8",
 "fields": {
  "deliveries_total": "int",
  "deliveries_rejected": "int",
  "verifier_errors": "enum:timestamp_outside_tolerance_zone|no_matching_signature|malformed_signature_header|other[]",
  "regions": "enum:us-east|ap-south|eu-west|other[]",
  "rejected_t_digits": "enum:10|13|other[]",
  "rejections_started_after_4_2_0": "bool"
 }
}
```

— airlock crossing P-8 · entry a577a3eb16ad184e · signed by payco

### 2026-11-04 21:42:38 · envoy-acme

**From Acme**
📊 Answer to query Q-P-8 (typed fields only; no free text can cross):
• deliveries_total = 91
• deliveries_rejected = 45
• verifier_errors = ["timestamp_outside_tolerance_zone", "malformed_signature_header"]
• regions = ["eu-west", "other"]
• rejected_t_digits = ["13"]
• rejections_started_after_4_2_0 = true

— airlock crossing A-6 · entry ca5c3cadcba25d5d · signed by acme

### 2026-11-04 21:53:05 · envoy-payco

**From PayCo**
Confirmed and fixed. The EU high-resolution clock we introduced in 4.2.0 was returning milliseconds, while `PayCo-Signature`'s `t=` is defined in whole Unix seconds — so affected deliveries carried a 13-digit timestamp that a correct verifier flags as malformed or outside tolerance. We've corrected the clock to emit whole seconds and added tests that fail if any region's signing timestamp is not a plausible seconds value, plus an end-to-end verify per region.

We re-sent 5 of your failed events: 5 accepted, 0 rejected. No change needed on your side, and please keep the replay check strict.

— airlock crossing P-9 · entry 7bb3e57b199de36e · signed by payco

