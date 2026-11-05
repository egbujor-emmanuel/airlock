import ScrambledText from "./components/reactbits/ScrambledText";
import type { LedgerEntry, MirrorState } from "./types";

const LABEL: Record<string, string> = {
  ingress: "question in",
  proposed: "proposed",
  approved: "approved",
  declined: "declined",
  receipt: "receipt",
  refused: "refused",
  blocked: "blocked",
  rejected: "rejected",
  breach: "canary breach",
};

function Entry({ entry, orgName }: { entry: LedgerEntry; orgName: string }) {
  const isValid = entry.linked && entry.signature_ok;
  return (
    <li className={`link ${entry.org} t-${entry.type} ${isValid ? "" : "bad"}`}>
      <span className="link-org">{orgName}</span>
      <span className="link-type">
        {LABEL[entry.type] ?? entry.type}
        {entry.crossing ? ` ${entry.crossing}` : ""}
      </span>
      <ScrambledText className="link-hash" radius={60} duration={0.8} speed={0.4} scrambleChars="0123456789abcdef">
        {`#${entry.seq} ${entry.hash.slice(0, 10)}`}
      </ScrambledText>
      <span className="link-check mono">{isValid ? "linked · signed" : "BROKEN"}</span>
    </li>
  );
}

/** Both ledgers interleaved in time: every link, every signature, checked. */
export function LedgerStrip({ state }: { state: MirrorState }) {
  const recent = state.entries.slice(-40).reverse();
  return (
    <section className="ledger" aria-labelledby="ledger-title">
      <header className="chamber-head">
        <h2 id="ledger-title">Disclosure ledgers</h2>
        <span className="chamber-sub">hash-chained · ML-DSA-65 (FIPS 204) · newest first</span>
      </header>
      <ol className="chain">
        {recent.map((e) => (
          <Entry key={`${e.org}-${e.seq}`} entry={e} orgName={state.orgs[e.org]} />
        ))}
      </ol>
    </section>
  );
}
