/**
 * App — Phase 1 list view of fixtures.
 * Renders all 8 ParsedDraft fixtures with no server running.
 */

import { ALL_FIXTURES } from './fixtures';
import type { ParsedDraft, LineItem } from './types';

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  let color = 'bg-red-600';
  let label = 'کم';
  if (confidence >= 0.85) {
    color = 'bg-emerald-600';
    label = 'اعلی';
  } else if (confidence >= 0.60) {
    color = 'bg-amber-500';
    label = 'درمیانی';
  }
  return (
    <span className={`${color} text-white text-xs px-2 py-0.5 rounded-full ltr-nums`}>
      {pct}% {label}
    </span>
  );
}

function StatusBadge({ passed }: { passed: boolean }) {
  return passed ? (
    <span className="bg-emerald-800 text-emerald-200 text-xs px-2 py-0.5 rounded-full">
      ✓ پاس
    </span>
  ) : (
    <span className="bg-red-800 text-red-200 text-xs px-2 py-0.5 rounded-full">
      ✗ بلاک
    </span>
  );
}

function ItemRow({ item }: { item: LineItem }) {
  return (
    <div className="flex items-center justify-between py-1 border-b border-gray-800 last:border-0">
      <div className="flex items-center gap-2">
        <span className="font-nastaliq text-sm">{item.display_name ?? item.raw_name}</span>
        {item.match_status !== 'resolved' && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-700 text-gray-300">
            {item.match_status}
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 ltr-nums text-sm text-gray-400">
        <span>{item.qty ?? '—'} {item.unit ?? ''}</span>
        <span className="text-gray-200 font-medium">
          {item.line_total != null ? `₨${item.line_total}` : '—'}
        </span>
        <span className="text-[10px] text-gray-500">{item.price_source}</span>
      </div>
    </div>
  );
}

function DraftCard({ draft }: { draft: ParsedDraft }) {
  const cust = draft.customer;
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="font-nastaliq text-lg">
            {cust.raw_name ?? 'نقد فروخت'}
          </h2>
          {cust.status !== 'resolved' && cust.status !== 'absent' && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-900 text-yellow-300">
              {cust.status}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <ConfidenceBadge confidence={draft.confidence} />
          <StatusBadge passed={draft.validation.passed} />
        </div>
      </div>

      {/* Meta row */}
      <div className="flex flex-wrap gap-2 text-xs text-gray-500">
        <span className="bg-gray-800 px-2 py-0.5 rounded">{draft.order_form}</span>
        <span className="bg-gray-800 px-2 py-0.5 rounded">{draft.payment_type}</span>
        <span className="bg-gray-800 px-2 py-0.5 rounded">{draft.path}</span>
        <span className="bg-gray-800 px-2 py-0.5 rounded ltr-nums">{draft.draft_id}</span>
      </div>

      {/* Items */}
      <div className="space-y-0">
        {draft.items.map((item, i) => (
          <ItemRow key={i} item={item} />
        ))}
        {draft.items.length === 0 && (
          <p className="text-gray-600 text-sm">کوئی آئٹم نہیں</p>
        )}
      </div>

      {/* Total */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-800">
        <span className="font-nastaliq text-sm text-gray-400">کل رقم</span>
        <span className="ltr-nums text-lg font-semibold text-emerald-400">
          ₨{draft.computed_total}
        </span>
      </div>

      {/* Validation issues */}
      {draft.validation.blocking.length > 0 && (
        <div className="space-y-1">
          {draft.validation.blocking.map((issue, i) => (
            <div key={i} className="text-xs bg-red-950 border border-red-800 rounded px-2 py-1 text-red-300">
              <span className="font-mono ltr-nums">{issue.rule}</span>: {issue.message}
            </div>
          ))}
        </div>
      )}
      {draft.validation.warnings.length > 0 && (
        <div className="space-y-1">
          {draft.validation.warnings.map((issue, i) => (
            <div key={i} className="text-xs bg-amber-950 border border-amber-800 rounded px-2 py-1 text-amber-300">
              <span className="font-mono ltr-nums">{issue.rule}</span>: {issue.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function App() {
  return (
    <div className="min-h-screen bg-gray-950 py-6 px-4 max-w-2xl mx-auto">
      <header className="mb-8 text-center">
        <h1 className="font-nastaliq text-3xl text-emerald-400 mb-1">بول کھاتا</h1>
        <p className="text-gray-500 text-sm">Phase 1 — Fixture Viewer</p>
      </header>
      <div className="space-y-4">
        {ALL_FIXTURES.map((draft) => (
          <DraftCard key={draft.draft_id} draft={draft} />
        ))}
      </div>
    </div>
  );
}
