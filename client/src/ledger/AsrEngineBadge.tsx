export function AsrEngineBadge({ engine }: { engine?: string }) {
  const norm = (engine || '').toLowerCase();

  if (norm === 'groq') {
    return (
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-950 border border-emerald-600 text-emerald-300"
        title="Groq Cloud Whisper-large-v3 (~660ms)"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        ⚡ Groq (~660ms)
      </span>
    );
  }

  if (norm === 'local') {
    return (
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-amber-950 border border-amber-600 text-amber-300"
        title="Local faster-whisper small int8 (10-14s)"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
        🐢 Local (10-14s)
      </span>
    );
  }

  if (norm === 'manual') {
    return (
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-blue-950 border border-blue-600 text-blue-300"
        title="دستی اندراج (Manual entry)"
      >
        ✍️ Manual
      </span>
    );
  }

  if (norm === 'demo_fixture') {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-purple-950 border border-purple-600 text-purple-300">
        Demo Fixture
      </span>
    );
  }

  return (
    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-gray-800 text-gray-300">
      {norm || 'unknown'}
    </span>
  );
}
