import { ChangeEvent, useEffect, useRef, useState } from "react";
import {
  CloudUpload,
  Download,
  Eye,
  FileText,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import {
  deleteDocument,
  downloadDocument,
  getIndexerStatus,
  listDocuments,
  runIndexer,
  uploadDocument,
  viewDocument,
} from "../api";
import type { DocumentItem } from "../types";

export function AdminPanel({ token }: { token: string }) {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [category, setCategory] = useState("product");
  const [busy, setBusy] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const pollCancelled = useRef(false);

  useEffect(() => {
    listDocuments(token).then(setDocuments).catch((reason) => setError(reason.message));
    return () => {
      pollCancelled.current = true;
    };
  }, [token]);

  function wait(ms: number) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  async function pollIndexerStatus() {
    pollCancelled.current = false;
    for (let attempt = 0; attempt < 36; attempt += 1) {
      if (pollCancelled.current) return;
      await wait(attempt === 0 ? 2500 : 5000);
      const status = await getIndexerStatus(token);
      const state = (status.last_result || status.status || "").toLowerCase();
      if (state === "success") {
        setNotice(
          `Indexing completed. Processed ${status.processed} document${status.processed === 1 ? "" : "s"}.`,
        );
        return;
      }
      if (state.includes("failure") || status.failed > 0) {
        setError(status.errors[0] || "Indexing failed. Please review the Azure AI Search indexer details.");
        return;
      }
      setNotice("Indexing is still running. You can continue using the app while it completes.");
    }
    setNotice("Indexing is still running. Refresh this page or check Azure AI Search indexer status shortly.");
  }

  async function onUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      await uploadDocument(token, file, category);
      setDocuments(await listDocuments(token));
      setNotice(`${file.name} uploaded. Click Run indexer to make it searchable.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed.");
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  async function remove(name: string) {
    if (!window.confirm(`Remove ${name} from the approved repository?`)) return;
    setBusy(true);
    setError("");
    try {
      const result = await deleteDocument(token, name);
      setDocuments(await listDocuments(token));
      if (result.cleanup_warning) {
        setNotice(`${name} removed from storage.`);
        setError(result.cleanup_warning);
      } else {
        const cleanupText = result.purged
          ? ` Removed ${result.purged} search chunk${result.purged === 1 ? "" : "s"}.`
          : " No matching search chunks were found.";
        setNotice(`${name} removed.${cleanupText}`);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Delete failed.");
      try {
        setDocuments(await listDocuments(token));
      } catch {
        setDocuments((current) => current.filter((item) => item.name !== name));
      }
    } finally {
      setBusy(false);
    }
  }

  async function reindex() {
    setBusy(true);
    setIndexing(true);
    setError("");
    try {
      const result = await runIndexer(token);
      const cleanupText = result.purged
        ? ` Removed ${result.purged} stale index chunk${result.purged === 1 ? "" : "s"}.`
        : "";
      setNotice(
        result.cleanup_warning || `Azure AI Search indexing has started.${cleanupText}`,
      );
      await pollIndexerStatus();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Indexer could not start.");
    } finally {
      setBusy(false);
      setIndexing(false);
    }
  }

  async function openDocument(name: string) {
    setError("");
    try {
      await viewDocument(token, name);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Document could not be opened.");
    }
  }

  async function saveDocument(name: string) {
    setError("");
    try {
      await downloadDocument(token, name);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Download failed.");
    }
  }

  return (
    <div>
      <header className="page-header">
        <div>
          <span className="eyebrow">ADMINISTRATION</span>
          <h1>Knowledge base</h1>
          <p>Only the administrator can manage approved documents.</p>
        </div>
        <button className="secondary-button" onClick={reindex} disabled={busy || indexing}>
          <RefreshCw size={16} className={indexing ? "spin" : ""} /> {indexing ? "Indexing..." : "Run indexer"}
        </button>
      </header>
      <section className="upload-card">
        <div><CloudUpload size={24} /><div><strong>Add an approved document</strong><p>Maximum 50 MB.</p></div></div>
        <select value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="product">Product</option><option value="delivery">Delivery</option>
          <option value="returns">Returns</option><option value="policy">Policy</option><option value="faq">FAQ</option>
        </select>
        <label className="primary-button file-button">
          {busy && !indexing ? <LoaderCircle size={17} className="spin" /> : <CloudUpload size={17} />} Upload
          <input type="file" accept=".pdf,.docx,.pptx,.xlsx,.txt" onChange={onUpload} disabled={busy || indexing} />
        </label>
      </section>
      {notice && <div className="success-banner">{notice}</div>}
      {error && <div className="error-banner">{error}</div>}
      <section className="document-card">
        <div className="section-heading"><h2>Approved documents</h2><p>{documents.length} files</p></div>
        {documents.map((document) => (
          <div className="document-row" key={document.name}>
            <div className="file-icon"><FileText size={19} /></div>
            <div className="file-name"><strong>{document.name}</strong><span>{(document.size / 1024 / 1024).toFixed(2)} MB</span></div>
            <span className="approved-pill"><ShieldCheck size={13} /> Approved</span>
            <div className="document-actions">
              <button className="icon-button" title="View document" aria-label={`View ${document.name}`} onClick={() => openDocument(document.name)}><Eye size={17} /></button>
              <button className="icon-button" title="Download document" aria-label={`Download ${document.name}`} onClick={() => saveDocument(document.name)}><Download size={17} /></button>
              <button className="icon-button danger" title="Delete document" aria-label={`Delete ${document.name}`} onClick={() => remove(document.name)}><Trash2 size={17} /></button>
            </div>
          </div>
        ))}
        {!documents.length && <div className="empty-state">No documents uploaded yet.</div>}
      </section>
    </div>
  );
}
