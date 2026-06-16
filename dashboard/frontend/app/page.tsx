"use client";

import { useEffect, useState, useCallback } from "react";
import { PlaneTakeoff, Zap, RefreshCw } from "lucide-react";
import { formatDistanceToNow, parseISO } from "date-fns";
import FlightMissionCard from "@/components/FlightMissionCard";
import PriceChart from "@/components/PriceChart";

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

type AutopilotData = {
  updated_at: string | null;
  trips: Trip[];
  signals: Signal[];
  history: Record<string, { ts: string; price: number }[]>;
  best_offers: Record<string, { price_total: number }>;
};

const EMPTY: AutopilotData = {
  updated_at: null,
  trips: [],
  signals: [],
  history: {},
  best_offers: {},
};

export default function Dashboard() {
  const [data, setData] = useState<AutopilotData>(EMPTY);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`/data/autopilot.json?t=${Date.now()}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error("Failed to load autopilot data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const sigMap: Record<string, Signal> = {};
  for (const s of data.signals) sigMap[s.trip_id] = s;

  const getPrevPrice = (tripId: string): number | null => {
    const pts = data.history[tripId] ?? [];
    return pts.length >= 2 ? pts[pts.length - 2].price : null;
  };

  const activeTrips = data.trips ?? [];

  return (
    <div className="min-h-screen bg-[#080f1a]">
      {/* Header */}
      <header className="border-b border-sky-900/30 bg-[#080f1a]/90 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-sky-500/15 border border-sky-500/30 flex items-center justify-center">
              <PlaneTakeoff size={18} className="text-sky-400" />
            </div>
            <div>
              <h1 className="text-white font-bold text-lg tracking-tight leading-none">Autopilot</h1>
              <p className="text-slate-500 text-xs">Flight Price Tracker</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {data.updated_at && (
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-sky-500" />
                </span>
                Updated {formatDistanceToNow(parseISO(data.updated_at), { addSuffix: true })}
              </div>
            )}
            <button
              onClick={fetchData}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs hover:bg-sky-500/20 transition-colors"
            >
              <RefreshCw size={11} />
              Refresh
            </button>
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Zap size={12} className="text-amber-400" />
              Onyx Media Group
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">

        {/* Warming up state */}
        {!loading && !data.updated_at && (
          <div className="rounded-2xl border border-sky-900/30 bg-[#0a1628] p-10 text-center">
            <PlaneTakeoff size={32} className="text-sky-800 mx-auto mb-3" />
            <p className="text-slate-400 font-semibold">Auto is warming up</p>
            <p className="text-slate-600 text-sm mt-1">
              First price check hasn't run yet. Start Auto locally to begin tracking.
            </p>
          </div>
        )}

        {/* Trip Cards */}
        {activeTrips.length > 0 && (
          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
                Trips Tracked
              </h2>
              <span className="text-xs text-slate-600">Round-trip totals for 2 passengers</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {activeTrips.map((t) => (
                <FlightMissionCard
                  key={t.id}
                  trip={t}
                  currentPrice={sigMap[t.id]?.current_price ?? data.best_offers[t.id]?.price_total ?? null}
                  prevPrice={getPrevPrice(t.id)}
                  signal={sigMap[t.id] ?? null}
                  loading={loading}
                />
              ))}
            </div>
          </section>
        )}

        {/* Price History Charts */}
        {activeTrips.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-4">
              Round-Trip Price History
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {activeTrips.map((t) => (
                <PriceChart
                  key={t.id}
                  missionLabel={t.label}
                  points={data.history[t.id] ?? []}
                  predictedLow={sigMap[t.id]?.predicted_low}
                  predictedHigh={sigMap[t.id]?.predicted_high}
                  currentPrice={sigMap[t.id]?.current_price}
                />
              ))}
            </div>
          </section>
        )}

        <footer className="text-center py-4 text-xs text-slate-700">
          Auto checks round-trip prices every 12 hours · Alerts on drops to milesdailey19@gmail.com
        </footer>
      </main>
    </div>
  );
}
