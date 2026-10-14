import { useEffect, useState, type FormEvent } from "react";
import { readCsrfToken, sessionFetch } from "./api";
import CrmPage from "./CrmPage";
import ProjectsPage from "./ProjectsPage";
import TeamPage from "./TeamPage";

type ApiStatus = "checking" | "connected" | "unavailable";
type Route =
  | "/"
  | "/login"
  | "/register"
  | "/app"
  | "/app/crm"
  | "/app/projects"
  | "/app/team";
type SessionResponse = {
  expires_in: number;
};
type User = {
  id: string;
  email: string;
  display_name: string;
};
type Workspace = {
  id: string;
  name: string;
  slug: string;
  role: string;
};

async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) {
    headers.set("Content-Type", "application/json");
  }

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
        : "We could not complete that request. Please try again.";
    throw new Error(message);
  }
  return payload as T;
}

function App() {
  const [route, setRoute] = useState<Route>(currentRoute());
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [logoutError, setLogoutError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/health/ready", { signal: controller.signal })
      .then((response) => {
        setApiStatus(response.ok ? "connected" : "unavailable");
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setApiStatus("unavailable");
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const onPopState = () => setRoute(currentRoute());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function navigate(path: Route) {
    window.history.pushState({}, "", path);
    setRoute(path);
  }

  async function signOut() {
    setLogoutError("");
    try {
      await apiRequest<void>("/api/auth/logout", { method: "POST" });
      navigate("/");
    } catch (requestError) {
      setLogoutError(
        requestError instanceof Error
          ? requestError.message
          : "We could not end your session. Please try again.",
      );
    }
  }

  const statusLabel = {
    checking: "Checking services",
    connected: "All systems ready",
    unavailable: "Service unavailable",
  }[apiStatus];

  return (
    <main className="workspace">
      <header className="topbar">
        <a
          className="brand"
          href="/"
          aria-label="WorkSphere home"
          onClick={(event) => {
            event.preventDefault();
            navigate("/");
          }}
        >
          <span className="brand-mark" aria-hidden="true">
            W
          </span>
          <span>worksphere</span>
        </a>
        {route === "/app" ||
        route === "/app/crm" ||
        route === "/app/projects" ||
        route === "/app/team" ? (
          <button
            className="button-link"
            type="button"
            onClick={() => void signOut()}
          >
            Sign out
          </button>
        ) : (
          <span className={`service-status service-status--${apiStatus}`}>
            <span className="status-dot" aria-hidden="true" />
            {statusLabel}
          </span>
        )}
      </header>

      {route === "/login" ? (
        <AuthForm mode="login" navigate={navigate} />
      ) : route === "/register" ? (
        <AuthForm mode="register" navigate={navigate} />
      ) : route === "/app" ||
        route === "/app/crm" ||
        route === "/app/projects" ||
        route === "/app/team" ? (
        <ProtectedWorkspace
          navigate={navigate}
          showCRM={route === "/app/crm"}
          showProjects={route === "/app/projects"}
          showTeam={route === "/app/team"}
        />
      ) : (
        <LandingPage navigate={navigate} />
      )}

      {logoutError && (
        <p className="form-error" role="alert">
          {logoutError}
        </p>
      )}

      <footer className="footer">
        <span>WorkSphere · Early access foundation</span>
        <span>Built for thoughtful teamwork</span>
      </footer>
    </main>
  );
}

function LandingPage({ navigate }: { navigate: (path: Route) => void }) {
  return (
    <>
      <section className="welcome" aria-labelledby="welcome-title">
        <p className="eyebrow">YOUR WORKSPACE</p>
        <h1 id="welcome-title">Good work happens together.</h1>
        <p className="welcome-copy">
          A calmer place to bring your people, customers, and projects into
          focus.
        </p>
        <div className="welcome-actions">
          <button
            className="button-primary"
            type="button"
            onClick={() => navigate("/register")}
          >
            Create a workspace
          </button>
          <button
            className="button-secondary"
            type="button"
            onClick={() => navigate("/login")}
          >
            Sign in
          </button>
        </div>
      </section>

      <section className="module-grid" aria-label="Workspace modules">
        <article className="module-card">
          <span className="module-icon module-icon--amber" aria-hidden="true">
            C
          </span>
          <div>
            <h2>Customer relationships</h2>
            <p>Keep conversations and opportunities moving.</p>
          </div>
          <span className="module-state">Coming next</span>
        </article>
        <article className="module-card">
          <span className="module-icon module-icon--blue" aria-hidden="true">
            P
          </span>
          <div>
            <h2>Projects and plans</h2>
            <p>Give shared goals a clear path forward.</p>
          </div>
          <span className="module-state">Coming next</span>
        </article>
        <article className="module-card">
          <span className="module-icon module-icon--green" aria-hidden="true">
            T
          </span>
          <div>
            <h2>People and teams</h2>
            <p>Make room for the people behind the work.</p>
          </div>
          <span className="module-state">Coming next</span>
        </article>
      </section>
    </>
  );
}

function AuthForm({
  mode,
  navigate,
}: {
  mode: "login" | "register";
  navigate: (path: Route) => void;
}) {
  const isRegister = mode === "register";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      await apiRequest<SessionResponse>(
        `/api/auth/${mode}`,
        {
          method: "POST",
          body: JSON.stringify(
            isRegister
              ? {
                  email,
                  password,
                  display_name: displayName,
                  workspace_name: workspaceName,
                }
              : { email, password },
          ),
        },
      );
      navigate("/app");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "We could not complete that request. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="auth-layout" aria-labelledby="auth-title">
      <div className="auth-card">
        <p className="eyebrow">{isRegister ? "GET STARTED" : "WELCOME BACK"}</p>
        <h1 id="auth-title">
          {isRegister ? "Create your workspace" : "Sign in to WorkSphere"}
        </h1>
        <p className="auth-intro">
          {isRegister
            ? "Set up your account and invite your team when you're ready."
            : "Pick up where your team left off."}
        </p>
        <form onSubmit={submit}>
          {isRegister && (
            <>
              <label className="form-field">
                <span>Your name</span>
                <input
                  autoComplete="name"
                  maxLength={120}
                  minLength={1}
                  onChange={(event) => setDisplayName(event.target.value)}
                  required
                  value={displayName}
                />
              </label>
              <label className="form-field">
                <span>Workspace name</span>
                <input
                  autoComplete="organization"
                  maxLength={120}
                  minLength={2}
                  onChange={(event) => setWorkspaceName(event.target.value)}
                  required
                  value={workspaceName}
                />
              </label>
            </>
          )}
          <label className="form-field">
            <span>Email</span>
            <input
              autoComplete="email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </label>
          <div className="form-field">
            <label htmlFor="auth-password">Password</label>
            <input
              aria-describedby={isRegister ? "password-hint" : undefined}
              autoComplete={isRegister ? "new-password" : "current-password"}
              id="auth-password"
              maxLength={128}
              minLength={isRegister ? 12 : 1}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
            {isRegister && (
              <span className="field-hint" id="password-hint">
                Use at least 12 characters.
              </span>
            )}
          </div>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button
            className="button-primary button-primary--wide"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting
              ? "Please wait…"
              : isRegister
                ? "Create workspace"
                : "Sign in"}
          </button>
        </form>
        <p className="auth-switch">
          {isRegister ? "Already have an account?" : "New to WorkSphere?"}{" "}
          <button
            className="button-link"
            onClick={() => navigate(isRegister ? "/login" : "/register")}
            type="button"
          >
            {isRegister ? "Sign in" : "Create an account"}
          </button>
        </p>
      </div>
    </section>
  );
}

function ProtectedWorkspace({
  navigate,
  showCRM,
  showProjects,
  showTeam,
}: {
  navigate: (path: Route) => void;
  showCRM: boolean;
  showProjects: boolean;
  showTeam: boolean;
}) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isActive = true;
    Promise.all([
      apiRequest<Workspace>("/api/workspaces/current"),
      apiRequest<User>("/api/auth/me"),
    ])
      .then(([currentWorkspace, currentUser]) => {
        if (isActive) {
          setWorkspace(currentWorkspace);
          setUser(currentUser);
        }
      })
      .catch((requestError: unknown) => {
        if (isActive) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Your session could not be verified. Please sign in again.",
          );
        }
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });
    return () => {
      isActive = false;
    };
  }, []);

  if (isLoading) {
    return (
      <section className="app-content" aria-live="polite">
        <p className="eyebrow">YOUR WORKSPACE</p>
        <h1>Loading your workspace…</h1>
      </section>
    );
  }

  if (!workspace || !user) {
    return (
      <section className="app-content" aria-labelledby="protected-title">
        <p className="eyebrow">SIGN-IN REQUIRED</p>
        <h1 id="protected-title">Your workspace is private.</h1>
        <p className="welcome-copy" role="alert">
          {error}
        </p>
        <button
          className="button-primary"
          onClick={() => navigate("/login")}
          type="button"
        >
          Sign in
        </button>
      </section>
    );
  }

  if (showCRM) {
    return (
      <CrmPage
        workspaceId={workspace.id}
        token={readCsrfToken()}
        onBack={() => navigate("/app")}
      />
    );
  }

  if (showProjects) {
    return (
      <ProjectsPage
        workspaceId={workspace.id}
        token={readCsrfToken()}
        onBack={() => navigate("/app")}
      />
    );
  }

  if (showTeam) {
    return (
      <TeamPage
        workspaceId={workspace.id}
        token={readCsrfToken()}
        onBack={() => navigate("/app")}
      />
    );
  }

  return (
    <section className="app-content" aria-labelledby="workspace-title">
      <p className="eyebrow">SIGNED IN AS {user.email}</p>
      <h1 id="workspace-title">{workspace.name}</h1>
      <p className="welcome-copy">
        You are a {workspace.role} in this workspace. Your team workspace is
        ready for the next milestone.
      </p>
      <div className="workspace-summary">
        <span>Workspace address</span>
        <strong>{workspace.slug}</strong>
      </div>
      <div className="module-grid workspace-modules">
        <article className="module-card">
          <span className="module-icon module-icon--amber" aria-hidden="true">
            C
          </span>
          <div>
            <h2>Customer relationships</h2>
            <p>Companies, contacts, and a trackable lead pipeline.</p>
          </div>
          <button
            className="button-link"
            onClick={() => navigate("/app/crm")}
            type="button"
          >
            Open CRM
          </button>
        </article>
        <article className="module-card">
          <span className="module-icon module-icon--blue" aria-hidden="true">
            P
          </span>
          <div>
            <h2>Projects and plans</h2>
            <p>Organize tasks, deadlines, priorities, and team updates.</p>
          </div>
          <button
            className="button-link"
            onClick={() => navigate("/app/projects")}
            type="button"
          >
            Open projects
          </button>
        </article>
        <article className="module-card">
          <span className="module-icon module-icon--green" aria-hidden="true">
            T
          </span>
          <div>
            <h2>People and collaboration</h2>
            <p>Team channels, employee leave, and candidate pipelines.</p>
          </div>
          <button
            className="button-link"
            onClick={() => navigate("/app/team")}
            type="button"
          >
            Open team
          </button>
        </article>
      </div>
    </section>
  );
}

function currentRoute(): Route {
  const path = window.location.pathname;
  if (
    path === "/login" ||
    path === "/register" ||
    path === "/app" ||
    path === "/app/crm" ||
    path === "/app/projects" ||
    path === "/app/team"
  ) {
    return path;
  }
  return "/";
}

export default App;
