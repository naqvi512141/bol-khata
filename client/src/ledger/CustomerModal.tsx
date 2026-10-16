import { useState } from 'react';
import type { LedgerEvent } from '../types';
import { recordPayment, recordAdjustment } from './events';
import { AsrEngineBadge } from './AsrEngineBadge';

interface CustomerModalProps {
  customerId: string;
  customerName: string;
  currentBalance: number;
  events: LedgerEvent[];
  shopId: string;
  deviceId: string;
  onClose: () => void;
  onEventAdded: () => void;
}

export function CustomerModal({
  customerId,
  customerName,
  currentBalance,
  events,
  shopId,
  deviceId,
  onClose,
  onEventAdded,
}: CustomerModalProps) {
  const [payAmount, setPayAmount] = useState('');
  const [adjAmount, setAdjAmount] = useState('');
  const [adjReason, setAdjReason] = useState('');
  const [activeTab, setActiveTab] = useState<'history' | 'pay' | 'adj'>('history');

  const customerEvents = events.filter((e) => e.customer_id === customerId);

  const handlePay = async (e: React.FormEvent) => {
    e.preventDefault();
    const amt = parseInt(payAmount, 10);
    if (!isNaN(amt) && amt > 0) {
      await recordPayment(shopId, customerId, amt, deviceId);
      setPayAmount('');
      onEventAdded();
      setActiveTab('history');
    }
  };

  const handleAdj = async (e: React.FormEvent) => {
    e.preventDefault();
    const amt = parseInt(adjAmount, 10);
    if (!isNaN(amt) && amt !== 0) {
      await recordAdjustment(shopId, customerId, amt, adjReason || 'تصحیح', deviceId);
      setAdjAmount('');
      setAdjReason('');
      onEventAdded();
      setActiveTab('history');
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-gray-700 w-full max-w-md rounded-2xl p-5 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 pb-3">
          <div>
            <h3 className="font-nastaliq text-xl text-white font-bold">{customerName}</h3>
            <span className="text-xs text-gray-400 font-nastaliq">
              بقایا رقم: <span className="ltr-nums text-emerald-400 font-bold text-sm">₨{currentBalance}</span>
            </span>
          </div>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-white p-1">✕</button>
        </div>

        {/* Tab buttons */}
        <div className="flex gap-2">
          {(['history', 'pay', 'adj'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-1.5 rounded-lg text-xs font-nastaliq transition-all ${
                activeTab === tab ? 'bg-emerald-600 text-white' : 'bg-gray-800 text-gray-300'
              }`}
            >
              {tab === 'history' ? 'تاریخچہ' : tab === 'pay' ? 'وصولی' : 'درستگی'}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto space-y-2 pr-1">
          {activeTab === 'history' && (
            <div className="space-y-2">
              {customerEvents.length === 0 ? (
                <p className="text-center py-6 text-gray-500 font-nastaliq text-sm">کوئی ٹرانزیکشن نہیں</p>
              ) : (
                customerEvents.map((ev) => (
                  <div key={ev.event_id} className="p-2.5 rounded-xl bg-gray-800/60 border border-gray-700/50 flex items-center justify-between text-xs">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-nastaliq text-gray-200 block">
                          {ev.type === 'sale_udhaar' ? 'ادھار فروخت' : ev.type === 'payment_received' ? 'رقم وصولی' : 'درستگی'}
                        </span>
                        <AsrEngineBadge engine={(ev.payload?.asr_engine as string) || (ev.source === 'manual' ? 'manual' : 'groq')} />
                      </div>
                      <span className="text-[10px] text-gray-500 ltr-nums">
                        {new Date(ev.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <span className={`font-mono ltr-nums font-bold ${ev.amount > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                      {ev.amount > 0 ? `+₨${ev.amount}` : `-₨${Math.abs(ev.amount)}`}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'pay' && (
            <form onSubmit={handlePay} className="space-y-3 pt-2">
              <label className="block text-xs font-nastaliq text-gray-300">وصول شدہ رقم (روپے)</label>
              <input
                type="number"
                required
                min="1"
                step="1"
                value={payAmount}
                onChange={(e) => setPayAmount(e.target.value)}
                placeholder="500"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-xl text-white ltr-nums text-sm"
              />
              <button type="submit" className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-nastaliq text-xs font-bold rounded-xl">
                وصولی درج کریں
              </button>
            </form>
          )}

          {activeTab === 'adj' && (
            <form onSubmit={handleAdj} className="space-y-3 pt-2">
              <label className="block text-xs font-nastaliq text-gray-300">تبدیلی رقم (+ اضافہ، - رعایت)</label>
              <input
                type="number"
                required
                step="1"
                value={adjAmount}
                onChange={(e) => setAdjAmount(e.target.value)}
                placeholder="-50"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-xl text-white ltr-nums text-sm"
              />
              <input
                type="text"
                value={adjReason}
                onChange={(e) => setAdjReason(e.target.value)}
                placeholder="وجہ (اختیاری)"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-xl text-white font-nastaliq text-sm"
              />
              <button type="submit" className="w-full py-2 bg-amber-600 hover:bg-amber-500 text-white font-nastaliq text-xs font-bold rounded-xl">
                درستگی لاگو کریں
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
