import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  api,
  ApiError,
  type DashboardStats,
  type FeedbackRule,
  type ScheduledJob,
} from "../api/client";
import { Alert } from "../components/Alert";

type GuideStep = {
  title: string;
  description: string;
  to: string;
  action: string;
  done: boolean;
  optional?: boolean;
};

export function GuidancePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [rules, setRules] = useState<FeedbackRule[]>([]);
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [dashboard, feedbackRules, scheduledJobs] = await Promise.all([
          api.get<DashboardStats>("/api/dashboard"),
          api.get<FeedbackRule[]>("/api/feedback-rules"),
          api.get<ScheduledJob[]>("/api/scheduled-jobs"),
        ]);
        setStats(dashboard);
        setRules(feedbackRules);
        setJobs(scheduledJobs);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
      }
    }
    void load();
  }, []);

  const steps = useMemo<GuideStep[]>(
    () => [
      {
        title: "Connect ACONEX",
        description: "Add OAuth credentials, authorize access, choose a project, then test the connection.",
        to: "/settings/aconex",
        action: stats?.aconex_configured ? "Review connection" : "Connect ACONEX",
        done: Boolean(stats?.aconex_configured),
      },
      {
        title: "Connect the destination sheet",
        description: "Share a Google Sheet with the service account and configure the output columns.",
        to: "/settings/google-sheets",
        action: stats?.sheets_configured ? "Review sheet" : "Connect Google Sheets",
        done: Boolean(stats?.sheets_configured),
      },
      {
        title: "Choose workflows to monitor",
        description: "Paste workflow numbers or a range such as 800–850. You can pause any item later.",
        to: "/tracked",
        action: stats?.tracked_enabled ? "Manage workflows" : "Add workflows",
        done: Boolean(stats?.tracked_enabled),
      },
      {
        title: "Define what should be synced",
        description: "Rules decide which steps, statuses, fields, and Final Mail comments are included.",
        to: "/feedback-rules",
        action: rules.length ? "Review rules" : "Create a rule",
        done: rules.some((rule) => rule.enabled),
      },
      {
        title: "Run once and check the result",
        description: "Start the full pipeline, watch its progress, then inspect Workflow Data and the sheet.",
        to: "/",
        action: stats?.last_run ? "Open Sync Center" : "Run the pipeline",
        done: Boolean(stats?.last_run?.status === "success"),
      },
      {
        title: "Automate future runs",
        description: "After the manual run looks right, schedule the full pipeline for the time you prefer.",
        to: "/schedules",
        action: jobs.some((job) => job.enabled) ? "Manage schedules" : "Create a schedule",
        done: jobs.some((job) => job.enabled),
        optional: true,
      },
    ],
    [jobs, rules, stats],
  );

  const requiredSteps = steps.filter((step) => !step.optional);
  const completed = requiredSteps.filter((step) => step.done).length;
  const nextStep = requiredSteps.find((step) => !step.done);
  const progress = Math.round((completed / requiredSteps.length) * 100);
  const isDeveloper = searchParams.get("view") === "developer";

  function setGuideView(view: "simple" | "developer") {
    setSearchParams(view === "developer" ? { view: "developer" } : {}, { replace: true });
  }

  return (
    <div className="page">
      <header className="page-header page-header-row">
        <div>
          <div className="eyebrow">Getting started</div>
          <h1 className="page-title">Guidance</h1>
          <p className="page-sub">
            {isDeveloper
              ? "Configure the API integrations, runtime environment, and service endpoints."
              : "Use the interface in this order. No API knowledge is required."}
          </p>
        </div>
        <Link className="btn secondary" to="/">
          <span className="material-symbols-outlined">space_dashboard</span>
          Open Sync Center
        </Link>
      </header>

      <Alert type="error">{error}</Alert>

      <div className="guide-view-switch" role="tablist" aria-label="Guidance version">
        <button
          type="button"
          role="tab"
          aria-selected={!isDeveloper}
          className={!isDeveloper ? "is-active" : ""}
          onClick={() => setGuideView("simple")}
        >
          <span className="material-symbols-outlined">touch_app</span>
          <span>
            <strong>Simple guide</strong>
            <small>Use the frontend</small>
          </span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={isDeveloper}
          className={isDeveloper ? "is-active" : ""}
          onClick={() => setGuideView("developer")}
        >
          <span className="material-symbols-outlined">code</span>
          <span>
            <strong>Developer guide</strong>
            <small>Configure APIs</small>
          </span>
        </button>
      </div>

      {isDeveloper ? (
        <DeveloperGuidance
          aconexConfigured={Boolean(stats?.aconex_configured)}
          sheetsConfigured={Boolean(stats?.sheets_configured)}
        />
      ) : (
        <>
          <section className="guide-progress-card">
            <div className="guide-progress-copy">
              <span className="guide-progress-value">{completed}/{requiredSteps.length}</span>
              <div>
                <strong>{progress === 100 ? "Core setup complete" : "Core setup progress"}</strong>
                <p>
                  {nextStep
                    ? `Recommended next: ${nextStep.title}`
                    : "You are ready to run and automate the workflow."}
                </p>
              </div>
            </div>
            <div className="guide-progress-track" aria-label={`${progress}% complete`}>
              <span style={{ width: `${progress}%` }} />
            </div>
            {nextStep && (
              <Link className="btn guide-next-button" to={nextStep.to}>
                {nextStep.action}
                <span className="material-symbols-outlined">arrow_forward</span>
              </Link>
            )}
          </section>

          <section className="guide-layout">
            <div className="guide-checklist">
              {steps.map((step, index) => (
                <article className={`guide-step${step.done ? " is-done" : ""}`} key={step.title}>
                  <div className="guide-step-marker">
                    <span className="guide-step-line" />
                    <span className="guide-step-number">
                      {step.done ? <span className="material-symbols-outlined">check</span> : index + 1}
                    </span>
                  </div>
                  <div className="guide-step-content">
                    <div className="guide-step-heading">
                      <h2>{step.title}</h2>
                      <span className={`badge ${step.done ? "ok" : step.optional ? "" : "warn"}`}>
                        {step.done ? "Complete" : step.optional ? "Optional" : "To do"}
                      </span>
                    </div>
                    <p>{step.description}</p>
                    <Link className="text-action" to={step.to}>
                      {step.action}
                      <span className="material-symbols-outlined">arrow_forward</span>
                    </Link>
                  </div>
                </article>
              ))}
            </div>

            <aside className="guide-aside">
              <div className="card">
                <h3>
                  <span className="material-symbols-outlined">conversion_path</span>
                  What the full pipeline does
                </h3>
                <ol className="plain-steps">
                  <li>Reads the workflows you chose to track.</li>
                  <li>Refreshes currently active workflows.</li>
                  <li>Fetches Final Mail comments required by your rules.</li>
                  <li>Writes changed rows to Google Sheets.</li>
                </ol>
              </div>

              <div className="card glossary-card">
                <h3>
                  <span className="material-symbols-outlined">dictionary</span>
                  Quick glossary
                </h3>
                <dl>
                  <dt>Tracked workflow</dt>
                  <dd>A workflow number the system checks every time it runs.</dd>
                  <dt>Feedback rule</dt>
                  <dd>A filter that decides which step data is useful and should be exported.</dd>
                  <dt>Final Mail</dt>
                  <dd>The completion email whose comment can be attached to a workflow step.</dd>
                  <dt>Pending sheet sync</dt>
                  <dd>Changed data waiting to be written to Google Sheets.</dd>
                </dl>
              </div>
            </aside>
          </section>
        </>
      )}
    </div>
  );
}

function DeveloperGuidance({
  aconexConfigured,
  sheetsConfigured,
}: {
  aconexConfigured: boolean;
  sheetsConfigured: boolean;
}) {
  return (
    <div className="developer-guide">
      <section className="developer-status">
        <div>
          <div className="eyebrow">Integration status</div>
          <h2>API configuration</h2>
          <p>Credentials are submitted through the frontend, encrypted by the backend, and never stored in localStorage.</p>
        </div>
        <div className="developer-status-actions">
          <Link to="/settings/aconex" className="developer-status-link">
            <span className={`status-dot ${aconexConfigured ? "ok" : "warn"}`} />
            <span><strong>ACONEX API</strong><small>{aconexConfigured ? "Configured" : "Not configured"}</small></span>
            <span className="material-symbols-outlined">arrow_forward</span>
          </Link>
          <Link to="/settings/google-sheets" className="developer-status-link">
            <span className={`status-dot ${sheetsConfigured ? "ok" : "warn"}`} />
            <span><strong>Google Sheets API</strong><small>{sheetsConfigured ? "Configured" : "Not configured"}</small></span>
            <span className="material-symbols-outlined">arrow_forward</span>
          </Link>
        </div>
      </section>

      <section className="architecture-card card">
        <div className="card-header">
          <h3><span className="material-symbols-outlined">account_tree</span>Runtime architecture</h3>
          <span className="badge">Docker Compose</span>
        </div>
        <div className="architecture-flow" aria-label="Runtime request flow">
          <div><span className="material-symbols-outlined">language</span><strong>Browser</strong><small>localhost:5173</small></div>
          <span className="material-symbols-outlined">arrow_forward</span>
          <div><span className="material-symbols-outlined">dns</span><strong>Nginx</strong><small>/api and /docs proxy</small></div>
          <span className="material-symbols-outlined">arrow_forward</span>
          <div><span className="material-symbols-outlined">api</span><strong>FastAPI</strong><small>backend:8000 internal</small></div>
          <span className="material-symbols-outlined">arrow_forward</span>
          <div><span className="material-symbols-outlined">database</span><strong>SQLite</strong><small>./data volume</small></div>
        </div>
        <p className="developer-note">
          The backend port is intentionally not published on the host. Use the frontend origin for REST,
          Swagger, and OpenAPI requests.
        </p>
      </section>

      <section className="developer-grid">
        <div className="stack">
          <article className="card developer-section">
            <div className="developer-section-head">
              <span className="developer-section-number">1</span>
              <div><h2>Configure ACONEX OAuth</h2><p>Oracle OAuth authorization-code flow with refresh-token support.</p></div>
            </div>
            <ol className="developer-steps">
              <li><strong>Register the callback URI.</strong><span>It must exactly match the Redirect URI entered in ACONEX Settings.</span></li>
              <li><strong>Save endpoints and client credentials.</strong><span>Authorization URL, Token URL, Base URL, audience, Client ID, and Client Secret.</span></li>
              <li><strong>Generate the authorization URL.</strong><span>Sign in to Oracle, approve access, then copy the callback <code>code</code>.</span></li>
              <li><strong>Exchange and verify.</strong><span>Exchange the code, load projects, save the Project ID, then run Test Connection.</span></li>
            </ol>
            <div className="field-reference">
              <div><code>authorization_url</code><span>Oracle login and consent endpoint</span></div>
              <div><code>token_url</code><span>Code exchange and token refresh endpoint</span></div>
              <div><code>base_url</code><span>Regional ACONEX host, for example eu1.aconex.com</span></div>
              <div><code>api_audience</code><span>OAuth audience expected by the API</span></div>
              <div><code>project_id</code><span>Project scope applied to workflow requests</span></div>
            </div>
            <Link className="btn secondary developer-link-button" to="/settings/aconex">
              Open ACONEX API settings <span className="material-symbols-outlined">arrow_forward</span>
            </Link>
          </article>

          <article className="card developer-section">
            <div className="developer-section-head">
              <span className="developer-section-number">2</span>
              <div><h2>Configure Google Sheets API</h2><p>Service-account authentication for read/write access.</p></div>
            </div>
            <ol className="developer-steps">
              <li><strong>Create a service account.</strong><span>Enable the Google Sheets API and download its JSON key.</span></li>
              <li><strong>Grant sheet access.</strong><span>Share the spreadsheet with the service account email as Editor.</span></li>
              <li><strong>Save and test.</strong><span>Provide the spreadsheet URL or ID, tab name, JSON key, and column mapping.</span></li>
            </ol>
            <Alert type="info">
              The row identity is <strong>Workflow Number + Step</strong>. Keep both fields in the column mapping.
            </Alert>
            <Link className="btn secondary developer-link-button" to="/settings/google-sheets">
              Open Google Sheets API settings <span className="material-symbols-outlined">arrow_forward</span>
            </Link>
          </article>

          <article className="card developer-section">
            <div className="developer-section-head">
              <span className="developer-section-number">3</span>
              <div><h2>Call the application API</h2><p>All routes use the same frontend origin in Compose.</p></div>
            </div>
            <div className="endpoint-list">
              <div><span className="http-method get">GET</span><code>/api/health</code><small>Service health</small></div>
              <div><span className="http-method get">GET</span><code>/api/dashboard</code><small>Setup and run summary</small></div>
              <div><span className="http-method put">PUT</span><code>/api/settings/aconex</code><small>Save OAuth settings</small></div>
              <div><span className="http-method post">POST</span><code>/api/settings/aconex/exchange-code</code><small>Exchange OAuth code</small></div>
              <div><span className="http-method post">POST</span><code>/api/runs</code><small>Start pipeline or one stage</small></div>
              <div><span className="http-method get">GET</span><code>/api/runs/&#123;id&#125;/events</code><small>SSE progress stream</small></div>
              <div><span className="http-method get">GET</span><code>/api/workflows</code><small>Search synced workflows</small></div>
            </div>
            <div className="code-sample">
              <div className="code-sample-title">Start the full pipeline</div>
              <pre><code>{`curl -X POST http://localhost:5173/api/runs \\
  -H "Content-Type: application/json" \\
  -d '{"action":"pipeline"}'`}</code></pre>
            </div>
          </article>
        </div>

        <aside className="developer-aside">
          <div className="card">
            <h3><span className="material-symbols-outlined">link</span>Runtime URLs</h3>
            <dl className="developer-definitions">
              <dt>Application</dt><dd><code>http://localhost:5173</code></dd>
              <dt>Swagger UI</dt><dd><a href="/docs" target="_blank" rel="noreferrer"><code>/docs</code></a></dd>
              <dt>OpenAPI JSON</dt><dd><a href="/openapi.json" target="_blank" rel="noreferrer"><code>/openapi.json</code></a></dd>
              <dt>Internal backend</dt><dd><code>http://backend:8000</code></dd>
            </dl>
          </div>

          <div className="card">
            <h3><span className="material-symbols-outlined">settings</span>Important environment values</h3>
            <dl className="developer-definitions">
              <dt><code>SECRET_KEY</code></dt><dd>Encryption-key derivation; replace the development value.</dd>
              <dt><code>DATABASE_URL</code></dt><dd>Defaults to the mounted SQLite database.</dd>
              <dt><code>CORS_ORIGINS</code></dt><dd>Allowed direct-browser origins for local development.</dd>
              <dt><code>DEFAULT_TIMEZONE</code></dt><dd>Scheduler timezone, currently Europe/Belgrade.</dd>
              <dt><code>ACONEX_REQUEST_TIMEOUT</code></dt><dd>Upstream request timeout in seconds.</dd>
            </dl>
          </div>

          <div className="card troubleshooting-card">
            <h3><span className="material-symbols-outlined">build</span>Quick diagnostics</h3>
            <div className="diagnostic-item"><strong>App does not open</strong><code>docker compose ps</code></div>
            <div className="diagnostic-item"><strong>API proxy fails</strong><code>docker compose logs backend</code></div>
            <div className="diagnostic-item"><strong>Test all endpoints</strong><a href="/docs" target="_blank" rel="noreferrer">Open Swagger UI</a></div>
            <div className="diagnostic-item"><strong>Port 8000 conflict</strong><span>The backend should show only <code>8000/tcp</code>, not a host mapping.</span></div>
          </div>
        </aside>
      </section>
    </div>
  );
}
