"use client";

import React, { useRef, useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Plane, Clock, AlertCircle, ArrowLeftRight,
  Sunrise, Sunset, Ban, TrendingUp, TrendingDown, Minus,
  BarChart2, ExternalLink,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { format, parseISO } from "date-fns";

type FlightOption = {
  available: true;
  price_total: number;
  price_per_person: number;
  depart_time: string;
  arrive_time: string;
  flight_number: string;
  airline: string;
  return_flight_number: string | null;
  return_depart_time: string | null;
  return_arrive_time: string | null;
  booking_token: string | null;
};

type Signal = {
  trip_id: string;
  action: "BUY" | "HOLD" | "WAIT";
  confidence: number;
  reasoning: string;
  days_to_depart: number;
  trend: "RISING" | "FALLING" | "STABLE";
  best_price_per_person: number | null;
  predicted_low_per_person: number | null;
  typical_range_ppp: [number, number] | null;
  price_level: "low" | "typical" | "high" | null;
  aa_nonstop_count: number;
  data_points: number;
};

type Trip = {
  id: string;
  label: string;
  origin: string;
  destination: string;
  depart_date: string;
  return_date: string;
  duration_days: number;
  passengers: number;
  preferred_airlines: string[];
};

type Props = {
  trip: Trip;
  morning: FlightOption[];
  afternoon: FlightOption[];
  signal: Signal | null;
  loading?: boolean;
  aaBookingUrl?: string;
};

const SIGNAL_CONFIG = {
  BUY:  { gradient: "from-emerald-600 to-green-500",  text: "text-emerald-400", bg: "bg-emerald-500/20", border: "border-emerald-500/30", glow: "rgba(16,185,129,0.4)" },
  HOLD: { gradient: "from-amber-600 to-yellow-500",   text: "text-amber-400",   bg: "bg-amber-500/20",   border: "border-amber-500/30",   glow: "rgba(245,158,11,0.4)" },
  WAIT: { gradient: "from-sky-600 to-blue-500",       text: "text-sky-400",     bg: "bg-sky-500/20",     border: "border-sky-500/30",     glow: "rgba(14,165,233,0.4)" },
};

const LEVEL_CONFIG = {
  low:     { label: "LOW",     color: "text-emerald-400", bg: "bg-emerald-500/15", border: "border-emerald-500/30", icon: TrendingDown },
  typical: { label: "TYPICAL", color: "text-amber-400",   bg: "bg-amber-500/15",   border: "border-amber-500/30",   icon: Minus },
  high:    { label: "HIGH",    color: "text-red-400",     bg: "bg-red-500/15",     border: "border-red-500/30",     icon: TrendingUp },
};

function SlotSection({
  icon, label, flights, aaBookingUrl,
}: {
  icon: React.ReactNode;
  label: string;
  flights: FlightOption[];
  aaBookingUrl?: string;
}) {
  if (!flights.length) {
    return (
      <div className="rounded-xl bg-slate-900/40 border border-slate-800/60 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm text-slate-500">{label}</span>
        </div>
        <div className="flex items-center gap-1.5 text-slate-600 text-xs">
          <Ban size={12} />
          No nonstop AA
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-700/50 overflow-hidden">
      {/* Slot header */}
      <div className="flex items-center gap-2 px-4 py-2 bg-slate-800/70 border-b border-slate-700/50">
        {icon}
        <span className="text-xs font-semibold text-slate-400">{label}</span>
        <span className="text-xs text-slate-600 ml-auto">{flights.length} option{flights.length !== 1 ? "s" : ""}</span>
      </div>

      {/* Flight rows */}
      <div className="divide-y divide-slate-800/60">
        {flights.map((f, i) => (
          <div
            key={f.flight_number || i}
            className={cn(
              "flex items-center gap-3 px-4 py-2.5",
              i === 0 ? "bg-emerald-500/5" : "bg-slate-900/30"
            )}
          >
            {/* Cheapest badge */}
            <div className="w-5 flex-shrink-0">
              {i === 0 && flights.length > 1 && (
                <span className="text-emerald-400 text-xs">★</span>
              )}
            </div>

            {/* Flight number */}
            <div className="w-16 flex-shrink-0">
              <p className="text-xs font-mono font-bold text-white">{f.flight_number || "—"}</p>
              {f.return_flight_number && (
                <p className="text-xs font-mono text-slate-600">{f.return_flight_number}</p>
              )}
            </div>

            {/* Times */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-semibold text-white tabular-nums">{f.depart_time}</span>
                <span className="text-slate-600 text-xs">→</span>
                <span className="text-sm text-slate-300 tabular-nums">{f.arrive_time}</span>
                <span className="text-slate-600 text-xs ml-1">outbound</span>
              </div>
              {f.return_depart_time && (
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="text-xs text-slate-500 tabular-nums">{f.return_depart_time}</span>
                  <span className="text-slate-700 text-xs">→</span>
                  <span className="text-xs text-slate-500 tabular-nums">{f.return_arrive_time}</span>
                  <span className="text-slate-700 text-xs ml-1">return</span>
                </div>
              )}
            </div>

            {/* Price + Book button */}
            <div className="text-right flex-shrink-0 flex flex-col items-end gap-1">
              <p className={cn("text-sm font-black tabular-nums", i === 0 ? "text-white" : "text-slate-400")}>
                ${f.price_per_person.toFixed(0)}
                <span className="text-xs font-normal text-slate-500">/pp</span>
              </p>
              <p className="text-xs text-slate-600">${f.price_total.toFixed(0)} total</p>
              {aaBookingUrl && (
                <a
                  href={aaBookingUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={`Open Kayak showing nonstop AA flights — select ${f.flight_number}, then click "Book on American.com"`}
                  className="flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-emerald-900/40 border border-emerald-700/40 text-emerald-400 hover:bg-emerald-800/60 hover:text-white transition-colors font-semibold"
                >
                  Book <ExternalLink size={10} />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Categorical interpreters — each number gets a defined meaning ──────────

function trackRecord(dataPoints: number): { label: string; sub: string } {
  if (dataPoints < 3)  return { label: "New",      sub: `${dataPoints} check${dataPoints !== 1 ? "s" : ""} — no pattern yet` };
  if (dataPoints < 10) return { label: "Building",  sub: `${dataPoints} checks — early trends forming` };
  if (dataPoints < 20) return { label: "Pattern",   sub: `${dataPoints} checks — confident signal` };
  if (dataPoints < 40) return { label: "Reliable",  sub: `${dataPoints} checks — ~30 days of data` };
  return               { label: "Proven",    sub: `${dataPoints} checks — full track record` };
}

function bookingWindow(daysAway: number): { label: string; sub: string; color: string } {
  if (daysAway < 7)   return { label: "Last Chance",  sub: `${daysAway}d left — book immediately`,         color: "text-red-400" };
  if (daysAway < 21)  return { label: "Book Now",     sub: `${daysAway}d left — prices rising fast`,       color: "text-orange-400" };
  if (daysAway < 60)  return { label: "Sweet Spot",   sub: `${daysAway}d out — ideal booking window`,     color: "text-emerald-400" };
  if (daysAway < 120) return { label: "Early Window", sub: `${daysAway}d out — ok to book, may drop`,     color: "text-cyan-400" };
  return               { label: "Too Early",   sub: `${daysAway}d out — watch, don't book yet`,    color: "text-slate-400" };
}

function priceDirection(trend: string): { label: string; sub: string; color: string } {
  if (trend === "RISING")  return { label: "↑ Rising",  sub: "Prices going up — act sooner",     color: "text-red-400" };
  if (trend === "FALLING") return { label: "↓ Falling", sub: "Prices trending down — watch it",  color: "text-emerald-400" };
  return                          { label: "→ Flat",    sub: "Prices stable — no rush signal",    color: "text-slate-400" };
}

export default function FlightMissionCard({ trip, morning, afternoon, signal, loading, aaBookingUrl }: Props) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [time, setTime] = useState(0);

  const action = signal?.action ?? "WAIT";
  const cfg = SIGNAL_CONFIG[action];
  const confidence = signal ? signal.confidence : 0;
  const confidencePct = Math.round(confidence * 100);
  const daysAway = signal?.days_to_depart ?? 0;
  const dataPoints = signal?.data_points ?? 0;

  const morningPPP = morning[0]?.price_per_person ?? null;
  const afternoonPPP = afternoon[0]?.price_per_person ?? null;

  const levelCfg = signal?.price_level ? LEVEL_CONFIG[signal.price_level] : null;
  const LevelIcon = levelCfg?.icon ?? Minus;

  const trendIcon = signal?.trend === "RISING"
    ? <TrendingUp size={11} className="text-red-400" />
    : signal?.trend === "FALLING"
    ? <TrendingDown size={11} className="text-emerald-400" />
    : <Minus size={11} className="text-slate-500" />;

  useEffect(() => {
    const onMove = (e: MouseEvent) => setMousePos({ x: e.clientX, y: e.clientY });
    const tick = () => { setTime(p => p + 0.01); requestAnimationFrame(tick); };
    window.addEventListener("mousemove", onMove);
    const id = requestAnimationFrame(tick);
    return () => { window.removeEventListener("mousemove", onMove); cancelAnimationFrame(id); };
  }, []);

  const rot = (() => {
    if (!cardRef.current || !isHovered) return { x: 0, y: 0 };
    const r = cardRef.current.getBoundingClientRect();
    return {
      x: -(((mousePos.y - r.top) / r.height - 0.5) * 14),
      y: ((mousePos.x - r.left) / r.width - 0.5) * 14,
    };
  })();

  if (loading) return <div className="rounded-2xl bg-slate-800/50 border border-slate-700/50 h-96 animate-pulse" />;

  const departFmt = trip.depart_date ? format(parseISO(trip.depart_date), "MMM d") : "";
  const returnFmt = trip.return_date ? format(parseISO(trip.return_date), "MMM d, yyyy") : "";

  return (
    <div ref={cardRef} style={{ perspective: "1500px" }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="relative w-full" style={{
        transform: isHovered
          ? `rotateX(${rot.x}deg) rotateY(${rot.y}deg) scale3d(1.02,1.02,1.02)`
          : "rotateX(0) rotateY(0) scale3d(1,1,1)",
        transition: isHovered ? "transform 0.1s ease-out" : "transform 0.5s ease-out",
        transformStyle: "preserve-3d",
      }}>
        <div className="relative rounded-2xl overflow-hidden shadow-2xl">
          <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900" />
          <div className="absolute inset-0" style={{
            background: `
              radial-gradient(circle at ${50 + Math.sin(time * 0.5) * 30}% ${50 + Math.cos(time * 0.7) * 30}%, rgba(6,182,212,0.15) 0%, transparent 50%),
              radial-gradient(circle at ${50 + Math.cos(time * 0.3) * 40}% ${50 + Math.sin(time * 0.4) * 40}%, rgba(14,165,233,0.1) 0%, transparent 40%)
            `,
            opacity: 0.6,
          }} />
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            {[...Array(18)].map((_, i) => (
              <div key={i} className="absolute rounded-full bg-cyan-400/30" style={{
                width: `${(i % 3) + 1}px`, height: `${(i % 3) + 1}px`,
                top: `${(i * 17 + 7) % 100}%`, left: `${(i * 23 + 11) % 100}%`,
                opacity: isHovered ? 0.6 : 0.2, transition: "opacity 0.5s ease-out",
                boxShadow: "0 0 4px 1px rgba(6,182,212,0.3)",
              }} />
            ))}
          </div>
          <div className="absolute inset-0 backdrop-blur-sm bg-slate-900/40 border border-slate-700/50" />

          <div className="relative p-5 space-y-4">

            {/* Header */}
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <ArrowLeftRight size={11} className="text-cyan-500" />
                  <span className="text-xs text-cyan-500 font-semibold uppercase tracking-wider">
                    Nonstop · American · {trip.duration_days}d
                  </span>
                  {signal?.aa_nonstop_count !== undefined && (
                    <span className="text-xs text-slate-600">
                      ({signal.aa_nonstop_count} AA flight{signal.aa_nonstop_count !== 1 ? "s" : ""})
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-2xl font-bold text-white">{trip.origin}</span>
                  <div className="flex items-center gap-1">
                    <div className="w-5 h-px bg-gradient-to-r from-cyan-500 to-transparent" />
                    <Plane size={13} className="text-cyan-400 rotate-90" />
                    <div className="w-5 h-px bg-gradient-to-l from-cyan-500 to-transparent" />
                  </div>
                  <span className="text-2xl font-bold text-white">{trip.destination}</span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">{departFmt} → {returnFmt}</p>
              </div>

              <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}>
                <div className={cn("flex flex-col items-center px-3 py-2 rounded-xl border backdrop-blur-sm", cfg.bg, cfg.border)}
                  style={{ boxShadow: `0 0 16px ${cfg.glow}` }}>
                  <AlertCircle size={13} className={cfg.text} />
                  <span className={cn("text-sm font-black mt-0.5", cfg.text)}>{action}</span>
                  <span className={cn("text-xs", cfg.text, "opacity-70")}>
                    {trackRecord(dataPoints).label}
                  </span>
                </div>
              </motion.div>
            </div>

            {/* Google Price Intel bar */}
            {levelCfg && (
              <div className={cn("flex items-center justify-between px-3 py-2 rounded-xl border", levelCfg.bg, levelCfg.border)}>
                <div className="flex items-center gap-2">
                  <BarChart2 size={13} className={levelCfg.color} />
                  <span className="text-xs text-slate-400">Google rates this price:</span>
                  <span className={cn("text-xs font-bold", levelCfg.color)}>{levelCfg.label}</span>
                </div>
                {signal?.typical_range_ppp && (
                  <span className="text-xs text-slate-500">
                    Typical ${signal.typical_range_ppp[0].toFixed(0)}–${signal.typical_range_ppp[1].toFixed(0)}/person
                  </span>
                )}
              </div>
            )}

            {/* Morning + Afternoon slots */}
            <div className="space-y-2">
              <SlotSection
                icon={<Sunrise size={14} className="text-amber-400 flex-shrink-0" />}
                label="Morning departures (5am–noon)"
                flights={morning}
                aaBookingUrl={aaBookingUrl}
              />
              <SlotSection
                icon={<Sunset size={14} className="text-orange-400 flex-shrink-0" />}
                label="Afternoon departures (noon–6pm)"
                flights={afternoon}
                aaBookingUrl={aaBookingUrl}
              />
            </div>

            {/* Stats row — every number has a defined category */}
            <div className="grid grid-cols-3 gap-2">
              {/* Tile 1: Track Record — replaces opaque confidence % */}
              {(() => {
                const tr = trackRecord(dataPoints);
                return (
                  <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50">
                    <div className="text-xs text-slate-500 mb-1 uppercase tracking-wider">Track Record</div>
                    <span className={cn("text-sm font-bold", cfg.text)}>{tr.label}</span>
                    <p className="text-xs text-slate-600 mt-1 leading-snug">{tr.sub}</p>
                  </div>
                );
              })()}

              {/* Tile 2: Booking Window — replaces bare day count */}
              {(() => {
                const bw = bookingWindow(daysAway);
                return (
                  <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50">
                    <div className="text-xs text-slate-500 mb-1 uppercase tracking-wider">Book When</div>
                    <div className="flex items-center gap-1">
                      <Clock size={11} className="text-slate-500 flex-shrink-0" />
                      <span className={cn("text-sm font-bold leading-none", bw.color)}>{bw.label}</span>
                    </div>
                    <p className="text-xs text-slate-600 mt-1 leading-snug">{bw.sub}</p>
                  </div>
                );
              })()}

              {/* Tile 3: Price Direction — replaces bare RISING/FALLING/STABLE */}
              {(() => {
                const pd = priceDirection(signal?.trend ?? "STABLE");
                return (
                  <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50">
                    <div className="text-xs text-slate-500 mb-1 uppercase tracking-wider">Direction</div>
                    <span className={cn("text-sm font-bold", pd.color)}>{pd.label}</span>
                    <p className="text-xs text-slate-600 mt-1 leading-snug">{pd.sub}</p>
                  </div>
                );
              })()}
            </div>

            {/* Auto reasoning */}
            {signal?.reasoning && (
              <div className="px-3 py-2.5 rounded-xl bg-slate-800/30 border border-slate-700/30">
                <p className="text-xs text-slate-400 leading-relaxed">
                  <span className="text-cyan-400 font-semibold">Auto: </span>
                  {signal.reasoning}
                </p>
              </div>
            )}

            {/* Price source disclaimer */}
            <div className="flex items-center gap-1.5 pt-1">
              <ExternalLink size={10} className="text-slate-700 flex-shrink-0" />
              <p className="text-xs text-slate-700 leading-snug">
                Prices from Google Flights at last check — click <span className="text-slate-600 font-medium">Book</span> to open Kayak (nonstop AA only), pick your flight, then select &ldquo;Book on American.com&rdquo; for AA checkout.
              </p>
            </div>

          </div>

          {/* Holographic shine */}
          <div className="absolute inset-0 rounded-2xl pointer-events-none" style={{
            background: isHovered && cardRef.current
              ? `radial-gradient(circle at ${mousePos.x - cardRef.current.getBoundingClientRect().left}px ${mousePos.y - cardRef.current.getBoundingClientRect().top}px, rgba(6,182,212,0.12) 0%, transparent 60%)`
              : "",
            opacity: isHovered ? 1 : 0,
            transition: "opacity 0.3s ease-out",
          }} />
        </div>

        <div className="absolute bottom-0 left-1/2 w-[90%] h-2.5 rounded-full bg-cyan-900/40 blur-xl" style={{
          transform: isHovered ? "translate(-50%, 15px) scale(0.95)" : "translate(-50%, 10px) scale(0.85)",
          opacity: isHovered ? 0.6 : 0.35,
          transition: "transform 0.5s ease-out, opacity 0.5s ease-out",
        }} />
      </div>
    </div>
  );
}
