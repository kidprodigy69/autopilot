"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { format, parseISO } from "date-fns";

type HistoryPoint = {
  ts: string;
  morning: number | null;
  afternoon: number | null;
};

type Props = {
  tripLabel: string;
  points: HistoryPoint[];
  predictedLow?: number;
};

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg bg-slate-900 border border-sky-900/50 px-3 py-2 text-sm shadow-xl">
      <p className="text-slate-400 text-xs mb-1.5">
        {label ? format(new Date(label), "MMM d, h:mma") : ""}
      </p>
      {payload.map((p: any) => p.value != null && (
        <p key={p.name} style={{ color: p.color }} className="font-bold">
          {p.name === "morning" ? "Morning" : "Afternoon"}: ${p.value.toFixed(0)}/person
        </p>
      ))}
    </div>
  );
}

export default function PriceChart({ tripLabel, points, predictedLow }: Props) {
  const data = points.map((p) => ({
    ts: p.ts,
    morning: p.morning ?? undefined,
    afternoon: p.afternoon ?? undefined,
    label: format(parseISO(p.ts), "MMM d"),
  }));

  const allVals = points.flatMap(p => [p.morning, p.afternoon]).filter((v): v is number => v != null);
  const minP = allVals.length ? Math.min(...allVals) * 0.95 : 0;
  const maxP = allVals.length ? Math.max(...allVals) * 1.05 : 1000;

  if (!points.length) {
    return (
      <div className="rounded-2xl border border-sky-900/40 bg-[#0a1628] p-5">
        <p className="text-sm text-slate-500 mb-4 font-semibold">{tripLabel} — Price History</p>
        <div className="flex items-center justify-center h-48 text-slate-600 text-sm">
          Collecting data — check back after first poll cycle
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-sky-900/40 bg-[#0a1628] p-5">
      <p className="text-sm text-slate-400 font-semibold mb-4">{tripLabel} — Price History</p>

      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(56,189,248,0.06)" />
          <XAxis
            dataKey="label"
            tick={{ fill: "#475569", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[minP, maxP]}
            tick={{ fill: "#475569", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `$${v.toFixed(0)}`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            iconType="circle"
            iconSize={8}
            formatter={(val) => <span className="text-xs text-slate-400 capitalize">{val}</span>}
          />

          {predictedLow && (
            <ReferenceLine
              y={predictedLow}
              stroke="rgba(52,211,153,0.4)"
              strokeDasharray="4 4"
              label={{ value: "Target", fill: "#34d399", fontSize: 10, position: "right" }}
            />
          )}

          <Line
            type="monotone"
            dataKey="morning"
            stroke="#f59e0b"
            strokeWidth={2}
            dot={false}
            connectNulls
            activeDot={{ r: 4, fill: "#f59e0b", stroke: "#0a1628", strokeWidth: 2 }}
          />
          <Line
            type="monotone"
            dataKey="afternoon"
            stroke="#38bdf8"
            strokeWidth={2}
            dot={false}
            connectNulls
            activeDot={{ r: 4, fill: "#38bdf8", stroke: "#0a1628", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
