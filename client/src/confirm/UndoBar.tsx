import { useEffect, useState } from 'react';
import type { ParsedDraft } from '../types';
import { AsrEngineBadge } from '../ledger/AsrEngineBadge';

interface UndoBarProps {
  draft: ParsedDraft;
  onUndo: () => void;
  onExpire: () => void;
  durationMs?: number;
}

export function UndoBar({
  draft,
  onUndo,
  onExpire,
  durationMs = 3000,
}: UndoBarProps) {
  const [timeLeftMs, setTimeLeftMs] = useState(durationMs);

  useEffect(() => {
    const start = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - start;
      const remaining = Math.max(0, durationMs - elapsed);
      setTimeLeftMs(remaining);

      if (remaining <= 0) {
        clearInterval(interval);
        onExpire();
      }
    }, 50);

    return () => clearInterval(interval);
  }, [durationMs, onExpire]);

  const pct = (timeLeftMs / durationMs) * 100;
  const custName = draft.customer.raw_name ?? 'نقد فروخت';

  return (
    <div className="fixed bottom-24 left-4 right-4 max-w-md mx-auto z-50 bg-gray-900 border-2 border-emerald-500 rounded-2xl p-3 shadow-2xl space-y-2 animate-slideUp">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
          <span className="font-nastaliq text-sm text-white font-medium">
            خودکار اندراج: {custName} (₨{draft.computed_total})
          </span>
          <AsrEngineBadge engine={draft.asr_engine || 'groq'} />
        </div>
        <button
          type="button"
          onClick={onUndo}
          className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 active:scale-95 text-white font-nastaliq text-xs font-bold shadow-md transition-all"
        >
          واپس لیں (Undo)
        </button>
      </div>

      <div className="w-full bg-gray-800 h-1.5 rounded-full overflow-hidden">
        <div
          className="h-full bg-emerald-400 transition-all duration-75 ease-linear"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
