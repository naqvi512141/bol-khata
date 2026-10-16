/**
 * Confidence badge displaying percentage and band label.
 * Docs: docs/02-contracts.md §5.
 */


interface ConfidenceBadgeProps {
  confidence: number;
}

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  const pct = Math.round(confidence * 100);
  let color = 'bg-red-900/60 text-red-200 border-red-700/60';
  let label = 'کم (Low)';

  if (confidence >= 0.85) {
    color = 'bg-emerald-900/60 text-emerald-200 border-emerald-700/60';
    label = 'اعلی (High)';
  } else if (confidence >= 0.60) {
    color = 'bg-amber-900/60 text-amber-200 border-amber-700/60';
    label = 'درمیانی (Med)';
  }

  return (
    <span
      className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border ${color}`}
    >
      <span className="ltr-nums font-mono font-medium">{pct}%</span>
      <span className="font-nastaliq text-[10px]">{label}</span>
    </span>
  );
}

