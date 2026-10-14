import { useCallback, useEffect, useState, type FormEvent } from "react";
import { sessionFetch } from "./api";

type TeamPageProps = {
  workspaceId: string;
  token: string;
  onBack: () => void;
};
type Tab = "communication" | "hr" | "ats";
type Channel = { id: string; name: string; description: string | null };
type Message = {
  id: string;
  channel_id: string;
  author_id: string;
  body: string;
  created_at: string;
};
type Department = { id: string; name: string };
type Employee = {
  id: string;
  department_id: string | null;
  first_name: string;
  last_name: string;
  email: string;
  job_title: string | null;
  start_date: string | null;
};
type LeaveRequest = {
  id: string;
  employee_id: string;
  start_date: string;
  end_date: string;
  reason: string | null;
  status: "pending" | "approved" | "rejected";
};
type Job = { id: string; title: string; department: string | null; status: string };
type Candidate = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
};
type Application = {
  id: string;
  candidate_id: string;
  job_id: string;
  status: string;
};
type ApplicationHistory = {
  id: string;
  from_status: string | null;
  to_status: string;
  created_at: string;
};

const APPLICATION_STAGES = [
  "applied",
  "screening",
  "interview",
  "offer",
  "hired",
  "rejected",
] as const;

async function teamRequest<T>(
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

function readable(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function dateLabel(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
    new Date(value.includes("T") ? value : `${value}T00:00:00`),
  );
}

export default function TeamPage({
  workspaceId,
  token,
  onBack,
}: TeamPageProps) {
  const [tab, setTab] = useState<Tab>("communication");
  const [channels, setChannels] = useState<Channel[]>([]);
  const [activeChannel, setActiveChannel] = useState<Channel | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [channelName, setChannelName] = useState("");
  const [messageDraft, setMessageDraft] = useState("");
  const [departments, setDepartments] = useState<Department[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [leaveRequests, setLeaveRequests] = useState<LeaveRequest[]>([]);
  const [departmentName, setDepartmentName] = useState("");
  const [employeeFirstName, setEmployeeFirstName] = useState("");
  const [employeeLastName, setEmployeeLastName] = useState("");
  const [employeeEmail, setEmployeeEmail] = useState("");
  const [employeeTitle, setEmployeeTitle] = useState("");
  const [employeeDepartment, setEmployeeDepartment] = useState("");
  const [leaveEmployee, setLeaveEmployee] = useState("");
  const [leaveStart, setLeaveStart] = useState("");
  const [leaveEnd, setLeaveEnd] = useState("");
  const [leaveReason, setLeaveReason] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [jobTitle, setJobTitle] = useState("");
  const [jobDepartment, setJobDepartment] = useState("");
  const [candidateFirstName, setCandidateFirstName] = useState("");
  const [candidateLastName, setCandidateLastName] = useState("");
  const [candidateEmail, setCandidateEmail] = useState("");
  const [candidateJob, setCandidateJob] = useState("");
  const [selectedApplication, setSelectedApplication] = useState<string | null>(
    null,
  );
  const [history, setHistory] = useState<ApplicationHistory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const baseUrl = `/api/workspaces/${workspaceId}`;

  const loadChannels = useCallback(async () => {
    setError("");
    try {
      const results = await teamRequest<Channel[]>(
        `${baseUrl}/communication/channels`,
        token,
      );
      setChannels(results);
      if (!activeChannel && results.length) setActiveChannel(results[0]);
      if (activeChannel && !results.some((channel) => channel.id === activeChannel.id)) {
        setActiveChannel(results[0] ?? null);
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Channels could not be loaded.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [activeChannel, baseUrl, token]);

  const loadMessages = useCallback(async () => {
    if (!activeChannel) {
      setMessages([]);
      return;
    }
    try {
      setMessages(
        await teamRequest<Message[]>(
          `${baseUrl}/communication/channels/${activeChannel.id}/messages?limit=50`,
          token,
        ),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Messages could not be loaded.",
      );
    }
  }, [activeChannel, baseUrl, token]);

  const loadHR = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [nextDepartments, nextEmployees, nextLeave] = await Promise.all([
        teamRequest<Department[]>(`${baseUrl}/hr/departments`, token),
        teamRequest<Employee[]>(`${baseUrl}/hr/employees`, token),
        teamRequest<LeaveRequest[]>(`${baseUrl}/hr/leave-requests`, token),
      ]);
      setDepartments(nextDepartments);
      setEmployees(nextEmployees);
      setLeaveRequests(nextLeave);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "HR records could not be loaded.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [baseUrl, token]);

  const loadATS = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [nextJobs, nextCandidates, nextApplications] = await Promise.all([
        teamRequest<Job[]>(`${baseUrl}/ats/jobs`, token),
        teamRequest<Candidate[]>(`${baseUrl}/ats/candidates`, token),
        teamRequest<Application[]>(`${baseUrl}/ats/applications`, token),
      ]);
      setJobs(nextJobs);
      setCandidates(nextCandidates);
      setApplications(nextApplications);
      if (candidateJob === "" && nextJobs.length) setCandidateJob(nextJobs[0].id);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Applicant records could not be loaded.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [baseUrl, candidateJob, token]);

  useEffect(() => {
    if (tab === "communication") {
      void loadChannels();
    } else if (tab === "hr") {
      void loadHR();
    } else {
      void loadATS();
    }
  }, [tab, loadATS, loadChannels, loadHR]);

  useEffect(() => {
    if (tab !== "communication") return;
    void loadMessages();
    const interval = window.setInterval(() => void loadMessages(), 5000);
    return () => window.clearInterval(interval);
  }, [activeChannel, loadMessages, tab]);

  async function createChannel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError("");
    try {
      const channel = await teamRequest<Channel>(
        `${baseUrl}/communication/channels`,
        token,
        {
          method: "POST",
          body: JSON.stringify({ name: channelName }),
        },
      );
      setChannelName("");
      setChannels((current) => [...current, channel]);
      setActiveChannel(channel);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Channel could not be created.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChannel) return;
    setIsSaving(true);
    setError("");
    try {
      await teamRequest<Message>(
        `${baseUrl}/communication/channels/${activeChannel.id}/messages`,
        token,
        {
          method: "POST",
          body: JSON.stringify({ body: messageDraft }),
        },
      );
      setMessageDraft("");
      await loadMessages();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Message could not be sent.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function createDepartment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await mutate(
      `${baseUrl}/hr/departments`,
      { name: departmentName },
      async () => {
        setDepartmentName("");
        await loadHR();
      },
    );
  }

  async function createEmployee(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await mutate(
      `${baseUrl}/hr/employees`,
      {
        first_name: employeeFirstName,
        last_name: employeeLastName,
        email: employeeEmail,
        job_title: employeeTitle || null,
        department_id: employeeDepartment || null,
      },
      async () => {
        setEmployeeFirstName("");
        setEmployeeLastName("");
        setEmployeeEmail("");
        setEmployeeTitle("");
        await loadHR();
      },
    );
  }

  async function createLeave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await mutate(
      `${baseUrl}/hr/leave-requests`,
      {
        employee_id: leaveEmployee,
        start_date: leaveStart,
        end_date: leaveEnd,
        reason: leaveReason || null,
      },
      async () => {
        setLeaveStart("");
        setLeaveEnd("");
        setLeaveReason("");
        await loadHR();
      },
    );
  }

  async function reviewLeave(request: LeaveRequest, status: "approved" | "rejected") {
    await mutate(
      `${baseUrl}/hr/leave-requests/${request.id}`,
      { status },
      loadHR,
      "PATCH",
    );
  }

  async function createJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await mutate(
      `${baseUrl}/ats/jobs`,
      { title: jobTitle, department: jobDepartment || null },
      async () => {
        setJobTitle("");
        setJobDepartment("");
        await loadATS();
      },
    );
  }

  async function createCandidate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await mutate(
      `${baseUrl}/ats/candidates`,
      {
        first_name: candidateFirstName,
        last_name: candidateLastName,
        email: candidateEmail,
        job_id: candidateJob,
      },
      async () => {
        setCandidateFirstName("");
        setCandidateLastName("");
        setCandidateEmail("");
        await loadATS();
      },
    );
  }

  async function updateApplication(application: Application, status: string) {
    await mutate(
      `${baseUrl}/ats/applications/${application.id}`,
      { status },
      async () => {
        await loadATS();
        await loadApplicationHistory(application.id);
      },
      "PATCH",
    );
  }

  async function loadApplicationHistory(applicationId: string) {
    setSelectedApplication(applicationId);
    try {
      setHistory(
        await teamRequest<ApplicationHistory[]>(
          `${baseUrl}/ats/applications/${applicationId}/history`,
          token,
        ),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Application history could not be loaded.",
      );
    }
  }

  async function mutate(
    path: string,
    body: Record<string, unknown>,
    onSuccess: () => Promise<void>,
    method = "POST",
  ) {
    setIsSaving(true);
    setError("");
    try {
      await teamRequest(path, token, {
        method,
        body: JSON.stringify(body),
      });
      await onSuccess();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The record could not be saved.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  const employeeNames = new Map(
    employees.map((employee) => [
      employee.id,
      `${employee.first_name} ${employee.last_name}`,
    ]),
  );
  const departmentNames = new Map(
    departments.map((department) => [department.id, department.name]),
  );
  const candidateNames = new Map(
    candidates.map((candidate) => [
      candidate.id,
      `${candidate.first_name} ${candidate.last_name}`,
    ]),
  );
  const jobNames = new Map(jobs.map((job) => [job.id, job.title]));

  return (
    <section className="team-page" aria-labelledby="team-title">
      <div className="team-heading">
        <div>
          <p className="eyebrow">PEOPLE AND COLLABORATION</p>
          <h1 id="team-title">Team</h1>
          <p className="welcome-copy">
            Messages, people operations, and candidate pipelines in one place.
          </p>
        </div>
        <button className="button-secondary" onClick={onBack} type="button">
          Back to workspace
        </button>
      </div>
      <nav className="team-tabs" aria-label="Team modules">
        {(["communication", "hr", "ats"] as const).map((item) => (
          <button
            aria-current={tab === item ? "page" : undefined}
            className={`team-tab${tab === item ? " team-tab--active" : ""}`}
            key={item}
            onClick={() => setTab(item)}
            type="button"
          >
            {item === "communication"
              ? "Communication"
              : item === "hr"
                ? "People"
                : "Hiring"}
          </button>
        ))}
      </nav>
      {error && (
        <p className="form-error team-error" role="alert">
          {error}
        </p>
      )}

      {tab === "communication" ? (
        <div className="team-layout">
          <section className="team-panel channel-panel" aria-label="Channels">
            <div className="team-panel-heading">
              <h2>Channels</h2>
            </div>
            {isLoading ? (
              <p className="team-state">Loading channels…</p>
            ) : channels.length === 0 ? (
              <p className="team-empty">Create the first channel for your team.</p>
            ) : (
              <div className="channel-list">
                {channels.map((channel) => (
                  <button
                    aria-current={activeChannel?.id === channel.id ? "true" : undefined}
                    className={`channel-choice${activeChannel?.id === channel.id ? " channel-choice--active" : ""}`}
                    key={channel.id}
                    onClick={() => setActiveChannel(channel)}
                    type="button"
                  >
                    <span aria-hidden="true">#</span>
                    {channel.name}
                  </button>
                ))}
              </div>
            )}
            <form className="team-form channel-create" onSubmit={createChannel}>
              <label className="form-field">
                <span>New channel</span>
                <input
                  maxLength={80}
                  onChange={(event) => setChannelName(event.target.value)}
                  required
                  value={channelName}
                />
              </label>
              <button className="button-primary button-primary--wide" disabled={isSaving}>
                Create channel
              </button>
            </form>
          </section>
          <section className="team-panel conversation-panel" aria-label="Messages">
            <div className="team-panel-heading">
              <h2>{activeChannel ? `# ${activeChannel.name}` : "Select a channel"}</h2>
              <span className="team-polling">Updates every 5 seconds</span>
            </div>
            {!activeChannel ? (
              <p className="team-empty">Choose a channel or create one to start a conversation.</p>
            ) : (
              <>
                <div className="message-list" aria-live="polite">
                  {messages.length === 0 ? (
                    <p className="team-empty">No messages yet. Start the conversation.</p>
                  ) : (
                    messages.map((message) => (
                      <article className="message-item" key={message.id}>
                        <p>{message.body}</p>
                        <time dateTime={message.created_at}>
                          {dateLabel(message.created_at)}
                        </time>
                      </article>
                    ))
                  )}
                </div>
                <form className="message-composer" onSubmit={sendMessage}>
                  <label className="sr-only" htmlFor="channel-message">
                    Write a message
                  </label>
                  <textarea
                    id="channel-message"
                    maxLength={5000}
                    onChange={(event) => setMessageDraft(event.target.value)}
                    placeholder={`Message #${activeChannel.name}`}
                    required
                    rows={3}
                    value={messageDraft}
                  />
                  <button className="button-primary" disabled={isSaving}>
                    Send
                  </button>
                </form>
              </>
            )}
          </section>
        </div>
      ) : tab === "hr" ? (
        <div className="team-layout team-layout--hr">
          <section className="team-panel">
            <div className="team-panel-heading"><h2>Departments</h2></div>
            <div className="team-inline-form">
              <form onSubmit={createDepartment}>
                <label className="form-field">
                  <span>Department name</span>
                  <input
                    maxLength={100}
                    onChange={(event) => setDepartmentName(event.target.value)}
                    required
                    value={departmentName}
                  />
                </label>
                <button className="button-secondary" disabled={isSaving}>Add</button>
              </form>
            </div>
            {departments.map((department) => (
              <div className="team-list-row" key={department.id}>
                <strong>{department.name}</strong>
              </div>
            ))}
          </section>
          <section className="team-panel">
            <div className="team-panel-heading"><h2>Employees</h2></div>
            {isLoading ? <p className="team-state">Loading people…</p> : employees.length === 0 ? (
              <p className="team-empty">No employee profiles yet.</p>
            ) : employees.map((employee) => (
              <article className="team-list-row" key={employee.id}>
                <div>
                  <strong>{employee.first_name} {employee.last_name}</strong>
                  <p>{employee.job_title || employee.email}</p>
                </div>
                <span>{employee.department_id ? departmentNames.get(employee.department_id) : "Unassigned"}</span>
              </article>
            ))}
            <form className="team-form team-form--embedded" onSubmit={createEmployee}>
              <h3>Add employee profile</h3>
              <div className="team-form-grid">
                <label className="form-field"><span>First name</span><input maxLength={80} onChange={(event) => setEmployeeFirstName(event.target.value)} required value={employeeFirstName} /></label>
                <label className="form-field"><span>Last name</span><input maxLength={80} onChange={(event) => setEmployeeLastName(event.target.value)} required value={employeeLastName} /></label>
              </div>
              <label className="form-field"><span>Work email</span><input onChange={(event) => setEmployeeEmail(event.target.value)} required type="email" value={employeeEmail} /></label>
              <label className="form-field"><span>Job title</span><input maxLength={120} onChange={(event) => setEmployeeTitle(event.target.value)} value={employeeTitle} /></label>
              <label className="form-field"><span>Department</span><select onChange={(event) => setEmployeeDepartment(event.target.value)} value={employeeDepartment}><option value="">Unassigned</option>{departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}</select></label>
              <button className="button-primary button-primary--wide" disabled={isSaving}>Add employee</button>
            </form>
          </section>
          <section className="team-panel">
            <div className="team-panel-heading"><h2>Leave requests</h2></div>
            {leaveRequests.length === 0 ? <p className="team-empty">No requests to review.</p> : leaveRequests.map((request) => (
              <article className="team-list-row team-leave-row" key={request.id}>
                <div>
                  <strong>{employeeNames.get(request.employee_id) || "Employee"}</strong>
                  <p>{dateLabel(request.start_date)} – {dateLabel(request.end_date)}</p>
                  {request.reason && <p>{request.reason}</p>}
                </div>
                {request.status === "pending" ? <div className="team-action-group"><button className="button-secondary" onClick={() => void reviewLeave(request, "approved")} type="button">Approve</button><button className="button-secondary" onClick={() => void reviewLeave(request, "rejected")} type="button">Reject</button></div> : <span className={`project-status project-status--${request.status === "approved" ? "active" : "on_hold"}`}>{readable(request.status)}</span>}
              </article>
            ))}
            <form className="team-form team-form--embedded" onSubmit={createLeave}>
              <h3>Submit leave request</h3>
              <label className="form-field"><span>Employee</span><select onChange={(event) => setLeaveEmployee(event.target.value)} required value={leaveEmployee}><option value="">Select employee</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.first_name} {employee.last_name}</option>)}</select></label>
              <div className="team-form-grid">
                <label className="form-field"><span>From</span><input onChange={(event) => setLeaveStart(event.target.value)} required type="date" value={leaveStart} /></label>
                <label className="form-field"><span>Through</span><input onChange={(event) => setLeaveEnd(event.target.value)} required type="date" value={leaveEnd} /></label>
              </div>
              <label className="form-field"><span>Reason</span><input maxLength={500} onChange={(event) => setLeaveReason(event.target.value)} value={leaveReason} /></label>
              <button className="button-primary button-primary--wide" disabled={isSaving || employees.length === 0}>Submit request</button>
            </form>
          </section>
        </div>
      ) : (
        <div className="team-layout team-layout--ats">
          <section className="team-panel">
            <div className="team-panel-heading"><h2>Open roles</h2></div>
            {jobs.length === 0 ? <p className="team-empty">Create an opening to start a pipeline.</p> : jobs.map((job) => (
              <article className="team-list-row" key={job.id}>
                <div><strong>{job.title}</strong><p>{job.department || "General"} · {readable(job.status)}</p></div>
              </article>
            ))}
            <form className="team-form team-form--embedded" onSubmit={createJob}>
              <h3>Create job opening</h3>
              <label className="form-field"><span>Job title</span><input maxLength={140} onChange={(event) => setJobTitle(event.target.value)} required value={jobTitle} /></label>
              <label className="form-field"><span>Department</span><input maxLength={100} onChange={(event) => setJobDepartment(event.target.value)} value={jobDepartment} /></label>
              <button className="button-primary button-primary--wide" disabled={isSaving}>Create opening</button>
            </form>
          </section>
          <section className="team-panel">
            <div className="team-panel-heading"><h2>Applications</h2></div>
            {isLoading ? <p className="team-state">Loading candidates…</p> : applications.length === 0 ? <p className="team-empty">No applications in this workspace.</p> : applications.map((application) => (
              <article className="team-list-row team-application-row" key={application.id}>
                <button className="team-candidate-link" onClick={() => void loadApplicationHistory(application.id)} type="button">
                  <strong>{candidateNames.get(application.candidate_id) || "Candidate"}</strong>
                  <span>{jobNames.get(application.job_id) || "Job opening"}</span>
                </button>
                <label className="team-stage-select"><span className="sr-only">Stage for {candidateNames.get(application.candidate_id) || "candidate"}</span><select onChange={(event) => void updateApplication(application, event.target.value)} value={application.status}>{APPLICATION_STAGES.map((stage) => <option key={stage} value={stage}>{readable(stage)}</option>)}</select></label>
              </article>
            ))}
            {selectedApplication && (
              <div className="team-history">
                <h3>Application history</h3>
                {history.map((entry) => <article className="team-history-row" key={entry.id}><span>{entry.from_status ? `${readable(entry.from_status)} → ` : ""}{readable(entry.to_status)}</span><time dateTime={entry.created_at}>{dateLabel(entry.created_at)}</time></article>)}
              </div>
            )}
          </section>
          <section className="team-panel">
            <div className="team-panel-heading"><h2>Candidates</h2></div>
            <form className="team-form" onSubmit={createCandidate}>
              <label className="form-field"><span>First name</span><input maxLength={80} onChange={(event) => setCandidateFirstName(event.target.value)} required value={candidateFirstName} /></label>
              <label className="form-field"><span>Last name</span><input maxLength={80} onChange={(event) => setCandidateLastName(event.target.value)} required value={candidateLastName} /></label>
              <label className="form-field"><span>Email</span><input onChange={(event) => setCandidateEmail(event.target.value)} required type="email" value={candidateEmail} /></label>
              <label className="form-field"><span>Apply to job</span><select onChange={(event) => setCandidateJob(event.target.value)} required value={candidateJob}><option value="">Select a job</option>{jobs.filter((job) => job.status === "open").map((job) => <option key={job.id} value={job.id}>{job.title}</option>)}</select></label>
              <button className="button-primary button-primary--wide" disabled={isSaving || !jobs.some((job) => job.status === "open")}>Add candidate</button>
            </form>
            <div className="candidate-list">{candidates.map((candidate) => <div className="team-list-row" key={candidate.id}><div><strong>{candidate.first_name} {candidate.last_name}</strong><p>{candidate.email}</p></div></div>)}</div>
          </section>
        </div>
      )}
    </section>
  );
}
