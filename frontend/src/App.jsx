import { useState, useEffect, useCallback } from "react"
import axios from "axios"
import StatsCards from "./components/StatsCards"
import TransactionTable from "./components/TransactionTable"
import PredictForm from "./components/PredictForm"
import RiskChart from "./components/RiskChart"
import MetricsPage from "./components/MetricsPage"
import HistoryPage from "./components/HistoryPage"
import ResultPanel from "./components/ResultPanel"

export default function App() {
  const [stats, setStats] = useState({ total: 0, fraud: 0, legit: 0, fraud_rate: 0 })
  const [transactions, setTransactions] = useState([])
  const [activePage, setActivePage] = useState("dashboard")
  const [latestResult, setLatestResult] = useState(null)

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, txRes] = await Promise.all([
        axios.get("http://localhost:8000/stats"),
        axios.get("http://localhost:8000/transactions")
      ])
      setStats(statsRes.data)
      setTransactions(txRes.data)
    } catch (e) {
      console.error("Failed to fetch data", e)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [fetchData])

  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: "▦" },
    { id: "analyze",   label: "Analyze",   icon: "⊕" },
    { id: "history",   label: "History",   icon: "☰" },
    { id: "metrics",   label: "Metrics",   icon: "◈" },
  ]

  return (
    <div style={{
      minHeight: "100vh",
      background: "#f4f5f7",
      color: "#1a1a2e",
      fontFamily: "'Inter', -apple-system, sans-serif",
      display: "flex"
    }}>
      {/* Sidebar */}
      <div style={{
        width: "220px", minHeight: "100vh",
        background: "#fff",
        borderRight: "1px solid #e8e8f0",
        padding: "24px 0",
        display: "flex", flexDirection: "column",
        position: "fixed", top: 0, left: 0,
        boxShadow: "2px 0 8px rgba(0,0,0,0.04)"
      }}>
        {/* Logo */}
        <div style={{ padding: "0 20px 32px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{
              width: "34px", height: "34px", borderRadius: "9px",
              background: "linear-gradient(135deg, #2563eb, #1d4ed8)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: "16px", boxShadow: "0 2px 8px rgba(37,99,235,0.3)"
            }}>🛡️</div>
            <div>
              <p style={{ fontSize: "14px", fontWeight: "700", margin: 0, color: "#1a1a2e" }}>FraudShield</p>
              <p style={{ fontSize: "10px", color: "#aaa", margin: 0 }}>v4.0 · 7 Models</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: "0 12px" }}>
          {navItems.map(item => (
            <button key={item.id} onClick={() => setActivePage(item.id)} style={{
              width: "100%", padding: "10px 12px",
              background: activePage === item.id ? "#eff6ff" : "transparent",
              border: activePage === item.id ? "1px solid #bfdbfe" : "1px solid transparent",
              borderRadius: "8px",
              color: activePage === item.id ? "#2563eb" : "#888",
              fontSize: "13px", fontWeight: activePage === item.id ? "600" : "400",
              cursor: "pointer", textAlign: "left",
              display: "flex", alignItems: "center", gap: "10px",
              marginBottom: "4px", transition: "all 0.15s"
            }}>
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        {/* Status */}
        <div style={{ padding: "0 20px" }}>
          <div style={{
            padding: "10px 12px", borderRadius: "8px",
            background: "#f0fdf4", border: "1px solid #bbf7d0"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
              <div style={{
                width: "6px", height: "6px", borderRadius: "50%",
                background: "#16a34a", boxShadow: "0 0 6px #16a34a"
              }} />
              <span style={{ fontSize: "11px", color: "#16a34a", fontWeight: "600" }}>LIVE</span>
            </div>
            <p style={{ fontSize: "10px", color: "#888", margin: 0 }}>
              {stats.total} transactions analyzed
            </p>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div style={{ marginLeft: "220px", flex: 1, padding: "32px" }}>
        {activePage === "dashboard" && (
          <div>
            <div style={{ marginBottom: "28px" }}>
              <h1 style={{ fontSize: "20px", fontWeight: "700", margin: "0 0 4px", color: "#1a1a2e" }}>
                Transaction Dashboard
              </h1>
              <p style={{ color: "#aaa", fontSize: "13px", margin: 0 }}>
                Real-time fraud monitoring · 5-model ensemble · LLM analysis
              </p>
            </div>
            <StatsCards stats={stats} />
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "16px", marginBottom: "16px" }}>
              <div style={{
                background: "#fff", border: "1px solid #e8e8f0",
                borderRadius: "12px", padding: "24px",
                boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
              }}>
                <p style={{ fontSize: "13px", fontWeight: "600", color: "#1a1a2e", marginBottom: "16px" }}>
                  Recent Transactions
                </p>
                <TransactionTable transactions={transactions.slice(0, 10)} />
              </div>
              <RiskChart stats={stats} />
            </div>
          </div>
        )}

{activePage === "analyze" && (
  <div>
    <div style={{ marginBottom: "28px" }}>
      <h1 style={{ fontSize: "20px", fontWeight: "700", margin: "0 0 4px", color: "#1a1a2e" }}>
        Analyze Transaction
      </h1>
      <p style={{ color: "#aaa", fontSize: "13px", margin: 0 }}>
        Submit a transaction for real-time ML ensemble scoring
      </p>
    </div>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", alignItems: "start" }}>
      <PredictForm onNewTransaction={fetchData} onResult={setLatestResult} />
      <ResultPanel result={latestResult} />
    </div>
  </div>
)}
        {activePage === "history" && (
          <div>
            <div style={{ marginBottom: "28px" }}>
              <h1 style={{ fontSize: "20px", fontWeight: "700", margin: "0 0 4px", color: "#1a1a2e" }}>
                Transaction History
              </h1>
              <p style={{ color: "#aaa", fontSize: "13px", margin: 0 }}>
                Full log of all analyzed transactions · Search, filter, and export
              </p>
            </div>
            <HistoryPage transactions={transactions} />
          </div>
        )}
        {activePage === "metrics" && <MetricsPage />}
      </div>
    </div>
  )
}