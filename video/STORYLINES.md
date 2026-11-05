# Airlock demo video: three storylines

Shared facts (all from run 3, `docs/evidence/run-3/`): 91 deliveries, 45 rejected; EU only; 13-digit `t=`; Q-P-8 → A-6 → fix in `hrclock.nowSeconds()` → 5/5 redelivered accepted; 13/13 crossings countersigned; 70/70 leak benchmark. Hackathon brief: "a short demo video of your workflow running", judged on whether "the demo video and README make it clear what you built and how Switch is used". Length 2:00–2:45, 1920×1080, 30 fps.

## A. The escalation (recommended: a stranger follows it, and every step is a real screen)

**Device:** a moment in someone's day, worked through as one real example. **Form:** split screen to one: Acme | shared | PayCo play side by side, and collapse into the Mirror at the payoff.

Acme's on-call engineer sees 45 of 91 payment webhooks rejected. PayCo says it isn't their bug (the real stripe-node #1254 reply). Airlock lets the two companies' agents solve it in one room, step by step on the real screens, with every crossing redacted, approved by a person and signed.

- **First 2 s:** a phone-sized alert, "45 of 91 PayCo webhooks rejected", over Acme's real log scrolling, with customer emails visible but blurred.
- **Beats:** hook (the alert) → tension ("can't be our bug… contact support"; the logs can't be pasted: emails, keys) → reveal (the FluidGlass lens over AIRLOCK) → proof, six verbs, each with its Switch primitive labelled: *report* (Discord), *ask* (typed query Q-P-8, approved in Telegram), *compute* (Claude Code answers from private logs; only typed values pass), *approve* (A-6), *fix* (OpenCode finds `hrclock.nowSeconds()`), *redeliver* (5/5 accepted) → payoff (the Mirror: doors open, ledgers verify, 13/13 countersigned) → claim → end card.
- **Look:** the Mirror's own world: graphite ground, Acme amber, PayCo teal, Space Grotesk and JetBrains Mono, film grain; real screenshots framed as panes.
- **Sound:** low pulse bed; a soft door-seal hiss on each approval; a click on each verb.

## B. Follow the number

**Device:** one object across apps: the number 45. **Form:** object-to-object chain, one continuous take.

The number 45 is born in Acme's private log, surrounded by secrets that get cut away. It becomes a chip in a typed answer, passes through the door, lands in PayCo's room, turns into the fix, and comes back as "5/5 accepted".

- **First 2 s:** extreme close-up of `45` inside a log line, with redaction bars slamming shut around it.
- **Beats:** the number → what can't travel with it (bars) → the typed answer → the door → PayCo's room → the fix → 5/5 → the ledger seal → claim.
- **Look:** macro typography on graphite, the number always in frame, chambers revealed as the camera pulls back.
- **Sound:** single sustained tone that resolves when 5/5 lands.

## C. The machine (the bold one)

**Device:** the object is the explanation: Airlock built as a physical machine. **Form:** a flight through one world.

Two chambers, a scanner that strips what can't leave, a lever only a person can pull, a press that stamps a post-quantum seal, and a second stamp from the other side. The camera flies through it as one message makes the trip, then cuts to the real run doing the same.

- **First 2 s:** the FluidGlass lens as a porthole, with a message capsule drifting inside.
- **Beats:** porthole → scanner → lever → press → countersign → cut to the real Discord/Telegram run → claim.
- **Look:** industrial 3D: brushed steel, amber and teal warning stripes, glass.
- **Sound:** machine foley: hiss, clunk, stamp.
