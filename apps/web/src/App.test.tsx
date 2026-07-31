import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { App, createAppRouter } from "./App";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

test("renders an accessible empty project state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [],
        page: { next_cursor: null, limit: 100 },
      }),
    }),
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createAppRouter(
    createMemoryHistory({ initialEntries: ["/"] }),
  );
  render(
    <QueryClientProvider client={queryClient}>
      <App router={router} />
    </QueryClientProvider>,
  );
  expect(
    await screen.findByRole("heading", { name: "No projects yet" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Organization UUID")).toBeRequired();
});
