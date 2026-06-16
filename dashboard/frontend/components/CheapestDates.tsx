"use client";

import { CalendarDays, Tag } from "lucide-react";
import { format, parseISO } from "date-fns";

type DateOption = {
  date: string;
  price: number;
  return_date?: string;
};

type Props = {
  missionLabel: string;
  dates: DateOption[];
  targetDate: string;
  loading?: boolean;
};

export default function CheapestDates({ missionLabel, dates, targetDate, loading }: Props) {
  if (loading) {
    return (
      <div className="rounded-2xl border border-sky-900/40 bg-[#0a1628] p-5">
        <p className="text-sm font-semibold text-slate-400 mb-3">Best Dates — {missionLabel}</p>
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-10 rounded-lg bg-slate-800 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  const cheapest = dates[0]?.price;
  const sorted = [...dates].slice(0, 7);

  return (
    <div className="rounded-2xl border border-sky-900/40 bg-[#0a1628] p-5">
      <div className="flex items-center gap-2 mb-4">
        <CalendarDays size={15} className="text-sky-400" />
        <p className="text-sm font-semibold text-slate-300">Best Dates — {missionLabel}</p>
      </div>

      {!dates.length ? (
        <p className="text-slate-600 text-sm">No date data yet — requires Amadeus API keys.</p>
      ) : (
        <div className="space-y-1.5">
          {sorted.map((d, i) => {
            const isCheapest = d.price === cheapest;
            const isTarget = d.date === targetDate;
            const savings = isTarget
              ? null
              : cheapest
              ? ((d.price - cheapest) / cheapest) * 100
              : null;

            return (
              <div
                key={d.date}
                className={`flex items-center justify-between rounded-lg px-3 py-2 ${
                  isCheapest
                    ? "bg-emerald-500/10 border border-emerald-500/25"
                    : isTarget
                    ? "bg-sky-500/10 border border-sky-500/25"
                    : "bg-slate-900/50 border border-transparent"
                }`}
              >
                <div className="flex items-center gap-2">
                  {isCheapest && <Tag size={12} className="text-emerald-400" />}
                  <span className="text-sm text-slate-300">
                    {format(parseISO(d.date), "EEE, MMM d")}
                  </span>
                  {isTarget && (
                    <span className="text-xs text-sky-400 bg-sky-500/15 px-1.5 py-0.5 rounded">
                      your date
                    </span>
                  )}
                  {isCheapest && (
                    <span className="text-xs text-emerald-400 bg-emerald-500/15 px-1.5 py-0.5 rounded">
                      cheapest
                    </span>
                  )}
                </div>
                <div className="text-right">
                  <span className={`text-sm font-bold tabular-nums ${isCheapest ? "text-emerald-400" : "text-white"}`}>
                    ${d.price.toFixed(0)}
                  </span>
                  {savings != null && savings > 0 && (
                    <span className="text-xs text-rose-400 ml-1">+{savings.toFixed(0)}%</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
