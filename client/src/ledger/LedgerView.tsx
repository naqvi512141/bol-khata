import { useState } from 'react';
import type { LedgerEvent } from '../types';
import { foldDaySummary, foldAllCustomerBalances } from './balanceFold';
import { CustomerModal } from './CustomerModal';
import { AsrEngineBadge } from './AsrEngineBadge';

interface LedgerViewProps {
  events: LedgerEvent[];
  shopId: string;
  deviceId: string;
  onRefresh: () => void;
}

export function LedgerView({ events, shopId, deviceId, onRefresh }: LedgerViewProps) {
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'customers' | 'events'>('customers');

  const summary = foldDaySummary(events);
  const customerBalances = foldAllCustomerBalances(events);

  const selectedBalance = selectedCustomerId
    ? customerBalances.get(selectedCustomerId)?.balance ?? 0
    : 0;

  return (
    <div className="space-y-4">
      {/* Day Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-3 text-center">
          <span className="text-[11px] text-gray-400 font-nastaliq block">آج کا ادھار</span>
          <span className="text-lg font-bold ltr-nums text-red-400">₨{summary.udhaarSales}</span>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-3 text-center">
          <span className="text-[11px] text-gray-400 font-nastaliq block">آج کی نقد</span>
          <span className="text-lg font-bold ltr-nums text-emerald-400">₨{summary.cashSales}</span>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-3 text-center">
          <span className="text-[11px] text-gray-400 font-nastaliq block">آج کی وصولی</span>
          <span className="text-lg font-bold ltr-nums text-blue-400">₨{summary.paymentsReceived}</span>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-3 text-center">
          <span className="text-[11px] text-gray-400 font-nastaliq block">نیٹ ادھار اضافہ</span>
          <span className="text-lg font-bold ltr-nums text-amber-400">
            {summary.netCreditChange >= 0 ? `+₨${summary.netCreditChange}` : `-₨${Math.abs(summary.netCreditChange)}`}
          </span>
        </div>
      </div>

      {/* Switcher */}
      <div className="flex bg-gray-900 rounded-xl p-1 border border-gray-800">
        <button
          type="button"
          onClick={() => setViewMode('customers')}
          className={`flex-1 py-1.5 text-xs font-nastaliq rounded-lg transition-all ${
            viewMode === 'customers' ? 'bg-emerald-600 text-white font-bold' : 'text-gray-400 hover:text-white'
          }`}
        >
          گاہکوں کے کھاتے ({customerBalances.size})
        </button>
        <button
          type="button"
          onClick={() => setViewMode('events')}
          className={`flex-1 py-1.5 text-xs font-nastaliq rounded-lg transition-all ${
            viewMode === 'events' ? 'bg-emerald-600 text-white font-bold' : 'text-gray-400 hover:text-white'
          }`}
        >
          تمام ٹرانزیکشنز ({events.length})
        </button>
      </div>

      {/* Content */}
      {viewMode === 'customers' ? (
        <div className="space-y-2">
          {Array.from(customerBalances.entries()).map(([cid, info]) => (
            <div
              key={cid}
              onClick={() => setSelectedCustomerId(cid)}
              className="bg-gray-900 hover:bg-gray-850 border border-gray-800 rounded-xl p-3.5 flex items-center justify-between cursor-pointer transition-all active:scale-[0.99]"
            >
              <div>
                <h4 className="font-nastaliq text-base text-white font-semibold">{cid}</h4>
                <span className="text-[11px] text-gray-400 ltr-nums">
                  {info.txnCount} ٹرانزیکشنز
                  {info.lastTxnAt && ` • ${new Date(info.lastTxnAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
                </span>
              </div>
              <div className="text-left">
                <span className="text-[10px] text-gray-400 block font-nastaliq">بقایا رقم</span>
                <span className={`text-base font-bold ltr-nums ${info.balance > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                  ₨{info.balance}
                </span>
              </div>
            </div>
          ))}
          {customerBalances.size === 0 && (
            <p className="text-center py-8 text-gray-500 font-nastaliq text-sm">
              کھاتے میں ابھی کوئی ریکارڈ درج نہیں ہوا
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {events.slice().reverse().map((ev) => {
            const engine = (ev.payload?.asr_engine as string) || (ev.source === 'manual' ? 'manual' : 'groq');
            const isPendingBackfill = ev.payload?.pending_backfill === true;
            return (
              <div
                key={ev.event_id}
                className="bg-gray-900 border border-gray-800 rounded-xl p-3 flex items-center justify-between text-xs"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-nastaliq text-white font-medium block">
                      {ev.customer_id ?? 'نقد فروخت'} ({ev.type === 'sale_udhaar' ? 'ادھار' : ev.type === 'sale_cash' ? 'نقد' : 'وصولی'})
                    </span>
                    <AsrEngineBadge engine={engine} />
                    {isPendingBackfill && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-nastaliq bg-amber-950/80 border border-amber-600 text-amber-300 animate-pulse">
                        بیک فل کا انتظار
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-gray-500 ltr-nums">
                    {new Date(ev.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>
                <span className={`font-mono font-bold text-sm ltr-nums ${ev.type === 'payment_received' ? 'text-blue-400' : ev.type === 'sale_cash' ? 'text-emerald-400' : 'text-red-400'}`}>
                  {ev.type === 'payment_received' ? `-₨${Math.abs(ev.amount)}` : `₨${ev.amount}`}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {selectedCustomerId && (
        <CustomerModal
          customerId={selectedCustomerId}
          customerName={selectedCustomerId}
          currentBalance={selectedBalance}
          events={events}
          shopId={shopId}
          deviceId={deviceId}
          onClose={() => setSelectedCustomerId(null)}
          onEventAdded={onRefresh}
        />
      )}
    </div>
  );
}
