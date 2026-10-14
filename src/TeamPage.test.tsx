import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TeamPage from "./TeamPage";

const WORKSPACE_ID = "workspace-1";
const BASE_URL = `/api/workspaces/${WORKSPACE_ID}`;

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("team workspace modules", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/communication/channels")) {
          return response([
            { id: "channel-1", name: "general", description: null },
          ]);
        }
        if (url.includes("/messages")) return response([]);
        if (url.includes("/hr/")) return response([]);
        if (url.endsWith("/ats/jobs")) return response([]);
        if (url.endsWith("/ats/candidates")) return response([]);
        if (url.endsWith("/ats/applications")) return response([]);
        return response({});
      }),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads channels and posts messages to the selected channel", async () => {
    const fetchMock = vi.mocked(fetch);
    render(
      <TeamPage
        workspaceId={WORKSPACE_ID}
        token="test-token"
        onBack={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: "# general" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Write a message"), {
      target: { value: "Welcome to the team." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/communication/channels/channel-1/messages`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ body: "Welcome to the team." }),
      }),
    );
    expect(
      new Headers(
        fetchMock.mock.calls.find(([input, init]) =>
          String(input).endsWith("/messages") && init?.method === "POST",
        )?.[1]?.headers,
      ).get("X-CSRF-Token"),
    ).toBe("test-token");
  });

  it("communicates that HR access is restricted for regular members", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      if (String(input).includes("/hr/")) {
        return response(
          {
            detail: {
              code: "workspace_role_required",
              message: "Your role cannot access this module.",
            },
          },
          403,
        );
      }
      if (String(input).endsWith("/communication/channels")) return response([]);
      if (String(input).endsWith("/ats/jobs")) return response([]);
      if (String(input).endsWith("/ats/candidates")) return response([]);
      if (String(input).endsWith("/ats/applications")) return response([]);
      return response([]);
    });
    render(
      <TeamPage
        workspaceId={WORKSPACE_ID}
        token="test-token"
        onBack={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "People" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your role cannot access this module.",
    );
  });

  it("creates an opening and presents the candidate pipeline", async () => {
    const fetchMock = vi.mocked(fetch).mockImplementation(
      async (input, init) => {
        if (String(input).endsWith("/ats/jobs") && init?.method === "POST") {
          return response({
            id: "job-1",
            title: "Product designer",
            department: null,
            status: "open",
          });
        }
        if (String(input).endsWith("/ats/jobs")) {
          return response([
            {
              id: "job-1",
              title: "Product designer",
              department: "Design",
              status: "open",
            },
          ]);
        }
        if (String(input).endsWith("/ats/candidates")) return response([]);
        if (String(input).endsWith("/ats/applications")) return response([]);
        if (String(input).endsWith("/communication/channels")) return response([]);
        return response([]);
      },
    );
    render(
      <TeamPage
        workspaceId={WORKSPACE_ID}
        token="test-token"
        onBack={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Hiring" }));
    fireEvent.change(await screen.findByLabelText("Job title"), {
      target: { value: "Product designer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create opening" }));

    expect(
      await screen.findAllByText("Product designer", { exact: true }),
    ).toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/ats/jobs`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ title: "Product designer", department: null }),
      }),
    );
  });
});
