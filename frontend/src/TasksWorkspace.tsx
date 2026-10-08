import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  createTask,
  getProjectMembers,
  listProjectTasks,
  listProjects,
  ProjectMember,
  reviewTask,
  TaskPriority,
  TaskType,
  updateTaskStatus,
  submitTaskForReview,
  WorkspaceProject,
  WorkspaceTask,
  WorkspaceUser,
} from "./api";

const PAGE_SIZE = 20;
const TASK_TYPES: TaskType[] = ["TASK", "FEATURE", "BUG"];
const TASK_PRIORITIES: TaskPriority[] = ["LOW", "MEDIUM", "HIGH", "URGENT"];

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

function label(value: string): string {
  return value.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string | null): string {
  if (!value) return "No deadline";
  return new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

interface TasksWorkspaceProps {
  user: WorkspaceUser;
  onSignOut: () => void;
  signingOut: boolean;
  onNavigateAdmin?: (view: "people" | "projects" | "tasks") => void;
}

export default function TasksWorkspace({ user, onSignOut, signingOut, onNavigateAdmin }: TasksWorkspaceProps) {
  const canManage = user.role === "ADMIN" || user.role === "MANAGER";
  const [projects, setProjects] = useState<WorkspaceProject[]>([]);
  const [projectId, setProjectId] = useState("");
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [tasks, setTasks] = useState<WorkspaceTask[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [creating, setCreating] = useState(false);
  const [busyTask, setBusyTask] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [feedback, setFeedback] = useState<Record<string, string>>({});

  const selectedProject = useMemo(() => projects.find((project) => project.id === projectId) ?? null, [projects, projectId]);

  useEffect(() => {
    let current = true;
    async function loadAllProjects() {
      setLoadingProjects(true);
      setError("");
      try {
        const first = await listProjects(0, 100, "");
        const pages = await Promise.all(Array.from({ length: Math.ceil((first.total - first.items.length) / 100) }, (_, index) =>
          listProjects((index + 1) * 100, 100, "")));
        const all = [...first.items, ...pages.flatMap((page) => page.items)];
        if (!current) return;
        setProjects(all);
        setProjectId((existing) => existing && all.some((project) => project.id === existing) ? existing : all[0]?.id ?? "");
      } catch (caught) {
        if (current) setError(errorMessage(caught));
      } finally {
        if (current) setLoadingProjects(false);
      }
    }
    void loadAllProjects();
    return () => { current = false; };
  }, []);

  const loadTasks = useCallback(async () => {
    if (!projectId) { setTasks([]); setTotal(0); setLoadingTasks(false); return; }
    setTasks([]);
    setTotal(0);
    setLoadingTasks(true);
    try {
      const page = await listProjectTasks(projectId, offset, PAGE_SIZE);
      setTasks(page.items);
      setTotal(page.total);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoadingTasks(false);
    }
  }, [offset, projectId]);

  useEffect(() => { void loadTasks(); }, [loadTasks]);

  useEffect(() => {
    let current = true;
    setMembers([]);
    if (!selectedProject || !canManage) return () => { current = false; };
    getProjectMembers(selectedProject.id)
      .then((membership) => { if (current) setMembers(membership.members.filter((member) => member.is_active && member.account_role === "MEMBER")); })
      .catch((caught) => { if (current) setError(errorMessage(caught)); });
    return () => { current = false; };
  }, [canManage, selectedProject]);

  function chooseProject(value: string) {
    setOffset(0);
    setProjectId(value);
    setError("");
    setNotice("");
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProject) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const task = {
      title: String(form.get("task-title")).trim(),
      description: String(form.get("task-description")).trim() || null,
      type: String(form.get("task-type")) as TaskType,
      priority: String(form.get("task-priority")) as TaskPriority,
      assignee_id: String(form.get("task-assignee")) || null,
      due_date: String(form.get("task-due-date")) || null,
    };
    setCreating(true);
    setError("");
    setNotice("");
    try {
      const created = await createTask(selectedProject.id, task);
      formElement.reset();
      setOffset(0);
      setNotice(`${created.issue_key} was created.`);
      const page = await listProjectTasks(selectedProject.id, 0, PAGE_SIZE);
      setTasks(page.items);
      setTotal(page.total);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setCreating(false);
    }
  }

  async function performTaskAction(task: WorkspaceTask, action: () => Promise<unknown>, successMessage: string) {
    setBusyTask(task.id);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(successMessage);
      await loadTasks();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusyTask("");
    }
  }

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return <main className="admin-page">
    <header className="admin-header">
      <a className="brand-lockup" href="#workspace" aria-label="Invictus Grid Workspace home">
        <span className="brand-mark" aria-hidden="true">IG</span><span className="brand-name">INVICTUS <b>GRID</b></span>
      </a>
      {user.role === "ADMIN" && <nav className="admin-nav" aria-label="Administration">
        <button className="admin-nav-link" type="button" onClick={() => onNavigateAdmin?.("people")}>People</button>
        <button className="admin-nav-link" type="button" onClick={() => onNavigateAdmin?.("projects")}>Projects</button>
        <button className="admin-nav-link" type="button" aria-current="page">Tasks</button>
      </nav>}
      <div className="admin-header-actions">
        <span className="admin-identity"><strong>{user.full_name}</strong><small>{label(user.role)}</small></span>
        <button className="text-button" type="button" onClick={onSignOut} disabled={signingOut}>Sign out</button>
      </div>
    </header>

    <div className="admin-content" id="workspace">
      <div className="admin-page-heading">
        <div><p className="eyebrow">{user.role === "MEMBER" ? "My workspace" : "Project execution"}</p>
          <h1>{user.role === "MEMBER" ? "My tasks" : "Tasks"}</h1>
          <p className="description">{user.role === "MEMBER" ? "Track your work and submit completed tasks for review." : "Create project work, monitor progress, and review submissions."}</p></div>
        <div className="member-count"><strong>{total}</strong><span>{total === 1 ? "task" : "tasks"}</span></div>
      </div>

      {error && <div className="error-banner" role="alert">{error}</div>}
      {notice && <div className="notice-banner" role="status">{notice}</div>}

      <section className="admin-panel task-browser" aria-labelledby="task-browser-title">
        <div className="panel-heading task-browser-heading">
          <div><h2 id="task-browser-title">Project work</h2><p>Choose a project to see its permitted tasks.</p></div>
          <div className="form-field task-project-select"><label htmlFor="task-project">Project</label>
            <select id="task-project" value={projectId} onChange={(event) => chooseProject(event.target.value)} disabled={loadingProjects || projects.length === 0}>
              {projects.length === 0 && <option value="">{loadingProjects ? "Loading projects…" : "No assigned projects"}</option>}
              {projects.map((project) => <option key={project.id} value={project.id}>{project.key} · {project.name}</option>)}
            </select>
          </div>
        </div>

        {canManage && selectedProject && !["COMPLETED", "ARCHIVED"].includes(selectedProject.status) && <form className="task-create-form" onSubmit={handleCreate}>
          <div className="task-form-title"><h3>Create a task</h3><span className="optional-label">{selectedProject.key}</span></div>
          <div className="form-field"><label htmlFor="task-title">Title</label><input id="task-title" name="task-title" maxLength={240} required disabled={creating} placeholder="What needs to be done?" /></div>
          <div className="form-field"><label htmlFor="task-assignee">Assign to</label>
            <select id="task-assignee" name="task-assignee" defaultValue="" disabled={creating || members.length === 0}>
              <option value="">Unassigned</option>{members.map((member) => <option key={member.user_id} value={member.user_id}>{member.full_name}</option>)}
            </select>
          </div>
          <div className="form-field"><label htmlFor="task-type">Type</label><select id="task-type" name="task-type" defaultValue="TASK" disabled={creating}>{TASK_TYPES.map((type) => <option key={type} value={type}>{label(type)}</option>)}</select></div>
          <div className="form-field"><label htmlFor="task-priority">Priority</label><select id="task-priority" name="task-priority" defaultValue="MEDIUM" disabled={creating}>{TASK_PRIORITIES.map((priority) => <option key={priority}>{priority}</option>)}</select></div>
          <div className="form-field"><label htmlFor="task-due-date">Due date <span className="optional-label">OPTIONAL</span></label><input id="task-due-date" name="task-due-date" type="date" disabled={creating} /></div>
          <div className="form-field task-description-field"><label htmlFor="task-description">Description <span className="optional-label">OPTIONAL</span></label><textarea id="task-description" name="task-description" maxLength={20000} rows={2} disabled={creating} placeholder="Add context or acceptance notes." /></div>
          <button className="primary-button task-create-button" type="submit" disabled={creating || loadingProjects}>
            {creating ? <><span className="button-spinner" /> Creating…</> : "Create task"}
          </button>
        </form>}

        <div className="workspace-task-list">
          {loadingTasks && <p className="project-list-message">Loading tasks…</p>}
          {!loadingTasks && tasks.length === 0 && <p className="project-list-message">{selectedProject ? "No tasks are available here yet." : "Choose a project to see its tasks."}</p>}
          {!loadingTasks && tasks.map((task) => <article className="workspace-task" key={task.id}>
            <div className="task-card-main">
              <div className="task-card-title"><span className="project-key">{task.issue_key}</span><span className={`task-status status-${task.status.toLowerCase().replace(/_/g, "-")}`}>{label(task.status)}</span></div>
              <h3>{task.title}</h3>
              {task.description && <p className="task-description-copy">{task.description}</p>}
              <div className="project-meta"><span>{label(task.type)}</span><span>{label(task.priority)} priority</span>
                {canManage && <span>{task.assignee_name ? `Assigned to ${task.assignee_name}` : "Unassigned"}</span>}
                <span>Due {formatDate(task.due_date)}</span></div>
            </div>
            <div className="task-actions">
              {user.role === "MEMBER" && ["TODO", "CHANGES_REQUIRED"].includes(task.status) && <button className="secondary-button" type="button" disabled={busyTask === task.id}
                onClick={() => void performTaskAction(task, () => updateTaskStatus(task.id, "IN_PROGRESS"), `${task.issue_key} moved to In Progress.`)}>{task.status === "TODO" ? "Start task" : "Resume task"}</button>}
              {user.role === "MEMBER" && task.status === "IN_PROGRESS" && <button className="primary-button task-action-primary" type="button" disabled={busyTask === task.id}
                onClick={() => void performTaskAction(task, () => submitTaskForReview(task.id), `${task.issue_key} was submitted for review.`)}>Submit for review</button>}
              {canManage && task.status === "PENDING_REVIEW" && <div className="review-actions">
                <label className="visually-hidden" htmlFor={`feedback-${task.id}`}>Feedback when requesting changes for {task.issue_key}</label>
                <textarea id={`feedback-${task.id}`} value={feedback[task.id] ?? ""} maxLength={5000} rows={2} placeholder="Feedback required to request changes" disabled={busyTask === task.id}
                  onChange={(event) => setFeedback((current) => ({ ...current, [task.id]: event.target.value }))} />
                <div><button className="secondary-button" type="button" disabled={busyTask === task.id}
                    onClick={() => void performTaskAction(task, () => reviewTask(task.id, "APPROVED", null), `${task.issue_key} was approved.`)}>Approve</button>
                  <button className="secondary-button changes-button" type="button" disabled={busyTask === task.id || !feedback[task.id]?.trim()}
                    onClick={() => void performTaskAction(task, () => reviewTask(task.id, "CHANGES_REQUIRED", feedback[task.id].trim()), `Changes were requested for ${task.issue_key}.`)}>Request changes</button></div>
              </div>}
            </div>
          </article>)}
        </div>
        {total > PAGE_SIZE && <footer className="table-footer"><span>Page {page} of {pageCount}</span><div className="pagination-controls">
          <button className="secondary-button" type="button" disabled={offset === 0 || loadingTasks} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
          <button className="secondary-button" type="button" disabled={offset + PAGE_SIZE >= total || loadingTasks} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button>
        </div></footer>}
      </section>
      <p className="admin-footnote">Your task list and actions are limited by your project role.</p>
    </div>
  </main>;
}
