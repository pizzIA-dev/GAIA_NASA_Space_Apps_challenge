import type { Metadata } from "next";
import { Suspense } from "react";
import { Atlas } from "@/components/atlas/Atlas";

export const metadata: Metadata = { title: "Atlas · Earth Trend Studio" };

export default function Page() {
  return (
    <Suspense>
      <Atlas />
    </Suspense>
  );
}
