import type { MirrorState, Org } from "./types";

type Props = { state: MirrorState };

function Verified({ org, state }: { org: Org; state: MirrorState }) {
  const v = state.verification[org];
  if (!v) {
    return (
      <li className={`seal ${org} missing`}>
        <span className="seal-org">{state.orgs[org]}</span>
        <span className="seal-detail">ledger not on this machine</span>
      </li>
    );
  }
  const isValid = v.chain_ok && v.signatures_ok;
  return (
    <li className={`seal ${org} ${isValid ? "ok" : "bad"}`}>
      <span className="seal-org">{state.orgs[org]}</span>
      <span className="seal-detail mono">
        {v.entries} entries · chain {v.chain_ok ? "✓" : "✗"} · ML-DSA-65 {v.signatures_ok ? "✓" : "✗"}
      </span>
    </li>
  );
}

export function Header({ state }: Props) {
  const approved = state.crossings.filter((c) => c.status === "approved").length;
  const waiting = state.crossings.filter((c) => c.status === "proposed").length;
  const source = state.source === "live" ? "live" : `replay · ${state.source.split(/[\\/]/).pop()}`;
  return (
    <header className="topbar">
      <span className="source mono">
        <span className="dot" /> {source}
      </span>
      <ul className="stats" aria-label="Crossing totals">
        <li>
          <b>{approved}</b> crossed
        </li>
        <li className={waiting ? "attention" : undefined}>
          <b>{waiting}</b> waiting for a human
        </li>
        <li>
          <b>{state.counts.redactions}</b> values withheld
        </li>
        <li>
          <b>{state.counts.ingress}</b> questions in
        </li>
      </ul>
      <ul className="seals" aria-label="Ledger verification">
        <Verified org="acme" state={state} />
        <Verified org="payco" state={state} />
      </ul>
    </header>
  );
}
