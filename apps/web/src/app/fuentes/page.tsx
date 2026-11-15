import type { Metadata } from "next";
import { Sources } from "@/components/pages/Sources";

export const metadata: Metadata = { title: "Fuentes · GaIA" };

export default function FuentesPage() {
  return <Sources />;
}
