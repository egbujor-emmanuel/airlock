import ElectricBorder from "./components/reactbits/ElectricBorder";
import GlareHover from "./components/reactbits/GlareHover";
import type { Crossing, MirrorState, Org } from "./types";
import { Message } from "./Message";

const short = (hash?: string) => (hash ? hash.slice(0, 12) : "");
const ORG_COLOR: Record<Org, string> = { acme: "#f0a43a", payco: "#35c2b4" };

function Status({ crossing }: { crossing: Crossing }) {
  if (crossing.status === "approved") {
    return <span className="pill approved">approved by {crossing.decided_by}</span>;
  }
  if (crossing.status === "declined") {
    return <span className="pill declined">declined by {crossing.decided_by}</span>;
  }
  return <span className="pill waiting">waiting for a human</span>;
}

function ProposalBody({ crossing }: { crossing: Crossing }) {
  return (
    <>
      <div className="card-head">
        <span className="cid mono">{crossing.id}</span>
        <Status crossing={crossing} />
      </div>
      {crossing.text ? <Message text={crossing.text} /> : <p className="body dim">(text not recorded)</p>}
      {crossing.redactions && crossing.redactions.length > 0 && (
        <p className="withheld">
          {crossing.redactions.length} withheld before anyone could approve:{" "}
          {crossing.redactions.map((r) => r.kind.replaceAll("_", " ")).join(", ")}
        </p>
      )}
    </>
  );
}

/** One company's private room: what its agent proposed, and what happened to it. */
export function PrivateChamber({ org, state }: { org: Org; state: MirrorState }) {
  const own = state.crossings.filter((c) => c.org === org).slice().reverse();
  const withheld = own.reduce((n, c) => n + (c.redactions?.length ?? 0), 0);
  return (
    <section className={`chamber private ${org}`} aria-labelledby={`${org}-title`}>
      <header className="chamber-head">
        <h2 id={`${org}-title`}>
          <span className={`chip ${org}`} aria-hidden="true" />
          {state.orgs[org]} inside
        </h2>
        <span className="chamber-sub">private room · {own.length} proposed · {withheld} withheld</span>
      </header>
      <ol className="cards" data-lenis-prevent>
        {own.map((c) =>
          c.status === "proposed" ? (
            // Waiting on a person: the one thing an operator must not miss.
            <li key={c.id} data-crossing={`${c.org}:${c.id}`}>
              <ElectricBorder color={ORG_COLOR[org]} speed={1} chaos={0.6} thickness={2} borderRadius={8}>
                <div className="card proposed">
                  <ProposalBody crossing={c} />
                </div>
              </ElectricBorder>
            </li>
          ) : (
            <li key={c.id} className={`card ${c.status}`} data-crossing={`${c.org}:${c.id}`}>
              <ProposalBody crossing={c} />
            </li>
          ),
        )}
      </ol>
    </section>
  );
}

/** The shared room: only what each company's approver released, with its receipt. */
export function SharedChamber({ state }: { state: MirrorState }) {
  const crossed = state.crossings.filter((c) => c.status === "approved").slice().reverse();
  return (
    <section className="chamber shared" aria-labelledby="shared-title">
      <header className="chamber-head">
        <h2 id="shared-title">
          <span className="chip steel" aria-hidden="true" />
          Shared room
        </h2>
        <span className="chamber-sub">what each company let the other see</span>
      </header>
      <ol className="cards" data-lenis-prevent>
        {crossed.map((c) => (
          <li key={`${c.org}:${c.id}`} className={`crossed-slot from-${c.org}`} data-shared={`${c.org}:${c.id}`}>
            <GlareHover
              width="100%"
              height="auto"
              background="transparent"
              borderRadius="6px"
              borderColor="transparent"
              glareColor={ORG_COLOR[c.org]}
              glareOpacity={0.22}
              variant="sheen"
              mode="hover"
            >
              <article className={`card crossed from-${c.org}`}>
                <div className="card-head">
                  <span className={`from ${c.org}`}>From {state.orgs[c.org]}</span>
                  <span className="cid mono">{c.id}</span>
                </div>
                {c.text && <Message text={c.text} />}
                <footer className="proof mono">
                  <span title="ledger entry hash">entry {short(c.entry)}</span>
                  <span className={c.signed ? "ok" : "bad"}>{c.signed ? "ML-DSA-65 ✓" : "signature ✗"}</span>
                  <span className={c.receipt ? "ok" : "pending"}>
                    {c.receipt ? `countersigned by ${state.orgs[c.receipt.by]} ✓` : "awaiting receipt"}
                  </span>
                </footer>
              </article>
            </GlareHover>
          </li>
        ))}
      </ol>
    </section>
  );
}
