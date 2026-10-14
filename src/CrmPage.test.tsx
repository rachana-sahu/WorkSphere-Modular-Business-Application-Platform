import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import CrmPage from "./CrmPage";

const WORKSPACE_ID = "workspace-1";
const BASE_URL = `/api/workspaces/${WORKSPACE_ID}/crm`;
const LEAD = {
  id: "lead-1",
  title: "Annual support renewal",
  stage: "new",
  source: "Referral",
  estimated_value: "12500.00",
  company_id: null,
  contact_id: null,
};

function response(body: unknown, ok = true): Response {
  return new Response(JSON.stringify(body), {
    status: ok ? 200 : 400,
    headers: { "Content-Type": "application/json" },
  });
}

function page(items: unknown[], total = items.length) {
  return { items, page: 1, page_size: 10, total };
}

describe("CRM workspace", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/companies")) return response(page([]));
        if (url.includes("/contacts")) return response(page([]));
        if (url.includes("/activities")) return response([]);
        if (url.includes("/notes")) return response([]);
        if (url.includes("/leads")) return response(page([LEAD]));
        return response({});
      }),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("lists leads and applies search and stage filters", async () => {
    const fetchMock = vi.mocked(fetch);
    render(
      <CrmPage workspaceId={WORKSPACE_ID} token="test-token" onBack={vi.fn()} />,
    );

    expect(
      await screen.findByRole("button", { name: "Annual support renewal" }),
    ).toBeInTheDocument();
    const stageFilter = screen.getByLabelText("Filter by stage");
    fireEvent.change(stageFilter, { target: { value: "qualified" } });
    fireEvent.change(screen.getByLabelText("Search leads"), {
      target: { value: "renewal" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    const searchCall = fetchMock.mock.calls.find(([input]) =>
      String(input).includes("q=renewal"),
    );
    expect(searchCall?.[0]).toBe(
      `${BASE_URL}/leads?page=1&page_size=10&q=renewal&stage=qualified`,
    );
    expect(new Headers(searchCall?.[1]?.headers).get("X-CSRF-Token")).toBe(
      "test-token",
    );
  });

  it("shows lead notes and activity and submits a new note", async () => {
    const fetchMock = vi.mocked(fetch).mockImplementation(
      async (input, init) => {
        const url = String(input);
        if (url.endsWith("/companies?page=1&page_size=100")) {
          return response(page([]));
        }
        if (url.endsWith("/contacts?page=1&page_size=100")) {
          return response(page([]));
        }
        if (url.endsWith("/activities")) {
          return response([
            {
              id: "activity-1",
              event_type: "lead_created",
              summary: "Lead was created.",
              created_at: "2025-01-01T00:00:00Z",
            },
          ]);
        }
        if (url.endsWith("/notes") && init?.method === "POST") {
          return response({
            id: "note-1",
            body: "Confirm renewal timing.",
            created_at: "2025-01-02T00:00:00Z",
          });
        }
        if (url.endsWith("/notes")) {
          return response([
            {
              id: "note-1",
              body: "Confirm renewal timing.",
              created_at: "2025-01-02T00:00:00Z",
            },
          ]);
        }
        if (url.includes("/leads?")) return response(page([LEAD]));
        return response({});
      },
    );
    render(
      <CrmPage workspaceId={WORKSPACE_ID} token="test-token" onBack={vi.fn()} />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Annual support renewal" }),
    );
    expect(await screen.findByText("Lead was created.")).toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText("Add a note"), {
      target: { value: "Confirm renewal timing." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));

    expect(
      await screen.findByText("Confirm renewal timing."),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/leads/lead-1/notes`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ body: "Confirm renewal timing." }),
      }),
    );
  });

  it("creates a company and reports API validation errors", async () => {
    const fetchMock = vi.mocked(fetch).mockImplementation(
      async (input, init) => {
        if (init?.method === "POST") {
          return response(
            {
              detail: {
                code: "company_exists",
                message: "A company with this name already exists.",
              },
            },
            false,
          );
        }
        const url = String(input);
        if (url.includes("/companies")) return response(page([]));
        if (url.includes("/contacts")) return response(page([]));
        return response(page([LEAD]));
      },
    );
    render(
      <CrmPage workspaceId={WORKSPACE_ID} token="test-token" onBack={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Companies" }));
    fireEvent.change(await screen.findByLabelText("Company name"), {
      target: { value: "Northwind" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save company" }));

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent("A company with this name already exists.");
    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/companies`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ name: "Northwind", industry: null }),
      }),
    );
  });
});
