type Props = { size?: number; title?: string; className?: string };

/**
 * The Airlock mark: two door leaves (Acme amber, PayCo teal) inside a pressure
 * ring, meeting at a seam of light. The seam is the only way through.
 */
export function LogoMark({ size = 36, title = "Airlock", className }: Props) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label={title}
    >
      <defs>
        <linearGradient id="al-amber" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffc46b" />
          <stop offset="1" stopColor="#e08a1e" />
        </linearGradient>
        <linearGradient id="al-teal" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#6ee8db" />
          <stop offset="1" stopColor="#1f9d90" />
        </linearGradient>
        <radialGradient id="al-seam" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#ffffff" stopOpacity="1" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
        <clipPath id="al-port">
          <circle cx="32" cy="32" r="21" />
        </clipPath>
      </defs>
      {/* pressure ring with eight bolts */}
      <circle cx="32" cy="32" r="29" fill="#14181e" stroke="#3a4350" strokeWidth="2" />
      {Array.from({ length: 8 }, (_, i) => {
        const a = (i * Math.PI) / 4;
        return <circle key={i} cx={32 + 25.5 * Math.cos(a)} cy={32 + 25.5 * Math.sin(a)} r="1.4" fill="#5d6876" />;
      })}
      <g clipPath="url(#al-port)">
        <rect x="11" y="11" width="42" height="42" fill="#0b0d10" />
        <path d="M11 11 H30.2 V53 H11 Z" fill="url(#al-amber)" />
        <path d="M33.8 11 H53 V53 H33.8 Z" fill="url(#al-teal)" />
        {/* leaf ribs */}
        <path d="M14 22 H28 M14 32 H28 M14 42 H28" stroke="#9a5a0e" strokeOpacity="0.45" strokeWidth="1.2" />
        <path d="M36 22 H50 M36 32 H50 M36 42 H50" stroke="#0f5c54" strokeOpacity="0.5" strokeWidth="1.2" />
      </g>
      <rect x="31.2" y="11" width="1.6" height="42" fill="#ffffff" />
      <ellipse cx="32" cy="32" rx="4" ry="21" fill="url(#al-seam)" opacity="0.55" />
      <circle cx="32" cy="32" r="21" fill="none" stroke="#0b0d10" strokeWidth="1.5" />
    </svg>
  );
}

export function Wordmark({ size = 34 }: { size?: number }) {
  return (
    <span className="logo">
      <LogoMark size={size} />
      <span className="logo-word">AIRLOCK</span>
    </span>
  );
}
