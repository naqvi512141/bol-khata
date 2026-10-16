import type { ParsedDraft } from '../types';

export type ConfidenceBand = 'high' | 'medium' | 'low';

export interface EvaluatedBand {
  band: ConfidenceBand;
  autoCommit: boolean;
  hasWarnings: boolean;
  hasBlocking: boolean;
  ruleIds: Set<string>;
}

export function evaluateConfidenceBand(draft: ParsedDraft): EvaluatedBand {
  const hasBlocking = draft.validation.blocking.length > 0;
  const hasWarnings = draft.validation.warnings.length > 0;
  const ruleIds = new Set<string>();

  for (const b of draft.validation.blocking) ruleIds.add(b.rule);
  for (const w of draft.validation.warnings) ruleIds.add(w.rule);

  // docs/02-contracts.md section 5:
  // >= 0.85 and no blocking: Chime, auto-commit, 3 s undo window
  // 0.60 - 0.85 and no blocking: Committed but flagged; only V3/V4 fields highlighted
  // < 0.60, or any blocking issue: Held in the review tray, no auto-commit
  if (!hasBlocking && draft.confidence >= 0.85) {
    return {
      band: 'high',
      autoCommit: true,
      hasWarnings,
      hasBlocking: false,
      ruleIds,
    };
  }

  if (!hasBlocking && draft.confidence >= 0.6) {
    return {
      band: 'medium',
      autoCommit: true,
      hasWarnings: true,
      hasBlocking: false,
      ruleIds,
    };
  }

  return {
    band: 'low',
    autoCommit: false,
    hasWarnings,
    hasBlocking: true,
    ruleIds,
  };
}
