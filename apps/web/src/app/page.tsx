import type { Metadata } from "next";
import { Suspense } from "react";
import { Dashboard } from "@/components/dashboard/Dashboard";

export const metadata: Metadata = { title: "GaIA" };

// Experiencia principal: panel unificado de un territorio (las demás secciones son opcionales).
export default function Home() {
  return (
    <Suspense>
      <Dashboard />
    </Suspense>
  );
}
