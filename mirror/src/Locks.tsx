import { useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import SpotlightCard from "./components/reactbits/SpotlightCard";
import type { MirrorState } from "./types";

gsap.registerPlugin(ScrollTrigger, useGSAP);

type Lock = { n: string; title: string; body: string; figure: string; caption: string; tone: string };

function locksFor(state: MirrorState): Lock[] {
  const approvals = state.crossings.filter((c) => c.status === "approved");
  const approvers = new Set(approvals.map((c) => c.decided_by).filter(Boolean));
  const countersigned = approvals.filter((c) => c.receipt).length;
  const queries = state.crossings.filter((c) => c.is_query).length;
  return [
    {
      n: "01",
      title: "Redacted before anyone sees it",
      body: "Keys, customers' emails, internal hosts and planted canaries are cut out, even when hidden in base64, hex, rot13 or full-width text. Typed questions go further: only numbers and fixed choices can answer them.",
      figure: String(state.counts.redactions),
      caption: `values withheld · ${queries} typed ${queries === 1 ? "query" : "queries"}`,
      tone: "amber",
    },
    {
      n: "02",
      title: "A person says yes",
      body: "The coding agents aren't in the shared room, so they can't post there. The only way out is the envoy, and it waits for an approver from the sending company to reply `approve`.",
      figure: String(approvals.length),
      caption: `approved by ${approvers.size} ${approvers.size === 1 ? "person" : "people"}`,
      tone: "steel",
    },
    {
      n: "03",
      title: "Signed twice, provable forever",
      body: "Each approval is written to a hash-chained ledger and signed with ML-DSA-65 (FIPS 204) before it's posted. The other company countersigns its receipt. Either side can verify the whole history.",
      figure: `${countersigned}/${approvals.length}`,
      caption: "countersigned by the other side",
      tone: "teal",
    },
  ];
}

export function Locks({ state }: { state: MirrorState }) {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduce) return;
      gsap.from(".lock", {
        y: 80,
        opacity: 0,
        stagger: 0.18,
        duration: 1,
        ease: "expo.out",
        scrollTrigger: { trigger: root.current, start: "top 75%" },
      });
      gsap.from(".locks-title", {
        y: 30,
        opacity: 0,
        duration: 0.9,
        ease: "power3.out",
        scrollTrigger: { trigger: root.current, start: "top 85%" },
      });
    },
    { scope: root },
  );

  return (
    <section className="locks" id="locks" ref={root} aria-labelledby="locks-title">
      <h2 className="locks-title" id="locks-title">
        Three locks between two companies
      </h2>
      <ol className="lock-row">
        {locksFor(state).map((lock) => (
          <li key={lock.n} className={`lock ${lock.tone}`}>
            <SpotlightCard className="lock-card" spotlightColor="rgba(255,255,255,0.18)" theme="dark">
              <span className="lock-n mono">{lock.n}</span>
              <h3>{lock.title}</h3>
              <p>{lock.body}</p>
              <div className="lock-figure">
                <span className="lock-figure-n">{lock.figure}</span>
                <span className="lock-figure-c">{lock.caption}</span>
              </div>
            </SpotlightCard>
          </li>
        ))}
      </ol>
    </section>
  );
}
