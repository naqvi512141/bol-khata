/**
 * Customer list showing folded balances and quick payment receipt action.
 * Docs: docs/03-build-plan.md Phase 7; AGENTS.md rule 11.
 */

import { useState } from 'react';
import type { CustomerBalance } from './ledgerService';

interface CustomerListProps {
  balances: CustomerBalance[];
  onRecordPayment: (customerId: string, amount: number) => void;
}

export function CustomerList({ balances, onRecordPayment }: CustomerListProps) {
  const [selectedCustId, setSelectedCustId] = useState<string | null>(null);
  const [paymentAmount, setPaymentAmount] = useState<string>('');

  const handlePaymentSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustId) return;
    const amount = parseInt(paymentAmount, 10);
    if (!isNaN(amount) && amount > 0) {
      onRecordPayment(selectedCustId, amount);
      setSelectedCustId(null);
      setPaymentAmount('');
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-nastaliq text-lg text-gray-200">گاہکوں کے کھاتے (Customer Ledgers)</h3>
        <span className="text-xs text-gray-500 font-mono ltr-nums">{balances.length} گاہک</span>
      </div>

      {balances.length === 0 ? (
        <p className="text-gray-500 text-sm font-nastaliq text-center py-6">کوئی گاہک ریکارڈ نہیں ملا</p>
      ) : (
        <div className="space-y-2">
          {balances.map((c) => (
            <div
              key={c.customerId}
              className="bg-gray-900 border border-gray-800 rounded-xl p-3 flex items-center justify-between hover:border-gray-700 transition-colors"
            >
              <div>
                <span className="font-nastaliq text-base text-white block">{c.displayName}</span>
                <span className="text-xs text-gray-500 ltr-nums font-mono">{c.customerId}</span>
              </div>

              <div className="flex items-center gap-3">
                <div className="text-right">
                  <span className="text-xs text-gray-400 font-nastaliq block">باقی رقم</span>
                  <span
                    className={`ltr-nums text-base font-bold ${
                      c.balance > 0 ? 'text-red-400' : 'text-emerald-400'
                    }`}
                  >
                    ₨{c.balance}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => setSelectedCustId(c.customerId)}
                  className="px-2.5 py-1 rounded-lg bg-gray-800 hover:bg-emerald-900/40 text-emerald-300 text-xs font-nastaliq border border-gray-700 hover:border-emerald-700 transition-all"
                >
                  وصولی
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Payment Modal */}
      {selectedCustId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <form
            onSubmit={handlePaymentSubmit}
            className="bg-gray-900 border border-gray-800 rounded-2xl p-5 w-full max-w-sm space-y-4"
          >
            <h4 className="font-nastaliq text-lg text-white">
              ادائیگی وصول کریں — {balances.find((b) => b.customerId === selectedCustId)?.displayName}
            </h4>

            <div>
              <label className="block text-xs text-gray-400 font-nastaliq mb-1">وصول شدہ رقم (روپے)</label>
              <input
                type="number"
                min="1"
                step="1"
                required
                autoFocus
                value={paymentAmount}
                onChange={(e) => setPaymentAmount(e.target.value)}
                placeholder="مثلاً 500"
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-white ltr-nums text-lg focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-2 pt-2">
              <button
                type="button"
                onClick={() => setSelectedCustId(null)}
                className="py-2 rounded-xl bg-gray-800 text-gray-300 font-nastaliq text-xs"
              >
                منسوخ
              </button>
              <button
                type="submit"
                className="py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-nastaliq text-xs font-semibold shadow"
              >
                محفوظ کریں
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

