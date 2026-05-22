import { useState, useMemo } from "react"
import axios from "axios"

const riskStyle = {
  HIGH:   { bg: "#fef2f2", color: "#dc2626", border: "#fecaca" },
  MEDIUM: { bg: "#fffbeb", color: "#d97706", border: "#fde68a" },
  LOW:    { bg: "#f0fdf4", color: "#16a34a", border: "#bbf7d0" }
}

export default function HistoryPage({ transactions }) {
  const [search, setSearch]       = useState("")
  const [riskFilter, setRisk]     = useState("ALL")
  const [verdictFilter, setVerdict] = useState("ALL")
  const [merchantFilter, setMerchant] = useState("ALL")
  const [expanded, setExpanded]   = useState(null)

  const merchants = useMemo(() => {
    const all = [...new Set(transactions.map(t => t.merchant_category))]
    return ["ALL", ...all.sort()]
  }, [transactions])

  const filtered = useMemo(() => {
    return transactions.filter(t => {
      const matchSearch =
        search === "" ||
        String(t.id).includes(search) ||
        t.merchant_category.toLowerCase().includes(search.toLowerCase()) ||
        t.location.toLowerCase().includes(search.toLowerCase()) ||
        String(t.amount).includes(search)

      const matchRisk    = riskFilter === "ALL"    || t.risk_tier === riskFilter
      const matchVerdict = verdictFilter === "ALL" ||
        (verdictFilter === "FRAUD" && t.is_fraud) ||
        (verdictFilter === "LEGIT" && !t.is_fraud)
      const matchMerchant = merchantFilter === "ALL" || t.merchant_category === merchantFilter

      return matchSearch && matchRisk && matchVerdict && matchMerchant
    })
  }, [transactions, search, riskFilter, verdictFilter, merchantFilter])

  const fraudCount = filtered.filter(t => t.is_fraud).length
  const legitCount = filtered.filter(t => !t.is_fraud).length

  const handleExport = () => {
    const headers = ["ID","Amount","Merchant","Location","Time","Transactions 24h","Card Age","Device","Risk","Verdict","Confidence","Timestamp"]
    const rows = filtered.map(t => [
      t.id, t.amount, t.merchant_category, t.location,
      t.time_of_day, t.transactions_last_24h, t.card_age_months,
      t.device_match, t.risk_tier,
      t.is_fraud ? "FRAUD" : "LEGIT",
      Math.round(t.confidence * 100) + "%",
      t.timestamp
    ])
    const csv = [headers, ...rows].map(r => r.join(",")).join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "fraudshield_transactions.csv"
    a.click()
  }

  const inputStyle = {
    padding: "8px 12px", background: "#f8f8fc",
    border: "1px solid #e8e8f0", borderRadius: "8px",
    color: "#1a1a2e", fontSize: "13px", outline: "none"
  }

  return (
    <div>
      {/* Filters */}
      <div style={{
        background: "#fff", border: "1px solid #e8e8f0",
        borderRadius: "12px", padding: "16px 20px",
        marginBottom: "16px", boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
        display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap"
      }}>
        {/* Search */}
        <div style={{ flex: 1, minWidth: "200px", position: "relative" }}>
          <span style={{
            position: "absolute", left: "10px", top: "50%",
            transform: "translateY(-50%)", color: "#aaa", fontSize: "13px"
          }}>🔍</span>
          <input
            style={{ ...inputStyle, width: "100%", paddingLeft: "30px" }}
            placeholder="Search by ID, merchant, location, amount..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        {/* Risk filter */}
        <select style={inputStyle} value={riskFilter} onChange={e => setRisk(e.target.value)}>
          <option value="ALL">All Risk Levels</option>
          <option value="HIGH">High Risk</option>
          <option value="MEDIUM">Medium Risk</option>
          <option value="LOW">Low Risk</option>
        </select>

        {/* Verdict filter */}
        <select style={inputStyle} value={verdictFilter} onChange={e => setVerdict(e.target.value)}>
          <option value="ALL">All Verdicts</option>
          <option value="FRAUD">Fraud Only</option>
          <option value="LEGIT">Legitimate Only</option>
        </select>

        {/* Merchant filter */}
        <select style={inputStyle} value={merchantFilter} onChange={e => setMerchant(e.target.value)}>
          {merchants.map(m => (
            <option key={m} value={m}>{m === "ALL" ? "All Merchants" : m}</option>
          ))}
        </select>

        {/* Export */}
        <button onClick={handleExport} style={{
          padding: "8px 16px", background: "#fff",
          border: "1px solid #e8e8f0", borderRadius: "8px",
          color: "#444", fontSize: "13px", fontWeight: "500",
          cursor: "pointer", whiteSpace: "nowrap"
        }}>
          ↓ Export CSV
        </button>
      </div>

      {/* Summary bar */}
      <div style={{
        display: "flex", gap: "12px", marginBottom: "16px"
      }}>
        {[
          { label: "Showing",  value: filtered.length, color: "#2563eb" },
          { label: "Fraud",    value: fraudCount,       color: "#dc2626" },
          { label: "Legit",    value: legitCount,       color: "#16a34a" },
        ].map(item => (
          <div key={item.label} style={{
            background: "#fff", border: "1px solid #e8e8f0",
            borderRadius: "8px", padding: "10px 16px",
            boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
            display: "flex", alignItems: "center", gap: "8px"
          }}>
            <span style={{ fontSize: "11px", color: "#aaa", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              {item.label}
            </span>
            <span style={{ fontSize: "16px", fontWeight: "700", color: item.color }}>
              {item.value}
            </span>
          </div>
        ))}
      </div>

      {/* Table */}
      <div style={{
        background: "#fff", border: "1px solid #e8e8f0",
        borderRadius: "12px", overflow: "hidden",
        boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
      }}>
        {filtered.length === 0 ? (
          <div style={{
            textAlign: "center", padding: "4rem",
            color: "#ccc", fontSize: "13px",
            display: "flex", flexDirection: "column",
            alignItems: "center", gap: "8px"
          }}>
            <span style={{ fontSize: "28px" }}>🔎</span>
            No transactions match your filters
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
            <thead>
              <tr style={{ background: "#fafafe", borderBottom: "1px solid #f0f0f8" }}>
                {["#", "Amount", "Merchant", "Location", "Time", "Device", "Risk", "Verdict", "Confidence", "Date"].map(h => (
                  <th key={h} style={{
                    padding: "11px 14px", textAlign: "left",
                    color: "#aaa", fontWeight: "500",
                    fontSize: "11px", textTransform: "uppercase",
                    letterSpacing: "0.05em"
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((tx) => {
                const risk = riskStyle[tx.risk_tier] || riskStyle.LOW
                const isExp = expanded === tx.id
                return (
                  <>
                    <tr
                      key={tx.id}
                      onClick={() => setExpanded(isExp ? null : tx.id)}
                      style={{
                        borderBottom: isExp ? "none" : "1px solid #f8f8fc",
                        cursor: "pointer", transition: "background 0.1s",
                        background: isExp ? "#fafafe" : "transparent"
                      }}
                      onMouseEnter={e => { if (!isExp) e.currentTarget.style.background = "#fafafe" }}
                      onMouseLeave={e => { if (!isExp) e.currentTarget.style.background = "transparent" }}
                    >
                      <td style={{ padding: "11px 14px", color: "#ccc", fontSize: "12px" }}>#{tx.id}</td>
                      <td style={{ padding: "11px 14px", color: "#1a1a2e", fontWeight: "600" }}>
                        ${parseFloat(tx.amount).toLocaleString()}
                      </td>
                      <td style={{ padding: "11px 14px", color: "#444" }}>{tx.merchant_category}</td>
                      <td style={{ padding: "11px 14px", color: "#888", fontSize: "12px" }}>{tx.location}</td>
                      <td style={{ padding: "11px 14px", color: "#888", fontSize: "12px" }}>{tx.time_of_day}</td>
                      <td style={{ padding: "11px 14px", color: "#888", fontSize: "12px" }}>{tx.device_match}</td>
                      <td style={{ padding: "11px 14px" }}>
                        <span style={{
                          background: risk.bg, color: risk.color,
                          border: `1px solid ${risk.border}`,
                          padding: "3px 8px", borderRadius: "6px",
                          fontSize: "11px", fontWeight: "600"
                        }}>
                          {tx.risk_tier}
                        </span>
                      </td>
                      <td style={{ padding: "11px 14px" }}>
                        <span style={{
                          color: tx.is_fraud ? "#dc2626" : "#16a34a",
                          fontWeight: "600", fontSize: "12px"
                        }}>
                          {tx.is_fraud ? "🚨 Fraud" : "✅ Legit"}
                        </span>
                      </td>
                      <td style={{ padding: "11px 14px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <div style={{
                            width: "50px", height: "4px",
                            background: "#f0f0f8", borderRadius: "2px", overflow: "hidden"
                          }}>
                            <div style={{
                              width: `${Math.round(tx.confidence * 100)}%`,
                              height: "100%",
                              background: tx.is_fraud ? "#dc2626" : "#16a34a",
                              borderRadius: "2px"
                            }} />
                          </div>
                          <span style={{ fontSize: "11px", color: "#aaa" }}>
                            {Math.round(tx.confidence * 100)}%
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: "11px 14px", color: "#aaa", fontSize: "11px" }}>
                        {new Date(tx.timestamp).toLocaleString()}
                      </td>
                    </tr>

                    {/* Expanded row — AI explanation */}
                    {isExp && (
                      <tr key={`${tx.id}-exp`}>
                        <td colSpan={10} style={{
                          padding: "0 14px 14px 14px",
                          background: "#fafafe",
                          borderBottom: "1px solid #f0f0f8"
                        }}>
                          <div style={{
                            padding: "14px 16px", borderRadius: "8px",
                            background: "#fff", border: "1px solid #e8e8f0"
                          }}>
                            <p style={{
                              fontSize: "11px", color: "#aaa",
                              textTransform: "uppercase", letterSpacing: "0.05em",
                              marginBottom: "8px", fontWeight: "500"
                            }}>
                              🤖 AI Analyst Report
                            </p>
                            <p style={{
                              fontSize: "12px", color: "#444",
                              lineHeight: "1.8", whiteSpace: "pre-line", margin: 0
                            }}>
                              {tx.reason || "No report available."}
                            </p>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}