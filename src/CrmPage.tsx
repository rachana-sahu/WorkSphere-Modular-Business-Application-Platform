import { useCallback, useEffect, useState, type FormEvent } from "react";
import { sessionFetch } from "./api";

type CRMTab = "leads" | "contacts" | "companies";
type CRMPageProps = {
  workspaceId: string;
  token: string;
  onBack: () => void;
};
type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};
type Company = {
  id: string;
  name: string;
  industry: string | null;
  domain: string | null;
};
type Contact = {
  id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  job_title: string | null;
  company_id: string | null;
};
type Lead = {
  id: string;
  title: string;
  stage: string;
  source: string | null;
  estimated_value: string | null;
  company_id: string | null;
  contact_id: string | null;
};
type Note = {
  id: string;
  body: string;
  created_at: string;
};
type Activity = {
  id: string;
  event_type: string;
  summary: string;
  created_at: string;
};

const PAGE_SIZE = 10;
const STAGES = ["new", "qualified", "proposal", "won", "lost"] as const;

async function crmRequest<T>(
  path: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("X-CSRF-Token", token);
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
        : "We could not load CRM data. Please try again.";
    throw new Error(message);
  }
  return payload as T;
}

function displayDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(new Date(value));
}

export default function CrmPage({
  workspaceId,
  token,
  onBack,
}: CRMPageProps) {
  const [tab, setTab] = useState<CRMTab>("leads");
  const [leads, setLeads] = useState<Page<Lead>>({
    items: [],
    page: 1,
    page_size: PAGE_SIZE,
    total: 0,
  });
  const [companies, setCompanies] = useState<Page<Company>>({
    items: [],
    page: 1,
    page_size: PAGE_SIZE,
    total: 0,
  });
  const [contacts, setContacts] = useState<Page<Contact>>({
    items: [],
    page: 1,
    page_size: PAGE_SIZE,
    total: 0,
  });
  const [companyOptions, setCompanyOptions] = useState<Company[]>([]);
  const [contactOptions, setContactOptions] = useState<Contact[]>([]);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState("");
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [noteDraft, setNoteDraft] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [companyIndustry, setCompanyIndustry] = useState("");
  const [contactFirstName, setContactFirstName] = useState("");
  const [contactLastName, setContactLastName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [leadTitle, setLeadTitle] = useState("");
  const [leadCompanyId, setLeadCompanyId] = useState("");
  const [leadContactId, setLeadContactId] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const baseUrl = `/api/workspaces/${workspaceId}/crm`;
  const loadRecords = useCallback(async () => {
    setIsLoading(true);
    setError("");
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (search) params.set("q", search);
    if (stage) params.set("stage", stage);
    try {
      if (tab === "leads") {
        setLeads(
          await crmRequest<Page<Lead>>(
            `${baseUrl}/leads?${params}`,
            token,
          ),
        );
      } else if (tab === "companies") {
        setCompanies(
          await crmRequest<Page<Company>>(
            `${baseUrl}/companies?${params}`,
            token,
          ),
        );
      } else {
        setContacts(
          await crmRequest<Page<Contact>>(
            `${baseUrl}/contacts?${params}`,
            token,
          ),
        );
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "CRM records could not be loaded.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [baseUrl, page, search, stage, tab, token]);

  useEffect(() => {
    void loadRecords();
  }, [loadRecords]);

  useEffect(() => {
    Promise.all([
      crmRequest<Page<Company>>(
        `${baseUrl}/companies?page=1&page_size=100`,
        token,
      ),
      crmRequest<Page<Contact>>(
        `${baseUrl}/contacts?page=1&page_size=100`,
        token,
      ),
    ])
      .then(([companyPage, contactPage]) => {
        setCompanyOptions(companyPage.items);
        setContactOptions(contactPage.items);
      })
      .catch((requestError: unknown) => {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "CRM reference data could not be loaded.",
        );
      });
  }, [baseUrl, token]);

  useEffect(() => {
    if (!selectedLead) {
      setNotes([]);
      setActivities([]);
      return;
    }
    let isActive = true;
    const leadUrl = `${baseUrl}/leads/${selectedLead.id}`;
    Promise.all([
      crmRequest<Note[]>(`${leadUrl}/notes`, token),
      crmRequest<Activity[]>(`${leadUrl}/activities`, token),
    ])
      .then(([nextNotes, nextActivities]) => {
        if (isActive) {
          setNotes(nextNotes);
          setActivities(nextActivities);
        }
      })
      .catch((requestError: unknown) => {
        if (isActive) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Lead history could not be loaded.",
          );
        }
      });
    return () => {
      isActive = false;
    };
  }, [baseUrl, selectedLead, token]);

  async function saveRecord(
    path: string,
    body: Record<string, unknown>,
  ): Promise<boolean> {
    setIsSaving(true);
    setError("");
    try {
      await crmRequest(path, token, {
        method: "POST",
        body: JSON.stringify(body),
      });
      await loadRecords();
      return true;
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The record could not be saved.",
      );
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  async function updateStage(lead: Lead, nextStage: string) {
    setError("");
    try {
      await crmRequest(`${baseUrl}/leads/${lead.id}`, token, {
        method: "PATCH",
        body: JSON.stringify({ stage: nextStage }),
      });
      await loadRecords();
      if (selectedLead?.id === lead.id) {
        setSelectedLead({ ...lead, stage: nextStage });
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Lead stage could not be changed.",
      );
    }
  }

  async function saveNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedLead) return;
    setIsSaving(true);
    setError("");
    try {
      await crmRequest(`${baseUrl}/leads/${selectedLead.id}/notes`, token, {
        method: "POST",
        body: JSON.stringify({ body: noteDraft }),
      });
      setNoteDraft("");
      const leadUrl = `${baseUrl}/leads/${selectedLead.id}`;
      const [nextNotes, nextActivities] = await Promise.all([
        crmRequest<Note[]>(`${leadUrl}/notes`, token),
        crmRequest<Activity[]>(`${leadUrl}/activities`, token),
      ]);
      setNotes(nextNotes);
      setActivities(nextActivities);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The note could not be saved.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  }

  const activePage =
    tab === "leads" ? leads : tab === "contacts" ? contacts : companies;
  return (
    <section className="crm-page" aria-labelledby="crm-title">
      <div className="crm-heading">
        <div>
          <p className="eyebrow">CUSTOMER RELATIONSHIPS</p>
          <h1 id="crm-title">CRM</h1>
          <p className="welcome-copy">
            Keep companies, people, and opportunities connected.
          </p>
        </div>
        <button className="button-secondary" onClick={onBack} type="button">
          Back to workspace
        </button>
      </div>

      <nav className="crm-tabs" aria-label="CRM records">
        {(["leads", "contacts", "companies"] as const).map((item) => (
          <button
            aria-current={tab === item ? "page" : undefined}
            className={`crm-tab${tab === item ? " crm-tab--active" : ""}`}
            key={item}
            onClick={() => {
              setTab(item);
              setPage(1);
              setSelectedLead(null);
            }}
            type="button"
          >
            {item[0].toUpperCase() + item.slice(1)}
          </button>
        ))}
      </nav>

      {error && (
        <p className="form-error crm-error" role="alert">
          {error}
        </p>
      )}

      <form className="crm-toolbar" onSubmit={submitSearch}>
        <label className="crm-search">
          <span className="sr-only">Search {tab}</span>
          <input
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder={`Search ${tab.toLowerCase()}…`}
            value={searchInput}
          />
        </label>
        {tab === "leads" && (
          <label className="crm-filter">
            <span className="sr-only">Filter by stage</span>
            <select
              onChange={(event) => {
                setStage(event.target.value);
                setPage(1);
              }}
              value={stage}
            >
              <option value="">All stages</option>
              {STAGES.map((value) => (
                <option key={value} value={value}>
                  {value[0].toUpperCase() + value.slice(1)}
                </option>
              ))}
            </select>
          </label>
        )}
        <button className="button-secondary" type="submit">
          Search
        </button>
      </form>

      <div className="crm-layout">
        <div className="crm-main">
          {tab === "leads" ? (
            <LeadList
              companies={companyOptions}
              contacts={contactOptions}
              isLoading={isLoading}
              leads={leads.items}
              onSelect={setSelectedLead}
              onStageChange={updateStage}
              selectedLeadId={selectedLead?.id}
            />
          ) : tab === "companies" ? (
            <CompanyList companies={companies.items} isLoading={isLoading} />
          ) : (
            <ContactList
              companies={companyOptions}
              contacts={contacts.items}
              isLoading={isLoading}
            />
          )}

          {!isLoading && activePage.total > PAGE_SIZE && (
            <div className="crm-pagination" aria-label="Pagination">
              <span>
                Page {activePage.page} of{" "}
                {Math.ceil(activePage.total / activePage.page_size)}
              </span>
              <button
                className="button-secondary"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                type="button"
              >
                Previous
              </button>
              <button
                className="button-secondary"
                disabled={page * activePage.page_size >= activePage.total}
                onClick={() => setPage((current) => current + 1)}
                type="button"
              >
                Next
              </button>
            </div>
          )}
        </div>

        <aside className="crm-side">
          {tab === "leads" ? (
            selectedLead ? (
              <LeadHistory
                activities={activities}
                lead={selectedLead}
                noteDraft={noteDraft}
                notes={notes}
                onNoteChange={setNoteDraft}
                onSaveNote={saveNote}
                isSaving={isSaving}
              />
            ) : (
              <CreateLeadForm
                companies={companyOptions}
                contacts={contactOptions}
                isSaving={isSaving}
                onCreate={async (data) => {
                  if (await saveRecord(`${baseUrl}/leads`, data)) {
                    setLeadTitle("");
                    setLeadCompanyId("");
                    setLeadContactId("");
                  }
                }}
                title={leadTitle}
                companyId={leadCompanyId}
                contactId={leadContactId}
                onTitleChange={setLeadTitle}
                onCompanyChange={setLeadCompanyId}
                onContactChange={setLeadContactId}
              />
            )
          ) : tab === "companies" ? (
            <CreateCompanyForm
              name={companyName}
              industry={companyIndustry}
              isSaving={isSaving}
              onNameChange={setCompanyName}
              onIndustryChange={setCompanyIndustry}
              onSubmit={async (data) => {
                if (await saveRecord(`${baseUrl}/companies`, data)) {
                  setCompanyName("");
                  setCompanyIndustry("");
                }
              }}
            />
          ) : (
            <CreateContactForm
              companies={companyOptions}
              firstName={contactFirstName}
              lastName={contactLastName}
              email={contactEmail}
              isSaving={isSaving}
              onFirstNameChange={setContactFirstName}
              onLastNameChange={setContactLastName}
              onEmailChange={setContactEmail}
              onSubmit={async (data) => {
                if (await saveRecord(`${baseUrl}/contacts`, data)) {
                  setContactFirstName("");
                  setContactLastName("");
                  setContactEmail("");
                }
              }}
            />
          )}
        </aside>
      </div>
    </section>
  );
}

function LeadList({
  leads,
  companies,
  contacts,
  isLoading,
  selectedLeadId,
  onSelect,
  onStageChange,
}: {
  leads: Lead[];
  companies: Company[];
  contacts: Contact[];
  isLoading: boolean;
  selectedLeadId?: string;
  onSelect: (lead: Lead) => void;
  onStageChange: (lead: Lead, stage: string) => void;
}) {
  const companiesById = new Map(companies.map((item) => [item.id, item.name]));
  const contactsById = new Map(
    contacts.map((item) => [
      item.id,
      `${item.first_name} ${item.last_name}`,
    ]),
  );
  if (isLoading) return <p className="crm-state">Loading leads…</p>;
  if (leads.length === 0) {
    return (
      <div className="crm-empty">
        <h2>No leads yet</h2>
        <p>Add an opportunity to start tracking your pipeline.</p>
      </div>
    );
  }
  return (
    <div className="crm-record-list">
      {leads.map((lead) => (
        <article
          className={`crm-record${lead.id === selectedLeadId ? " crm-record--selected" : ""}`}
          key={lead.id}
        >
          <div className="crm-record-main">
            <button
              className="crm-record-title"
              onClick={() => onSelect(lead)}
              type="button"
            >
              {lead.title}
            </button>
            <p>
              {lead.company_id ? companiesById.get(lead.company_id) ?? "Company" : ""}
              {lead.company_id && lead.contact_id ? " · " : ""}
              {lead.contact_id ? contactsById.get(lead.contact_id) ?? "Contact" : ""}
            </p>
          </div>
          <div className="crm-record-meta">
            {lead.estimated_value !== null && (
              <strong>
                {new Intl.NumberFormat(undefined, {
                  style: "currency",
                  currency: "USD",
                  maximumFractionDigits: 0,
                }).format(Number(lead.estimated_value))}
              </strong>
            )}
            <label className="stage-select">
              <span className="sr-only">Stage for {lead.title}</span>
              <select
                onChange={(event) => onStageChange(lead, event.target.value)}
                value={lead.stage}
              >
                {STAGES.map((value) => (
                  <option key={value} value={value}>
                    {value[0].toUpperCase() + value.slice(1)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </article>
      ))}
    </div>
  );
}

function CompanyList({
  companies,
  isLoading,
}: {
  companies: Company[];
  isLoading: boolean;
}) {
  if (isLoading) return <p className="crm-state">Loading companies…</p>;
  if (companies.length === 0) {
    return (
      <div className="crm-empty">
        <h2>No companies yet</h2>
        <p>Add a company to connect it to your contacts and opportunities.</p>
      </div>
    );
  }
  return (
    <div className="crm-record-list">
      {companies.map((company) => (
        <article className="crm-record" key={company.id}>
          <div className="crm-record-main">
            <h2>{company.name}</h2>
            <p>{company.domain || company.industry || "Company"}</p>
          </div>
          {company.industry && (
            <span className="module-state">{company.industry}</span>
          )}
        </article>
      ))}
    </div>
  );
}

function ContactList({
  contacts,
  companies,
  isLoading,
}: {
  contacts: Contact[];
  companies: Company[];
  isLoading: boolean;
}) {
  const companyNames = new Map(companies.map((item) => [item.id, item.name]));
  if (isLoading) return <p className="crm-state">Loading contacts…</p>;
  if (contacts.length === 0) {
    return (
      <div className="crm-empty">
        <h2>No contacts yet</h2>
        <p>Add a person to connect your team with a customer.</p>
      </div>
    );
  }
  return (
    <div className="crm-record-list">
      {contacts.map((contact) => (
        <article className="crm-record" key={contact.id}>
          <div className="crm-record-main">
            <h2>
              {contact.first_name} {contact.last_name}
            </h2>
            <p>
              {contact.email || contact.job_title || "Contact"}
              {contact.company_id
                ? ` · ${companyNames.get(contact.company_id) ?? "Company"}`
                : ""}
            </p>
          </div>
          {contact.job_title && (
            <span className="module-state">{contact.job_title}</span>
          )}
        </article>
      ))}
    </div>
  );
}

function CreateCompanyForm({
  name,
  industry,
  isSaving,
  onNameChange,
  onIndustryChange,
  onSubmit,
}: {
  name: string;
  industry: string;
  isSaving: boolean;
  onNameChange: (value: string) => void;
  onIndustryChange: (value: string) => void;
  onSubmit: (data: Record<string, unknown>) => Promise<void>;
}) {
  return (
    <form
      className="crm-create-form"
      onSubmit={(event) => {
        event.preventDefault();
        void onSubmit({ name, industry: industry || null });
      }}
    >
      <h2>Add a company</h2>
      <label className="form-field">
        <span>Company name</span>
        <input
          maxLength={120}
          onChange={(event) => onNameChange(event.target.value)}
          required
          value={name}
        />
      </label>
      <label className="form-field">
        <span>Industry</span>
        <input
          maxLength={100}
          onChange={(event) => onIndustryChange(event.target.value)}
          value={industry}
        />
      </label>
      <button className="button-primary button-primary--wide" disabled={isSaving}>
        {isSaving ? "Saving…" : "Save company"}
      </button>
    </form>
  );
}

function CreateContactForm({
  companies,
  firstName,
  lastName,
  email,
  isSaving,
  onFirstNameChange,
  onLastNameChange,
  onEmailChange,
  onSubmit,
}: {
  companies: Company[];
  firstName: string;
  lastName: string;
  email: string;
  isSaving: boolean;
  onFirstNameChange: (value: string) => void;
  onLastNameChange: (value: string) => void;
  onEmailChange: (value: string) => void;
  onSubmit: (data: Record<string, unknown>) => Promise<void>;
}) {
  return (
    <form
      className="crm-create-form"
      onSubmit={(event) => {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);
        void onSubmit({
          first_name: firstName,
          last_name: lastName,
          email: email || null,
          company_id: String(formData.get("contact-company") || "") || null,
        });
      }}
    >
      <h2>Add a contact</h2>
      <label className="form-field">
        <span>First name</span>
        <input
          maxLength={80}
          onChange={(event) => onFirstNameChange(event.target.value)}
          required
          value={firstName}
        />
      </label>
      <label className="form-field">
        <span>Last name</span>
        <input
          maxLength={80}
          onChange={(event) => onLastNameChange(event.target.value)}
          required
          value={lastName}
        />
      </label>
      <label className="form-field">
        <span>Email</span>
        <input
          onChange={(event) => onEmailChange(event.target.value)}
          type="email"
          value={email}
        />
      </label>
      <label className="form-field">
        <span>Company</span>
        <select id="contact-company" name="contact-company">
          <option value="">No company</option>
          {companies.map((company) => (
            <option key={company.id} value={company.id}>
              {company.name}
            </option>
          ))}
        </select>
      </label>
      <button className="button-primary button-primary--wide" disabled={isSaving}>
        {isSaving ? "Saving…" : "Save contact"}
      </button>
    </form>
  );
}

function CreateLeadForm({
  companies,
  contacts,
  isSaving,
  onCreate,
  title,
  companyId,
  contactId,
  onTitleChange,
  onCompanyChange,
  onContactChange,
}: {
  companies: Company[];
  contacts: Contact[];
  isSaving: boolean;
  onCreate: (data: Record<string, unknown>) => Promise<void>;
  title: string;
  companyId: string;
  contactId: string;
  onTitleChange: (value: string) => void;
  onCompanyChange: (value: string) => void;
  onContactChange: (value: string) => void;
}) {
  return (
    <form
      className="crm-create-form"
      onSubmit={(event) => {
        event.preventDefault();
        void onCreate({
          title,
          company_id: companyId || null,
          contact_id: contactId || null,
        });
      }}
    >
      <h2>Add a lead</h2>
      <label className="form-field">
        <span>Opportunity</span>
        <input
          maxLength={160}
          onChange={(event) => onTitleChange(event.target.value)}
          required
          value={title}
        />
      </label>
      <label className="form-field">
        <span>Company</span>
        <select
          onChange={(event) => onCompanyChange(event.target.value)}
          value={companyId}
        >
          <option value="">No company</option>
          {companies.map((company) => (
            <option key={company.id} value={company.id}>
              {company.name}
            </option>
          ))}
        </select>
      </label>
      <label className="form-field">
        <span>Contact</span>
        <select
          onChange={(event) => onContactChange(event.target.value)}
          value={contactId}
        >
          <option value="">No contact</option>
          {contacts.map((contact) => (
            <option key={contact.id} value={contact.id}>
              {contact.first_name} {contact.last_name}
            </option>
          ))}
        </select>
      </label>
      <button className="button-primary button-primary--wide" disabled={isSaving}>
        {isSaving ? "Saving…" : "Save lead"}
      </button>
    </form>
  );
}

function LeadHistory({
  lead,
  notes,
  activities,
  noteDraft,
  onNoteChange,
  onSaveNote,
  isSaving,
}: {
  lead: Lead;
  notes: Note[];
  activities: Activity[];
  noteDraft: string;
  onNoteChange: (value: string) => void;
  onSaveNote: (event: FormEvent<HTMLFormElement>) => void;
  isSaving: boolean;
}) {
  return (
    <div className="crm-history">
      <h2>{lead.title}</h2>
      <p className="eyebrow">NOTES</p>
      <form onSubmit={onSaveNote}>
        <label className="sr-only" htmlFor="lead-note">
          Add a note
        </label>
        <textarea
          id="lead-note"
          maxLength={5000}
          onChange={(event) => onNoteChange(event.target.value)}
          placeholder="Capture a useful detail…"
          required
          rows={3}
          value={noteDraft}
        />
        <button
          className="button-primary button-primary--wide"
          disabled={isSaving}
          type="submit"
        >
          {isSaving ? "Saving…" : "Add note"}
        </button>
      </form>
      <div className="history-list">
        {notes.length === 0 ? (
          <p className="crm-muted">No notes recorded.</p>
        ) : (
          notes.map((note) => (
            <article className="history-item" key={note.id}>
              <p>{note.body}</p>
              <time dateTime={note.created_at}>{displayDate(note.created_at)}</time>
            </article>
          ))
        )}
      </div>
      <p className="eyebrow history-heading">ACTIVITY</p>
      <div className="history-list">
        {activities.length === 0 ? (
          <p className="crm-muted">No activity recorded.</p>
        ) : (
          activities.map((activity) => (
            <article className="history-item" key={activity.id}>
              <p>{activity.summary}</p>
              <time dateTime={activity.created_at}>
                {displayDate(activity.created_at)}
              </time>
            </article>
          ))
        )}
      </div>
    </div>
  );
}
