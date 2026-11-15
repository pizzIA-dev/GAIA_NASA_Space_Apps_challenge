"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "@/lib/api";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        // No reintentar errores de contrato (4xx): son respuestas honestas, no fallos transitorios.
        retry: (n, e) => !(e instanceof ApiError && e.problem.status >= 400 && e.problem.status < 500) && n < 2,
      },
    },
  }));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
