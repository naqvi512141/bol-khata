/**
 * Draft basket component showing open transaction, countdown progress,
 * and large discard / commit controls.
 * Docs: docs/03-build-plan.md Phase 7.
 */

import type { ParsedDraft } from '../types';
import { ConfidenceBadge } from '../confirm/ConfidenceBadge';

interface DraftBasketProps {
  draft: ParsedDraft;
  secondsRemaining: number;
  onDiscard: () => void;
  onCommit: () => void;
}

export function DraftBasket({
  draft,
  secondsRemaining,
  onDiscard,
  onCommit,
}: DraftBasketProps) {
  const custName = draft.customer.raw_name || (draft.payment_type === 'cash' ? 'نقد فروخت' : 'نامعلوم گاہک');
  const progressPct = Math.max(0, Math.min(100, (secondsRemaining / 20) * 100));

  return (
    <div className="bg-gray-900 border-2 border-emerald-500/50 rounded-2xl p-4 shadow-2xl space-y-4">
      {/* Header with timer and customer */}
      <div className="flex items-center justify-between border-b border-gray-800 pb-3">
        <div>
          <span className="text-xs text-emerald-400 font-medium">جاری ڈرافٹ ٹوکری</span>
          <h2 className="font-nastaliq text-xl text-white">{custName}</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs bg-gray-800 text-gray-300 px-2 py-1 rounded-md ltr-nums font-mono">
            {secondsRemaining}s
          </span>
          <ConfidenceBadge confidence={draft.confidence} />
        </div>
      </div>

      {/* Progress countdown bar */}
      <div className="w-full bg-gray-800 h-1.5 rounded-full overflow-hidden">
        <div
          className="bg-emerald-500 h-full transition-all duration-500 ease-linear"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {/* Items List */}
      <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
        {draft.items.map((item, idx) => {
          const isWarning = draft.validation.warnings.some((w) => w.item_index === idx);
          const isBlocking = draft.validation.blocking.some((b) => b.item_index === idx);

          return (
            <div
              key={idx}
              className={`flex items-center justify-between p-2 rounded-lg border ${
                isBlocking
                  ? 'bg-red-950/40 border-red-800/80 text-red-200'
                  : isWarning
                  ? 'bg-amber-950/40 border-amber-800/80 text-amber-200'
                  : 'bg-gray-850 border-gray-800 text-gray-200'
              }`}
            >
              <div className="flex flex-col">
                <span className="font-nastaliq text-base">{item.display_name || item.raw_name}</span>
                <span className="text-xs text-gray-400 ltr-nums">
                  {item.qty ?? '1'} {item.unit ?? ''}
                  {item.unit_price ? ` × ₨${item.unit_price}` : ''}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="ltr-nums font-semibold text-emerald-400">
                  {item.line_total != null ? `₨${item.line_total}` : '—'}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Total and Action Buttons */}
      <div className="pt-2 border-t border-gray-800 space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-nastaliq text-base text-gray-400">کل رقم</span>
          <span className="ltr-nums text-2xl font-bold text-emerald-400">
            ₨{draft.computed_total}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-1">
          {/* Large Discard Control (AGENTS.md rule: large discard control) */}
          <button
            type="button"
            onClick={onDiscard}
            className="w-full py-2.5 rounded-xl bg-gray-800 hover:bg-red-900/60 text-red-400 border border-gray-700 hover:border-red-700 text-sm font-nastaliq transition-all active:scale-95"
          >
            منسوخ کریں (Discard)
          </button>

          {/* Commit Button */}
          <button
            type="button"
            onClick={onCommit}
            className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-nastaliq text-sm font-semibold shadow-lg shadow-emerald-600/30 transition-all active:scale-95"
          >
            محفوظ کریں (Save)
          </button>
        </div>
      </div>
    </div>
  );
}

