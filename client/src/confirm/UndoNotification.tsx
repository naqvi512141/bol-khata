/**
 * 3-second undo notification banner for auto-committed transactions.
 * AGENTS.md rule: 3 second undo on every auto-commit. Not optional.
 */

import { useEffect, useState } from 'react';
import type { LedgerEvent } from '../types';

interface UndoNotificationProps {
  event: LedgerEvent;
  onUndo: (event: LedgerEvent) => void;
  onDismiss: () => void;
}

export function UndoNotification({ event, onUndo, onDismiss }: UndoNotificationProps) {
  const [msRemaining, setMsRemaining] = useState(3000);

  useEffect(() => {
    const startTime = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const left = Math.max(0, 3000 - elapsed);
      setMsRemaining(left);
      if (left <= 0) {
        clearInterval(interval);
        onDismiss();
      }
    }, 50);

    return () => clearInterval(interval);
  }, [onDismiss]);

  const progressPct = (msRemaining / 3000) * 100;

  return (
    <div className="fixed bottom-24 left-4 right-4 max-w-md mx-auto z-50 animate-slide-up">
      <div className="bg-gray-900 border-2 border-emerald-500 rounded-2xl shadow-2xl p-3.5 space-y-2 overflow-hidden">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
            <span className="font-nastaliq text-sm text-gray-200">
              اندراج خودکار محفوظ ہو گیا
            </span>
            <span className="ltr-nums text-sm font-bold text-emerald-400">
              ₨{Math.abs(event.amount)}
            </span>
          </div>

          <button
            type="button"
            onClick={() => onUndo(event)}
            className="px-3 py-1 rounded-lg bg-red-600 hover:bg-red-500 text-white font-nastaliq text-xs font-semibold shadow-md active:scale-95 transition-all"
          >
            واپس لیں (Undo)
          </button>
        </div>

        {/* 3s Countdown bar */}
        <div className="w-full bg-gray-800 h-1 rounded-full overflow-hidden">
          <div
            className="bg-emerald-500 h-full transition-all duration-75 ease-linear"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

