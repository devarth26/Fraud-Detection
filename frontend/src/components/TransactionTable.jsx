export default function TransactionTable({ transactions }) {
  const riskStyle = {
    HIGH:   { bg: "#fef2f2", color: "#dc2626", border: "#fecaca" },
    MEDIUM: { bg: "#fffbeb", color: "#d97706", border: "#fde68a" },
    LOW:    { bg: "#f0fdf4", color: "#16a34a", border: "#bbf7d0" }
  }

  if (transactions.length === 0) {
    return (
      <div style={{
        textAlign: "center", padding: "3rem",
        color: "#ccc", fontSize: "13px",
        display: "flex", flexDirection: "column",
        alignItems: "center", gap: "8px"
      }}>
        <span style={{ fontSize: "28px" }}>📭</span>
        No transactions yet. Submit one from the Analyze tab.
      </div>
    )
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #f0f0f8" }}>
            {["#", "Amount", "Merchant", "Location", "Risk", "Verdict", "Confidence"].map(h => (
              <th key={h} style={{
                padding: "8px 12px", textAlign: "left",
                color: "#aaa", fontWeight: "500",
                fontSize: "11px", textTransform: "uppercase",
                letterSpacing: "0.05em"
              }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx) => {
            const risk = riskStyle[tx.risk_tier] || riskStyle.LOW
            return (
              <tr key={tx.id}
                style={{ borderBottom: "1px solid #f8f8fc", transition: "background 0.1s" }}
                onMouseEnter={e => e.currentTarget.style.background = "#fafafe"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <td style={{ padding: "11px 12px", color: "#ccc", fontSize: "12px" }}>
                  #{tx.id}
                </td>
                <td style={{ padding: "11px 12px", color: "#1a1a2e", fontWeight: "600" }}>
                  ${parseFloat(tx.amount).toLocaleString()}
                </td>
                <td style={{ padding: "11px 12px", color: "#444" }}>
                  {tx.merchant_category}
                </td>
                <td style={{ padding: "11px 12px", color: "#888", fontSize: "12px" }}>
                  {tx.location}
                </td>
                <td style={{ padding: "11px 12px" }}>
                  <span style={{
                    background: risk.bg, color: risk.color,
                    border: `1px solid ${risk.border}`,
                    padding: "3px 8px", borderRadius: "6px",
                    fontSize: "11px", fontWeight: "600"
                  }}>
                    {tx.risk_tier}
                  </span>
                </td>
                <td style={{ padding: "11px 12px" }}>
                  <span style={{
                    color: tx.is_fraud ? "#dc2626" : "#16a34a",
                    fontWeight: "500", fontSize: "12px"
                  }}>
                    {tx.is_fraud ? "🚨 Fraud" : "✅ Legit"}
                  </span>
                </td>
                <td style={{ padding: "11px 12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div style={{
                      flex: 1, height: "4px",
                      background: "#f0f0f8", borderRadius: "2px",
                      overflow: "hidden", minWidth: "60px"
                    }}>
                      <div style={{
                        width: `${Math.round(tx.confidence * 100)}%`,
                        height: "100%",
                        background: tx.is_fraud ? "#dc2626" : "#16a34a",
                        borderRadius: "2px"
                      }} />
                    </div>
                    <span style={{ fontSize: "11px", color: "#aaa", minWidth: "32px" }}>
                      {Math.round(tx.confidence * 100)}%
                    </span>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}