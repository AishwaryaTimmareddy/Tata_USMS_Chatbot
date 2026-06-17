import { useEffect, useState } from "react";
import { CheckCircle2, CloudCog, RefreshCw, XCircle } from "lucide-react";
import { getHealth } from "../api";
import type { Health } from "../types";

const names: Record<string, string> = {
  azureOpenAI: "Azure OpenAI",
  azureContentSafety: "Azure Content Safety",
  azureAISearch: "Azure AI Search",
  azureBlobStorage: "Azure Blob Storage",
  azureCosmosDB: "Azure Cosmos DB",
  applicationAuthentication: "Application authentication",
};

export function ReadinessPanel() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState("");

  async function refresh() {
    setError("");
    try {
      setHealth(await getHealth());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Health check failed.");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div>
      <header className="page-header">
        <div>
          <span className="eyebrow">CONFIGURATION</span>
          <h1>Azure readiness</h1>
          <p>Supply these values after the Azure subscription resources are created.</p>
        </div>
        <button className="secondary-button" onClick={refresh}>
          <RefreshCw size={16} /> Refresh
        </button>
      </header>

      <section className="readiness-summary">
        <div className="cloud-icon"><CloudCog size={30} /></div>
        <div>
          <strong>{health?.ready ? "Ready for Azure requests" : "Waiting for Azure configuration"}</strong>
          <p>
            {health?.ready
              ? "All required service endpoints and application settings are present."
              : "The application does not substitute local services when Azure is unavailable."}
          </p>
        </div>
      </section>

      {error && <div className="error-banner">{error}</div>}
      <div className="readiness-grid">
        {health &&
          Object.entries(health.services).map(([key, service]) => (
            <article className="service-card" key={key}>
              <div className={service.configured ? "service-icon ready" : "service-icon pending"}>
                {service.configured ? <CheckCircle2 size={21} /> : <XCircle size={21} />}
              </div>
              <div>
                <strong>{names[key] ?? key}</strong>
                <span>{service.configured ? "Configured" : "Configuration required"}</span>
              </div>
              {!service.configured && (
                <ul>
                  {service.missing.map((setting) => <li key={setting}>{setting}</li>)}
                </ul>
              )}
            </article>
          ))}
      </div>
    </div>
  );
}
