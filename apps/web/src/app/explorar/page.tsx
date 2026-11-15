import type { Metadata } from "next";
import { Suspense } from "react";
import { Explorer } from "@/components/explorer/Explorer";

export const metadata: Metadata = { title: "Detalle de una variable · GaIA" };

export default function ExplorarPage() {
  return (
    <Suspense>
      <Explorer />
    </Suspense>
  );
}
