/**
 * Append-only ledger event timeline.
 * AGENTS.md rule 11: The ledger is append-only. Never UPDATE, never DELETE.
 */

import type { LedgerEvent } from '../types';

interface RecentEventsProps {
  events: LedgerEvent[];
  customerMap?: Record<string, string>;
}

export function RecentEvents({ events, customerMap = {} }: RecentEventsProps) {
  const sorted = [...events].sort((a, b) => b.created_at.localeCompare(a.created_at));

  const getEventBadge = (type: LedgerEvent['type']) => {
    switch (type) {
      case 'sale_udhaar':
        return <span className="bg-red-900/50 text-red-300 border border-red-800 text-[10px] px-2 py-0.5 rounded-full font-nastaliq">ادھار</span>;
      case 'sale_cash':
        return <span className="bg-emerald-900/50 text-emerald-300 border border-emerald-800 text-[10px] px-2 py-0.5 rounded-full font-nastaliq">نقد</span>;
      case 'payment_received':
        return <span className="bg-blue-900/50 text-blue-300 border border-blue-800 text-[10px] px-2 py-0.5 rounded-full font-nastaliq">وصولی</span>;
      case 'adjustment':
        return <span className="bg-purple-900/50 text-purple-300 border border-purple-800 text-[10px] px-2 py-0.5 rounded-full font-nastaliq">درستگی (Undo)</span>;
      default:
        return <span className="bg-gray-800 text-gray-300 text-[10px] px-2 py-0.5 rounded-full">{type}</span>;
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-nastaliq text-lg text-gray-200">حالیہ اندراجات (Recent Ledger Events)</h3>
        <span className="text-xs text-gray-500 font-mono ltr-nums">{events.length} کل واقعات</span>
      </div>

      {sorted.length === 0 ? (
        <p className="text-gray-500 text-sm font-nastaliq text-center py-6">کوئی اندراج موجود نہیں</p>
      ) : (
        <div className="space-y-2">
          {sorted.map((ev) => {
            const custName = ev.customer_id
              ? customerMap[ev.customer_id] || ev.customer_id
              : 'نقد گاہک';

            return (
              <div
                key={ev.event_id}
                className="bg-gray-900 border border-gray-800 rounded-xl p-3 flex items-center justify-between"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-nastaliq text-base text-white">{custName}</span>
                    {getEventBadge(ev.type)}
                  </div>

                  <div className="text-xs text-gray-400">
                    {ev.items.length > 0 ? (
                      <span>{ev.items.map((i) => i.display_name || i.raw_name).join('، ')}</span>
                    ) : (
                      <span className="text-gray-500">ادائیگی / ایڈجسٹمنٹ</span>
                    )}
                  </div>

                  <div className="text-[10px] text-gray-500 font-mono ltr-nums">
                    {new Date(ev.created_at).toLocaleTimeString('ur-PK', { hour: '2-digit', minute: '2-digit' })} • {ev.source}
                  </div>
                </div>

                <div className="text-right">
                  <span
                    className={`ltr-nums text-lg font-bold ${
                      ev.amount > 0 ? 'text-red-400' : 'text-emerald-400'
                    }`}
                  >
                    {ev.amount > 0 ? `+₨${ev.amount}` : `-₨${Math.abs(ev.amount)}`}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

