"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { format, parseISO } from "date-fns";

type Point = { ts: string; price: number };

type Props = {
  missionLabel: string;
  points: Point[];
  predictedLow?: number;
  predictedHigh?: number;
  currentPrice?: number;
};

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg bg-slate-900 border border-sky-900/50 px-3 py-2 text-sm shadow-xl">
      <p className="text-slate-400 text-xs mb-1">
        {label ? format(new Date(label), "MMM d, h:mma") : ""}
      </p>
      <p className="text-white font-bold">${payload[0].value.toFixed(0)}</p>
    </div>
  );
}

export default function PriceChart({
  missionLabel,
  points,
  predictedLow,
  predictedHigh,
  currentPrice,
}: Props) {
  const data = points.map((p) => ({
    ts: p.ts,
    price: p.price,
    label: format(parseISO(p.ts), "MMM d HH:mm"),
  }));

  const prices = points.map((p) => p.price);
  const minP = prices.length ? Math.min(...prices) * 0.97 : 0;
  const maxP = prices.length ? Math.max(...prices) * 1.03 : 1000;

  if (!points.length) {
    return (
      <div className="rounded-2xl border border-sky-900/40 bg-[#0a1628] p-5">
        <p className="text-sm text-slate-500 mb-4 font-semibold">{missionLabel} — Price History</p>
        <div className="flex items-center justify-center h-48 text-slate-600 text-sm">
          Collecting data — check back after first poll cycle
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-sky-900/40 bg-[#0a1628] p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-slate-400 font-semibold">{missionLabel} — Price History</p>
        {currentPrice && (
          <span className="text-sky-400 font-bold text-sm tabular-nums">
            ${currentPrice.toFixed(0)} now
          </span>
        )}
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
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

          {predictedLow && (
            <ReferenceLine
              y={predictedLow}
              stroke="rgba(52,211,153,0.4)"
              strokeDasharray="4 4"
              label={{ value: "Target Low", fill: "#34d399", fontSize: 10, position: "right" }}
            />
          )}
          {predictedHigh && (
            <ReferenceLine
              y={predictedHigh}
              stroke="rgba(248,113,113,0.3)"
              strokeDasharray="4 4"
              label={{ value: "Predicted High", fill: "#f87171", fontSize: 10, position: "right" }}
            />
          )}

          <Line
            type="monotone"
            dataKey="price"
            stroke="#38bdf8"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: "#38bdf8", stroke: "#0a1628", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
