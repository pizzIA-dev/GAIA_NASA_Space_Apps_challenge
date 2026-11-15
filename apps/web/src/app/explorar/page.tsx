import type { Metadata } from "next";
import { Suspense } from "react";
import { Explorer } from "@/components/explorer/Explorer";

export const metadata: Metadata = { title: "Explorar · Earth Trend Studio" };

export default function ExplorarPage() {
  return (
    <Suspense>
      <Explorer />
    </Suspense>
  );
}
