import FluidGlass from "./components/reactbits/FluidGlass";
import GlassSurface from "./components/reactbits/GlassSurface";
import ShinyText from "./components/reactbits/ShinyText";
import { Wordmark } from "./Logo";
import { useCountUp } from "./useCountUp";
import type { MirrorState } from "./types";

function Stat({ value, label, tone }: { value: number; label: string; tone?: "amber" | "teal" | "ok" }) {
  const ref = useCountUp<HTMLSpanElement>(value);
  return (
    <li className={`hero-stat ${tone ?? ""}`}>
      <span className="hero-stat-n" ref={ref}>
        0
      </span>
      <span className="hero-stat-l">{label}</span>
    </li>
  );
}

const plain = (text: string) =>
  text
    .replace(/\[REDACTED:([a-z_]+)#\d+\]/g, "▮▮ $1 ▮▮")
    .replace(/```json[\s\S]*?```/g, "")
    .replace(/[*`]/g, "")
    .trim();

/** The most recent crossing, on a pane of glass: what just went through. */
function LatestCrossing({ state }: { state: MirrorState }) {
  const latest = state.crossings.filter((c) => c.status === "approved").at(-1);
  if (!latest) return null;
  const text = plain(latest.text ?? "");
  const preview = text.length > 170 ? `${text.slice(0, 170)}…` : text;
  return (
    <aside className="hero-latest" aria-label="Latest crossing">
      <GlassSurface width="100%" height="auto" borderRadius={14} blur={14} backgroundOpacity={0.08} brightness={60}>
        <div className="hero-latest-inner">
          <div className="hero-latest-head">
            <span className="eyebrow mono">Latest crossing</span>
            <span className={`from ${latest.org}`}>
              {state.orgs[latest.org]} → shared · {latest.id}
            </span>
          </div>
          <p>{preview}</p>
          <div className="proof mono">
            <span>approved by {latest.decided_by}</span>
            <span className={latest.signed ? "ok" : "bad"}>ML-DSA-65 {latest.signed ? "✓" : "✗"}</span>
            <span className={latest.receipt ? "ok" : "pending"}>
              {latest.receipt ? `countersigned by ${state.orgs[latest.receipt.by]}` : "awaiting receipt"}
            </span>
          </div>
        </div>
      </GlassSurface>
    </aside>
  );
}

export function Hero({ state }: { state: MirrorState }) {
  // The lens scales with the screen: a 300px lens would cover a phone's whole word.
  const lensSize = Math.round(Math.min(300, Math.max(120, window.innerWidth * 0.21)));
  const crossed = state.crossings.filter((c) => c.status === "approved").length;
  const signatures = state.entries.filter((e) => e.signature_ok).length;
  const verified = Object.values(state.verification).every((v) => v && v.chain_ok && v.signatures_ok);
  const source = state.source === "live" ? "Live" : `Replay · ${state.source.split(/[\\/]/).pop()}`;

  return (
    <section className="hero" aria-labelledby="hero-title">
      <FluidGlass
        className="hero-glass"
        text="AIRLOCK"
        textColor="#e8e6e1"
        fontFamily="Space Grotesk"
        fontWeight={600}
        background="#0e1013"
        shape="lens"
        size={lensSize}
        refraction={1.15}
        dispersion={0.55}
        frost={0.05}
        tint={0.08}
        color="#9fe7de"
        interaction="follow"
        morphOnClick
      />
      <div className="hero-top">
        <Wordmark />
        <span className={`hero-status ${verified ? "ok" : "bad"}`}>
          <span className="dot" /> {source} · ledgers {verified ? "verified" : "FAILED verification"}
        </span>
      </div>
      <div className="hero-copy">
        <h1 id="hero-title" className="sr-only">
          Airlock
        </h1>
        <p className="hero-tagline">
          <ShinyText
            text="Two companies. Two AI agents. Nothing private crosses without a human saying yes."
            color="#c9ccd1"
            shineColor="#ffffff"
            speed={3.2}
          />
        </p>
        <p className="hero-sub">
          A live view of the boundary between <b className="amber">Acme</b> and <b className="teal">PayCo</b>, built on
          Switch. Every crossing redacted, approved by a person, and signed with ML-DSA-65.
        </p>
        <ul className="hero-stats" aria-label="Live totals">
          <Stat value={crossed} label="crossings approved" tone="ok" />
          <Stat value={state.counts.redactions} label="values withheld" tone="amber" />
          <Stat value={signatures} label="post-quantum signatures verified" tone="teal" />
          <Stat value={state.counts.ingress} label="questions from outside" />
        </ul>
      </div>
      <LatestCrossing state={state} />
      <a className="hero-cue" href="#locks">
        <span>See how it holds</span>
        <span className="hero-cue-line" aria-hidden="true" />
      </a>
    </section>
  );
}
