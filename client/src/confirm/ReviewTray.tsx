/**
 * Review Tray modal/drawer for blocking or low-confidence drafts.
 * AGENTS.md rule: Ambiguous customer identity is always blocking. Never auto-select.
 */

import { useState } from 'react';
import type { ParsedDraft } from '../types';
import { ConfidenceBadge } from './ConfidenceBadge';

interface ReviewTrayProps {
  drafts: ParsedDraft[];
  isOpen: boolean;
  onClose: () => void;
  onResolveAndCommit: (draft: ParsedDraft, resolvedCustomerId?: string) => void;
  onDiscardDraft: (draftId: string) => void;
}

export function ReviewTray({
  drafts,
  isOpen,
  onClose,
  onResolveAndCommit,
  onDiscardDraft,
}: ReviewTrayProps) {
  const [selectedCustomerMap, setSelectedCustomerMap] = useState<Record<string, string>>({});

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm p-3">
      <div className="bg-gray-900 border border-gray-800 rounded-3xl w-full max-w-lg max-h-[85vh] flex flex-col overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <h2 className="font-nastaliq text-xl text-yellow-400">جائزہ ٹرے (Review Tray)</h2>
            <span className="text-xs bg-yellow-900/60 text-yellow-300 px-2 py-0.5 rounded-full ltr-nums">
              {drafts.length}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800"
          >
            ✕
          </button>
        </div>

        {/* Content list */}
        <div className="p-4 overflow-y-auto space-y-4">
          {drafts.length === 0 ? (
            <p className="text-center py-8 text-gray-500 font-nastaliq">کوئی زیرِ جائزہ ڈرافٹ نہیں</p>
          ) : (
            drafts.map((d) => {
              const cust = d.customer;
              const isAmbiguous = cust.status === 'ambiguous';

              return (
                <div key={d.draft_id} className="bg-gray-850 border border-gray-750 rounded-2xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-nastaliq text-lg font-semibold text-white">
                        {cust.raw_name || 'نامعلوم گاہک'}
                      </span>
                      {isAmbiguous && (
                        <span className="mr-2 text-xs bg-red-900/60 text-red-300 border border-red-700/60 px-2 py-0.5 rounded-full font-nastaliq">
                          مبہم گاہک
                        </span>
                      )}
                    </div>
                    <ConfidenceBadge confidence={d.confidence} />
                  </div>

                  {/* Ambiguous candidates selector */}
                  {isAmbiguous && cust.candidates.length > 0 && (
                    <div className="space-y-1.5 bg-gray-900/80 p-2.5 rounded-xl border border-yellow-700/40">
                      <p className="text-xs text-yellow-300 font-nastaliq">صحیح گاہک منتخب کریں:</p>
                      <div className="flex flex-wrap gap-2">
                        {cust.candidates.map((cid) => (
                          <button
                            key={cid}
                            type="button"
                            onClick={() => setSelectedCustomerMap((prev) => ({ ...prev, [d.draft_id]: cid }))}
                            className={`px-3 py-1 rounded-lg text-xs font-nastaliq transition-all ${
                              selectedCustomerMap[d.draft_id] === cid
                                ? 'bg-emerald-600 text-white font-semibold'
                                : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                            }`}
                          >
                            {cid}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Validation Issues list */}
                  {d.validation.blocking.length > 0 && (
                    <div className="space-y-1">
                      {d.validation.blocking.map((iss, i) => (
                        <div key={i} className="text-xs bg-red-950/60 border border-red-900 text-red-300 px-2 py-1 rounded-md">
                          <span className="font-mono font-bold ltr-nums">{iss.rule}</span>: {iss.message}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Items summary */}
                  <div className="text-xs text-gray-400 border-t border-gray-800 pt-2 flex justify-between items-center">
                    <span>{d.items.length} آئٹمز</span>
                    <span className="ltr-nums font-bold text-emerald-400 text-base">₨{d.computed_total}</span>
                  </div>

                  {/* Action buttons */}
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => onDiscardDraft(d.draft_id)}
                      className="py-1.5 rounded-lg bg-gray-800 hover:bg-red-900/50 text-red-400 text-xs font-nastaliq border border-gray-700"
                    >
                      مسترد کریں
                    </button>
                    <button
                      type="button"
                      onClick={() => onResolveAndCommit(d, selectedCustomerMap[d.draft_id])}
                      className="py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-nastaliq font-semibold shadow"
                    >
                      تصدیق و اندراج
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

