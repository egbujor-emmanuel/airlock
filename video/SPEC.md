# SPEC: Airlock demo, storyline A "The escalation"

GOAL:    a judge understands in one viewing what Airlock does, how to use it step by step, and that Switch is what makes it possible, and remembers: "their agent and mine fixed it together, and nothing private crossed without a yes."
OUTPUT:  HyperFrames, 1920 x 1080, 30 fps, voiceover + quiet music bed + UI sounds.
TIME:    ~140 s x 30 = ~4200 frames. Music ~96 BPM (18.75 frames per beat); scene changes land on bar lines where the voice allows.

## Narration (the clock; ~19 words a scene; every claim from docs/evidence/run-3)

| # | Scene | Voiceover |
|---|---|---|
| 1 | Hook 0–11 s | Forty-five of ninety-one payment webhooks, rejected. Acme's checkout is losing sales, and the vendor, PayCo, says it isn't their bug. |
| 2 | Tension 11–24 s | The evidence is in Acme's logs. But those logs hold customers' emails and Acme's own keys. Nobody can paste them into a vendor ticket. |
| 3 | Reveal 24–33 s | Airlock lets each company's AI agent work on the problem with the other's, inside Switch, without anything private crossing. |
| 4 | Setup 33–52 s | Each company has a private Switch room, here on Telegram, and Acme's runs on its own Switch server. A shared Discord room holds people from both sides, and two envoys. The coding agents are never in it. |
| 5 | Ask 52–68 s | PayCo's OpenCode agent doesn't guess. It sends a typed question: how many failed, with which error, from which region, how many digits in the timestamp. A PayCo engineer approves it. |
| 6 | Answer 68–86 s | Acme's Claude Code agent works the answer out from Acme's private logs. Only numbers and fixed choices can cross, so no email, host or key can ride along. Acme approves. |
| 7 | Fix 86–105 s | Forty-five rejected, all from the EU, all with thirteen-digit timestamps: milliseconds. PayCo's agent finds the clock, fixes it, and redelivers. Five of five accepted. |
| 8 | Proof 105–125 s | Every crossing was redacted, approved by a person, signed with post-quantum ML-DSA-65, and countersigned by the other side. Either company can verify all of it. |
| 9 | Claim 125–140 s | Airlock. Your agent can work with theirs, and nothing private crosses without a human saying yes. Built on Switch. |

## LOOK (the Mirror's own world)

- Ground #0e1013 with 3% grain; panels #181c22, 1 px #262c35 borders, 6 px radius.
- Ink #e8e6e1, dim #8b919a. Acme amber #f0a43a only on Acme things; PayCo teal #35c2b4 only on PayCo things; green #7bd389 only on verified/accepted; red #ff5d5d only on rejected.
- Display: Space Grotesk 600, titles 96 px / -1% tracking, scene lines 56 px. Mono: JetBrains Mono 400, 28 px minimum for anything read.
- Medium: real product UI. Screen recordings of Telegram, Discord and the Mirror sit in panes with a 0 24 48 rgba(0,0,0,0.45) shadow. Diagrams are drawn in the same line weight as the Mirror (1.5 px strokes).

## OBJECTS

- **Acme's log:** real log lines (the format from make_fixtures), emails and keys blurred by a solid bar, never readable.
- **The rooms:** three panes (Acme Private, the shared room, PayCo Inside) with the app's real chrome from the recordings.
- **The envoy:** the Airlock mark (two leaves and a seam) as the only thing that sits on a room boundary.
- **The door:** the Mirror's striped pressure door; it opens only on an approval.
- **The typed answer:** the real chips from A-6 (91 / 45 / eu-west / 13).
- **The ledger:** entries with hash links and "ML-DSA-65 ✓".

## MOTION

- Enter: power3.out 18 f. Move and camera: expo.inOut 24 f. Exit: power2.in 12 f.
- Door: leaves part in 12 f, the crossing travels 24 f, leaves seal in 14 f.
- One hero move per shot; secondary moves at 60% travel, 4–6 f behind. Nothing moves while it's being read.
- Recording panes push in 6% over their shot to the element named by the voice (circle with a 3 px amber or teal ring, 10 f draw).

## SHOTS

1. Alert card "45 of 91 PayCo webhooks rejected" over Acme's log scrolling (blurred PII). Push in. Sound: low hit.
2. The stripe-node #1254 reply as a quote poster ("…can't be a stripe-node bug… contact our support team"), then the log with every email and key slammed shut by bars. Sound: bar thunks.
3. The FluidGlass lens over AIRLOCK (Mirror capture); the mark lands. Sound: glass swell.
4. One diagram that grows: Acme Private (server B) → shared room (server A) → PayCo Inside, each labelled with its Switch primitive as it's named (room, membership, envoy, addressing). Coding agents shown outside the shared room.
5. PayCo Inside recording: OpenCode's `ask {...}` → the 🔒 Crossing P-n card → "approve P-n" typed. Ring on each field name as the voice lists it.
6. Acme Private recording: Claude Code's `answer Q-...` → Envoy's typed-only card → approve. Cut-in of the "⛔ Not sent" refusal for a free-text answer (from the test) to show the guarantee.
7. Shared room: the answer lands with its signed footer; the three numbers lift out as large type; cut to the `hrclock.nowSeconds()` diff (milliseconds → seconds); then Acme's log turning green: 5 accepted lines.
8. The Mirror control room: the door opens, the crossing travels, the ledger strip fills, "13/13 countersigned"; then `airlock-verify` output.
9. The mark, the line, "Built on Switch", the repo URL. Holds 3 s.

## BANNED

Floating particles, glow orbs, purple/blue gradients, centred-everything, everything fading up together, bullet slides, three cards in a row, text moving while read, any readable email/key/hostname, any claim not in run 3.

## QA frames

- 0: the alert reads with no context (thumbnail).
- ~28 s: the AIRLOCK lens title is sharp.
- ~45 s: the diagram shows the coding agents outside the shared room.
- ~78 s: the typed answer's chips readable at 1080.
- ~100 s: "5 of 5 accepted" readable.
- ~118 s: "13/13 countersigned" and "ML-DSA-65 ✓" readable.
- last frame: the mark and "Built on Switch".

## From the reference (MrNetwork's Silicr demo, ZECATHON 2026, 118 s; studied frame by frame)

The person's reference film, so its devices are allowed here exactly as it uses them:
- **Grounds shift by section**: graphite (#0e1013) for hook and product, warm paper (#f3efe7, ink #1b1d21) for the "why it's hard" diagram, a full amber field (#f0a43a, ink #14110c) for the reveal and the positioning line.
- **One serif italic accent word per title** (Instrument Serif italic; everything else Space Grotesk): "rejected", "different", "boundary", "yes".
- **Pill subtitles**: the voiceover as captions in a rounded pill at the bottom centre (#f3efe7 at 92%, ink #1b1d21, 30 px), key words in bold; one caption group per phrase, never more than 9 words on screen.
- **Product in window frames**: recordings inside a window frame with a thin title bar naming the room (Telegram · Acme Private, Discord · #acme-x-payco).
- **Proof with real identifiers**: ledger entry hashes, crossing ids and the verify output, set like the reference's block-number cards.
- **Positioning line** before the end card: "Not another ~~chat-bot bridge~~. A *boundary*."
- **End card**: the mark, AIRLOCK, the tagline, the repo URL, "Flip the Switch 2026 · Built on Switch", holding 3 s.

Scene 4 becomes the sponsor beat: "Switch puts agents in rooms" (rooms, membership, any agent), mirroring the reference's "Zcash is *different*".
