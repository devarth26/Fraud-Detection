export default function StatsCards({ stats }) {
  const cards = [
    {
      label: "Total Analyzed",
      value: stats.total,
      color: "#2563eb",
      bg: "#eff6ff",
      border: "#bfdbfe",
      icon: "📋"
    },
    {
      label: "Fraud Detected",
      value: stats.fraud,
      color: "#dc2626",
      bg: "#fef2f2",
      border: "#fecaca",
      icon: "🚨"
    },
    {
      label: "Legitimate",
      value: stats.legit,
      color: "#16a34a",
      bg: "#f0fdf4",
      border: "#bbf7d0",
      icon: "✅"
    },
    {
      label: "Fraud Rate",
      value: stats.total > 0 ? `${stats.fraud_rate}%` : "—",
      color: "#d97706",
      bg: "#fffbeb",
      border: "#fde68a",
      icon: "⚠️"
    }
  ]

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(4, 1fr)",
      gap: "16px",
      marginBottom: "24px"
    }}>
      {cards.map((card) => (
        <div key={card.label} style={{
          background: "#fff",
          border: "1px solid #e8e8f0",
          borderRadius: "12px",
          padding: "20px",
          boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
            <p style={{
              fontSize: "11px", color: "#aaa", margin: 0,
              textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: "500"
            }}>
              {card.label}
            </p>
            <div style={{
              width: "28px", height: "28px", borderRadius: "8px",
              background: card.bg, border: `1px solid ${card.border}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: "13px"
            }}>
              {card.icon}
            </div>
          </div>
          <p style={{ fontSize: "28px", fontWeight: "700", color: card.color, margin: 0 }}>
            {card.value}
          </p>
        </div>
      ))}
    </div>
  )
}