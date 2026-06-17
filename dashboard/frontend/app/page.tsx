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

type AutopilotData = {
  updated_at: string | null;
  trips: Trip[];
  signals: Signal[];
  flight_options: Record<string, { morning: FlightOption[]; afternoon: FlightOption[]; aa_booking_url?: string }>;
  history: Record<string, { ts: string; morning: number | null; afternoon: number | null }[]>;
};

const EMPTY: AutopilotData = {
  updated_at: null,
  trips: [],
  signals: [],
  flight_options: {},
  history: {},
};

export default function Dashboard() {
  const [data, setData] = useState<AutopilotData>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    try {
      const res = await fetch(`/data/autopilot.json?t=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error("Failed to load autopilot data:", e);
    } finally {
      setLoading(false);
      if (manual) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData(false);
    const interval = setInterval(() => fetchData(false), 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const sigMap: Record<string, Signal> = {};
  for (const s of data.signals) sigMap[s.trip_id] = s;

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
              onClick={() => fetchData(true)}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs hover:bg-sky-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw size={11} className={refreshing ? "animate-spin" : ""} />
              {refreshing ? "Refreshing…" : "Refresh"}
            </button>
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Zap size={12} className="text-amber-400" />
              Onyx Media Group
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">

        {!loading && !data.updated_at && (
          <div className="rounded-2xl border border-sky-900/30 bg-[#0a1628] p-10 text-center">
            <PlaneTakeoff size={32} className="text-sky-800 mx-auto mb-3" />
            <p className="text-slate-400 font-semibold">Auto is warming up</p>
            <p className="text-slate-600 text-sm mt-1">
              First price check hasn&apos;t run yet. GitHub Actions will kick off at 8am or 8pm EST.
            </p>
          </div>
        )}

        {activeTrips.length > 0 && (
          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
                Trips Tracked
              </h2>
              <span className="text-xs text-slate-600">Nonstop · American Airlines · per person</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {activeTrips.map((t) => {
                const opts = (data.flight_options ?? {})[t.id];
                return (
                  <FlightMissionCard
                    key={t.id}
                    trip={t}
                    morning={opts?.morning ?? []}
                    afternoon={opts?.afternoon ?? []}
                    signal={sigMap[t.id] ?? null}
                    loading={loading}
                    aaBookingUrl={opts?.aa_booking_url}
                  />
                );
              })}
            </div>
          </section>
        )}

        {activeTrips.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-4">
              Price History — Per Person
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {activeTrips.map((t) => (
                <PriceChart
                  key={t.id}
                  tripLabel={t.label}
                  points={data.history[t.id] ?? []}
                  predictedLow={sigMap[t.id]?.predicted_low_per_person ?? undefined}
                />
              ))}
            </div>
          </section>
        )}

        <footer className="text-center py-4 text-xs text-slate-700">
          Auto checks round-trip prices every 12 hours · Alerts on drops ≥5% to milesdailey19@gmail.com
        </footer>
      </main>
    </div>
  );
}
