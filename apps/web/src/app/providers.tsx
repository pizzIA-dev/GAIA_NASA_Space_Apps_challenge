"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, isTransient } from "@/lib/api";
import { ApiWakeBanner } from "@/components/ApiWakeBanner";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        // No reintentar errores de contrato (4xx): son respuestas honestas, no fallos transitorios.
        // Servidor gratuito dormido: hasta ~2 min de reintentos cada 10 s (el aviso superior lo explica).
        retry: (n, e) => (isTransient(e) ? n < 12 : !(e instanceof ApiError && e.problem.status >= 400 && e.problem.status < 500) && n < 2),
        retryDelay: (n, e) => (isTransient(e) ? 10_000 : Math.min(1000 * 2 ** n, 8000)),
      },
    },
  }));
  return <QueryClientProvider client={client}><ApiWakeBanner />{children}</QueryClientProvider>;
}
