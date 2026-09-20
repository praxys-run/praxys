/** Shared by the static app document and the session-restoration boundary. */
export default function AppLoadingShell() {
  return (
    <main className="app-loading-shell" aria-busy="true" aria-label="Praxys">
      <div className="app-loading-brand">Praxys</div>
      <div className="app-loading-lines" aria-hidden="true">
        <span /><span /><span />
      </div>
    </main>
  );
}
