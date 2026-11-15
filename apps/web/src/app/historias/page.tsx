import type { Metadata } from "next";
import { Upcoming } from "@/components/pages/Upcoming";

export const metadata: Metadata = { title: "Historias · Earth Trend Studio" };

export default function Page() {
  return <Upcoming title="Historias" description="Investigaciones guiadas y reproducibles, como el caso de El Niño Costero y las lluvias en Trujillo." />;
}
