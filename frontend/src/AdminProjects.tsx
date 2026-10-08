import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  ApiError,
  createProject,
  getProjectMembers,
  listAllUsers,
  listProjects,
  NewProject,
  ProjectMember,
  ProjectStatus,
  replaceProjectMembers,
  WorkspaceProject,
  WorkspaceUser,
} from "./api";

const PAGE_SIZE = 20;
const PROJECT_STATUSES: ProjectStatus[] = ["PLANNED", "ACTIVE", "COMPLETED", "ARCHIVED"];

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

function toggleId(ids: string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id];
}

function formatDate(value: string | null): string {
  if (!value) return "No deadline";
  return new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString(undefined, {
    month: "short", day: "numeric", year: "numeric",
  });
}

interface AdminProjectsProps {
  admin: WorkspaceUser;
  onNavigate: (view: "people" | "projects") => void;
  onSignOut: () => void;
  signingOut: boolean;
}

export default function AdminProjects({ admin, onNavigate, onSignOut, signingOut }: AdminProjectsProps) {
  const [projects, setProjects] = useState<WorkspaceProject[]>([]);
  const [users, setUsers] = useState<WorkspaceUser[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [creating, setCreating] = useState(false);
  const [savingMembers, setSavingMembers] = useState(false);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [selectedProject, setSelectedProject] = useState<WorkspaceProject | null>(null);
  const [selectedManagers, setSelectedManagers] = useState<string[]>([]);
  const [selectedMembers, setSelectedMembers] = useState<string[]>([]);
  const [inactiveAssignments, setInactiveAssignments] = useState<ProjectMember[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadProjects = useCallback(async (active: () => boolean = () => true) => {
    setLoadingProjects(true);
    setError("");
    try {
      const page = await listProjects(offset, PAGE_SIZE, search);
      if (!active()) return;
      setProjects(page.items);
      setTotal(page.total);
    } catch (caught) {
      if (active()) setError(errorMessage(caught));
    } finally {
      if (active()) setLoadingProjects(false);
    }
  }, [offset, search]);

  useEffect(() => {
    let current = true;
    void loadProjects(() => current);
    return () => { current = false; };
  }, [loadProjects]);

  useEffect(() => {
    let current = true;
    listAllUsers()
      .then((allUsers) => { if (current) setUsers(allUsers); })
      .catch((caught) => { if (current) setError(errorMessage(caught)); })
      .finally(() => { if (current) setLoadingUsers(false); });
    return () => { current = false; };
  }, []);

  const activeManagers = users.filter((user) => user.is_active && user.role === "MANAGER");
  const activeMembers = users.filter((user) => user.is_active && user.role === "MEMBER");
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function applySearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("");
    setOffset(0);
    setSearch(searchInput.trim());
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedManagers.length === 0) {
      setError("Choose at least one active Manager for this project.");
      return;
    }
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const project: NewProject = {
      key: String(form.get("project-key")).trim().toUpperCase(),
      name: String(form.get("project-name")).trim(),
      description: String(form.get("project-description")).trim() || null,
      status: String(form.get("project-status")) as ProjectStatus,
      due_date: String(form.get("due-date")) || null,
      manager_ids: selectedManagers,
      member_ids: selectedMembers,
    };
    setCreating(true);
    setError("");
    setNotice("");
    try {
      await createProject(project);
      formElement.reset();
      setSelectedManagers([]);
      setSelectedMembers([]);
      setOffset(0);
      setSearchInput("");
      setSearch("");
      setNotice(`${project.key} was created with ${project.manager_ids.length} Manager${project.manager_ids.length === 1 ? "" : "s"} and ${project.member_ids.length} Member${project.member_ids.length === 1 ? "" : "s"}.`);
    } catch (caught) {
      setError(errorMessage(caught));
      return;
    } finally {
      setCreating(false);
    }
    try {
      const firstPage = await listProjects(0, PAGE_SIZE, "");
      setProjects(firstPage.items);
      setTotal(firstPage.total);
    } catch {
      setError("Project was created, but the project list could not refresh.");
    }
  }

  async function openMembershipEditor(project: WorkspaceProject) {
    setSelectedProject(project);
    setLoadingMembers(true);
    setError("");
    setNotice("");
    try {
      const memberships = await getProjectMembers(project.id);
      const managers = memberships.managers.filter((member) => member.is_active && member.account_role === "MANAGER");
      const members = memberships.members.filter((member) => member.is_active && member.account_role === "MEMBER");
      setSelectedManagers(managers.map((member) => member.user_id));
      setSelectedMembers(members.map((member) => member.user_id));
      setInactiveAssignments([
        ...memberships.managers.filter((member) => !member.is_active || member.account_role !== "MANAGER"),
        ...memberships.members.filter((member) => !member.is_active || member.account_role !== "MEMBER"),
      ]);
    } catch (caught) {
      setError(errorMessage(caught));
      setSelectedProject(null);
    } finally {
      setLoadingMembers(false);
    }
  }

  async function saveMemberships() {
    if (!selectedProject || selectedManagers.length === 0) {
      setError("Every project must have at least one active Manager.");
      return;
    }
    setSavingMembers(true);
    setError("");
    setNotice("");
    try {
      const result = await replaceProjectMembers(selectedProject.id, selectedManagers, selectedMembers);
      setProjects((current) => current.map((project) => project.id === selectedProject.id
        ? { ...project, manager_count: result.managers.length, member_count: result.members.length }
        : project));
      setInactiveAssignments([]);
      setNotice(`Membership for ${selectedProject.key} was updated.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSavingMembers(false);
    }
  }

  return (
    <main className="admin-page">
      <header className="admin-header">
        <a className="brand-lockup" href="#workspace" aria-label="Invictus Grid Workspace home">
          <span className="brand-mark" aria-hidden="true">IG</span>
          <span className="brand-name">INVICTUS <b>GRID</b></span>
        </a>
        <nav className="admin-nav" aria-label="Administration">
          <button className="admin-nav-link" type="button" onClick={() => onNavigate("people")}>People</button>
          <button className="admin-nav-link" type="button" aria-current="page" onClick={() => onNavigate("projects")}>Projects</button>
        </nav>
        <div className="admin-header-actions">
          <span className="admin-identity"><strong>{admin.full_name}</strong><small>Administrator</small></span>
          <button className="text-button" type="button" onClick={onSignOut} disabled={signingOut}>Sign out</button>
        </div>
      </header>

      <div className="admin-content" id="workspace">
        <div className="admin-page-heading">
          <div><p className="eyebrow">Workspace administration</p><h1>Projects</h1>
            <p className="description">Create projects and assign Managers and Members.</p></div>
          <div className="member-count"><strong>{total}</strong><span>{total === 1 ? "project" : "projects"}</span></div>
        </div>

        {error && <div className="error-banner" role="alert">{error}</div>}
        {notice && <div className="notice-banner" role="status">{notice}</div>}

        <section className="admin-panel create-panel" aria-labelledby="create-project-title">
          <div className="panel-heading"><div><h2 id="create-project-title">Create a project</h2>
            <p>Every project needs a unique key and at least one active Manager.</p></div>
            <span className="panel-step">NEW PROJECT</span></div>
          <form className="project-form" onSubmit={handleCreate}>
            <div className="form-field"><label htmlFor="project-key">Project key</label>
              <input id="project-key" name="project-key" maxLength={10} pattern="[A-Za-z][A-Za-z0-9]{1,9}" placeholder="e.g. IGW" title="Use 2–10 letters or numbers, starting with a letter." required disabled={creating} />
              <small>2–10 characters, starts with a letter. Used in task keys.</small></div>
            <div className="form-field"><label htmlFor="project-name">Project name</label>
              <input id="project-name" name="project-name" maxLength={180} placeholder="e.g. Invictus Grid Workspace" required disabled={creating} /></div>
            <div className="form-field"><label htmlFor="project-status">Status</label>
              <select id="project-status" name="project-status" defaultValue="PLANNED" disabled={creating}>
                {PROJECT_STATUSES.map((status) => <option key={status} value={status}>{status.charAt(0) + status.slice(1).toLowerCase()}</option>)}
              </select></div>
            <div className="form-field"><label htmlFor="due-date">Deadline <span className="optional-label">OPTIONAL</span></label>
              <input id="due-date" name="due-date" type="date" disabled={creating} /></div>
            <div className="form-field project-description-field"><label htmlFor="project-description">Description <span className="optional-label">OPTIONAL</span></label>
              <textarea id="project-description" name="project-description" maxLength={5000} rows={3} placeholder="What is this project working toward?" disabled={creating} /></div>
            <div className="member-pickers">
              <MemberPicker title="Managers" hint="Choose at least one active Manager." users={activeManagers} selected={selectedManagers}
                onToggle={(id) => setSelectedManagers((current) => toggleId(current, id))} loading={loadingUsers} />
              <MemberPicker title="Members" hint="Select the project Members." users={activeMembers} selected={selectedMembers}
                onToggle={(id) => setSelectedMembers((current) => toggleId(current, id))} loading={loadingUsers} />
            </div>
            <button className="primary-button create-button project-create-button" type="submit" disabled={creating || loadingUsers || selectedManagers.length === 0}>
              {creating ? <><span className="button-spinner" /> Creating…</> : "Create project"}
            </button>
          </form>
        </section>

        <section className="admin-panel users-panel projects-panel" aria-labelledby="projects-title">
          <div className="panel-heading users-panel-heading"><div><h2 id="projects-title">All projects</h2>
            <p>Review project status, deadlines, and assigned people.</p></div>
            <form className="search-form" onSubmit={applySearch} role="search">
              <label className="visually-hidden" htmlFor="project-search">Search projects</label>
              <input id="project-search" type="search" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search key or name" />
              <button className="secondary-button" type="submit">Search</button>
            </form>
          </div>
          <div className="project-list">
            {loadingProjects && <p className="project-list-message">Loading projects…</p>}
            {!loadingProjects && projects.length === 0 && <p className="project-list-message">{search ? "No projects match your search." : "No projects yet. Create the first one above."}</p>}
            {!loadingProjects && projects.map((project) => (
              <article className="project-row" key={project.id}>
                <div className="project-key-mark">{project.key.slice(0, 2)}</div>
                <div className="project-row-main"><div className="project-title-line"><span className="project-key">{project.key}</span>
                  <h3>{project.name}</h3><span className={`project-status status-${project.status.toLowerCase()}`}>{project.status.replace("_", " ")}</span></div>
                  {project.description && <p>{project.description}</p>}
                  <div className="project-meta"><span>{project.manager_count} Manager{project.manager_count === 1 ? "" : "s"}</span>
                    <span>{project.member_count} Member{project.member_count === 1 ? "" : "s"}</span><span>Due {formatDate(project.due_date)}</span></div>
                </div>
                <button className="secondary-button manage-members-button" type="button" disabled={loadingMembers} onClick={() => void openMembershipEditor(project)}>Manage members</button>
              </article>
            ))}
          </div>
          <footer className="table-footer"><span>{total > 0 ? `Showing ${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} of ${total}` : "0 projects"}</span>
            <div className="pagination-controls"><button className="secondary-button" type="button" disabled={loadingProjects || offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
              <span>Page {page} of {pageCount}</span>
              <button className="secondary-button" type="button" disabled={loadingProjects || offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button></div>
          </footer>
        </section>

        {selectedProject && <section className="admin-panel membership-panel" aria-labelledby="membership-title">
          <div className="panel-heading"><div><h2 id="membership-title">Manage members · {selectedProject.key}</h2>
            <p>Assign active accounts by their organization role.</p></div>
            <button className="text-button" type="button" onClick={() => setSelectedProject(null)}>Close</button></div>
          {loadingMembers ? <p className="project-list-message">Loading project members…</p> : <>
            {inactiveAssignments.length > 0 && <div className="inactive-assignment-note">{inactiveAssignments.length} inactive or role-changed assignment{inactiveAssignments.length === 1 ? "" : "s"} cannot retain access and will be removed when you save.</div>}
            <div className="member-pickers membership-pickers">
              <MemberPicker title="Managers" hint="At least one active Manager must remain assigned." users={activeManagers} selected={selectedManagers}
                onToggle={(id) => setSelectedManagers((current) => toggleId(current, id))} loading={loadingUsers} />
              <MemberPicker title="Members" hint="Project Members can be added or removed here." users={activeMembers} selected={selectedMembers}
                onToggle={(id) => setSelectedMembers((current) => toggleId(current, id))} loading={loadingUsers} />
            </div>
            <div className="membership-actions"><button className="secondary-button" type="button" onClick={() => setSelectedProject(null)} disabled={savingMembers}>Cancel</button>
              <button className="primary-button" type="button" onClick={() => void saveMemberships()} disabled={savingMembers || selectedManagers.length === 0}>
                {savingMembers ? <><span className="button-spinner" /> Saving…</> : "Save membership"}
              </button></div>
          </>}
        </section>}
        <p className="admin-footnote">Project creation and membership changes are recorded in the audit log.</p>
      </div>
    </main>
  );
}

interface MemberPickerProps {
  title: string;
  hint: string;
  users: WorkspaceUser[];
  selected: string[];
  loading: boolean;
  onToggle: (userId: string) => void;
}

function MemberPicker({ title, hint, users, selected, loading, onToggle }: MemberPickerProps) {
  return <fieldset className="member-picker">
    <legend>{title}<span className="selection-count">{selected.length} selected</span></legend>
    <p>{hint}</p>
    <div className="member-picker-list">
      {loading && <span className="picker-message">Loading accounts…</span>}
      {!loading && users.length === 0 && <span className="picker-message">No active accounts with this role. Create one in People first.</span>}
      {!loading && users.map((user) => <label className="member-option" key={user.id}>
        <input type="checkbox" checked={selected.includes(user.id)} onChange={() => onToggle(user.id)} />
        <span><strong>{user.full_name}</strong><small>{user.email}</small></span>
      </label>)}
    </div>
  </fieldset>;
}
