import { FormEvent, useCallback, useEffect, useState } from "react";

import { ApiError, createUser, listUsers, NewUser, setUserActive, setUserRole, WorkspaceUser } from "./api";

const PAGE_SIZE = 20;

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

function passwordIsStrong(password: string): boolean {
  return password.length >= 12 && /[a-z]/.test(password) && /[A-Z]/.test(password)
    && /\d/.test(password) && /[^A-Za-z0-9]/.test(password);
}

interface AdminUsersProps {
  admin: WorkspaceUser;
  onSignOut: () => void;
  signingOut: boolean;
}

export default function AdminUsers({ admin, onSignOut, signingOut }: AdminUsersProps) {
  const [users, setUsers] = useState<WorkspaceUser[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadUsers = useCallback(async (active: () => boolean = () => true) => {
    setLoading(true);
    setError("");
    try {
      const page = await listUsers(offset, PAGE_SIZE, search);
      if (!active()) return;
      setUsers(page.items);
      setTotal(page.total);
    } catch (caught) {
      if (active()) setError(errorMessage(caught));
    } finally {
      if (active()) setLoading(false);
    }
  }, [offset, search]);

  useEffect(() => {
    let current = true;
    void loadUsers(() => current);
    return () => { current = false; };
  }, [loadUsers]);

  function applySearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("");
    setOffset(0);
    setSearch(searchInput.trim());
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const initialPassword = String(form.get("initial-password"));
    if (!passwordIsStrong(initialPassword)) {
      setError("Use at least 12 characters with uppercase and lowercase letters, a number, and a symbol.");
      return;
    }
    const newUser: NewUser = {
      full_name: String(form.get("full-name")).trim(),
      email: String(form.get("new-email")).trim(),
      role: String(form.get("new-role")) as WorkspaceUser["role"],
      initial_password: initialPassword,
    };
    setCreating(true);
    setError("");
    setNotice("");
    try {
      await createUser(newUser);
      formElement.reset();
      setSearchInput("");
      setSearch("");
      setOffset(0);
      setNotice("Account created. Share the initial password with the member; they’ll be asked to change it at first sign-in.");
    } catch (caught) {
      setError(errorMessage(caught));
      return;
    } finally {
      setCreating(false);
    }
    try {
      const firstPage = await listUsers(0, PAGE_SIZE, "");
      setUsers(firstPage.items);
      setTotal(firstPage.total);
    } catch {
      setError("Account was created, but the directory could not refresh. Reload the list to see it.");
    }
  }

  async function updateStatus(target: WorkspaceUser) {
    setPendingId(target.id);
    setError("");
    setNotice("");
    try {
      const updated = await setUserActive(target.id, !target.is_active);
      setUsers((current) => current.map((item) => item.id === updated.id ? updated : item));
      setNotice(`${updated.full_name}’s account is now ${updated.is_active ? "active" : "deactivated"}.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setPendingId(null);
    }
  }

  async function updateRole(target: WorkspaceUser, role: WorkspaceUser["role"]) {
    if (role === target.role) return;
    setPendingId(target.id);
    setError("");
    setNotice("");
    try {
      const updated = await setUserRole(target.id, role);
      setUsers((current) => current.map((item) => item.id === updated.id ? updated : item));
      setNotice(`${updated.full_name}’s role is now ${updated.role.toLowerCase()}.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setPendingId(null);
    }
  }

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <main className="admin-page">
      <header className="admin-header">
        <a className="brand-lockup" href="#workspace" aria-label="Invictus Grid Workspace home">
          <span className="brand-mark" aria-hidden="true">IG</span>
          <span className="brand-name">INVICTUS <b>GRID</b></span>
        </a>
        <div className="admin-header-actions">
          <span className="admin-identity"><strong>{admin.full_name}</strong><small>Administrator</small></span>
          <button className="text-button" type="button" onClick={onSignOut} disabled={signingOut}>Sign out</button>
        </div>
      </header>

      <div className="admin-content" id="workspace">
        <div className="admin-page-heading">
          <div><p className="eyebrow">Workspace administration</p><h1>People</h1>
            <p className="description">Create accounts and manage access for your club.</p></div>
          <div className="member-count"><strong>{total}</strong><span>{total === 1 ? "account" : "accounts"}</span></div>
        </div>

        {error && <div className="error-banner" role="alert">{error}</div>}
        {notice && <div className="notice-banner" role="status">{notice}</div>}

        <section className="admin-panel create-panel" aria-labelledby="create-user-title">
          <div className="panel-heading"><div><h2 id="create-user-title">Add a member</h2>
            <p>Create a provisioned account. The member must set a new password at first sign-in.</p></div>
            <span className="panel-step">NEW ACCOUNT</span></div>
          <form className="create-user-form" onSubmit={handleCreate}>
            <div className="form-field"><label htmlFor="full-name">Full name</label>
              <input id="full-name" name="full-name" autoComplete="name" maxLength={160} placeholder="e.g. Aanya Sharma" required disabled={creating} /></div>
            <div className="form-field"><label htmlFor="new-email">Email address</label>
              <input id="new-email" name="new-email" type="email" autoComplete="email" maxLength={320} placeholder="member@example.com" required disabled={creating} /></div>
            <div className="form-field"><label htmlFor="new-role">Role</label>
              <select id="new-role" name="new-role" defaultValue="MEMBER" disabled={creating}>
                <option value="MEMBER">Member</option><option value="MANAGER">Manager</option><option value="ADMIN">Admin</option>
              </select></div>
            <div className="form-field"><label htmlFor="initial-password">Initial password</label>
              <input id="initial-password" name="initial-password" type="password" autoComplete="new-password" minLength={12} required disabled={creating} />
              <small>12+ characters with upper/lowercase, number, and symbol.</small></div>
            <button className="primary-button create-button" type="submit" disabled={creating}>
              {creating ? <><span className="button-spinner" /> Creating…</> : "Create account"}
            </button>
          </form>
        </section>

        <section className="admin-panel users-panel" aria-labelledby="users-title">
          <div className="panel-heading users-panel-heading"><div><h2 id="users-title">All accounts</h2>
            <p>Manage roles and account access.</p></div>
            <form className="search-form" onSubmit={applySearch} role="search">
              <label className="visually-hidden" htmlFor="user-search">Search accounts</label>
              <input id="user-search" type="search" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search name or email" />
              <button className="secondary-button" type="submit">Search</button>
            </form>
          </div>

          <div className="table-wrap">
            <table className="user-table">
              <thead><tr><th scope="col">Member</th><th scope="col">Role</th><th scope="col">Status</th><th scope="col">Created</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
              <tbody>
                {loading && <tr><td className="table-message" colSpan={5}>Loading accounts…</td></tr>}
                {!loading && users.length === 0 && <tr><td className="table-message" colSpan={5}>{search ? "No accounts match your search." : "No accounts yet."}</td></tr>}
                {!loading && users.map((item) => {
                  const isSelf = item.id === admin.id;
                  const isPending = pendingId === item.id;
                  return <tr key={item.id}>
                    <td><div className="user-cell"><span className="avatar" aria-hidden="true">{item.full_name.charAt(0).toUpperCase()}</span>
                      <span><strong>{item.full_name}{isSelf && <em className="you-label">YOU</em>}</strong><small>{item.email}</small></span></div></td>
                    <td><label className="visually-hidden" htmlFor={`role-${item.id}`}>Role for {item.full_name}</label>
                      <select id={`role-${item.id}`} className="role-select" value={item.role} disabled={isPending || isSelf}
                        onChange={(event) => void updateRole(item, event.target.value as WorkspaceUser["role"])}>
                        <option value="ADMIN">Admin</option><option value="MANAGER">Manager</option><option value="MEMBER">Member</option>
                      </select></td>
                    <td><span className={`status-label ${item.is_active ? "is-active" : "is-inactive"}`}><span />{item.is_active ? "Active" : "Inactive"}</span></td>
                    <td className="date-cell">{new Date(item.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</td>
                    <td className="action-cell">{isSelf ? <span className="self-note">Current account</span> :
                      <button className="row-action" type="button" disabled={isPending} onClick={() => void updateStatus(item)}>
                        {isPending ? "Saving…" : item.is_active ? "Deactivate" : "Reactivate"}
                      </button>}</td>
                  </tr>;
                })}
              </tbody>
            </table>
          </div>

          <footer className="table-footer"><span>{total > 0 ? `Showing ${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} of ${total}` : "0 accounts"}</span>
            <div className="pagination-controls"><button className="secondary-button" type="button" disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
              <span>Page {page} of {pageCount}</span>
              <button className="secondary-button" type="button" disabled={loading || offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button></div>
          </footer>
        </section>
        <p className="admin-footnote">Account creation, role changes, and access changes are recorded in the audit log.</p>
      </div>
    </main>
  );
}
