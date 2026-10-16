import React, { useState } from 'react';
import type { CaptureJob } from '../types';

interface OfflineManualEntryModalProps {
  job: CaptureJob;
  onCommit: (customerId: string | null, amount: number, isCash: boolean) => void;
  onDismiss: () => void;
}

export function OfflineManualEntryModal({
  job,
  onCommit,
  onDismiss,
}: OfflineManualEntryModalProps) {
  const [customerName, setCustomerName] = useState('');
  const [amount, setAmount] = useState('');
  const [isCash, setIsCash] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const parsedAmount = parseInt(amount, 10);
    if (!isNaN(parsedAmount) && parsedAmount > 0) {
      onCommit(customerName.trim() || null, parsedAmount, isCash);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-amber-600/70 w-full max-w-md rounded-2xl p-5 shadow-2xl space-y-4">
        <div className="flex items-center justify-between border-b border-gray-800 pb-2">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse" />
            <h3 className="font-nastaliq text-lg text-amber-300 font-bold">
              آف لائن دستی اندراج (سرور غیر دستیاب)
            </h3>
          </div>
          <button type="button" onClick={onDismiss} className="text-gray-400 hover:text-white p-1">
            ✕
          </button>
        </div>

        <p className="text-xs text-gray-300 font-nastaliq leading-relaxed">
          آواز کامیابی سے محفوظ کر لی گئی ہے (ULID: <span className="ltr-nums font-mono text-gray-400">{job.job_id.slice(0, 10)}...</span>)۔ سرور کے بحال ہونے پر مکمل آڈیو ٹرانسکرپٹ خودکار طور پر بیک فل ہو جائے گی۔ فی الحال رقم دستی درج فرمائیں:
        </p>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs font-nastaliq text-gray-300 mb-1">
              گاہک کا نام (اختیاری، نقد کی صورت میں خالی چھوڑیں)
            </label>
            <input
              type="text"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              placeholder="مثلاً احمد بھائی"
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-xl text-white font-nastaliq text-sm focus:ring-2 focus:ring-amber-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-nastaliq text-gray-300 mb-1">
              رقم (روپے) *
            </label>
            <input
              type="number"
              required
              min="1"
              step="1"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="مثلاً 500"
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-xl text-white ltr-nums text-base font-bold focus:ring-2 focus:ring-amber-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-3 pt-1">
            <label className="flex items-center gap-2 cursor-pointer text-xs font-nastaliq text-gray-300">
              <input
                type="radio"
                name="paytype"
                checked={!isCash}
                onChange={() => setIsCash(false)}
                className="text-amber-500 focus:ring-amber-500"
              />
              ادھار (کھاتہ)
            </label>
            <label className="flex items-center gap-2 cursor-pointer text-xs font-nastaliq text-gray-300">
              <input
                type="radio"
                name="paytype"
                checked={isCash}
                onChange={() => setIsCash(true)}
                className="text-emerald-500 focus:ring-emerald-500"
              />
              نقد فروخت
            </label>
          </div>

          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-800">
            <button
              type="button"
              onClick={onDismiss}
              className="py-2.5 rounded-xl text-xs font-nastaliq font-bold bg-gray-800 hover:bg-gray-700 text-gray-300 transition-all"
            >
              بعد میں
            </button>
            <button
              type="submit"
              className="py-2.5 rounded-xl text-xs font-nastaliq font-bold bg-amber-600 hover:bg-amber-500 text-white shadow-lg shadow-amber-600/30 transition-all"
            >
              کھاتے میں لکھیں
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
