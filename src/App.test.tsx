import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
}

function mockReadyService() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ready" }),
    }),
  );
}

describe("WorkSphere authentication flow", () => {
  beforeEach(() => {
    document.cookie = "worksphere_csrf=; Max-Age=0; path=/";
    window.history.replaceState({}, "", "/");
    mockReadyService();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("offers account creation and sign-in from the landing page", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: "Good work happens together.",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create a workspace" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("registers and opens the protected workspace without storing a bearer token", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/health/ready") {
        return jsonResponse({ status: "ready" });
      }
      if (url === "/api/auth/register") {
        document.cookie = "worksphere_csrf=test-csrf-token; path=/";
        return jsonResponse({
          expires_in: 1800,
        });
      }
      if (url === "/api/workspaces/current") {
        return jsonResponse({
          id: "workspace-id",
          name: "Research Team",
          slug: "research-team",
          role: "owner",
        });
      }
      return jsonResponse({
        id: "user-id",
        email: "owner@example.com",
        display_name: "Workspace Owner",
      });
    });

    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Create a workspace" }));
    fireEvent.change(await screen.findByLabelText("Your name"), {
      target: { value: "Workspace Owner" },
    });
    fireEvent.change(screen.getByLabelText("Workspace name"), {
      target: { value: "Research Team" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "owner@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "a-long-secure-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create workspace" }));

    expect(
      await screen.findByRole("heading", { name: "Research Team" }),
    ).toBeInTheDocument();
    expect(sessionStorage.length).toBe(0);
    expect(localStorage.length).toBe(0);
    const workspaceRequest = fetchMock.mock.calls.find(
      ([input]) => input === "/api/workspaces/current",
    );
    expect(workspaceRequest?.[1]?.credentials).toBe("same-origin");
  });

  it("shows field errors returned for an unsuccessful sign-in", async () => {
    window.history.replaceState({}, "", "/login");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url: string) => {
        if (url === "/api/health/ready") {
          return { ok: true, json: async () => ({ status: "ready" }) };
        }
        return {
          ok: false,
          json: async () => ({
            detail: {
              code: "invalid_credentials",
              message: "Email or password is incorrect.",
            },
          }),
        };
      }),
    );
    render(<App />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "person@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "not-the-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Email or password is incorrect.",
    );
    expect(sessionStorage.length).toBe(0);
  });

  it("does not fetch protected workspace data without a session", async () => {
    window.history.replaceState({}, "", "/app");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ready" }),
    });
    fetchMock.mockImplementation(async (input) => {
      if (input === "/api/health/ready") {
        return jsonResponse({ status: "ready" });
      }
      return new Response(
        JSON.stringify({
          detail: {
            code: "authentication_required",
            message: "A valid session or access token is required.",
          },
        }),
        {
          status: 401,
          headers: { "Content-Type": "application/json" },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Your workspace is private.",
      }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/workspaces/current",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("loads the workspace and user profile for a signed-in user", async () => {
    window.history.replaceState({}, "", "/app");
    document.cookie = "worksphere_csrf=test-csrf-token; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/health/ready") {
        return jsonResponse({ status: "ready" });
      }
      if (url === "/api/workspaces/current") {
        return jsonResponse({
          id: "workspace-id",
          name: "Design Team",
          slug: "design-team",
          role: "owner",
        });
      }
      return jsonResponse({
        id: "user-id",
        email: "owner@example.com",
        display_name: "Workspace Owner",
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Design Team" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/owner@example\.com/)).toBeInTheDocument();
    const workspaceRequest = fetchMock.mock.calls.find(
      ([input]) => input === "/api/workspaces/current",
    );
    expect(workspaceRequest?.[1]?.credentials).toBe("same-origin");
    expect(
      new Headers(workspaceRequest?.[1]?.headers).get("Authorization"),
    ).toBeNull();
  });

  it("opens the Team screen from the signed-in workspace", async () => {
    window.history.replaceState({}, "", "/app");
    document.cookie = "worksphere_csrf=test-csrf-token; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/health/ready") {
        return jsonResponse({ status: "ready" });
      }
      if (url === "/api/workspaces/current") {
        return jsonResponse({
          id: "workspace-id",
          name: "Design Team",
          slug: "design-team",
          role: "owner",
        });
      }
      if (url === "/api/auth/me") {
        return jsonResponse({
          id: "user-id",
          email: "owner@example.com",
          display_name: "Workspace Owner",
        });
      }
      if (url.endsWith("/communication/channels")) return jsonResponse([]);
      if (url.endsWith("/ats/jobs")) return jsonResponse([]);
      if (url.endsWith("/ats/candidates")) return jsonResponse([]);
      if (url.endsWith("/ats/applications")) return jsonResponse([]);
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Open team" }));

    expect(await screen.findByRole("heading", { name: "Team" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Communication" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "People" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hiring" })).toBeInTheDocument();
  });
});
