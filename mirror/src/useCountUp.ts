import { useEffect, useRef } from "react";
import gsap from "gsap";

/** Counts an element's number up to `value` with GSAP (instant under reduced motion). */
export function useCountUp<T extends HTMLElement>(value: number, duration = 1.4) {
  const ref = useRef<T>(null);
  const shown = useRef({ n: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const tween = gsap.to(shown.current, {
      n: value,
      duration: reduce ? 0 : duration,
      ease: "power3.out",
      onUpdate: () => {
        el.textContent = Math.round(shown.current.n).toLocaleString();
      },
    });
    return () => {
      tween.kill();
    };
  }, [value, duration]);

  return ref;
}
