const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export default function App() {
  return (
    <main className="page-shell">
      <section className="welcome-card" aria-labelledby="welcome-title">
        <div className="brand-mark" aria-hidden="true">IG</div>
        <p className="eyebrow">Invictus Grid</p>
        <h1 id="welcome-title">Workspace foundation is ready</h1>
        <p className="description">
          A shared home for club projects, tasks, reviews, and work evidence.
        </p>
        <span className="status-pill"><span className="status-dot" /> API configured</span>
        <p className="connection-note">Backend: <code>{apiBaseUrl}</code></p>
      </section>
    </main>
  );
}
