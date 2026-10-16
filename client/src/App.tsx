/**
 * Main Bol Khata application shell — Phase 7 full client implementation.
 * AGENTS.md rules strictly followed:
 * - Push-to-talk only, no always-on listening.
 * - Money is int PKR always.
 * - Dexie only for persistence, no localStorage.
 * - Append-only ledger, 3-second undo on every auto-commit.
 * - Every component strictly under 200 lines.
 */

import { useState, useEffect, useCallback } from 'react';
import { db } from './db';
import { generateULID } from './lib/ulid';
import { useWakeLock } from './capture/useWakeLock';
import { useAudioRecorder } from './capture/useAudioRecorder';
import { PushToTalkButton } from './capture/PushToTalkButton';
import { enqueueJob, subscribeToJobSuccess, triggerQueueDrain } from './queue/jobQueue';
import { draftManager, type DraftState } from './draft/draftManager';
import { DraftBasket } from './draft/DraftBasket';
import { ReviewTray } from './confirm/ReviewTray';
import { UndoNotification } from './confirm/UndoNotification';
import { DaySummary } from './ledger/DaySummary';
import { CustomerList } from './ledger/CustomerList';
import { RecentEvents } from './ledger/RecentEvents';
import {
  commitDraftToLedger,
  recordPayment,
  undoEvent,
  computeBalancesFromEvents,
  computeDaySummary,
} from './ledger/ledgerService';
import { chimePlayer } from './tts/chimes';
import { readbackService } from './tts/readback';
import { Header } from './components/Header';
import { NavigationTabs, type ActiveTab } from './components/NavigationTabs';
import { FixtureList } from './components/FixtureList';
import type { LedgerEvent, ParsedDraft } from './types';

export function App() {
  useWakeLock(true);
  const { isRecording, audioLevel, error: recordError, startRecording, stopRecording } = useAudioRecorder();

  const [activeTab, setActiveTab] = useState<ActiveTab>('counter');
  const [draftState, setDraftState] = useState<DraftState>({ draft: null, secondsRemaining: 0 });
  const [heldReviewDrafts, setHeldReviewDrafts] = useState<ParsedDraft[]>([]);
  const [isReviewOpen, setIsReviewOpen] = useState(false);
  const [recentCommittedEvent, setRecentCommittedEvent] = useState<LedgerEvent | null>(null);
  const [events, setEvents] = useState<LedgerEvent[]>([]);

  const refreshEvents = useCallback(async () => {
    setEvents(await db.events.toArray());
  }, []);

  useEffect(() => {
    refreshEvents();
    triggerQueueDrain();

    const unsubDraft = draftManager.subscribe(setDraftState);
    const unsubQueue = subscribeToJobSuccess((draft) => {
      if (draft.confidence < 0.6 || !draft.validation.passed) {
        setHeldReviewDrafts((p) => [...p, draft]);
        chimePlayer.play('review');
      } else {
        draftManager.handleIncomingDraft(draft);
      }
    });

    draftManager.setAutoCommitHandler(async (draft) => {
      if (draft.validation.passed && draft.confidence >= 0.85) {
        const ev = await commitDraftToLedger(draft, 'voice');
        setRecentCommittedEvent(ev);
        await refreshEvents();
        readbackService.announceDraft(draft, true);
      } else {
        setHeldReviewDrafts((p) => [...p, draft]);
        chimePlayer.play('review');
      }
    });

    return () => {
      unsubDraft();
      unsubQueue();
    };
  }, [refreshEvents]);

  const handleRecordStop = async () => {
    const res = await stopRecording();
    if (!res) return chimePlayer.play('error');

    await enqueueJob({
      job_id: generateULID(),
      shop_id: 'demo_shop_01',
      draft_id: draftManager.getDraftId(),
      audio_blob: res.blob,
      duration_ms: res.duration_ms,
      peak_rms: res.peak_rms,
      clip_ratio: res.clip_ratio,
      codec: res.codec,
    });
  };

  const handleManualCommit = async () => {
    const draft = draftManager.commitNow();
    if (draft) {
      setRecentCommittedEvent(await commitDraftToLedger(draft, 'voice'));
      await refreshEvents();
      readbackService.announceDraft(draft, true);
    }
  };

  const balances = Object.values(computeBalancesFromEvents(events));
  const daySummary = computeDaySummary(events);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 py-4 px-4 max-w-lg mx-auto pb-24 font-sans select-none">
      <Header reviewCount={heldReviewDrafts.length} onOpenReview={() => setIsReviewOpen(true)} />
      <NavigationTabs activeTab={activeTab} onTabChange={setActiveTab} />

      {recordError && (
        <div className="mb-3 p-2.5 rounded-xl bg-red-950 border border-red-800 text-red-300 text-xs text-center font-nastaliq">
          {recordError}
        </div>
      )}

      {activeTab === 'counter' && (
        <main className="space-y-4">
          {draftState.draft ? (
            <DraftBasket
              draft={draftState.draft}
              secondsRemaining={draftState.secondsRemaining}
              onDiscard={() => draftManager.discard()}
              onCommit={handleManualCommit}
            />
          ) : (
            <PushToTalkButton
              isRecording={isRecording}
              audioLevel={audioLevel}
              onStart={startRecording}
              onStop={handleRecordStop}
            />
          )}
          <DaySummary summary={daySummary} />
        </main>
      )}

      {activeTab === 'customers' && (
        <CustomerList
          balances={balances}
          onRecordPayment={async (cid, amt) => {
            await recordPayment(cid, amt);
            await refreshEvents();
            chimePlayer.play('success');
          }}
        />
      )}

      {activeTab === 'history' && <RecentEvents events={events} />}
      {activeTab === 'fixtures' && (
        <FixtureList onSelectFixture={(f) => draftManager.handleIncomingDraft(f)} />
      )}

      {recentCommittedEvent && (
        <UndoNotification
          event={recentCommittedEvent}
          onUndo={async (ev) => {
            await undoEvent(ev);
            setRecentCommittedEvent(null);
            await refreshEvents();
            chimePlayer.play('review');
          }}
          onDismiss={() => setRecentCommittedEvent(null)}
        />
      )}

      <ReviewTray
        isOpen={isReviewOpen}
        drafts={heldReviewDrafts}
        onClose={() => setIsReviewOpen(false)}
        onDiscardDraft={(id) => setHeldReviewDrafts((p) => p.filter((d) => d.draft_id !== id))}
        onResolveAndCommit={async (draft, resolvedCid) => {
          if (resolvedCid) {
            draft.customer.customer_id = resolvedCid;
            draft.customer.status = 'resolved';
          }
          await commitDraftToLedger(draft, 'manual');
          setHeldReviewDrafts((p) => p.filter((d) => d.draft_id !== draft.draft_id));
          await refreshEvents();
          chimePlayer.play('success');
        }}
      />
    </div>
  );
}
