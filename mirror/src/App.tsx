import { useEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { ReactLenis } from "lenis/react";
import type { LenisRef } from "lenis/react";
import Noise from "./components/reactbits/Noise";
import { Header } from "./Header";
import { Hero } from "./Hero";
import { Locks } from "./Locks";
import { PrivateChamber, SharedChamber } from "./Chamber";
import { LedgerStrip } from "./LedgerStrip";
import { LogoMark } from "./Logo";
import { useMirror } from "./useMirror";
import type { MirrorState, Org } from "./types";

gsap.registerPlugin(ScrollTrigger, useGSAP);

const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function Door({ org, doorRef }: { org: Org; doorRef: React.RefObject<HTMLDivElement | null> }) {
  return (
    <div className={`door ${org}`} ref={doorRef} aria-hidden="true">
      <span className="leaf top" />
      <span className="seam" />
      <span className="leaf bottom" />
    </div>
  );
}

/** Opens the sending company's door, carries the new crossing through, seals it. */
function useCrossingMotion(state: MirrorState, scope: React.RefObject<HTMLElement | null>) {
  const doors = { acme: useRef<HTMLDivElement>(null), payco: useRef<HTMLDivElement>(null) };
  const seen = useRef<Set<string> | null>(null);

  useGSAP(
    () => {
      const crossed = state.crossings.filter((c) => c.status === "approved").map((c) => `${c.org}:${c.id}`);
      if (seen.current === null) {
        seen.current = new Set(crossed); // first paint: nothing is "arriving"
        return;
      }
      const arriving = crossed.filter((key) => !seen.current!.has(key));
      arriving.forEach((key) => seen.current!.add(key));
      for (const key of arriving) {
        const org = key.split(":")[0] as Org;
        const card = scope.current?.querySelector(`[data-shared="${key}"]`);
        const door = doors[org].current;
        if (!card || !door) continue;
        if (prefersReducedMotion()) {
          gsap.from(card, { opacity: 0, duration: 0.3 });
          continue;
        }
        const leaves = door.querySelectorAll(".leaf");
        gsap
          .timeline()
          .to(door, { "--seam-glow": 1, duration: 0.2 }, 0)
          .to(leaves[0], { yPercent: -100, duration: 0.4, ease: "power3.inOut" }, 0)
          .to(leaves[1], { yPercent: 100, duration: 0.4, ease: "power3.inOut" }, 0)
          .from(card, { x: org === "acme" ? -160 : 160, opacity: 0, scale: 0.94, duration: 0.8, ease: "expo.out" }, 0.25)
          .to(leaves, { yPercent: 0, duration: 0.45, ease: "power3.inOut" }, 1.0)
          .to(door, { "--seam-glow": 0, duration: 0.5 }, 1.2);
      }
    },
    { dependencies: [state], scope },
  );
  return doors;
}

function ControlRoom({ state }: { state: MirrorState }) {
  const scope = useRef<HTMLElement>(null);
  const doors = useCrossingMotion(state, scope);

  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      gsap.from(".chamber", {
        y: 60,
        opacity: 0,
        stagger: 0.12,
        duration: 1,
        ease: "expo.out",
        scrollTrigger: { trigger: scope.current, start: "top 80%" },
      });
      gsap.from(".door .leaf.top", { yPercent: -100, duration: 1.1, ease: "power4.out", scrollTrigger: { trigger: scope.current, start: "top 70%" } });
      gsap.from(".door .leaf.bottom", { yPercent: 100, duration: 1.1, ease: "power4.out", scrollTrigger: { trigger: scope.current, start: "top 70%" } });
    },
    { scope },
  );

  if (state.crossings.length === 0) {
    return (
      <Notice title="No crossings yet">
        <p>The envoys are listening. Start the scenario to see the first one:</p>
        <pre className="mono">uv run python scripts/start_scenario.py</pre>
      </Notice>
    );
  }
  return (
    <main className="stage" ref={scope} aria-label="Control room">
      <PrivateChamber org="acme" state={state} />
      <Door org="acme" doorRef={doors.acme} />
      <SharedChamber state={state} />
      <Door org="payco" doorRef={doors.payco} />
      <PrivateChamber org="payco" state={state} />
    </main>
  );
}

function Notice({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="notice" role="status">
      <h2>{title}</h2>
      {children}
    </div>
  );
}

function Page({ state }: { state: MirrorState }) {
  return (
    <>
      <Hero state={state} />
      <Locks state={state} />
      <section className="room" aria-labelledby="room-title">
        <div className="section-head">
          <span className="eyebrow mono">Control room</span>
          <h2 id="room-title" className="section-title">
            Every crossing, as it happens
          </h2>
        </div>
        <Header state={state} />
        {state.missing.length > 0 && (
          <p className="banner" role="status">
            {state.missing.map((o) => state.orgs[o]).join(" and ")}'s ledger isn't on this machine, so only part of the
            picture is shown.
          </p>
        )}
        {state.breaches.length > 0 && (
          <p className="banner breach" role="alert">
            Canary breach: a value that only exists in one company's private data showed up where it shouldn't.
          </p>
        )}
        <ControlRoom state={state} />
      </section>
      <LedgerStrip state={state} />
      <footer className="foot">
        <LogoMark size={28} />
        <span>
          Airlock · built on <b>Switch</b> · disclosure ledgers signed with ML-DSA-65 (FIPS 204)
        </span>
      </footer>
    </>
  );
}

function Mirror() {
  const { connection, retry } = useMirror();
  if (connection.phase === "connecting") {
    return (
      <Notice title="Connecting to the ledgers…">
        <p className="dim">Reading both companies' disclosure ledgers.</p>
      </Notice>
    );
  }
  if (connection.phase === "error") {
    return (
      <Notice title="Mirror is offline">
        <p>{connection.message}</p>
        <button type="button" className="retry" onClick={retry}>
          Retry
        </button>
      </Notice>
    );
  }
  return (
    <>
      {connection.isReconnecting && (
        <p className="reconnecting" role="status">
          Connection to the ledgers dropped. Reconnecting; showing the last state.
        </p>
      )}
      <Page state={connection.state} />
    </>
  );
}

export default function App() {
  const lenisRef = useRef<LenisRef>(null);

  useEffect(() => {
    // Lenis runs on GSAP's ticker and tells ScrollTrigger about every scroll.
    function update(time: number) {
      lenisRef.current?.lenis?.raf(time * 1000);
    }
    gsap.ticker.add(update);
    gsap.ticker.lagSmoothing(0);
    const lenis = lenisRef.current?.lenis;
    lenis?.on("scroll", ScrollTrigger.update);
    return () => {
      gsap.ticker.remove(update);
      lenis?.off("scroll", ScrollTrigger.update);
    };
  }, []);

  const grain = <Noise opacity={0.07} fps={18} blendMode="overlay" fixed zIndex={50} />;
  if (prefersReducedMotion()) {
    return (
      <>
        {grain}
        <Mirror />
      </>
    );
  }
  return (
    <ReactLenis root options={{ autoRaf: false }} ref={lenisRef}>
      {grain}
      <Mirror />
    </ReactLenis>
  );
}
