export function LogoMark({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#C2410C" />
      <path
        d="M7 22c4-1 5-8 9-8s4 5 9-4"
        fill="none"
        stroke="#fff"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="7" cy="22" r="2.5" fill="#fff" />
    </svg>
  );
}
