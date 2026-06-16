"use client";

import React, { useRef, useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Plane, TrendingUp, TrendingDown, Clock, AlertCircle, ArrowLeftRight, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { format, parseISO } from "date-fns";

type Signal = {
  trip_id: string;
  action: "BUY" | "HOLD" | "WAIT";
  confidence: number;
  reasoning: string;
  days_to_depart: number;
  trend: "RISING" | "FALLING" | "STABLE";
  current_price: number;
  predicted_low: number;
  predicted_high: number;
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
  currentPrice: number | null;
  prevPrice: number | null;
  signal: Signal | null;
  loading?: boolean;
};

const SIGNAL_CONFIG = {
  BUY: {
    gradient: "from-emerald-600 to-green-500",
    text: "text-emerald-400",
    bg: "bg-emerald-500/20",
    border: "border-emerald-500/30",
    glow: "rgba(16, 185, 129, 0.4)",
  },
  HOLD: {
    gradient: "from-amber-600 to-yellow-500",
    text: "text-amber-400",
    bg: "bg-amber-500/20",
    border: "border-amber-500/30",
    glow: "rgba(245, 158, 11, 0.4)",
  },
  WAIT: {
    gradient: "from-sky-600 to-blue-500",
    text: "text-sky-400",
    bg: "bg-sky-500/20",
    border: "border-sky-500/30",
    glow: "rgba(14, 165, 233, 0.4)",
  },
};

export default function FlightMissionCard({ trip, currentPrice, prevPrice, signal, loading }: Props) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [time, setTime] = useState(0);

  const action = signal?.action ?? "WAIT";
  const cfg = SIGNAL_CONFIG[action];
  const confidence = signal ? Math.round(signal.confidence * 100) : 0;
  const daysAway = signal?.days_to_depart ?? 0;

  const priceChange = currentPrice && prevPrice ? currentPrice - prevPrice : null;
  const priceChangePct = priceChange && prevPrice ? ((priceChange / prevPrice) * 100).toFixed(1) : null;
  const isPriceDown = priceChange !== null && priceChange < 0;

  const perPerson = currentPrice ? currentPrice / trip.passengers : null;

  const departFormatted = trip.depart_date
    ? format(parseISO(trip.depart_date), "MMM d")
    : "";
  const returnFormatted = trip.return_date
    ? format(parseISO(trip.return_date), "MMM d, yyyy")
    : "";

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => setMousePosition({ x: e.clientX, y: e.clientY });
    const tick = () => { setTime((p) => p + 0.01); requestAnimationFrame(tick); };
    window.addEventListener("mousemove", handleMouseMove);
    const id = requestAnimationFrame(tick);
    return () => { window.removeEventListener("mousemove", handleMouseMove); cancelAnimationFrame(id); };
  }, []);

  const getRotation = () => {
    if (!cardRef.current || !isHovered) return { x: 0, y: 0 };
    const rect = cardRef.current.getBoundingClientRect();
    return {
      x: -(((mousePosition.y - rect.top) / rect.height - 0.5) * 16),
      y: ((mousePosition.x - rect.left) / rect.width - 0.5) * 16,
    };
  };
  const rot = getRotation();

  if (loading) {
    return <div className="rounded-2xl bg-slate-800/50 border border-slate-700/50 h-80 animate-pulse" />;
  }

  return (
    <div
      ref={cardRef}
      style={{ perspective: "1500px" }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div
        className="relative w-full"
        style={{
          transform: isHovered
            ? `rotateX(${rot.x}deg) rotateY(${rot.y}deg) scale3d(1.02,1.02,1.02)`
            : "rotateX(0) rotateY(0) scale3d(1,1,1)",
          transition: isHovered ? "transform 0.1s ease-out" : "transform 0.5s ease-out",
          transformStyle: "preserve-3d",
        }}
      >
        <div className="relative rounded-2xl overflow-hidden shadow-2xl">
          <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900" />

          {/* Animated ambient glow */}
          <div
            className="absolute inset-0"
            style={{
              background: `
                radial-gradient(circle at ${50 + Math.sin(time * 0.5) * 30}% ${50 + Math.cos(time * 0.7) * 30}%, rgba(6,182,212,0.15) 0%, transparent 50%),
                radial-gradient(circle at ${50 + Math.cos(time * 0.3) * 40}% ${50 + Math.sin(time * 0.4) * 40}%, rgba(14,165,233,0.1) 0%, transparent 40%)
              `,
              opacity: 0.6,
            }}
          />

          {/* Stars */}
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            {[...Array(18)].map((_, i) => (
              <div
                key={i}
                className="absolute rounded-full bg-cyan-400/30"
                style={{
                  width: `${(i % 3) + 1}px`,
                  height: `${(i % 3) + 1}px`,
                  top: `${(i * 17 + 7) % 100}%`,
                  left: `${(i * 23 + 11) % 100}%`,
                  opacity: isHovered ? 0.6 : 0.25,
                  transition: "opacity 0.5s ease-out",
                  boxShadow: "0 0 4px 1px rgba(6,182,212,0.3)",
                }}
              />
            ))}
          </div>

          <div className="absolute inset-0 backdrop-blur-sm bg-slate-900/40 border border-slate-700/50" />

          <div className="relative p-6 space-y-4">
            {/* Route header — round trip indicator */}
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <ArrowLeftRight size={12} className="text-cyan-500" />
                  <span className="text-xs text-cyan-500 font-semibold uppercase tracking-wider">
                    Round Trip · {trip.duration_days} days
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-2xl font-bold text-white">{trip.origin}</span>
                  <div className="flex items-center gap-1">
                    <div className="w-6 h-px bg-gradient-to-r from-cyan-500 to-transparent" />
                    <Plane size={14} className="text-cyan-400 rotate-90" />
                    <div className="w-6 h-px bg-gradient-to-l from-cyan-500 to-transparent" />
                  </div>
                  <span className="text-2xl font-bold text-white">{trip.destination}</span>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  {departFormatted} → {returnFormatted}
                </p>
              </div>

              {/* Signal badge */}
              <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}>
                <div
                  className={cn(
                    "flex flex-col items-center px-3 py-2 rounded-xl border backdrop-blur-sm",
                    cfg.bg, cfg.border
                  )}
                  style={{ boxShadow: `0 0 16px ${cfg.glow}` }}
                >
                  <AlertCircle size={14} className={cfg.text} />
                  <span className={cn("text-sm font-black mt-0.5", cfg.text)}>{action}</span>
                </div>
              </motion.div>
            </div>

            {/* Price — round trip total */}
            <div className="space-y-1">
              {currentPrice ? (
                <>
                  <div className="flex items-baseline gap-3">
                    <span className="text-5xl font-bold text-white tabular-nums">
                      ${currentPrice.toFixed(0)}
                    </span>
                    {priceChange !== null && priceChangePct !== null && (
                      <div className={cn("flex items-center gap-1", isPriceDown ? "text-emerald-400" : "text-red-400")}>
                        {isPriceDown ? <TrendingDown size={16} /> : <TrendingUp size={16} />}
                        <span className="text-sm font-semibold">
                          {isPriceDown ? "" : "+"}${Math.abs(priceChange).toFixed(0)} ({priceChangePct}%)
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-500">
                    <span>round-trip total</span>
                    <span>·</span>
                    <Users size={11} className="text-slate-600" />
                    <span>${perPerson?.toFixed(0)} per person</span>
                    {prevPrice && <span>· prev ${prevPrice.toFixed(0)}</span>}
                  </div>
                </>
              ) : (
                <div className="h-14 w-48 rounded-lg bg-slate-800 animate-pulse" />
              )}
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50 backdrop-blur-sm">
                <div className="text-xs text-slate-400 mb-1">Confidence</div>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-bold text-cyan-400">{confidence}</span>
                  <span className="text-sm text-slate-400">%</span>
                </div>
                <div className="mt-2 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${confidence}%` }}
                    transition={{ duration: 1, ease: "easeOut" }}
                    className={cn("h-full rounded-full bg-gradient-to-r", cfg.gradient)}
                  />
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50 backdrop-blur-sm">
                <div className="text-xs text-slate-400 mb-1">Days Away</div>
                <div className="flex items-center gap-2">
                  <Clock size={16} className="text-cyan-400" />
                  <span className="text-2xl font-bold text-white">{daysAway}</span>
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  {daysAway < 14 ? "Book now!" : daysAway < 45 ? "Sweet spot" : "Watch & wait"}
                </div>
              </div>
            </div>

            {/* Auto reasoning */}
            {signal?.reasoning && (
              <div className="p-3 rounded-xl bg-slate-800/30 border border-slate-700/30 backdrop-blur-sm">
                <p className="text-xs text-slate-400 leading-relaxed">
                  <span className="text-cyan-400 font-semibold">Auto: </span>
                  {signal.reasoning}
                </p>
              </div>
            )}
          </div>

          {/* Holographic hover shine */}
          <div
            className="absolute inset-0 rounded-2xl pointer-events-none"
            style={{
              background: isHovered && cardRef.current
                ? `radial-gradient(circle at ${mousePosition.x - cardRef.current.getBoundingClientRect().left}px ${mousePosition.y - cardRef.current.getBoundingClientRect().top}px, rgba(6,182,212,0.12) 0%, transparent 60%)`
                : "",
              opacity: isHovered ? 1 : 0,
              transition: "opacity 0.3s ease-out",
            }}
          />
        </div>

        {/* Shadow */}
        <div
          className="absolute bottom-0 left-1/2 w-[90%] h-2.5 rounded-full bg-cyan-900/40 blur-xl"
          style={{
            transform: isHovered ? "translate(-50%, 15px) scale(0.95)" : "translate(-50%, 10px) scale(0.85)",
            opacity: isHovered ? 0.6 : 0.35,
            transition: "transform 0.5s ease-out, opacity 0.5s ease-out",
          }}
        />
      </div>
    </div>
  );
}
