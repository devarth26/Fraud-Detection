import { useState, useEffect } from "react"
import axios from "axios"

const modelColors = {
  xgboost:             "#2563eb",
  random_forest:       "#16a34a",
  logistic_regression: "#d97706",
  gradient_boosting:   "#9333ea",
  lstm:                "#0891b2",
  autoencoder:         "#db2777"
}

const modelLabels = {
  xgboost:             "XGBoost",
  random_forest:       "Random Forest",
  logistic_regression: "Logistic Regression",
  gradient_boosting:   "Gradient Boosting",
  lstm:                "LSTM (Bidirectional + Attention)",
  autoencoder:         "Autoencoder"
}

const modelRoles = {
  xgboost:             "Primary classifier · Gradient boosting",
  random_forest:       "Stability anchor · Bagging ensemble",
  logistic_regression: "Linear baseline · Fast inference",
  gradient_boosting:   "Sequential boosting · High precision",
  lstm:                "Sequence modeling · Behavioral anomaly detection",
  autoencoder:         "Reconstruction-based · Unsupervised anomaly detection"
}

function MetricBar({ value, color }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <div style={{
        flex: 1, height: "6px", background: "#f0f0f8",
        borderRadius: "3px", overflow: "hidden"
      }}>
        <div style={{
          width: `${value * 100}%`, height: "100%",
          background: color, borderRadius: "3px",
          transition: "width 1s ease"
        }} />
      </div>
      <span style={{ fontSize: "12px", color: "#1a1a2e", minWidth: "42px", textAlign: "right", fontWeight: "600" }}>
        {(value * 100).toFixed(1)}%
      </span>
    </div>
  )
}

function ModelCard({ model, data }) {
  const color = modelColors[model] || "#2563eb"
  const label = modelLabels[model] || model
  const isUnsupervised = data.precision === null

  return (
    <div style={{
      background: "#fff", border: "1px solid #e8e8f0",
      borderRadius: "12px", padding: "20px",
      boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "18px" }}>
        <div style={{
          width: "10px", height: "10px", borderRadius: "50%",
          background: color, boxShadow: `0 0 6px ${color}`
        }} />
        <p style={{ fontSize: "13px", fontWeight: "700", color: "#1a1a2e", margin: 0 }}>
          {label}
        </p>
        <span style={{
          marginLeft: "auto", fontSize: "11px",
          padding: "3px 10px", borderRadius: "20px",
          background: "#f0fdf4", color: "#16a34a",
          border: "1px solid #bbf7d0", fontWeight: "600"
        }}>
          AUC {data.auc}
        </span>
      </div>

      {isUnsupervised ? (
        <div style={{
          padding: "12px", borderRadius: "8px",
          background: "#f8f8fc", border: "1px solid #e8e8f0",
          textAlign: "center"
        }}>
          <p style={{ fontSize: "12px", color: "#aaa", margin: 0 }}>
            Unsupervised model — precision/recall not applicable
          </p>
          <p style={{ fontSize: "11px", color: "#aaa", margin: "4px 0 0" }}>
            Evaluated by reconstruction error distribution
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div>
            <p style={{ fontSize: "11px", color: "#aaa", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.05em" }}>Precision</p>
            <MetricBar value={data.precision} color={color} />
          </div>
          <div>
            <p style={{ fontSize: "11px", color: "#aaa", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.05em" }}>Recall</p>
            <MetricBar value={data.recall} color={color} />
          </div>
          <div>
            <p style={{ fontSize: "11px", color: "#aaa", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.05em" }}>F1 Score</p>
            <MetricBar value={data.f1} color={color} />
          </div>
        </div>
      )}
    </div>
  )
}

export default function MetricsPage() {
  const [metrics, setMetrics] = useState(null)

  useEffect(() => {
    axios.get("http://localhost:8000/metrics").then(r => setMetrics(r.data))
  }, [])

  if (!metrics) return (
    <div style={{
      display: "flex", alignItems: "center",
      justifyContent: "center", height: "400px",
      color: "#ccc", flexDirection: "column", gap: "8px"
    }}>
      <span style={{ fontSize: "28px" }}>⏳</span>
      Loading metrics...
    </div>
  )

  return (
    <div>
      <div style={{ marginBottom: "28px" }}>
        <h1 style={{ fontSize: "20px", fontWeight: "700", margin: "0 0 4px", color: "#1a1a2e" }}>
          Model Performance
        </h1>
        <p style={{ color: "#aaa", fontSize: "13px", margin: 0 }}>
          Evaluated on 20,000 held-out transactions · Trained on 100K synthetic transactions with SMOTE balancing
        </p>
      </div>

      {/* Training Info Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "12px", marginBottom: "24px" }}>
        {[
          { label: "Training Samples", value: "100,000", color: "#2563eb" },
          { label: "After SMOTE",      value: "~197,000", color: "#9333ea" },
          { label: "Test Samples",     value: "20,000",   color: "#16a34a" },
          { label: "Fraud Rate",       value: "1.5%",     color: "#d97706" }
        ].map(item => (
          <div key={item.label} style={{
            background: "#fff", border: "1px solid #e8e8f0",
            borderRadius: "12px", padding: "18px",
            boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
          }}>
            <p style={{ fontSize: "11px", color: "#aaa", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "8px", fontWeight: "500" }}>
              {item.label}
            </p>
            <p style={{ fontSize: "22px", fontWeight: "700", color: item.color, margin: 0 }}>
              {item.value}
            </p>
          </div>
        ))}
      </div>

      {/* Model Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "16px", marginBottom: "24px" }}>
        {Object.entries(metrics).map(([model, data]) => (
          <ModelCard key={model} model={model} data={data} />
        ))}
      </div>

      {/* Comparison Table */}
      <div style={{
        background: "#fff", border: "1px solid #e8e8f0",
        borderRadius: "12px", padding: "24px",
        boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
      }}>
        <p style={{ fontSize: "13px", fontWeight: "600", color: "#1a1a2e", marginBottom: "16px" }}>
          Full Model Comparison
        </p>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #f0f0f8" }}>
              {["Model", "Precision", "Recall", "F1 Score", "AUC-ROC", "Role"].map(h => (
                <th key={h} style={{
                  padding: "10px 14px", textAlign: "left",
                  color: "#aaa", fontWeight: "500",
                  fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.05em"
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(metrics).map(([model, data]) => (
              <tr key={model}
                style={{ borderBottom: "1px solid #f8f8fc", transition: "background 0.1s" }}
                onMouseEnter={e => e.currentTarget.style.background = "#fafafe"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <td style={{ padding: "12px 14px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: modelColors[model] || "#ccc" }} />
                    <span style={{ color: "#1a1a2e", fontWeight: "500" }}>{modelLabels[model] || model}</span>
                  </div>
                </td>
                <td style={{ padding: "12px 14px", color: "#444" }}>
                  {data.precision !== null ? `${(data.precision * 100).toFixed(1)}%` : "—"}
                </td>
                <td style={{ padding: "12px 14px", color: "#444" }}>
                  {data.recall !== null ? `${(data.recall * 100).toFixed(1)}%` : "—"}
                </td>
                <td style={{ padding: "12px 14px", color: "#444" }}>
                  {data.f1 !== null ? `${(data.f1 * 100).toFixed(1)}%` : "—"}
                </td>
                <td style={{ padding: "12px 14px" }}>
                  <span style={{ color: "#16a34a", fontWeight: "700" }}>{data.auc}</span>
                </td>
                <td style={{ padding: "12px 14px", color: "#888", fontSize: "12px" }}>
                  {modelRoles[model] || "—"}
                </td>
              </tr>
            ))}
            <tr
              style={{ borderTop: "2px solid #f0f0f8", transition: "background 0.1s" }}
              onMouseEnter={e => e.currentTarget.style.background = "#fafafe"}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}
            >
              <td style={{ padding: "12px 14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#ccc" }} />
                  <span style={{ color: "#aaa", fontWeight: "500" }}>Isolation Forest</span>
                </div>
              </td>
              <td colSpan={3} style={{ padding: "12px 14px", color: "#ccc", fontSize: "12px" }}>
                Unsupervised · No probability output
              </td>
              <td style={{ padding: "12px 14px", color: "#ccc" }}>—</td>
              <td style={{ padding: "12px 14px", color: "#888", fontSize: "12px" }}>
                Anomaly detection · Catches novel fraud
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}