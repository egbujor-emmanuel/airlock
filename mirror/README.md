# Airlock Mirror

The live view of the boundary between the two companies: a hero with a 3D lens over the
wordmark, the three locks, the control room with its pressure doors, and both disclosure
ledgers re-verified as they grow.

```bash
npm install && npm run build                 # once
cd .. && uv run airlock-mirror               # http://127.0.0.1:8787, live ledgers
uv run airlock-mirror --evidence docs/evidence/run-3   # replay a recorded run
npm run dev                                  # hot reload; /api proxies to the Python API on :8787
```

Built with React 19, GSAP (`useGSAP`, ScrollTrigger), Lenis synced to the GSAP ticker, and
React Bits components (FluidGlass, GlassSurface, SpotlightCard, ElectricBorder, GlareHover,
ScrambledText, ShinyText, Noise) in `src/components/reactbits/`. With reduced motion, Lenis is
off and crossings fade instead of travelling. Rendered review: `evidence/design-review.json`.
