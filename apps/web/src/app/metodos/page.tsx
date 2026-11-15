import type { Metadata } from "next";
import { Methods } from "@/components/pages/Methods";

export const metadata: Metadata = { title: "Métodos · GaIA" };

export default function MetodosPage() {
  return <Methods />;
}
