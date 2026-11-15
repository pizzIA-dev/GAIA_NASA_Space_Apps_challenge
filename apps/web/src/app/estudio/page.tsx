import type { Metadata } from "next";
import { Suspense } from "react";
import { Studio } from "@/components/studio/Studio";

export const metadata: Metadata = { title: "Análisis avanzado · GaIA" };

export default function EstudioPage() {
  return (
    <Suspense>
      <Studio />
    </Suspense>
  );
}
