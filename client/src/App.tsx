import { useBolKhata } from './useBolKhata';
import { PttButton } from './capture/pttButton';
import { DraftView } from './draft/DraftView';
import { UndoBar } from './confirm/UndoBar';
import { ReviewTray } from './confirm/ReviewTray';
import { LedgerView } from './ledger/LedgerView';
import { OfflineManualEntryModal } from './ledger/OfflineManualEntryModal';
import { IS_DEMO_FIXTURES } from './queue/api';

export function App() {
  const {
    shopId,
    deviceId,
    events,
    heldDrafts,
    draftState,
    undoDraft,
    queueStats,
    isTrayOpen,
    degradedJob,
    setIsTrayOpen,
    handleAudioCaptured,
    handleDiscardDraft,
    handleCommitDraftNow,
    handleUndo,
    handleExpireUndo,
    handleCommitHeldDraft,
    handleRejectHeldDraft,
    handleManualOfflineCommit,
    dismissDegradedJob,
    refreshEvents,
  } = useBolKhata();

  return (
    <div className="min-h-screen bg-gray-950 text-white font-sans flex flex-col justify-between selection:bg-emerald-500 selection:text-black">
      {/* Persistent Demo Data Warning Banner (gated behind VITE_USE_FIXTURES) */}
      {IS_DEMO_FIXTURES && (
        <div className="w-full bg-amber-500 text-black font-mono font-bold text-center py-1.5 px-4 text-xs tracking-wider uppercase sticky top-0 z-50 shadow-md">
          DEMO DATA -- NOT LIVE
        </div>
      )}

      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-40 bg-gray-900/90 backdrop-blur border-b border-gray-800 px-4 py-3 max-w-2xl mx-auto w-full flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center font-nastaliq font-bold text-white shadow-lg shadow-emerald-700/50">
            کھ
          </div>
          <div>
            <h1 className="font-nastaliq text-xl font-bold text-emerald-400 leading-tight">
              بول کھاتا
            </h1>
            <span className="text-[10px] text-gray-500 font-mono ltr-nums block">
              {shopId} • {deviceId}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Queue in-flight indicator */}
          {(queueStats.inFlight > 0 || queueStats.queued > 0) && (
            <div className="flex items-center gap-1.5 bg-blue-950/80 border border-blue-700 text-blue-300 text-xs px-2.5 py-1 rounded-full animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
              <span className="font-nastaliq text-[11px]">پراسیسنگ:</span>
              <span className="ltr-nums font-mono font-bold">
                {queueStats.inFlight}/{queueStats.queued}
              </span>
            </div>
          )}

          {/* Review tray button with badge */}
          <button
            type="button"
            onClick={() => setIsTrayOpen(true)}
            className="relative p-2 rounded-xl bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-200 transition-all active:scale-95 flex items-center gap-1.5"
            title="نظرثانی ٹرے"
          >
            <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <span className="font-nastaliq text-xs hidden sm:inline">نظرثانی</span>
            {heldDrafts.length > 0 && (
              <span className="absolute -top-1.5 -right-1.5 bg-amber-500 text-black text-[11px] font-bold px-1.5 py-0.2 rounded-full shadow ltr-nums">
                {heldDrafts.length}
              </span>
            )}
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-2xl mx-auto w-full p-4 space-y-4 pb-36">
        {/* Active Draft Basket (if any) */}
        {draftState.draft && (
          <DraftView
            draft={draftState.draft}
            secondsRemaining={draftState.secondsRemaining}
            onDiscard={handleDiscardDraft}
            onCommitNow={handleCommitDraftNow}
          />
        )}

        {/* Ledger & Customer Balances */}
        <LedgerView
          events={events}
          shopId={shopId}
          deviceId={deviceId}
          onRefresh={refreshEvents}
        />
      </main>

      {/* 3-Second Undo Bar for Auto-Commit */}
      {undoDraft && (
        <UndoBar
          draft={undoDraft}
          onUndo={handleUndo}
          onExpire={handleExpireUndo}
        />
      )}

      {/* Fixed Bottom Push-to-Talk Bar */}
      <footer className="fixed bottom-0 left-0 right-0 z-30 bg-gradient-to-t from-gray-950 via-gray-950/95 to-transparent pt-4 pb-6 px-4">
        <div className="max-w-2xl mx-auto flex justify-center">
          <PttButton onAudioCaptured={handleAudioCaptured} />
        </div>
      </footer>

      {/* Review Tray Modal */}
      <ReviewTray
        heldDrafts={heldDrafts}
        isOpen={isTrayOpen}
        onClose={() => setIsTrayOpen(false)}
        onCommitDraft={handleCommitHeldDraft}
        onRejectDraft={handleRejectHeldDraft}
      />

      {/* Degraded Offline Manual Entry Modal */}
      {degradedJob && (
        <OfflineManualEntryModal
          job={degradedJob}
          onCommit={handleManualOfflineCommit}
          onDismiss={dismissDegradedJob}
        />
      )}
    </div>
  );
}
export default App;
