import { useEffect, useMemo, useState } from "react";
import { api, setSession, getSession } from "./lib/api/client";

export default function SamplesPanel() {
  const [authMsg, setAuthMsg] = useState("");
  const [displayName, setDisplayName] = useState("Guest");
  const [sessionId, setSessionId] = useState(getSession());

  const [health, setHealth] = useState(null);
  const [samplesResp, setSamplesResp] = useState(null);

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  async function doGuestAuth() {
    setErr(null);
    setAuthMsg("");
    setLoading(true);
    try {
      const r = await api.post("/auth/guest", { display_name: displayName });
      const sid = r?.session?.id || r?.session || "";
      if (!sid) throw new Error("No session id returned");
      setSession(sid);
      setSessionId(sid);
      setAuthMsg("Signed in (guest).");
    } catch (e) {
      const msg = e?.data?.message || e?.data?.error || e?.message || String(e);
      setErr(msg);
    } finally {
      setLoading(false);
    }
  }

  async function loadHealth() {
    setErr(null);
    setLoading(true);
    try {
      const r = await api.get("/health");
      setHealth(r);
    } catch (e) {
      const msg = e?.data?.message || e?.data?.error || e?.message || String(e);
      setErr(msg);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }

  async function loadSamples() {
    setErr(null);
    setLoading(true);
    try {
      const r = await api.get("/sample/list");
      setSamplesResp(r);
    } catch (e) {
      const msg = e?.data?.message || e?.data?.error || e?.message || String(e);
      setErr(msg);
      setSamplesResp(null);
    } finally {
      setLoading(false);
    }
  }

  // Optional: if a session exists already, try loading samples once on mount.
  useEffect(() => {
    if (getSession()) loadSamples();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rows = useMemo(() => {
    const r = samplesResp;
    if (!r) return [];
    if (Array.isArray(r)) return r;
    if (Array.isArray(r.samples)) return r.samples;
    if (Array.isArray(r.items)) return r.items;
    return [];
  }, [samplesResp]);

  return (
    <div style={{ padding: 12 }}>
      <h2 style={{ marginTop: 0 }}>Demo: Samples</h2>

      <div style={{ padding: 12, border: "1px solid #ddd", borderRadius: 8, marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <strong>Auth</strong>
          <span style={{ opacity: 0.8 }}>session:</span>
          <code style={{ fontSize: 12 }}>{sessionId || "(none)"}</code>
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="display name"
            style={{ padding: "6px 8px" }}
          />
          <button onClick={doGuestAuth} disabled={loading} style={{ padding: "6px 10px" }}>
            Guest Sign-In
          </button>
          <button onClick={loadSamples} disabled={loading} style={{ padding: "6px 10px" }}>
            Load samples
          </button>
          <button onClick={loadHealth} disabled={loading} style={{ padding: "6px 10px" }}>
            Load health
          </button>
          {authMsg ? <span style={{ marginLeft: 8 }}>{authMsg}</span> : null}
        </div>

        {loading ? <div style={{ marginTop: 8, opacity: 0.8 }}>Loading…</div> : null}
        {err ? <div style={{ marginTop: 8, color: "crimson" }}>Error: {err}</div> : null}

        {health ? (
          <div style={{ marginTop: 10, opacity: 0.9 }}>
            <strong>Health:</strong>{" "}
            <code style={{ fontSize: 12 }}>{typeof health === "string" ? health : JSON.stringify(health)}</code>
          </div>
        ) : null}
      </div>

      <div style={{ marginBottom: 10, opacity: 0.85 }}>
        {samplesResp?.count != null ? (
          <span>
            Returned <strong>{rows.length}</strong> / <strong>{samplesResp.count}</strong>
          </span>
        ) : (
          <span>
            Returned <strong>{rows.length}</strong>
          </span>
        )}
      </div>

      {rows.length ? (
        <div style={{ overflowX: "auto" }}>
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <thead>
              <tr>
                {["id", "external_id", "status", "container_id", "created_at"].map((h) => (
                  <th key={h} style={{ textAlign: "left", padding: "8px 10px", borderBottom: "1px solid #ccc" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((s, i) => (
                <tr key={s?.id ?? s?.external_id ?? i}>
                  <td style={{ padding: "8px 10px", borderBottom: "1px solid #eee" }}>{s?.id ?? "—"}</td>
                  <td style={{ padding: "8px 10px", borderBottom: "1px solid #eee" }}>{s?.external_id ?? "—"}</td>
                  <td style={{ padding: "8px 10px", borderBottom: "1px solid #eee" }}>{s?.status ?? "—"}</td>
                  <td style={{ padding: "8px 10px", borderBottom: "1px solid #eee" }}>{s?.container_id ?? "—"}</td>
                  <td style={{ padding: "8px 10px", borderBottom: "1px solid #eee" }}>{s?.created_at ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <pre style={{ background: "#111", color: "#eee", padding: 12, borderRadius: 10, overflowX: "auto" }}>
{samplesResp ? JSON.stringify(samplesResp, null, 2) : "Click Guest Sign-In, then Load samples. Use Load health to check /health."}
        </pre>
      )}
    </div>
  );
}
