export default function ResultPanel({ result }) {
        if (!result) return (
      <div style={{
        background: "#fff", border: "1px solid #e8e8f0",
        borderRadius: "12px", padding: "40px 24px",
        boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        minHeight: "500px", textAlign: "center"
      }}>
        <div style={{
          width: "56px", height: "56px", borderRadius: "16px",
          background: "#eff6ff", display: "flex",
          alignItems: "center", justifyContent: "center",
          fontSize: "24px", marginBottom: "16px"
        }}>🛡️</div>
        <p style={{ fontSize: "14px", fontWeight: "600", color: "#1a1a2e", marginBottom: "6px" }}>
          Awaiting Analysis
        </p>
        <p style={{ fontSize: "12px", color: "#aaa", maxWidth: "200px", lineHeight: "1.6" }}>
          Fill in the transaction details and click Analyze to see the ML results here
        </p>
      </div>
    )
  
    const isFraud = result.is_fraud
  
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
  
        {/* Main verdict */}
<div style={{
  background: isFraud ? "#fef2f2" : "#f0fdf4",
  border: `1px solid ${isFraud ? "#fecaca" : "#bbf7d0"}`,
  borderRadius: "12px", padding: "20px",
  boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
}}>
  <p style={{
    fontSize: "18px", fontWeight: "700", marginBottom: "12px",
    color: isFraud ? "#dc2626" : "#16a34a"
  }}>
    {isFraud ? "🚨 FRAUD DETECTED" : "✅ TRANSACTION LEGITIMATE"}
  </p>
  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px", marginBottom: "12px" }}>
    {[
      { label: "Confidence", value: `${Math.round(result.confidence * 100)}%` },
      { label: "Risk Tier",  value: result.risk_tier },
      { label: "TX ID",      value: `#${result.transaction_id}` }
    ].map(item => (
      <div key={item.label} style={{
        background: "#fff", borderRadius: "8px",
        padding: "10px 12px", border: "1px solid #e8e8f0"
      }}>
        <p style={{ fontSize: "10px", color: "#aaa", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "4px" }}>
          {item.label}
        </p>
        <p style={{ fontSize: "14px", fontWeight: "700", color: "#1a1a2e", margin: 0 }}>
          {item.value}
        </p>
      </div>
    ))}
  </div>

  {/* Orchestration scores */}
  {result.orchestration && (
    <div style={{ marginBottom: "12px" }}>
      <p style={{ fontSize: "10px", color: "#aaa", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
        Weighted Risk Score
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "6px" }}>
        {Object.entries(result.orchestration.component_scores).map(([key, val]) => (
          <div key={key} style={{
            background: "#fff", borderRadius: "6px",
            padding: "6px 8px", border: "1px solid #e8e8f0",
            textAlign: "center"
          }}>
            <p style={{ fontSize: "9px", color: "#aaa", textTransform: "uppercase", marginBottom: "2px" }}>
              {key}
            </p>
            <p style={{ fontSize: "12px", fontWeight: "700", color: val > 0.5 ? "#dc2626" : "#16a34a", margin: 0 }}>
              {Math.round(val * 100)}%
            </p>
          </div>
        ))}
      </div>
    </div>
  )}

  {/* Rules triggered */}
  {result.rules && result.rules.rules_triggered.length > 0 && (
    <div>
      <p style={{ fontSize: "10px", color: "#aaa", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
        {result.rules.rule_count} Rule{result.rules.rule_count > 1 ? "s" : ""} Triggered
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
        {result.rules.rules_triggered.map(rule => (
          <span key={rule} style={{
            fontSize: "10px", padding: "3px 8px",
            background: "#fef2f2", color: "#dc2626",
            border: "1px solid #fecaca", borderRadius: "4px",
            fontWeight: "500"
          }}>
            {rule.replace(/_/g, " ")}
          </span>
        ))}
      </div>
      {result.orchestration?.hard_override && (
        <p style={{ fontSize: "10px", color: "#d97706", marginTop: "6px", fontWeight: "600" }}>
          ⚠️ Hard override: {result.orchestration.override_reason?.replace(/_/g, " ")}
        </p>
      )}
    </div>
  )}
</div>

{/* Fraud Persona */}
{result.persona && result.persona.primary_persona.type !== "UNKNOWN" && (
  <div style={{
    background: "#fff", border: "1px solid #e8e8f0",
    borderRadius: "12px", padding: "16px 20px",
    boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
  }}>
    <p style={{
      fontSize: "11px", fontWeight: "600", color: "#aaa",
      textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "12px"
    }}>
      🎭 Fraud Persona Detection
    </p>

    {/* Primary persona */}
    <div style={{
      padding: "14px", borderRadius: "8px", marginBottom: "10px",
      background: result.persona.primary_persona.severity === "CRITICAL" ? "#fef2f2" :
                  result.persona.primary_persona.severity === "HIGH" ? "#fffbeb" : "#f0fdf4",
      border: `1px solid ${
        result.persona.primary_persona.severity === "CRITICAL" ? "#fecaca" :
        result.persona.primary_persona.severity === "HIGH" ? "#fde68a" : "#bbf7d0"
      }`
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
        <span style={{
          fontSize: "13px", fontWeight: "700",
          color: result.persona.primary_persona.severity === "CRITICAL" ? "#dc2626" :
                 result.persona.primary_persona.severity === "HIGH" ? "#d97706" : "#16a34a"
        }}>
          {result.persona.primary_persona.label}
        </span>
        <span style={{
          fontSize: "10px", fontWeight: "600", padding: "2px 8px", borderRadius: "4px",
          background: result.persona.primary_persona.severity === "CRITICAL" ? "#dc2626" :
                      result.persona.primary_persona.severity === "HIGH" ? "#d97706" : "#16a34a",
          color: "#fff"
        }}>
          {result.persona.primary_persona.severity}
        </span>
      </div>
      <p style={{ fontSize: "12px", color: "#666", marginBottom: "8px", lineHeight: "1.5" }}>
        {result.persona.primary_persona.description}
      </p>
      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
        {result.persona.primary_persona.indicators.map(ind => (
          <span key={ind} style={{
            fontSize: "10px", padding: "2px 8px", borderRadius: "4px",
            background: "#f0f0f8", color: "#666", border: "1px solid #e8e8f0"
          }}>
            {ind.replace(/_/g, " ")}
          </span>
        ))}
      </div>
    </div>

    {/* Other personas */}
    {result.persona.all_personas.length > 1 && (
      <div>
        <p style={{ fontSize: "10px", color: "#aaa", marginBottom: "6px" }}>
          {result.persona.persona_count - 1} additional pattern{result.persona.persona_count > 2 ? "s" : ""} detected
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          {result.persona.all_personas.slice(1).map(p => (
            <div key={p.type} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "8px 12px", borderRadius: "6px",
              background: "#f8f8fc", border: "1px solid #e8e8f0"
            }}>
              <span style={{ fontSize: "12px", color: "#444", fontWeight: "500" }}>
                {p.label}
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <div style={{
                  width: "60px", height: "4px",
                  background: "#e8e8f0", borderRadius: "2px", overflow: "hidden"
                }}>
                  <div style={{
                    width: `${Math.round(p.confidence * 100)}%`,
                    height: "100%", background: "#d97706", borderRadius: "2px"
                  }} />
                </div>
                <span style={{ fontSize: "11px", color: "#aaa" }}>
                  {Math.round(p.confidence * 100)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    )}
  </div>
)}
  
        {/* Ensemble models */}
        <div style={{
          background: "#fff", border: "1px solid #e8e8f0",
          borderRadius: "12px", padding: "16px 20px",
          boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
        }}>
          <p style={{
            fontSize: "11px", fontWeight: "600", color: "#aaa",
            textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "12px"
          }}>
            Ensemble Models ({result.ensemble.votes}/5 flagged)
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
            {Object.entries(result.ensemble.model_results).map(([model, data]) => (
              <div key={model} style={{
                padding: "10px 12px", borderRadius: "8px",
                background: data.fraud ? "#fef2f2" : "#f8f8fc",
                border: `1px solid ${data.fraud ? "#fecaca" : "#e8e8f0"}`
              }}>
                <p style={{
                  fontSize: "10px", color: "#aaa",
                  textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "4px"
                }}>
                  {model.replace(/_/g, " ")}
                </p>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{
                    fontSize: "12px", fontWeight: "700",
                    color: data.fraud ? "#dc2626" : "#16a34a"
                  }}>
                    {data.fraud ? "FRAUD" : "LEGIT"}
                  </span>
                  {data.confidence !== null && (
                    <span style={{ fontSize: "11px", color: "#aaa" }}>
                      {Math.round(data.confidence * 100)}%
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
  
        {/* LSTM */}
        {/* LSTM Behavioral Analysis */}
<div style={{
  background: "#fff", border: "1px solid #e8e8f0",
  borderRadius: "12px", padding: "16px 20px",
  boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
}}>
  <p style={{
    fontSize: "11px", fontWeight: "600", color: "#aaa",
    textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "4px"
  }}>
    LSTM Behavioral Analysis
  </p>
  <p style={{ fontSize: "11px", color: "#ccc", marginBottom: "12px" }}>
    Bidirectional sequence model — attention weights show which past transactions influenced this decision
  </p>

  <div style={{
    padding: "12px", borderRadius: "8px", marginBottom: "12px",
    background: result.lstm.verdict ? "#fef2f2" : "#f0fdf4",
    border: `1px solid ${result.lstm.verdict ? "#fecaca" : "#bbf7d0"}`
  }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span style={{
        fontSize: "12px", fontWeight: "700",
        color: result.lstm.verdict ? "#dc2626" : "#16a34a"
      }}>
        {result.lstm.verdict ? "🚨 BEHAVIORAL ANOMALY" : "✅ NORMAL BEHAVIOR"}
      </span>
      <span style={{ fontSize: "11px", color: "#aaa" }}>
        {Math.round(result.lstm.confidence * 100)}% anomaly score
      </span>
    </div>
  </div>

  {/* Attention Heatmap */}
  <p style={{ fontSize: "10px", color: "#aaa", marginBottom: "8px", fontWeight: "500" }}>
    ATTENTION HEATMAP — transaction influence weights
  </p>
  <div style={{ display: "flex", gap: "4px", marginBottom: "6px" }}>
    {result.lstm.attention_weights.map((w, i) => {
      const isLast    = i === result.lstm.attention_weights.length - 1
      const maxWeight = Math.max(...result.lstm.attention_weights)
      const intensity = w / maxWeight
      const isCurrent = isLast

      // Color: blue for current, red-orange for high attention, gray for low
      const bg = isCurrent
        ? `rgba(37, 99, 235, ${0.3 + intensity * 0.7})`
        : intensity > 0.7
          ? `rgba(220, 38, 38, ${0.2 + intensity * 0.6})`
          : `rgba(156, 163, 175, ${0.15 + intensity * 0.4})`

      const border = isCurrent
        ? "2px solid #2563eb"
        : intensity > 0.7
          ? "1px solid #fca5a5"
          : "1px solid #e8e8f0"

      return (
        <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "4px" }}>
          {/* Cell */}
          <div style={{
            width: "100%", height: "48px",
            background: bg,
            border: border,
            borderRadius: "6px",
            display: "flex", alignItems: "center", justifyContent: "center",
            position: "relative"
          }}
            title={`Transaction ${i === result.lstm.attention_weights.length - 1 ? "(current)" : `t-${result.lstm.attention_weights.length - 1 - i}`}: ${(w * 100).toFixed(1)}% attention`}
          >
            <span style={{
              fontSize: "9px", fontWeight: "700",
              color: isCurrent ? "#1d4ed8" : intensity > 0.7 ? "#991b1b" : "#6b7280"
            }}>
              {(w * 100).toFixed(0)}%
            </span>
          </div>
          {/* Label */}
          <span style={{
            fontSize: "8px", color: isCurrent ? "#2563eb" : "#aaa",
            fontWeight: isCurrent ? "700" : "400",
            whiteSpace: "nowrap"
          }}>
            {isCurrent ? "NOW" : `t-${result.lstm.attention_weights.length - 1 - i}`}
          </span>
        </div>
      )
    })}
  </div>

  {/* Legend */}
  <div style={{
    display: "flex", gap: "12px", marginTop: "8px",
    padding: "8px 10px", borderRadius: "6px",
    background: "#f8f8fc", border: "1px solid #e8e8f0"
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
      <div style={{ width: "12px", height: "12px", borderRadius: "2px", background: "rgba(220,38,38,0.6)", border: "1px solid #fca5a5" }} />
      <span style={{ fontSize: "10px", color: "#666" }}>High influence</span>
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
      <div style={{ width: "12px", height: "12px", borderRadius: "2px", background: "rgba(156,163,175,0.3)", border: "1px solid #e8e8f0" }} />
      <span style={{ fontSize: "10px", color: "#666" }}>Low influence</span>
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
      <div style={{ width: "12px", height: "12px", borderRadius: "2px", background: "rgba(37,99,235,0.7)", border: "2px solid #2563eb" }} />
      <span style={{ fontSize: "10px", color: "#666" }}>Current transaction</span>
    </div>
  </div>
</div>

{/* SHAP Feature Contributions */}
{result.shap && result.shap.top_features && (
  <div style={{
    background: "#fff", border: "1px solid #e8e8f0",
    borderRadius: "12px", padding: "16px 20px",
    boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
  }}>
    <p style={{
      fontSize: "11px", fontWeight: "600", color: "#aaa",
      textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "4px"
    }}>
      SHAP — Feature Contributions
    </p>
    <p style={{ fontSize: "11px", color: "#ccc", marginBottom: "12px" }}>
      Why XGBoost made this decision — each feature's contribution
    </p>

    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      {result.shap.top_features.map((f, i) => {
        const isFraud   = f.direction === "fraud"
        const maxImpact = result.shap.top_features[0].abs_impact
        const barWidth  = Math.round((f.abs_impact / maxImpact) * 100)

        return (
          <div key={i}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "3px" }}>
              <span style={{ fontSize: "11px", color: "#444", fontWeight: "500" }}>
                {f.feature.replace(/_/g, " ")}
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <span style={{ fontSize: "10px", color: "#aaa" }}>
                  val: {typeof f.value === 'number' && f.value > 100
                    ? f.value.toLocaleString()
                    : f.value}
                </span>
                <span style={{
                  fontSize: "10px", fontWeight: "700",
                  color: isFraud ? "#dc2626" : "#16a34a"
                }}>
                  {isFraud ? "+" : ""}{f.shap_value.toFixed(3)}
                </span>
              </div>
            </div>
            <div style={{
              height: "5px", background: "#f0f0f8",
              borderRadius: "3px", overflow: "hidden"
            }}>
              <div style={{
                width: `${barWidth}%`,
                height: "100%",
                background: isFraud ? "#dc2626" : "#16a34a",
                borderRadius: "3px",
                transition: "width 0.6s ease"
              }} />
            </div>
          </div>
        )
      })}
    </div>

    <div style={{
      marginTop: "12px", paddingTop: "10px",
      borderTop: "1px solid #f0f0f8",
      display: "flex", justifyContent: "space-between"
    }}>
      <span style={{ fontSize: "10px", color: "#aaa" }}>
        Base value: {result.shap.base_value.toFixed(3)}
      </span>
      <span style={{ fontSize: "10px", color: "#aaa" }}>
        Total SHAP: <strong style={{ color: result.shap.total_shap > 0 ? "#dc2626" : "#16a34a" }}>
          {result.shap.total_shap > 0 ? "+" : ""}{result.shap.total_shap.toFixed(3)}
        </strong>
      </span>
    </div>
  </div>
)}

        {/* Autoencoder */}
<div style={{
  background: "#fff", border: "1px solid #e8e8f0",
  borderRadius: "12px", padding: "16px 20px",
  boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
}}>
  <p style={{
    fontSize: "11px", fontWeight: "600", color: "#aaa",
    textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "12px"
  }}>
    Autoencoder — Reconstruction Analysis
  </p>
  <div style={{
    padding: "12px", borderRadius: "8px",
    background: result.autoencoder.verdict ? "#fef2f2" : "#f0fdf4",
    border: `1px solid ${result.autoencoder.verdict ? "#fecaca" : "#bbf7d0"}`,
    marginBottom: "10px"
  }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
      <span style={{
        fontSize: "12px", fontWeight: "700",
        color: result.autoencoder.verdict ? "#dc2626" : "#16a34a"
      }}>
        {result.autoencoder.verdict ? "🚨 ANOMALOUS PATTERN" : "✅ NORMAL PATTERN"}
      </span>
      <span style={{ fontSize: "11px", color: "#aaa" }}>
        anomaly score: {Math.min(result.autoencoder.anomaly_score, 2).toFixed(2)}x
      </span>
    </div>

    {/* Anomaly score bar */}
    <p style={{ fontSize: "10px", color: "#aaa", marginBottom: "4px" }}>
      Reconstruction error vs threshold (higher = more anomalous)
    </p>
    <div style={{
      height: "8px", background: "#f0f0f8",
      borderRadius: "4px", overflow: "hidden", marginBottom: "4px"
    }}>
      <div style={{
        width: `${Math.min(result.autoencoder.anomaly_score / 2 * 100, 100)}%`,
        height: "100%",
        background: result.autoencoder.anomaly_score > 1
          ? "#dc2626"
          : "#16a34a",
        borderRadius: "4px",
        transition: "width 0.5s ease"
      }} />
    </div>
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ fontSize: "9px", color: "#ccc" }}>normal</span>
      <span style={{ fontSize: "9px", color: "#aaa" }}>threshold</span>
      <span style={{ fontSize: "9px", color: "#dc2626" }}>anomalous</span>
    </div>
  </div>
</div>
  
        {/* LLM Explanation */}
        <div style={{
          background: "#fff", border: "1px solid #e8e8f0",
          borderRadius: "12px", padding: "16px 20px",
          boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
        }}>
          <p style={{
            fontSize: "11px", fontWeight: "600", color: "#aaa",
            textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "12px"
          }}>
            🤖 AI Analyst Report
          </p>
          <p style={{
            fontSize: "12px", color: "#444",
            lineHeight: "1.8", whiteSpace: "pre-line", margin: 0
          }}>
            {result.explanation}
          </p>
        </div>
  
      </div>
    )
  }