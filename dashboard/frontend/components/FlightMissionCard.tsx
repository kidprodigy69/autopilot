"use client";

import React, { useRef, useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Plane, Clock, AlertCircle, ArrowLeftRight, Sunrise, Sunset, Ban } from "lucide-react";
import { cn } from "@/lib/utils";
import { format, parseISO } from "date-fns";

type FlightSlot = {
  available: boolean;
  price_total: number | null;
  price_per_person: number | null;
  depart_time: string | null;
  flight_number: string | null;
  airline: string | null;
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
  morning: FlightSlot | null;
  afternoon: FlightSlot | null;
  signal: Signal | null;
  loading?: boolean;
};

const SIGNAL_CONFIG = {
  BUY:  { gradient: "from-emerald-600 to-green-500",  text: "text-emerald-400", bg: "bg-emerald-500/20", border: "border-emerald-500/30", glow: "rgba(16,185,129,0.4)" },
  HOLD: { gradient: "from-amber-600 to-yellow-500",   text: "text-amber-400",   bg: "bg-amber-500/20",   border: "border-amber-500/30",   glow: "rgba(245,158,11,0.4)" },
  WAIT: { gradient: "from-sky-600 to-blue-500",       text: "text-sky-400",     bg: "bg-sky-500/20",     border: "border-sky-500/30",     glow: "rgba(14,165,233,0.4)" },
};

function SlotRow({
  icon,
  label,
  slot,
  passengers,
  highlight,
}: {
  icon: React.ReactNode;
  label: string;
  slot: FlightSlot | null;
  passengers: number;
  highlight?: boolean;
}) {
  if (!slot || !slot.available) {
    return (
      <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-900/40 border border-slate-800/60">
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm text-slate-500">{label}</span>
        </div>
        <div className="flex items-center gap-1.5 text-slate-600 text-xs">
          <Ban size={12} />
          No nonstop AA flight
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      "flex items-center justify-between px-4 py-3 rounded-xl border transition-colors",
      highlight
        ? "bg-emerald-500/8 border-emerald-500/25"
        : "bg-slate-800/50 border-slate-700/50"
    )}>
      <div className="flex items-center gap-3">
        {icon}
        <div>
          <p className="text-xs text-slate-400">{label}</p>
          <p className="text-white font-semibold text-sm">{slot.depart_time}</p>
          {slot.flight_number && (
            <p className="text-xs text-slate-600 font-mono">{slot.flight_number}</p>
          )}
        </div>
      </div>
      <div className="text-right">
        <p className="text-xl font-black text-white tabular-nums">
          ${slot.price_per_person?.toFixed(0)}
        </p>
        <p className="text-xs text-slate-500">per person</p>
        <p className="text-xs text-slate-600">${slot.price_total?.toFixed(0)} total</p>
      </div>
    </div>
  );
}

export default function FlightMissionCard({ trip, morning, afternoon, signal, loading }: Props) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [time, setTime] = useState(0);

  const action = signal?.action ?? "WAIT";
  const cfg = SIGNAL_CONFIG[action];
  const confidence = signal ? Math.round(signal.confidence * 100) : 0;
  const daysAway = signal?.days_to_depart ?? 0;

  // Highlight the cheaper slot
  const morningPPP = morning?.price_per_person ?? null;
  const afternoonPPP = afternoon?.price_per_person ?? null;
  const morningCheaper = morningPPP !== null && (afternoonPPP === null || morningPPP <= afternoonPPP);

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

  if (loading) return <div className="rounded-2xl bg-slate-800/50 border border-slate-700/50 h-80 animate-pulse" />;

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
                opacity: isHovered ? 0.6 : 0.2,
                transition: "opacity 0.5s ease-out",
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
                  <span className="text-xs text-slate-500">
                    {confidence < 40 ? "Low" : confidence < 70 ? "Med" : "High"}
                  </span>
                </div>
              </motion.div>
            </div>

            {/* Morning + Afternoon slots */}
            <div className="space-y-2">
              <SlotRow
                icon={<Sunrise size={15} className="text-amber-400 flex-shrink-0" />}
                label="Morning departure"
                slot={morning}
                passengers={trip.passengers}
                highlight={morningCheaper && !!morningPPP}
              />
              <SlotRow
                icon={<Sunset size={15} className="text-orange-400 flex-shrink-0" />}
                label="Afternoon departure"
                slot={afternoon}
                passengers={trip.passengers}
                highlight={!morningCheaper && !!afternoonPPP}
              />
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50">
                <div className="text-xs text-slate-400 mb-1">Signal Strength</div>
                <div className="flex items-baseline gap-1">
                  <span className={cn("text-xl font-bold", cfg.text)}>
                    {confidence < 40 ? "Low" : confidence < 70 ? "Med" : "High"}
                  </span>
                  <span className="text-xs text-slate-600">{confidence}%</span>
                </div>
                <div className="mt-1.5 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }} animate={{ width: `${confidence}%` }}
                    transition={{ duration: 1, ease: "easeOut" }}
                    className={cn("h-full rounded-full bg-gradient-to-r", cfg.gradient)}
                  />
                </div>
                <p className="text-xs text-slate-600 mt-1">
                  {confidence < 40 ? "Building history" : confidence < 70 ? "Moderate data" : "Strong signal"}
                </p>
              </div>
              <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50">
                <div className="text-xs text-slate-400 mb-1">Days Away</div>
                <div className="flex items-center gap-1.5">
                  <Clock size={14} className="text-cyan-400" />
                  <span className="text-xl font-bold text-white">{daysAway}</span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  {daysAway < 14 ? "Book now!" : daysAway < 45 ? "Sweet spot" : "Watch & wait"}
                </p>
              </div>
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
