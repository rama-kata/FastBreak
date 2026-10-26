export function Logo({ color }: { color: string }) {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <circle cx="14" cy="14" r="12" stroke={color} strokeWidth="2.5" />
      <path
        d="M2 14h24M14 2v24M5.5 5.5c4 3 4 14 0 17M22.5 5.5c-4 3-4 14 0 17"
        stroke={color}
        strokeWidth="2"
      />
    </svg>
  );
}
