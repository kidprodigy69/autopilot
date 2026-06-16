"use client";

import { Radio, RefreshCw, AlertCircle, CheckCircle } from "lucide-react";
import { formatDistanceToNow, parseISO } from "date-fns";

type Status = {
  last_run: string | null;
  runs: number;
  errors: Array<{ ts: string; error: string }>;
  last_prices?: Record<string, number>;
};

type Props = {
  status: Status | null;
  onRefresh: () => void;
  refreshing: boolean;
};

export default function TrackerStatus({ status, onRefresh, refreshing }: Props) {
  const isHealthy = !status?.errors?.length || status.errors.length === 0;
  const lastError = status?.errors?.[status.errors.length - 1];

  return (
    <div className="rounded-2xl border border-sky-900/40 bg-[#0a1628] p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Radio size={15} className="text-sky-400" />
          <span className="text-sm font-semibold text-slate-300">Auto Tracker</span>
        </div>
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs hover:bg-sky-500/20 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
          Refresh Now
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg bg-slate-900/60 p-3 text-center">
          <p className="text-2xl font-black text-white tabular-nums">
            {status?.runs ?? 0}
          </p>
          <p className="text-xs text-slate-500 mt-0.5">Total Polls</p>
        </div>
        <div className="rounded-lg bg-slate-900/60 p-3 text-center">
          <div className="flex items-center justify-center gap-1.5">
            {isHealthy ? (
              <CheckCircle size={16} className="text-emerald-400" />
            ) : (
              <AlertCircle size={16} className="text-rose-400" />
            )}
            <p className="text-sm font-bold text-white">
              {isHealthy ? "Healthy" : "Error"}
            </p>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">System</p>
        </div>
        <div className="rounded-lg bg-slate-900/60 p-3 text-center">
          <p className="text-sm font-bold text-white">
            {status?.last_run
              ? formatDistanceToNow(parseISO(status.last_run), { addSuffix: true })
              : "Never"}
          </p>
          <p className="text-xs text-slate-500 mt-0.5">Last Poll</p>
        </div>
      </div>

      {lastError && (
        <div className="mt-3 rounded-lg bg-rose-950/30 border border-rose-900/30 px-3 py-2">
          <p className="text-xs text-rose-400 font-mono">
            {lastError.error}
          </p>
        </div>
      )}

      {/* Live pulse indicator */}
      <div className="flex items-center gap-2 mt-4">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-sky-500" />
        </span>
        <span className="text-xs text-slate-500">
          Polling every 6h · 240 of 250 free calls/month · Alerts to milesdailey19@gmail.com
        </span>
      </div>
    </div>
  );
}
