"use client";

import { useEffect, useState, useCallback } from "react";
import { PlaneTakeoff, Zap, RefreshCw } from "lucide-react";
import { formatDistanceToNow, parseISO } from "date-fns";
import FlightMissionCard from "@/components/FlightMissionCard";
import PriceChart from "@/components/PriceChart";
import CheapestDates from "@/components/CheapestDates";

type Mission = {
  id: string;
  label: string;
  origin: string;
  destination: string;
  depart_date: string;
  passengers: number;
  preferred_airlines: string[];
};

type Signal = {
  mission_id: string;
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
  missions: Mission[];
  signals: Signal[];
  history: Record<string, { ts: string; price: number }[]>;
  best_offers: Record<string, { price_total: number }>;
};

const EMPTY: AutopilotData = {
  updated_at: null,
  missions: [],
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
    // Re-fetch every 10 minutes on the client side
    const interval = setInterval(fetchData, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const sigMap: Record<string, Signal> = {};
  for (const s of data.signals) sigMap[s.mission_id] = s;

  // Get second-to-last history point as "previous price" for the delta display
  const getPrevPrice = (missionId: string): number | null => {
    const pts = data.history[missionId] ?? [];
    return pts.length >= 2 ? pts[pts.length - 2].price : null;
  };

  return (
    <div className="min-h-screen bg-[#080f1a]">
      {/* Header */}
      <header className="border-b border-sky-900/30 bg-[#080f1a]/90 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-sky-500/15 border border-sky-500/30 flex items-center justify-center">
              <PlaneTakeoff size={18} className="text-sky-400" />
            </div>
            <div>
              <h1 className="text-white font-bold text-lg tracking-tight leading-none">
                Autopilot
              </h1>
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

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">

        {/* No data yet state */}
        {!loading && !data.updated_at && (
          <div className="rounded-2xl border border-sky-900/30 bg-[#0a1628] p-10 text-center">
            <PlaneTakeoff size={32} className="text-sky-800 mx-auto mb-3" />
            <p className="text-slate-400 font-semibold">Auto is warming up</p>
            <p className="text-slate-600 text-sm mt-1">
              First price check hasn't run yet. Start Auto locally to begin tracking.
            </p>
          </div>
        )}

        {/* Mission Cards */}
        {data.missions.length > 0 && (
          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
                Active Missions
              </h2>
              <span className="text-xs text-slate-600">
                {data.missions.length} flights tracked
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {data.missions.map((m) => (
                <FlightMissionCard
                  key={m.id}
                  mission={m}
                  currentPrice={sigMap[m.id]?.current_price ?? data.best_offers[m.id]?.price_total ?? null}
                  prevPrice={getPrevPrice(m.id)}
                  signal={sigMap[m.id] ?? null}
                  loading={loading}
                />
              ))}
            </div>
          </section>
        )}

        {/* Price History Charts */}
        {data.missions.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-4">
              Price History
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {data.missions.map((m) => (
                <PriceChart
                  key={m.id}
                  missionLabel={m.label}
                  points={data.history[m.id] ?? []}
                  predictedLow={sigMap[m.id]?.predicted_low}
                  predictedHigh={sigMap[m.id]?.predicted_high}
                  currentPrice={sigMap[m.id]?.current_price}
                />
              ))}
            </div>
          </section>
        )}

        {/* Footer */}
        <footer className="text-center py-4 text-xs text-slate-700">
          Auto checks prices every 12 hours and emails alerts on drops ·{" "}
          <span className="text-slate-600">Onyx Media Group</span>
        </footer>
      </main>
    </div>
  );
}
