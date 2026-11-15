import type { Metadata } from "next";
import { Upcoming } from "@/components/pages/Upcoming";

export const metadata: Metadata = { title: "Estudio · Earth Trend Studio" };

export default function Page() {
  return <Upcoming title="Estudio" description="Un lienzo para comparar variables y territorios lado a lado, arrastrando variables a los ejes." />;
}
