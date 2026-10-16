import { useState } from 'react';
import type { ParsedDraft } from '../types';
import { ItemRow } from './ItemRow';

interface ReviewTrayProps {
  heldDrafts: ParsedDraft[];
  isOpen: boolean;
  onClose: () => void;
  onCommitDraft: (draft: ParsedDraft) => void;
  onRejectDraft: (draftId: string) => void;
}

export function ReviewTray({
  heldDrafts,
  isOpen,
  onClose,
  onCommitDraft,
  onRejectDraft,
}: ReviewTrayProps) {
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [editedDrafts, setEditedDrafts] = useState<Record<string, ParsedDraft>>({});

  if (!isOpen) return null;

  const activeId = selectedDraftId || heldDrafts[0]?.draft_id;
  const current = editedDrafts[activeId] || heldDrafts.find((d) => d.draft_id === activeId);

  const handlePriceUpdate = (itemIdx: number, newPrice: number) => {
    if (!current) return;
    const newItems = [...current.items];
    newItems[itemIdx] = {
      ...newItems[itemIdx],
      line_total: newPrice,
      price_source: 'spoken',
    };
    const newTotal = newItems.reduce((acc, it) => acc + (it.line_total || 0), 0);
    const newBlocking = current.validation.blocking.filter(
      (b) => !(b.rule === 'V7' && (b.item_index === itemIdx || b.item_index === null))
    );

    const updated: ParsedDraft = {
      ...current,
      items: newItems,
      computed_total: newTotal,
      validation: {
        ...current.validation,
        blocking: newBlocking,
        passed: newBlocking.length === 0,
      },
    };
    setEditedDrafts((prev) => ({ ...prev, [current.draft_id]: updated }));
  };

  const handleSelectCustomer = (cand: string) => {
    if (!current) return;
    const newBlocking = current.validation.blocking.filter((b) => b.rule !== 'V6');
    const updated: ParsedDraft = {
      ...current,
      customer: {
        ...current.customer,
        raw_name: cand,
        status: 'resolved',
      },
      validation: {
        ...current.validation,
        blocking: newBlocking,
        passed: newBlocking.length === 0,
      },
    };
    setEditedDrafts((prev) => ({ ...prev, [current.draft_id]: updated }));
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-gray-700 w-full max-w-lg rounded-2xl p-5 shadow-2xl space-y-4 max-h-[90vh] flex flex-col animate-scaleUp">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 pb-3">
          <div className="flex items-center gap-2">
            <span className="font-nastaliq text-xl text-amber-400 font-bold">نظرثانی ٹرے</span>
            <span className="bg-amber-600 text-white text-xs px-2 py-0.5 rounded-full ltr-nums font-bold">
              {heldDrafts.length}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-white text-lg font-bold p-1"
          >
            ✕
          </button>
        </div>

        {/* Drafts selector if multiple */}
        {heldDrafts.length > 1 && (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {heldDrafts.map((d, i) => (
              <button
                key={d.draft_id}
                type="button"
                onClick={() => setSelectedDraftId(d.draft_id)}
                className={`px-3 py-1 text-xs rounded-lg font-nastaliq whitespace-nowrap transition-all ${
                  d.draft_id === activeId
                    ? 'bg-amber-600 text-white font-bold'
                    : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                }`}
              >
                مسودہ #{i + 1} ({d.customer.raw_name ?? 'نقد'})
              </button>
            ))}
          </div>
        )}

        {/* Active Draft Details */}
        {current ? (
          <div className="flex-1 overflow-y-auto space-y-4 pr-1">
            {/* Customer ambiguity disambiguation (V6) */}
            {current.customer.status !== 'resolved' && current.customer.status !== 'absent' && (
              <div className="bg-amber-950/70 border border-amber-700 rounded-xl p-3 space-y-2">
                <span className="font-nastaliq text-xs text-amber-300 block font-semibold">
                  گاہک کے نام میں ابہام (درست نام منتخب کریں):
                </span>
                <div className="flex flex-wrap gap-2">
                  {(current.customer.candidates.length > 0
                    ? current.customer.candidates
                    : ['احمد', 'احمد علی', 'بلال', 'عمران', 'نقد']
                  ).map((cand) => (
                    <button
                      key={cand}
                      type="button"
                      onClick={() => handleSelectCustomer(cand)}
                      className="px-3 py-1 rounded-lg bg-gray-800 hover:bg-amber-700 text-white text-xs font-nastaliq border border-gray-600 active:scale-95 transition-all"
                    >
                      {cand}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Items with field highlights */}
            <div className="space-y-1">
              {current.items.map((it, idx) => (
                <ItemRow
                  key={idx}
                  item={it}
                  itemIndex={idx}
                  validation={current.validation}
                  onUpdatePrice={handlePriceUpdate}
                />
              ))}
            </div>

            {/* Total */}
            <div className="flex items-center justify-between pt-2 border-t border-gray-800">
              <span className="font-nastaliq text-sm text-gray-400">کل رقم</span>
              <span className="ltr-nums text-xl font-bold text-emerald-400">
                ₨{current.computed_total}
              </span>
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500 font-nastaliq">
            نظرثانی کے لیے کوئی مسودہ نہیں ہے
          </div>
        )}

        {/* Action buttons */}
        {current && (
          <div className="grid grid-cols-2 gap-3 pt-3 border-t border-gray-800">
            <button
              type="button"
              onClick={() => onRejectDraft(current.draft_id)}
              className="py-2.5 rounded-xl font-nastaliq text-xs font-bold bg-red-950/80 hover:bg-red-900 border border-red-700 text-red-200 active:scale-95 transition-all"
            >
              مسترد کریں
            </button>
            <button
              type="button"
              disabled={current.validation.blocking.length > 0}
              onClick={() => onCommitDraft(current)}
              className={`py-2.5 rounded-xl font-nastaliq text-xs font-bold text-white shadow-md active:scale-95 transition-all ${
                current.validation.blocking.length > 0
                  ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                  : 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-700/50'
              }`}
            >
              تصدیق اور کھاتے میں اندراج
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
