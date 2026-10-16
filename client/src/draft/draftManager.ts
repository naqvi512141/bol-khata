/**
 * Draft basket manager with 20s append window and timer reset.
 * AGENTS.md rule: 20s draft window, utterances append, large discard control.
 */

import type { ParsedDraft, LineItem } from '../types';

export const DRAFT_WINDOW_MS = 20000;

export interface DraftState {
  draft: ParsedDraft | null;
  secondsRemaining: number;
}

export type DraftListener = (state: DraftState) => void;

class DraftManager {
  private currentDraft: ParsedDraft | null = null;
  private timerId: ReturnType<typeof setTimeout> | null = null;
  private intervalId: ReturnType<typeof setInterval> | null = null;
  private expiresAt: number = 0;
  private listeners = new Set<DraftListener>();
  private onAutoCommitCallback: ((draft: ParsedDraft) => void) | null = null;

  public setAutoCommitHandler(handler: (draft: ParsedDraft) => void): void {
    this.onAutoCommitCallback = handler;
  }

  public subscribe(listener: DraftListener): () => void {
    this.listeners.add(listener);
    listener(this.getState());
    return () => this.listeners.delete(listener);
  }

  public getCurrentDraft(): ParsedDraft | null {
    return this.currentDraft;
  }

  public getDraftId(): string | null {
    return this.currentDraft ? this.currentDraft.draft_id : null;
  }

  public handleIncomingDraft(incoming: ParsedDraft): void {
    if (!this.currentDraft) {
      // First utterance starts new draft basket
      this.currentDraft = incoming;
      this.resetTimer();
      return;
    }

    // Merge incoming utterance items into open draft
    const mergedItems: LineItem[] = [...this.currentDraft.items, ...incoming.items];
    const computedTotal = mergedItems.reduce(
      (sum, item) => sum + (item.line_total != null ? Math.round(item.line_total) : 0),
      0
    );

    // Prefer resolved customer over absent/provisional
    let resolvedCustomer = this.currentDraft.customer;
    if (incoming.customer.status === 'resolved' || resolvedCustomer.status === 'absent') {
      resolvedCustomer = incoming.customer;
    }

    const mergedDraft: ParsedDraft = {
      ...this.currentDraft,
      job_ids: Array.from(new Set([...this.currentDraft.job_ids, ...incoming.job_ids])),
      customer: resolvedCustomer,
      items: mergedItems,
      computed_total: computedTotal,
      confidence: Math.min(this.currentDraft.confidence, incoming.confidence),
      validation: incoming.validation,
      order_form: incoming.order_form,
    };

    this.currentDraft = mergedDraft;
    this.resetTimer();
  }

  public discard(): void {
    this.clearTimer();
    this.currentDraft = null;
    this.notify();
  }

  public commitNow(): ParsedDraft | null {
    const draft = this.currentDraft;
    this.clearTimer();
    this.currentDraft = null;
    this.notify();
    return draft;
  }

  private resetTimer(): void {
    this.clearTimer();
    this.expiresAt = Date.now() + DRAFT_WINDOW_MS;

    this.intervalId = setInterval(() => {
      this.notify();
    }, 500);

    this.timerId = setTimeout(() => {
      this.handleTimeout();
    }, DRAFT_WINDOW_MS);

    this.notify();
  }

  private handleTimeout(): void {
    const draft = this.currentDraft;
    this.clearTimer();
    this.currentDraft = null;
    this.notify();

    if (draft && this.onAutoCommitCallback) {
      this.onAutoCommitCallback(draft);
    }
  }

  private clearTimer(): void {
    if (this.timerId) clearTimeout(this.timerId);
    if (this.intervalId) clearInterval(this.intervalId);
    this.timerId = null;
    this.intervalId = null;
    this.expiresAt = 0;
  }

  private getState(): DraftState {
    const remaining = Math.max(0, Math.ceil((this.expiresAt - Date.now()) / 1000));
    return {
      draft: this.currentDraft,
      secondsRemaining: this.expiresAt > 0 ? remaining : 0,
    };
  }

  private notify(): void {
    const state = this.getState();
    for (const listener of this.listeners) {
      listener(state);
    }
  }
}

export const draftManager = new DraftManager();

