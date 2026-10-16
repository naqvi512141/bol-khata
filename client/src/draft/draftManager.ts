import { db } from '../db';
import type { ParsedDraft } from '../types';

export const DRAFT_WINDOW_MS = 20000;

export interface DraftState {
  draft: ParsedDraft | null;
  expiresAt: number | null;
  secondsRemaining: number;
}

export type DraftChangeCallback = (state: DraftState) => void;

export class DraftManager {
  private _draft: ParsedDraft | null = null;
  private _expiresAt: number | null = null;
  private _timerId: number | null = null;
  private _onDraftChange?: DraftChangeCallback;
  private _onWindowExpired?: (draft: ParsedDraft) => void;

  constructor(handlers?: {
    onDraftChange?: DraftChangeCallback;
    onWindowExpired?: (draft: ParsedDraft) => void;
  }) {
    this._onDraftChange = handlers?.onDraftChange;
    this._onWindowExpired = handlers?.onWindowExpired;
  }

  get activeDraft(): ParsedDraft | null {
    return this._draft;
  }

  get draftId(): string | null {
    return this._draft ? this._draft.draft_id : null;
  }

  updateWithUtterance(incomingDraft: ParsedDraft): void {
    if (!this._draft || this._draft.draft_id !== incomingDraft.draft_id) {
      // New draft opened
      this._draft = incomingDraft;
    } else {
      // Appended to existing open draft
      this._draft = incomingDraft;
    }

    this._expiresAt = Date.now() + DRAFT_WINDOW_MS;
    this._persist(this._draft);
    this._startTimer();
    this._notify();
  }

  discard(): void {
    if (this._draft) {
      db.drafts.delete(this._draft.draft_id).catch(() => {});
    }
    this._clear();
  }

  commitDone(): void {
    if (this._draft) {
      db.drafts.delete(this._draft.draft_id).catch(() => {});
    }
    this._clear();
  }

  private _clear(): void {
    if (this._timerId !== null) {
      clearInterval(this._timerId);
      this._timerId = null;
    }
    this._draft = null;
    this._expiresAt = null;
    this._notify();
  }

  private _startTimer(): void {
    if (this._timerId !== null) {
      clearInterval(this._timerId);
    }

    this._timerId = window.setInterval(() => {
      if (!this._expiresAt || !this._draft) {
        this._clear();
        return;
      }

      const diff = this._expiresAt - Date.now();
      if (diff <= 0) {
        const expiredDraft = this._draft;
        this._clear();
        this._onWindowExpired?.(expiredDraft);
      } else {
        this._notify();
      }
    }, 200);
  }

  private _notify(): void {
    const secondsRemaining = this._expiresAt
      ? Math.max(0, Math.ceil((this._expiresAt - Date.now()) / 1000))
      : 0;

    this._onDraftChange?.({
      draft: this._draft,
      expiresAt: this._expiresAt,
      secondsRemaining,
    });
  }

  private _persist(draft: ParsedDraft): void {
    db.drafts
      .put({
        draft_id: draft.draft_id,
        customer_id: draft.customer.customer_id,
        opened_at: new Date().toISOString(),
        data: draft,
      })
      .catch(() => {});
  }
}
