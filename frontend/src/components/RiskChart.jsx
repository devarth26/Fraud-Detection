import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts"

export default function RiskChart({ stats }) {
  const data = [
    { name: "Legitimate", value: stats.legit || 0 },
    { name: "Fraud", value: stats.fraud || 0 }
  ]

  const COLORS = ["#16a34a", "#dc2626"]

  return (
    <div style={{
      background: "#fff",
      border: "1px solid #e8e8f0",
      borderRadius: "12px",
      padding: "20px",
      boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
    }}>
      <p style={{ fontSize: "13px", fontWeight: "600", color: "#1a1a2e", marginBottom: "4px" }}>
        Fraud Distribution
      </p>
      <p style={{ fontSize: "11px", color: "#aaa", marginBottom: "16px" }}>
        Legitimate vs flagged transactions
      </p>

      {stats.total === 0 ? (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          height: "200px", color: "#ccc", fontSize: "13px",
          flexDirection: "column", gap: "8px"
        }}>
          <span style={{ fontSize: "24px" }}>📊</span>
          No data yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={90}
              paddingAngle={3}
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={index} fill={COLORS[index]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "#fff",
                border: "1px solid #e8e8f0",
                borderRadius: "8px",
                color: "#1a1a2e",
                boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                fontSize: "12px"
              }}
            />
            <Legend
              formatter={(value) => (
                <span style={{ color: "#666", fontSize: "12px" }}>{value}</span>
              )}
            />
          </PieChart>
        </ResponsiveContainer>
      )}

      {stats.total > 0 && (
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr",
          gap: "8px", marginTop: "8px"
        }}>
          <div style={{
            padding: "10px", borderRadius: "8px",
            background: "#f0fdf4", border: "1px solid #bbf7d0",
            textAlign: "center"
          }}>
            <p style={{ fontSize: "16px", fontWeight: "700", color: "#16a34a", margin: 0 }}>
              {stats.legit}
            </p>
            <p style={{ fontSize: "10px", color: "#aaa", margin: 0 }}>Legitimate</p>
          </div>
          <div style={{
            padding: "10px", borderRadius: "8px",
            background: "#fef2f2", border: "1px solid #fecaca",
            textAlign: "center"
          }}>
            <p style={{ fontSize: "16px", fontWeight: "700", color: "#dc2626", margin: 0 }}>
              {stats.fraud}
            </p>
            <p style={{ fontSize: "10px", color: "#aaa", margin: 0 }}>Fraud</p>
          </div>
        </div>
      )}
    </div>
  )
}