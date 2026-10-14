import { useCallback, useEffect, useState, type FormEvent } from "react";
import { sessionFetch } from "./api";

type ProjectsPageProps = {
  workspaceId: string;
  token: string;
  onBack: () => void;
};
type ProjectStatus = "active" | "on_hold" | "completed";
type TaskStatus = "todo" | "in_progress" | "done";
type TaskPriority = "low" | "medium" | "high";
type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};
type Project = {
  id: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  created_at: string;
};
type ProjectTask = {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  due_date: string | null;
  assigned_to: string | null;
  created_at: string;
};
type ProjectMember = { id: string; display_name: string };
type Comment = { id: string; author_id: string; body: string; created_at: string };
type Activity = {
  id: string;
  task_id: string | null;
  event_type: string;
  summary: string;
  created_at: string;
};
type ProjectStatusDraft = {
  draft: string;
  provider: "mock";
  disclaimer: string;
};

const PAGE_SIZE = 10;
const PROJECT_STATUSES: ProjectStatus[] = ["active", "on_hold", "completed"];
const TASK_STATUSES: TaskStatus[] = ["todo", "in_progress", "done"];
const TASK_PRIORITIES: TaskPriority[] = ["low", "medium", "high"];

async function projectRequest<T>(
  path: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("X-CSRF-Token", token);
  if (options.body) headers.set("Content-Type", "application/json");
  const response = await sessionFetch(path, { ...options, headers });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? payload.detail
        : null;
    const message =
      detail &&
      typeof detail === "object" &&
      "message" in detail &&
      typeof detail.message === "string"
        ? detail.message
        : "The request could not be completed. Please try again.";
    throw new Error(message);
  }
  return payload as T;
}

function pretty(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formattedDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
    new Date(value),
  );
}

export default function ProjectsPage({
  workspaceId,
  token,
  onBack,
}: ProjectsPageProps) {
  const baseUrl = `/api/workspaces/${workspaceId}/projects`;
  const [projects, setProjects] = useState<Page<Project>>({
    items: [],
    page: 1,
    page_size: PAGE_SIZE,
    total: 0,
  });
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Page<ProjectTask>>({
    items: [],
    page: 1,
    page_size: PAGE_SIZE,
    total: 0,
  });
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [selectedTask, setSelectedTask] = useState<ProjectTask | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [statusDraft, setStatusDraft] = useState<ProjectStatusDraft | null>(null);
  const [projectSearchInput, setProjectSearchInput] = useState("");
  const [projectSearch, setProjectSearch] = useState("");
  const [projectStatusFilter, setProjectStatusFilter] = useState("");
  const [taskSearchInput, setTaskSearchInput] = useState("");
  const [taskSearch, setTaskSearch] = useState("");
  const [taskStatusFilter, setTaskStatusFilter] = useState("");
  const [projectPage, setProjectPage] = useState(1);
  const [taskPage, setTaskPage] = useState(1);
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDescription, setTaskDescription] = useState("");
  const [taskPriority, setTaskPriority] = useState<TaskPriority>("medium");
  const [taskDueDate, setTaskDueDate] = useState("");
  const [taskAssignee, setTaskAssignee] = useState("");
  const [commentDraft, setCommentDraft] = useState("");
  const [isLoadingProjects, setIsLoadingProjects] = useState(true);
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isGeneratingDraft, setIsGeneratingDraft] = useState(false);
  const [error, setError] = useState("");
  const selectedTaskId = selectedTask?.id;

  const loadProjects = useCallback(async () => {
    setIsLoadingProjects(true);
    setError("");
    const params = new URLSearchParams({
      page: String(projectPage),
      page_size: String(PAGE_SIZE),
    });
    if (projectSearch) params.set("q", projectSearch);
    if (projectStatusFilter) params.set("project_status", projectStatusFilter);
    try {
      setProjects(
        await projectRequest<Page<Project>>(`${baseUrl}?${params}`, token),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Projects could not be loaded.",
      );
    } finally {
      setIsLoadingProjects(false);
    }
  }, [baseUrl, projectPage, projectSearch, projectStatusFilter, token]);

  const loadTasks = useCallback(async () => {
    if (!selectedProject) {
      setTasks({ items: [], page: 1, page_size: PAGE_SIZE, total: 0 });
      return;
    }
    setIsLoadingTasks(true);
    setError("");
    const params = new URLSearchParams({
      page: String(taskPage),
      page_size: String(PAGE_SIZE),
    });
    if (taskSearch) params.set("q", taskSearch);
    if (taskStatusFilter) params.set("task_status", taskStatusFilter);
    try {
      const result = await projectRequest<Page<ProjectTask>>(
        `${baseUrl}/${selectedProject.id}/tasks?${params}`,
        token,
      );
      setTasks(result);
      if (selectedTaskId) {
        const nextSelectedTask = result.items.find(
          (task) => task.id === selectedTaskId,
        );
        setSelectedTask(nextSelectedTask ?? null);
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Project tasks could not be loaded.",
      );
    } finally {
      setIsLoadingTasks(false);
    }
  }, [
    baseUrl,
    selectedProject,
    selectedTaskId,
    taskPage,
    taskSearch,
    taskStatusFilter,
    token,
  ]);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    projectRequest<ProjectMember[]>(`${baseUrl}/members`, token)
      .then(setMembers)
      .catch((requestError: unknown) => {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Workspace members could not be loaded.",
        );
      });
  }, [baseUrl, token]);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  useEffect(() => {
    if (!selectedProject) {
      setActivities([]);
      return;
    }
    let isActive = true;
    projectRequest<Activity[]>(
      `${baseUrl}/${selectedProject.id}/activities`,
      token,
    )
      .then((result) => {
        if (isActive) setActivities(result);
      })
      .catch((requestError: unknown) => {
        if (isActive) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Project activity could not be loaded.",
          );
        }
      });
    return () => {
      isActive = false;
    };
  }, [baseUrl, selectedProject, token]);

  useEffect(() => {
    if (!selectedProject || !selectedTask) {
      setComments([]);
      return;
    }
    let isActive = true;
    projectRequest<Comment[]>(
      `${baseUrl}/${selectedProject.id}/tasks/${selectedTask.id}/comments`,
      token,
    )
      .then((result) => {
        if (isActive) setComments(result);
      })
      .catch((requestError: unknown) => {
        if (isActive) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Task comments could not be loaded.",
          );
        }
      });
    return () => {
      isActive = false;
    };
  }, [baseUrl, selectedProject, selectedTask, token]);

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    try {
      const created = await projectRequest<Project>(baseUrl, token, {
        method: "POST",
        body: JSON.stringify({
          name: projectName,
          description: projectDescription || null,
        }),
      });
      setProjectName("");
      setProjectDescription("");
      setSelectedProject(created);
      setSelectedTask(null);
      setTaskPage(1);
      await loadProjects();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Project could not be created.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProject) return;
    setIsSaving(true);
    setError("");
    try {
      await projectRequest<ProjectTask>(
        `${baseUrl}/${selectedProject.id}/tasks`,
        token,
        {
          method: "POST",
          body: JSON.stringify({
            title: taskTitle,
            description: taskDescription || null,
            priority: taskPriority,
            due_date: taskDueDate || null,
            assigned_to: taskAssignee || null,
          }),
        },
      );
      setTaskTitle("");
      setTaskDescription("");
      setTaskPriority("medium");
      setTaskDueDate("");
      setTaskAssignee("");
      await Promise.all([loadTasks(), loadActivities()]);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Task could not be created.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function loadActivities() {
    if (!selectedProject) return;
    try {
      setActivities(
        await projectRequest<Activity[]>(
          `${baseUrl}/${selectedProject.id}/activities`,
          token,
        ),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Project activity could not be loaded.",
      );
    }
  }

  async function updateProjectStatus(nextStatus: ProjectStatus) {
    if (!selectedProject) return;
    try {
      const updated = await projectRequest<Project>(
        `${baseUrl}/${selectedProject.id}`,
        token,
        {
          method: "PATCH",
          body: JSON.stringify({ status: nextStatus }),
        },
      );
      setSelectedProject(updated);
      await Promise.all([loadProjects(), loadActivities()]);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Project status could not be changed.",
      );
    }
  }

  async function updateTaskStatus(task: ProjectTask, nextStatus: TaskStatus) {
    if (!selectedProject) return;
    try {
      await projectRequest<ProjectTask>(
        `${baseUrl}/${selectedProject.id}/tasks/${task.id}`,
        token,
        {
          method: "PATCH",
          body: JSON.stringify({ status: nextStatus }),
        },
      );
      await Promise.all([loadTasks(), loadActivities()]);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Task status could not be changed.",
      );
    }
  }

  async function submitComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProject || !selectedTask) return;
    setIsSaving(true);
    setError("");
    try {
      await projectRequest<Comment>(
        `${baseUrl}/${selectedProject.id}/tasks/${selectedTask.id}/comments`,
        token,
        {
          method: "POST",
          body: JSON.stringify({ body: commentDraft }),
        },
      );
      setCommentDraft("");
      const [nextComments, nextActivities] = await Promise.all([
        projectRequest<Comment[]>(
          `${baseUrl}/${selectedProject.id}/tasks/${selectedTask.id}/comments`,
          token,
        ),
        projectRequest<Activity[]>(
          `${baseUrl}/${selectedProject.id}/activities`,
          token,
        ),
      ]);
      setComments(nextComments);
      setActivities(nextActivities);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Comment could not be added.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function generateStatusDraft() {
    if (!selectedProject) return;
    setIsGeneratingDraft(true);
    setError("");
    setStatusDraft(null);
    try {
      setStatusDraft(
        await projectRequest<ProjectStatusDraft>(
          `/api/workspaces/${workspaceId}/assistant/projects/${selectedProject.id}/status-draft`,
          token,
          { method: "POST" },
        ),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "A project update draft could not be generated.",
      );
    } finally {
      setIsGeneratingDraft(false);
    }
  }

  function submitProjectSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProjectPage(1);
    setProjectSearch(projectSearchInput.trim());
  }

  function submitTaskSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTaskPage(1);
    setTaskSearch(taskSearchInput.trim());
  }

  const memberNames = new Map(members.map((member) => [member.id, member.display_name]));

  return (
    <section className="project-page" aria-labelledby="projects-title">
      <div className="project-heading">
        <div>
          <p className="eyebrow">PLANNING AND DELIVERY</p>
          <h1 id="projects-title">Projects</h1>
          <p className="welcome-copy">
            Coordinate work, ownership, priorities, and due dates.
          </p>
        </div>
        <button className="button-secondary" onClick={onBack} type="button">
          Back to workspace
        </button>
      </div>

      {error && (
        <p className="form-error project-error" role="alert">
          {error}
        </p>
      )}

      <div className="project-layout">
        <div className="project-main">
          <form className="project-toolbar" onSubmit={submitProjectSearch}>
            <label className="project-search">
              <span className="sr-only">Search projects</span>
              <input
                onChange={(event) => setProjectSearchInput(event.target.value)}
                placeholder="Search projects…"
                value={projectSearchInput}
              />
            </label>
            <label className="project-select">
              <span className="sr-only">Filter projects by status</span>
              <select
                onChange={(event) => {
                  setProjectStatusFilter(event.target.value);
                  setProjectPage(1);
                }}
                value={projectStatusFilter}
              >
                <option value="">All project statuses</option>
                {PROJECT_STATUSES.map((value) => (
                  <option key={value} value={value}>
                    {pretty(value)}
                  </option>
                ))}
              </select>
            </label>
            <button className="button-secondary" type="submit">
              Search
            </button>
          </form>
          <div className="project-columns">
            <section className="project-list-panel" aria-label="Project list">
              <div className="project-panel-heading">
                <h2>Workspace projects</h2>
                <span>{projects.total}</span>
              </div>
              {isLoadingProjects ? (
                <p className="project-state" aria-live="polite">
                  Loading projects…
                </p>
              ) : projects.items.length === 0 ? (
                <div className="project-empty">
                  <h3>No projects yet</h3>
                  <p>Create a project to give work a shared home.</p>
                </div>
              ) : (
                <div className="project-record-list">
                  {projects.items.map((project) => (
                    <button
                      aria-current={
                        selectedProject?.id === project.id ? "true" : undefined
                      }
                      className={`project-record${selectedProject?.id === project.id ? " project-record--selected" : ""}`}
                      key={project.id}
                      onClick={() => {
                        setSelectedProject(project);
                        setSelectedTask(null);
                        setStatusDraft(null);
                        setTaskPage(1);
                        setTaskSearch("");
                        setTaskSearchInput("");
                        setTaskStatusFilter("");
                      }}
                      type="button"
                    >
                      <span className="project-record-title">{project.name}</span>
                      <span
                        className={`project-status project-status--${project.status}`}
                      >
                        {pretty(project.status)}
                      </span>
                      <span className="project-record-description">
                        {project.description || "No description"}
                      </span>
                    </button>
                  ))}
                </div>
              )}
              {projects.total > PAGE_SIZE && (
                <div className="project-pagination">
                  <span>
                    Page {projects.page} of{" "}
                    {Math.ceil(projects.total / projects.page_size)}
                  </span>
                  <button
                    className="button-secondary"
                    disabled={projectPage <= 1}
                    onClick={() =>
                      setProjectPage((current) => Math.max(current - 1, 1))
                    }
                    type="button"
                  >
                    Previous
                  </button>
                  <button
                    className="button-secondary"
                    disabled={projectPage * projects.page_size >= projects.total}
                    onClick={() => setProjectPage((current) => current + 1)}
                    type="button"
                  >
                    Next
                  </button>
                </div>
              )}
            </section>

            <section className="task-panel" aria-label="Project tasks">
              {!selectedProject ? (
                <div className="project-empty project-empty--large">
                  <h2>Select a project</h2>
                  <p>Choose a project to see its tasks and activity.</p>
                </div>
              ) : (
                <>
                  <div className="project-panel-heading task-panel-heading">
                    <div>
                      <p className="eyebrow">TASKS</p>
                      <h2>{selectedProject.name}</h2>
                    </div>
                    <label className="project-select">
                      <span className="sr-only">
                        Status for {selectedProject.name}
                      </span>
                      <select
                        aria-label={`Status for ${selectedProject.name}`}
                        onChange={(event) =>
                          void updateProjectStatus(
                            event.target.value as ProjectStatus,
                          )
                        }
                        value={selectedProject.status}
                      >
                        {PROJECT_STATUSES.map((value) => (
                          <option key={value} value={value}>
                            {pretty(value)}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <form className="task-toolbar" onSubmit={submitTaskSearch}>
                    <label className="project-search">
                      <span className="sr-only">Search tasks</span>
                      <input
                        onChange={(event) => setTaskSearchInput(event.target.value)}
                        placeholder="Search tasks…"
                        value={taskSearchInput}
                      />
                    </label>
                    <label className="project-select">
                      <span className="sr-only">Filter tasks by status</span>
                      <select
                        onChange={(event) => {
                          setTaskStatusFilter(event.target.value);
                          setTaskPage(1);
                        }}
                        value={taskStatusFilter}
                      >
                        <option value="">All task statuses</option>
                        {TASK_STATUSES.map((value) => (
                          <option key={value} value={value}>
                            {pretty(value)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button className="button-secondary" type="submit">
                      Search
                    </button>
                  </form>
                  {isLoadingTasks ? (
                    <p className="project-state" aria-live="polite">
                      Loading tasks…
                    </p>
                  ) : tasks.items.length === 0 ? (
                    <div className="project-empty">
                      <h3>No tasks in this view</h3>
                      <p>Add a task or change the current search and filter.</p>
                    </div>
                  ) : (
                    <div className="task-list">
                      {tasks.items.map((task) => (
                        <article
                          className={`task-record${selectedTask?.id === task.id ? " task-record--selected" : ""}`}
                          key={task.id}
                        >
                          <div className="task-record-content">
                            <button
                              className="task-record-title"
                              onClick={() => setSelectedTask(task)}
                              type="button"
                            >
                              {task.title}
                            </button>
                            <p>
                              {task.assigned_to
                                ? memberNames.get(task.assigned_to) ?? "Assigned"
                                : "Unassigned"}
                              {task.due_date
                                ? ` · Due ${formattedDate(`${task.due_date}T00:00:00`)}`
                                : ""}
                            </p>
                          </div>
                          <div className="task-record-meta">
                            <span className={`priority priority--${task.priority}`}>
                              {pretty(task.priority)}
                            </span>
                            <label className="project-select">
                              <span className="sr-only">
                                Status for {task.title}
                              </span>
                              <select
                                onChange={(event) =>
                                  void updateTaskStatus(
                                    task,
                                    event.target.value as TaskStatus,
                                  )
                                }
                                value={task.status}
                              >
                                {TASK_STATUSES.map((value) => (
                                  <option key={value} value={value}>
                                    {pretty(value)}
                                  </option>
                                ))}
                              </select>
                            </label>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                  {tasks.total > PAGE_SIZE && (
                    <div className="project-pagination">
                      <span>
                        Page {tasks.page} of{" "}
                        {Math.ceil(tasks.total / tasks.page_size)}
                      </span>
                      <button
                        className="button-secondary"
                        disabled={taskPage <= 1}
                        onClick={() =>
                          setTaskPage((current) => Math.max(current - 1, 1))
                        }
                        type="button"
                      >
                        Previous
                      </button>
                      <button
                        className="button-secondary"
                        disabled={taskPage * tasks.page_size >= tasks.total}
                        onClick={() => setTaskPage((current) => current + 1)}
                        type="button"
                      >
                        Next
                      </button>
                    </div>
                  )}
                </>
              )}
            </section>
          </div>
        </div>

        <aside className="project-side">
          {!selectedProject ? (
            <form className="project-form" onSubmit={createProject}>
              <h2>Create a project</h2>
              <label className="form-field">
                <span>Project name</span>
                <input
                  maxLength={120}
                  onChange={(event) => setProjectName(event.target.value)}
                  required
                  value={projectName}
                />
              </label>
              <label className="form-field">
                <span>Description</span>
                <textarea
                  maxLength={5000}
                  onChange={(event) =>
                    setProjectDescription(event.target.value)
                  }
                  rows={3}
                  value={projectDescription}
                />
              </label>
              <button
                className="button-primary button-primary--wide"
                disabled={isSaving}
                type="submit"
              >
                {isSaving ? "Saving…" : "Create project"}
              </button>
            </form>
          ) : (
            <>
              <section className="project-assistant" aria-labelledby="project-assistant-title">
                <p className="eyebrow">MOCK PROVIDER · NO EXTERNAL AI</p>
                <h2 id="project-assistant-title">Draft a status update</h2>
                <p>
                  On request, use this project’s tasks and recent activity to
                  prepare a draft. Review it before sharing.
                </p>
                <button
                  className="button-secondary"
                  disabled={isGeneratingDraft}
                  onClick={() => void generateStatusDraft()}
                  type="button"
                >
                  {isGeneratingDraft ? "Preparing draft…" : "Generate draft"}
                </button>
                {statusDraft && (
                  <div className="project-assistant-result">
                    <label className="form-field" htmlFor="status-draft">
                      Edit draft
                      <textarea
                        id="status-draft"
                        maxLength={1200}
                        onChange={(event) =>
                          setStatusDraft({
                            ...statusDraft,
                            draft: event.target.value,
                          })
                        }
                        rows={5}
                        value={statusDraft.draft}
                      />
                    </label>
                    <p className="project-assistant-disclaimer">
                      {statusDraft.disclaimer}
                    </p>
                  </div>
                )}
              </section>
              {selectedTask ? (
                <section className="task-discussion" aria-label="Task discussion">
                  <div className="discussion-heading">
                    <div>
                      <p className="eyebrow">TASK DISCUSSION</p>
                      <h2>{selectedTask.title}</h2>
                    </div>
                    <button
                      aria-label="Close task discussion"
                      className="button-link"
                      onClick={() => setSelectedTask(null)}
                      type="button"
                    >
                      Close
                    </button>
                  </div>
                  <form onSubmit={submitComment}>
                    <label className="sr-only" htmlFor="task-comment">
                      Add a comment
                    </label>
                    <textarea
                      id="task-comment"
                      maxLength={5000}
                      onChange={(event) => setCommentDraft(event.target.value)}
                      placeholder="Share an update…"
                      required
                      rows={3}
                      value={commentDraft}
                    />
                    <button
                      className="button-primary button-primary--wide"
                      disabled={isSaving}
                      type="submit"
                    >
                      {isSaving ? "Saving…" : "Add comment"}
                    </button>
                  </form>
                  <div className="project-history">
                    {comments.length === 0 ? (
                      <p className="project-muted">No comments yet.</p>
                    ) : (
                      comments.map((comment) => (
                        <article className="project-history-item" key={comment.id}>
                          <p>{comment.body}</p>
                          <time dateTime={comment.created_at}>
                            {formattedDate(comment.created_at)}
                          </time>
                        </article>
                      ))
                    )}
                  </div>
                </section>
              ) : (
                <form className="project-form" onSubmit={createTask}>
                  <h2>Add a task</h2>
                  <label className="form-field">
                    <span>Task title</span>
                    <input
                      maxLength={160}
                      onChange={(event) => setTaskTitle(event.target.value)}
                      required
                      value={taskTitle}
                    />
                  </label>
                  <label className="form-field">
                    <span>Description</span>
                    <textarea
                      maxLength={5000}
                      onChange={(event) =>
                        setTaskDescription(event.target.value)
                      }
                      rows={3}
                      value={taskDescription}
                    />
                  </label>
                  <label className="form-field">
                    <span>Priority</span>
                    <select
                      onChange={(event) =>
                        setTaskPriority(event.target.value as TaskPriority)
                      }
                      value={taskPriority}
                    >
                      {TASK_PRIORITIES.map((value) => (
                        <option key={value} value={value}>
                          {pretty(value)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="form-field">
                    <span>Due date</span>
                    <input
                      onChange={(event) => setTaskDueDate(event.target.value)}
                      type="date"
                      value={taskDueDate}
                    />
                  </label>
                  <label className="form-field">
                    <span>Assignee</span>
                    <select
                      onChange={(event) => setTaskAssignee(event.target.value)}
                      value={taskAssignee}
                    >
                      <option value="">Unassigned</option>
                      {members.map((member) => (
                        <option key={member.id} value={member.id}>
                          {member.display_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="button-primary button-primary--wide"
                    disabled={isSaving}
                    type="submit"
                  >
                    {isSaving ? "Saving…" : "Create task"}
                  </button>
                </form>
              )}
              <section className="project-activity" aria-labelledby="project-activity-title">
                <p className="eyebrow">RECENT UPDATES</p>
                <h2 id="project-activity-title">Project activity</h2>
                {activities.length === 0 ? (
                  <p className="project-muted">No activity recorded yet.</p>
                ) : (
                  <div className="project-history">
                    {activities.map((activity) => (
                      <article className="project-history-item" key={activity.id}>
                        <p>{activity.summary}</p>
                        <time dateTime={activity.created_at}>
                          {formattedDate(activity.created_at)}
                        </time>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </aside>
      </div>
    </section>
  );
}
