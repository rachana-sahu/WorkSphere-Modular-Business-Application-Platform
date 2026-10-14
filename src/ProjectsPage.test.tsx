import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ProjectsPage from "./ProjectsPage";

const WORKSPACE_ID = "workspace-projects";
const BASE_URL = `/api/workspaces/${WORKSPACE_ID}/projects`;
const PROJECT = {
  id: "project-1",
  name: "Website launch",
  description: "Deliver the new public site.",
  status: "active",
  created_at: "2026-10-01T00:00:00Z",
};
const TASK = {
  id: "task-1",
  project_id: PROJECT.id,
  title: "Publish release notes",
  description: null,
  status: "todo",
  priority: "high",
  due_date: "2026-11-01",
  assigned_to: null,
  created_at: "2026-10-01T00:00:00Z",
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

describe("Projects workspace", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/members")) return response([]);
        if (url.includes("/activities")) return response([]);
        if (url.includes("/tasks?")) return response(page([TASK]));
        if (url.includes("/projects?")) return response(page([PROJECT]));
        return response({});
      }),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads projects and filters the selected project's tasks", async () => {
    const fetchMock = vi.mocked(fetch);
    render(
      <ProjectsPage
        workspaceId={WORKSPACE_ID}
        token="project-token"
        onBack={vi.fn()}
      />,
    );
    fireEvent.click(await screen.findByRole("button", { name: /Website launch/ }));

    expect(
      await screen.findByRole("button", { name: "Publish release notes" }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Filter tasks by status"), {
      target: { value: "done" },
    });
    const taskListCall = fetchMock.mock.calls.find(([input]) =>
      String(input).includes("task_status=done"),
    );

    expect(taskListCall?.[0]).toBe(
      `${BASE_URL}/project-1/tasks?page=1&page_size=10&task_status=done`,
    );
    expect(new Headers(taskListCall?.[1]?.headers).get("X-CSRF-Token")).toBe(
      "project-token",
    );
  });

  it("adds a comment to a task and refreshes its activity", async () => {
    const fetchMock = vi.mocked(fetch).mockImplementation(
      async (input, init) => {
        const url = String(input);
        if (url.endsWith("/members")) return response([]);
        if (url.includes("/activities")) {
          return response([
            {
              id: "activity-1",
              task_id: TASK.id,
              event_type: "task_comment_added",
              summary: "A comment was added to 'Publish release notes'.",
              created_at: "2026-10-02T00:00:00Z",
            },
          ]);
        }
        if (url.includes("/comments") && init?.method === "POST") {
          return response({
            id: "comment-1",
            body: "Ready for review.",
            author_id: "member-1",
            created_at: "2026-10-02T00:00:00Z",
          });
        }
        if (url.includes("/comments")) {
          return response([
            {
              id: "comment-1",
              body: "Ready for review.",
              author_id: "member-1",
              created_at: "2026-10-02T00:00:00Z",
            },
          ]);
        }
        if (url.includes("/tasks?")) return response(page([TASK]));
        if (url.includes("/projects?")) return response(page([PROJECT]));
        return response({});
      },
    );
    render(
      <ProjectsPage
        workspaceId={WORKSPACE_ID}
        token="project-token"
        onBack={vi.fn()}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: /Website launch/ }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Publish release notes" }),
    );
    fireEvent.change(await screen.findByLabelText("Add a comment"), {
      target: { value: "Ready for review." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add comment" }));

    expect(await screen.findByText("Ready for review.")).toBeInTheDocument();
    expect(
      await screen.findByText(
        "A comment was added to 'Publish release notes'.",
      ),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/project-1/tasks/task-1/comments`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ body: "Ready for review." }),
      }),
    );
  });

  it("creates a task with priority, deadline, and a workspace assignee", async () => {
    const fetchMock = vi.mocked(fetch).mockImplementation(
      async (input, init) => {
        const url = String(input);
        if (url.endsWith("/members")) {
          return response([{ id: "member-1", display_name: "Morgan Lee" }]);
        }
        if (url.includes("/activities")) return response([]);
        if (url.endsWith("/tasks") && init?.method === "POST") {
          return response({
            ...TASK,
            id: "task-new",
            title: "Confirm launch checklist",
            priority: "high",
            due_date: "2026-12-05",
            assigned_to: "member-1",
          });
        }
        if (url.endsWith("/tasks") || url.includes("/tasks?")) {
          return response(page([TASK]));
        }
        if (url.includes("/projects?")) return response(page([PROJECT]));
        return response({});
      },
    );
    render(
      <ProjectsPage
        workspaceId={WORKSPACE_ID}
        token="project-token"
        onBack={vi.fn()}
      />,
    );
    fireEvent.click(await screen.findByRole("button", { name: /Website launch/ }));
    fireEvent.change(await screen.findByLabelText("Task title"), {
      target: { value: "Confirm launch checklist" },
    });
    fireEvent.change(screen.getByLabelText("Priority"), {
      target: { value: "high" },
    });
    fireEvent.change(screen.getByLabelText("Due date"), {
      target: { value: "2026-12-05" },
    });
    fireEvent.change(screen.getByLabelText("Assignee"), {
      target: { value: "member-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create task" }));

    const createCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input) === `${BASE_URL}/project-1/tasks` &&
        init?.method === "POST",
    );
    expect(createCall?.[1]?.body).toBe(
      JSON.stringify({
        title: "Confirm launch checklist",
        description: null,
        priority: "high",
        due_date: "2026-12-05",
        assigned_to: "member-1",
      }),
    );
  });

  it("generates an editable project status draft only after explicit action", async () => {
    const fetchMock = vi.mocked(fetch).mockImplementation(
      async (input: RequestInfo | URL) => {
        if (String(input).includes("/status-draft")) {
          return response({
            draft: "Website launch has tasks underway. Review before sharing.",
            provider: "mock",
            disclaimer:
              "Review and edit this draft before sharing; it may omit context or be inaccurate.",
          });
        }
        const url = String(input);
        if (url.endsWith("/members")) return response([]);
        if (url.includes("/activities")) return response([]);
        if (url.includes("/tasks?")) return response(page([TASK]));
        if (url.includes("/projects?")) return response(page([PROJECT]));
        return response({});
      },
    );
    render(
      <ProjectsPage
        workspaceId={WORKSPACE_ID}
        token="project-token"
        onBack={vi.fn()}
      />,
    );
    fireEvent.click(await screen.findByRole("button", { name: /Website launch/ }));

    expect(fetchMock).not.toHaveBeenCalledWith(
      `/api/workspaces/${WORKSPACE_ID}/assistant/projects/project-1/status-draft`,
      expect.anything(),
    );
    expect(screen.getByText(/no external ai/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Generate draft" }));

    const draftField = await screen.findByLabelText("Edit draft");
    expect(draftField).toHaveValue(
      "Website launch has tasks underway. Review before sharing.",
    );
    expect(screen.getByText(/may omit context or be inaccurate/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/workspaces/${WORKSPACE_ID}/assistant/projects/project-1/status-draft`,
      expect.objectContaining({ method: "POST" }),
    );
    fireEvent.change(draftField, { target: { value: "Edited by me." } });
    expect(draftField).toHaveValue("Edited by me.");
  });

  it("shows assistant provider errors without hiding the project screen", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      if (String(input).includes("/status-draft")) {
        return response(
          {
            detail: {
              code: "assistant_unavailable",
              message: "The project update assistant is temporarily unavailable.",
            },
          },
          false,
        );
      }
      const url = String(input);
      if (url.endsWith("/members")) return response([]);
      if (url.includes("/activities")) return response([]);
      if (url.includes("/tasks?")) return response(page([TASK]));
      if (url.includes("/projects?")) return response(page([PROJECT]));
      return response({});
    });
    render(
      <ProjectsPage
        workspaceId={WORKSPACE_ID}
        token="project-token"
        onBack={vi.fn()}
      />,
    );
    fireEvent.click(await screen.findByRole("button", { name: /Website launch/ }));
    fireEvent.click(screen.getByRole("button", { name: "Generate draft" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The project update assistant is temporarily unavailable.",
    );
    expect(screen.getByRole("heading", { name: "Projects" })).toBeInTheDocument();
  });

  it("creates a project and displays API validation feedback", async () => {
    const fetchMock = vi.mocked(fetch).mockImplementation(
      async (input, init) => {
        if (String(input).endsWith("/members")) return response([]);
        if (init?.method === "POST") {
          return response(
            {
              detail: {
                code: "validation_error",
                message: "A project name is required.",
              },
            },
            false,
          );
        }
        if (String(input).includes("/projects?")) return response(page([]));
        return response([]);
      },
    );
    render(
      <ProjectsPage
        workspaceId={WORKSPACE_ID}
        token="project-token"
        onBack={vi.fn()}
      />,
    );

    fireEvent.change(await screen.findByLabelText("Project name"), {
      target: { value: "Delivery planning" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A project name is required.",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      BASE_URL,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "Delivery planning",
          description: null,
        }),
      }),
    );
  });
});
