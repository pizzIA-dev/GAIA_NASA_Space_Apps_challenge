import type { Metadata } from "next";
import { Suspense } from "react";
import { Studio } from "@/components/studio/Studio";

export const metadata: Metadata = { title: "Estudio · Earth Trend Studio" };

export default function EstudioPage() {
  return (
    <Suspense>
      <Studio />
    </Suspense>
  );
}
