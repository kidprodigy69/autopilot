"use client";

import { Plane, TrendingDown, TrendingUp, Minus, Clock, Users } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

type Signal = {
  action: "BUY" | "HOLD" | "WAIT";
  confidence: number;
  reasoning: string;
  days_to_depart: number;
  trend: "RISING" | "FALLING" | "STABLE";
};

type Mission = {
  id: string;
  label: string;
  origin: string;
  destination: string;
  depart_date: string;
  passengers: number;
  preferred_airlines: string[];
};

type Props = {
  mission: Mission;
  currentPrice: number | null;
  prevPrice: number | null;
  signal: Signal | null;
  loading?: boolean;
};

const ACTION_CONFIG = {
  BUY: {
    bg: "bg-emerald-500/20",
    border: "border-emerald-500/40",
    text: "text-emerald-400",
    ring: "shadow-[0_0_16px_rgba(52,211,153,0.25)]",
    pulse: true,
  },
  HOLD: {
    bg: "bg-amber-500/20",
    border: "border-amber-500/40",
    text: "text-amber-400",
    ring: "",
    pulse: false,
  },
  WAIT: {
    bg: "bg-sky-500/20",
    border: "border-sky-500/40",
    text: "text-sky-400",
    ring: "",
    pulse: false,
  },
};

function PriceDelta({ current, prev }: { current: number; prev: number }) {
  const diff = current - prev;
  const pct = ((diff / prev) * 100).toFixed(1);
  if (Math.abs(diff) < 0.5) return null;
  const isDown = diff < 0;
  return (
    <span
      className={`flex items-center gap-1 text-sm font-semibold ${
        isDown ? "text-emerald-400" : "text-rose-400"
      }`}
    >
      {isDown ? <TrendingDown size={14} /> : <TrendingUp size={14} />}
      {isDown ? "" : "+"}
      {pct}%
    </span>
  );
}

function TrendIcon({ trend }: { trend: Signal["trend"] }) {
  if (trend === "FALLING") return <TrendingDown size={14} className="text-emerald-400" />;
  if (trend === "RISING") return <TrendingUp size={14} className="text-rose-400" />;
  return <Minus size={14} className="text-slate-400" />;
}

export default function FlightMissionCard({ mission, currentPrice, prevPrice, signal, loading }: Props) {
  const action = signal?.action ?? "WAIT";
  const cfg = ACTION_CONFIG[action];

  return (
    <div className="relative rounded-2xl border border-sky-900/40 bg-[#0a1628] overflow-hidden glow-cyan">
      {/* Top accent bar */}
      <div
        className={`h-0.5 w-full ${
          action === "BUY"
            ? "bg-gradient-to-r from-emerald-500 to-teal-400"
            : action === "HOLD"
            ? "bg-gradient-to-r from-amber-500 to-yellow-400"
            : "bg-gradient-to-r from-sky-500 to-blue-400"
        }`}
      />

      <div className="p-5">
        {/* Header row */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-widest mb-1">
              {mission.label}
            </p>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-white tracking-tight">
                {mission.origin}
              </span>
              <Plane size={18} className="text-sky-400 rotate-45" />
              <span className="text-2xl font-bold text-white tracking-tight">
                {mission.destination}
              </span>
            </div>
            <p className="text-sm text-slate-400 mt-0.5">
              {new Date(mission.depart_date + "T12:00:00").toLocaleDateString("en-US", {
                weekday: "short",
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </p>
          </div>

          {/* Action badge */}
          <div
            className={`flex flex-col items-center gap-1 px-4 py-2 rounded-xl border ${cfg.bg} ${cfg.border} ${cfg.ring} ${
              cfg.pulse ? "animate-pulse-slow" : ""
            }`}
          >
            <span className={`text-lg font-black tracking-wider ${cfg.text}`}>
              {action}
            </span>
            {signal && (
              <span className="text-xs text-slate-400">
                {Math.round(signal.confidence * 100)}% conf.
              </span>
            )}
          </div>
        </div>

        {/* Price row */}
        <div className="flex items-end gap-3 mb-4">
          {loading ? (
            <div className="h-12 w-40 rounded-lg bg-slate-800 animate-pulse" />
          ) : currentPrice ? (
            <>
              <span className="text-4xl font-black text-white tabular-nums">
                ${currentPrice.toFixed(0)}
              </span>
              <div className="pb-1 flex flex-col gap-0.5">
                <span className="text-xs text-slate-500">total for {mission.passengers} pax</span>
                {prevPrice && <PriceDelta current={currentPrice} prev={prevPrice} />}
              </div>
            </>
          ) : (
            <span className="text-slate-500 text-lg">Fetching price...</span>
          )}
        </div>

        {/* Stats row */}
        <div className="flex items-center gap-4 mb-4 text-sm">
          <div className="flex items-center gap-1.5 text-slate-400">
            <Clock size={13} />
            <span>
              {signal?.days_to_depart != null
                ? `${signal.days_to_depart}d away`
                : "—"}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-400">
            <Users size={13} />
            <span>{mission.passengers} passengers</span>
          </div>
          {signal && (
            <div className="flex items-center gap-1.5 text-slate-400">
              <TrendIcon trend={signal.trend} />
              <span className="capitalize">{signal.trend.toLowerCase()}</span>
            </div>
          )}
          {mission.preferred_airlines.length > 0 && (
            <div className="flex gap-1">
              {mission.preferred_airlines.map((a) => (
                <span
                  key={a}
                  className="px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 text-xs font-mono"
                >
                  {a}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Reasoning */}
        {signal?.reasoning && (
          <div className="rounded-lg bg-slate-900/60 border border-slate-800 px-3 py-2">
            <p className="text-xs text-slate-400 leading-relaxed">
              <span className="text-sky-400 font-semibold">Auto: </span>
              {signal.reasoning}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
