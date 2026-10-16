/**
 * App top header with Urdu title and Review Tray badge counter.
 * Docs: docs/03-build-plan.md Phase 7.
 */


interface HeaderProps {
  reviewCount: number;
  onOpenReview: () => void;
}

export function Header({ reviewCount, onOpenReview }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-gray-800 pb-3 mb-4">
      <div>
        <h1 className="font-nastaliq text-2xl text-emerald-400 font-bold tracking-wide">بول کھاتا</h1>
        <p className="text-[11px] text-gray-500 font-nastaliq">دکانداروں کے لیے بول کر کھاتہ چلانے کا نظام</p>
      </div>

      <div className="flex items-center gap-2">
        {reviewCount > 0 && (
          <button
            type="button"
            onClick={onOpenReview}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-yellow-950/80 border border-yellow-700/80 text-yellow-300 hover:bg-yellow-900 transition-all animate-bounce"
            aria-label="جائزہ ٹرے"
          >
            <span className="w-2 h-2 rounded-full bg-yellow-400" />
            <span className="font-nastaliq text-xs font-semibold">جائزہ ٹرے</span>
            <span className="bg-yellow-800 text-yellow-200 text-[10px] px-1.5 py-0.2 rounded-full font-mono ltr-nums">
              {reviewCount}
            </span>
          </button>
        )}
      </div>
    </header>
  );
}

