import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserHistory } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App, createAppRouter } from "./App";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 15_000 } },
});

const root = document.getElementById("root");
if (root === null) {
  throw new Error("application root element is missing");
}
const router = createAppRouter(createBrowserHistory());

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
