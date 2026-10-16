import type { ParsedDraft } from '../types';

interface DraftViewProps {
  draft: ParsedDraft;
  secondsRemaining: number;
  onDiscard: () => void;
  onCommitNow: () => void;
}

export function DraftView({
  draft,
  secondsRemaining,
  onDiscard,
  onCommitNow,
}: DraftViewProps) {
  const pct = Math.max(0, Math.min(100, (secondsRemaining / 20) * 100));
  const custName = draft.customer.raw_name ?? 'نقد فروخت';

  return (
    <div className="bg-emerald-950/40 border-2 border-emerald-500/50 rounded-2xl p-4 shadow-xl space-y-4 animate-fadeIn">
      {/* 20s Window Header & Countdown Bar */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="font-nastaliq text-emerald-300 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            کھلا مسودہ (مزید بولیں تو شامل ہوگا)
          </span>
          <span className="ltr-nums font-mono text-emerald-400 font-bold">
            {secondsRemaining}s
          </span>
        </div>
        <div className="w-full bg-gray-800 h-1.5 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-500 transition-all duration-200"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Customer & Total */}
      <div className="flex items-center justify-between pb-2 border-b border-gray-800">
        <div>
          <span className="text-xs text-gray-400 block font-nastaliq">گاہک</span>
          <span className="font-nastaliq text-lg font-bold text-white">{custName}</span>
        </div>
        <div className="text-left">
          <span className="text-xs text-gray-400 block font-nastaliq">موجودہ رقم</span>
          <span className="ltr-nums text-xl font-bold text-emerald-400">
            ₨{draft.computed_total}
          </span>
        </div>
      </div>

      {/* Item list */}
      <div className="space-y-1.5 max-h-48 overflow-y-auto">
        {draft.items.map((item, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between py-1 px-2 rounded bg-gray-900/60 text-sm"
          >
            <span className="font-nastaliq text-gray-200">
              {item.display_name ?? item.raw_name}
            </span>
            <div className="flex items-center gap-2 ltr-nums text-gray-300 text-xs">
              <span>{item.qty ?? 1} {item.unit ?? ''}</span>
              <span className="font-semibold text-emerald-300">
                ₨{item.line_total ?? 0}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Action Controls */}
      <div className="grid grid-cols-2 gap-3 pt-2">
        <button
          type="button"
          onClick={onDiscard}
          className="w-full py-3 px-4 rounded-xl font-nastaliq text-sm font-bold bg-red-950/80 hover:bg-red-900 border border-red-700 text-red-200 shadow-md active:scale-95 transition-all"
        >
          مسودہ منسوخ کریں
        </button>
        <button
          type="button"
          onClick={onCommitNow}
          className="w-full py-3 px-4 rounded-xl font-nastaliq text-sm font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md active:scale-95 transition-all"
        >
          ابھی کھاتے میں لکھیں
        </button>
      </div>
    </div>
  );
}
