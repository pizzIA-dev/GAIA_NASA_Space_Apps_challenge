import type { Metadata } from "next";
import { Upcoming } from "@/components/pages/Upcoming";

export const metadata: Metadata = { title: "Atlas · Earth Trend Studio" };

export default function Page() {
  return <Upcoming title="Atlas" description="Mapas de tendencias de cada variable para comparar regiones de un vistazo." />;
}
