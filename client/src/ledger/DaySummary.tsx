/**
 * Day summary card displaying today's total Udhaar, Cash, and Wasooli in PKR.
 * AGENTS.md rule 1: Money is int PKR always.
 */

import type { DaySummaryData } from './ledgerService';

interface DaySummaryProps {
  summary: DaySummaryData;
}

export function DaySummary({ summary }: DaySummaryProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 shadow-lg space-y-3">
      <div className="flex items-center justify-between border-b border-gray-800/80 pb-2">
        <h3 className="font-nastaliq text-base text-gray-300">آج کا خلاصہ (Today's Summary)</h3>
        <span className="text-xs text-gray-500 font-mono ltr-nums">
          {summary.txnCount} ٹرانزیکشنز
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center">
        {/* Credit (Udhaar) */}
        <div className="bg-red-950/30 border border-red-900/40 rounded-xl p-2.5">
          <span className="text-xs text-red-400 font-nastaliq block">ادھار فروخت</span>
          <span className="ltr-nums text-lg font-bold text-red-300">
            ₨{summary.totalCreditSales}
          </span>
        </div>

        {/* Cash */}
        <div className="bg-emerald-950/30 border border-emerald-900/40 rounded-xl p-2.5">
          <span className="text-xs text-emerald-400 font-nastaliq block">نقد فروخت</span>
          <span className="ltr-nums text-lg font-bold text-emerald-300">
            ₨{summary.totalCashSales}
          </span>
        </div>

        {/* Payments Received (Wasooli) */}
        <div className="bg-blue-950/30 border border-blue-900/40 rounded-xl p-2.5">
          <span className="text-xs text-blue-400 font-nastaliq block">وصولی</span>
          <span className="ltr-nums text-lg font-bold text-blue-300">
            ₨{summary.totalPayments}
          </span>
        </div>
      </div>
    </div>
  );
}

