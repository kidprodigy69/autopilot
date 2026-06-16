import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Auto — Autopilot Flight Tracker",
  description: "Intelligent flight price tracking by Onyx Media Group",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
