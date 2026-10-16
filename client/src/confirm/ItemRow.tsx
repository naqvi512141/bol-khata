import type { LineItem, ValidationResult } from '../types';

interface ItemRowProps {
  item: LineItem;
  itemIndex: number;
  validation: ValidationResult;
  onUpdatePrice?: (index: number, price: number) => void;
}

export function ItemRow({
  item,
  itemIndex,
  validation,
  onUpdatePrice,
}: ItemRowProps) {
  const hasV3 = validation.warnings.some(
    (w) => w.rule === 'V3' && (w.item_index === itemIndex || w.item_index === null)
  );
  const hasV4 = validation.warnings.some(
    (w) => w.rule === 'V4' && (w.item_index === itemIndex || w.item_index === null)
  );
  const hasV7 = validation.blocking.some(
    (b) => b.rule === 'V7' && (b.item_index === itemIndex || b.item_index === null)
  );

  return (
    <div className="flex flex-col py-2 border-b border-gray-800 last:border-0 gap-1 text-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-nastaliq text-base text-gray-100">
            {item.display_name ?? item.raw_name}
          </span>
          {item.match_status !== 'resolved' && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
              {item.match_status}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Qty field with V4 warning highlight */}
          <span
            className={`ltr-nums px-1.5 py-0.5 rounded text-xs ${
              hasV4
                ? 'bg-amber-950 border border-amber-600 text-amber-200 font-bold'
                : 'text-gray-300'
            }`}
            title={hasV4 ? 'V4: مقدار معمول سے زیادہ ہے' : undefined}
          >
            {item.qty ?? 1} {item.unit ?? ''}
          </span>

          {/* Line total / price with V3 or V7 highlight */}
          {hasV7 ? (
            <div className="flex items-center gap-1">
              <input
                type="number"
                placeholder="قیمت درج کریں"
                className="w-24 px-2 py-0.5 text-xs bg-red-950 border border-red-500 rounded text-red-200 ltr-nums focus:outline-none focus:ring-1 focus:ring-red-400"
                onChange={(e) => {
                  const val = parseInt(e.target.value, 10);
                  if (!isNaN(val) && val > 0 && onUpdatePrice) {
                    onUpdatePrice(itemIndex, val);
                  }
                }}
              />
              <span className="text-[10px] text-red-400 font-nastaliq">قیمت غائب</span>
            </div>
          ) : (
            <span
              className={`ltr-nums font-semibold px-1.5 py-0.5 rounded ${
                hasV3
                  ? 'bg-amber-950 border border-amber-500 text-amber-300'
                  : 'text-emerald-400'
              }`}
              title={hasV3 ? 'V3: قیمت اوسط سے مختلف ہے' : undefined}
            >
              ₨{item.line_total ?? 0}
            </span>
          )}
        </div>
      </div>

      {(hasV3 || hasV4) && (
        <div className="flex gap-2 text-[10px] text-amber-400">
          {hasV3 && <span>⚠️ V3: قیمت معمول سے ہٹ کر ہے</span>}
          {hasV4 && <span>⚠️ V4: مقدار غیر معمولی ہے</span>}
        </div>
      )}
    </div>
  );
}
