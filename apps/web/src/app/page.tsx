import { redirect } from "next/navigation";

// Entrada directa a Explorar con un ejemplo listo (plan §4.1), sin landing.
export default function Home() {
  redirect("/explorar");
}
