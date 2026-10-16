/**
 * Fixture list subcomponent for offline demo and testing against fixtures.
 */

import { ALL_FIXTURES } from '../fixtures';
import type { ParsedDraft } from '../types';

interface FixtureListProps {
  onSelectFixture: (fixture: ParsedDraft) => void;
}

export function FixtureList({ onSelectFixture }: FixtureListProps) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-400 font-nastaliq">Phase 1 ٹیسٹ فکسچرز (ٹیسٹ کے لیے منتخب کریں):</p>
      {ALL_FIXTURES.map((f) => (
        <button
          key={f.draft_id}
          type="button"
          onClick={() => onSelectFixture(f)}
          className="w-full text-right p-3 rounded-xl bg-gray-900 border border-gray-800 hover:border-emerald-600 transition-all text-xs"
        >
          <div className="flex justify-between font-nastaliq text-sm text-white">
            <span>{f.customer.raw_name || 'نقد'} ({f.order_form})</span>
            <span className="ltr-nums text-emerald-400 font-bold">₨{f.computed_total}</span>
          </div>
          <div className="text-[11px] text-gray-500 font-mono ltr-nums mt-1">
            {f.draft_id} • {f.items.length} آئٹمز • {Math.round(f.confidence * 100)}%
          </div>
        </button>
      ))}
    </div>
  );
}

