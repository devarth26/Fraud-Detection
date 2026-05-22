import { useState } from "react"
import axios from "axios"

const inputStyle = {
  width: "100%", padding: "9px 12px",
  background: "#f8f8fc", border: "1px solid #e8e8f0",
  borderRadius: "8px", color: "#1a1a2e", fontSize: "13px",
  outline: "none", transition: "border 0.15s"
}

const labelStyle = {
  display: "block", fontSize: "11px",
  color: "#aaa", marginBottom: "6px",
  textTransform: "uppercase", letterSpacing: "0.05em",
  fontWeight: "500"
}

export default function PredictForm({ onNewTransaction, onResult }) {
    const [form, setForm] = useState({
    amount: "",
    merchant_category: "Electronics",
    location: "Same city",
    time_of_day: "Business hours",
    transactions_last_24h: "",
    card_age_months: "",
    device_match: "Known device, matching IP"
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const update = (field, value) => setForm(prev => ({ ...prev, [field]: value }))

  const handleSubmit = async () => {
    if (!form.amount || !form.transactions_last_24h || !form.card_age_months) {
      alert("Please fill in Amount, Transactions in 24h, and Card Age.")
      return
    }
    setLoading(true)
    setResult(null)
    try {
      const payload = {
        ...form,
        amount: parseFloat(form.amount),
        transactions_last_24h: parseInt(form.transactions_last_24h),
        card_age_months: parseInt(form.card_age_months)
      }
      const res = await axios.post("http://localhost:8000/predict", payload)
      setResult(res.data)
      onResult(res.data)
      onNewTransaction()
    } catch (e) {
      alert("API error. Make sure the backend is running.")
    }
    setLoading(false)
  }

  return (
    <div style={{
      background: "#fff", border: "1px solid #e8e8f0",
      borderRadius: "12px", padding: "24px",
      boxShadow: "0 1px 4px rgba(0,0,0,0.04)"
    }}>
      <p style={{ fontSize: "14px", fontWeight: "600", color: "#1a1a2e", marginBottom: "4px" }}>
        Transaction Details
      </p>
      <p style={{ fontSize: "12px", color: "#aaa", marginBottom: "20px" }}>
        Fill in the transaction fields to run the ML ensemble
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px", marginBottom: "14px" }}>
        <div>
          <label style={labelStyle}>Amount ($)</label>
          <input style={inputStyle} type="number" placeholder="e.g. 2500"
            value={form.amount} onChange={e => update("amount", e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Merchant Category</label>
          <select style={inputStyle} value={form.merchant_category}
            onChange={e => update("merchant_category", e.target.value)}>
            {["Electronics","Travel","Groceries","Luxury goods","Online transfer",
              "ATM withdrawal","Restaurant","Crypto exchange"].map(o => (
              <option key={o}>{o}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Location</label>
          <select style={inputStyle} value={form.location}
            onChange={e => update("location", e.target.value)}>
            {["Same city","Different state","International","High-risk country"].map(o => (
              <option key={o}>{o}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Time of Day</label>
          <select style={inputStyle} value={form.time_of_day}
            onChange={e => update("time_of_day", e.target.value)}>
            {["Business hours","Evening","Late night (12–5am)","Early morning"].map(o => (
              <option key={o}>{o}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Transactions in last 24h</label>
          <input style={inputStyle} type="number" placeholder="e.g. 3"
            value={form.transactions_last_24h}
            onChange={e => update("transactions_last_24h", e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Card Age (months)</label>
          <input style={inputStyle} type="number" placeholder="e.g. 24"
            value={form.card_age_months}
            onChange={e => update("card_age_months", e.target.value)} />
        </div>
      </div>

      <div style={{ marginBottom: "20px" }}>
        <label style={labelStyle}>Device / IP Match</label>
        <select style={inputStyle} value={form.device_match}
          onChange={e => update("device_match", e.target.value)}>
          {["Known device, matching IP","New device, matching IP",
            "Known device, new IP","New device, new IP","VPN / proxy detected"].map(o => (
            <option key={o}>{o}</option>
          ))}
        </select>
      </div>

      <button onClick={handleSubmit} disabled={loading} style={{
        width: "100%", padding: "11px",
        background: loading ? "#e8e8f0" : "#2563eb",
        border: "none", borderRadius: "8px",
        color: loading ? "#aaa" : "#fff",
        fontSize: "13px", fontWeight: "600",
        cursor: loading ? "not-allowed" : "pointer",
        transition: "all 0.15s",
        boxShadow: loading ? "none" : "0 2px 8px rgba(37,99,235,0.3)"
      }}>
        {loading ? "Analyzing..." : "Analyze Transaction"}
      </button>

     
    </div>
  )
}