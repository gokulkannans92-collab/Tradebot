import { useEffect, useState, useRef, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'https://purple-performer-entrepreneur-sustained.trycloudflare.com'

// ── Small helper hooks / utils ────────────────────────────────────────────────

function EyeIcon({ open }) {
  return open ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
      <line x1="1" y1="1" x2="23" y2="23"/>
    </svg>
  )
}

function MaskedInput({ value, onChange, placeholder, disabled, style }) {
  const [show, setShow] = useState(false)
  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <input
        type={show ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        placeholder={placeholder || '••••••••'}
        disabled={disabled}
        style={{ width: '100%', paddingRight: '44px', ...(style || {}) }}
      />
      <button
        type="button"
        onMouseDown={() => setShow(true)}
        onMouseUp={() => setShow(false)}
        onMouseLeave={() => setShow(false)}
        onTouchStart={() => setShow(true)}
        onTouchEnd={() => setShow(false)}
        style={{
          position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
          background: 'none', border: 'none',
          color: show ? 'var(--color-primary)' : 'rgba(255,255,255,0.35)',
          cursor: 'pointer', padding: '0', display: 'flex', alignItems: 'center', outline: 'none'
        }}
        title="Hold to reveal"
      >
        <EyeIcon open={show} />
      </button>
    </div>
  )
}

// ── Password strength helper ──────────────────────────────────────────────────
function getPasswordStrength(pass) {
  if (!pass) return { score: 0, conditions: { length: false, upper: false, lower: false, number: false, special: false } }
  const conditions = {
    length: pass.length >= 8,
    upper: /[A-Z]/.test(pass),
    lower: /[a-z]/.test(pass),
    number: /[0-9]/.test(pass),
    special: /[^A-Za-z0-9]/.test(pass)
  }
  return { score: Object.values(conditions).filter(Boolean).length, conditions }
}

// ── Toast notification (lightweight) ─────────────────────────────────────────
function Toast({ msg, type, onDone }) {
  useEffect(() => {
    const t = setTimeout(onDone, 3000)
    return () => clearTimeout(t)
  }, [onDone])
  const bg = type === 'success' ? 'rgba(166,227,161,0.18)' : type === 'error' ? 'rgba(243,139,168,0.18)' : 'rgba(137,180,250,0.18)'
  const border = type === 'success' ? '#a6e3a1' : type === 'error' ? '#f38ba8' : '#89b4fa'
  return (
    <div style={{
      position: 'fixed', bottom: '24px', right: '24px', zIndex: 9999,
      background: bg, border: `1px solid ${border}`, borderRadius: '12px',
      padding: '14px 20px', color: 'white', fontSize: '0.88rem',
      backdropFilter: 'blur(20px)', boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      animation: 'slideUp 0.3s ease', maxWidth: '340px'
    }}>
      {type === 'success' ? '✅ ' : type === 'error' ? '❌ ' : 'ℹ️ '}{msg}
    </div>
  )
}

// ── Collapsible sidebar section ───────────────────────────────────────────────
function SidebarSection({ title, icon, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="control-section-card" style={{ marginBottom: '8px' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', background: 'none', border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0'
        }}
      >
        <h4 className="section-card-title" style={{ margin: 0 }}>{icon} {title}</h4>
        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem', transition: 'transform 0.2s', transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}>▼</span>
      </button>
      {open && <div className="section-card-body" style={{ marginTop: '10px' }}>{children}</div>}
    </div>
  )
}

// ── Main App Component ────────────────────────────────────────────────────────
function App() {
  // ── Auth state ────────────────────────────────────────────────────────────
  const [userId, setUserId] = useState(localStorage.getItem('tradebot_user') || '')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState(localStorage.getItem('tradebot_token') || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showLoginPassword, setShowLoginPassword] = useState(false)
  const [showRegisterPassword, setShowRegisterPassword] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const [displayName, setDisplayName] = useState('')
  const [brokerType, setBrokerType] = useState('MOCK')
  const [successMessage, setSuccessMessage] = useState('')

  // ── Navigation ────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState('overview')
  const [isControlCenterOpen, setIsControlCenterOpen] = useState(false)
  const [isNavigationOpen, setIsNavigationOpen] = useState(false)

  // ── Real-time & API states ────────────────────────────────────────────────
  const [status, setStatus] = useState(null)
  const [positions, setPositions] = useState([])
  const [trades, setTrades] = useState([])
  const [config, setConfig] = useState(null)
  const [editedConfig, setEditedConfig] = useState(null)
  const [isEditing, setIsEditing] = useState(false)

  // ── Operator edit states ──────────────────────────────────────────────────
  const [isEditingOperator, setIsEditingOperator] = useState(false)
  const [editedOperatorName, setEditedOperatorName] = useState('')
  const [editedOperatorBroker, setEditedOperatorBroker] = useState('MOCK')
  const [editedOperatorActive, setEditedOperatorActive] = useState(true)
  const [editedOperatorPassword, setEditedOperatorPassword] = useState('')
  const [showEditPassword, setShowEditPassword] = useState(false)
  // Full risk rules editing
  const [editedRisk, setEditedRisk] = useState({
    total_capital: 100000,
    trade_capital: 100000,
    max_trades_per_day: 5,
    max_daily_loss: 15000,
    trade_target_rs: 10000,
    trade_sl_rs: 1000
  })

  // ── Credentials editing (Management tab) ─────────────────────────────────
  const [isEditingCreds, setIsEditingCreds] = useState(false)
  const [editedCreds, setEditedCreds] = useState({
    api_key: '', api_secret: '', client_id: '', password: '', totp_secret: ''
  })

  // ── Notifications / Telegram / AI ────────────────────────────────────────
  const [telegramToken, setTelegramToken] = useState('')
  const [telegramChatId, setTelegramChatId] = useState('')
  const [geminiKey, setGeminiKey] = useState('')
  const [isEditingNotif, setIsEditingNotif] = useState(false)
  const [testingTelegram, setTestingTelegram] = useState(false)
  const [testingGemini, setTestingGemini] = useState(false)

  // ── Sidebar: AI Market Selection ──────────────────────────────────────────
  const [aiMarketSelection, setAiMarketSelection] = useState(false)

  // ── Logs / Console ────────────────────────────────────────────────────────
  const [logs, setLogs] = useState([])
  const [logFilter, setLogFilter] = useState('')
  const [logLevel, setLogLevel] = useState('ALL')   // ALL | INFO | WARN | ERROR
  const [compactLogs, setCompactLogs] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const terminalEndRef = useRef(null)

  // ── Trades / History ──────────────────────────────────────────────────────
  const [quotes, setQuotes] = useState({})
  const [tradeSearch, setTradeSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState('today')
  const [selectedTrade, setSelectedTrade] = useState(null)

  // ── Toast ─────────────────────────────────────────────────────────────────
  const [toast, setToast] = useState(null)
  const showToast = useCallback((msg, type = 'info') => setToast({ msg, type }), [])

  // ── WebSocket refs ────────────────────────────────────────────────────────
  const wsLogsRef = useRef(null)
  const wsQuotesRef = useRef(null)

  // ── Effects ───────────────────────────────────────────────────────────────
  useEffect(() => {
    if (token) {
      fetchStatus(); fetchPositions(); fetchTrades(); fetchConfig()
      connectLogsWS(token); connectQuotesWS(token)
      const interval = setInterval(() => { fetchStatus(); fetchPositions() }, 5000)
      return () => { clearInterval(interval); disconnectWebSockets() }
    }
  }, [token])

  useEffect(() => {
    if (autoScroll && activeTab === 'logs' && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, activeTab, autoScroll])

  // ── WebSocket helpers ────────────────────────────────────────────────────
  function disconnectWebSockets() {
    if (wsLogsRef.current) { wsLogsRef.current.close(); wsLogsRef.current = null }
    if (wsQuotesRef.current) { wsQuotesRef.current.close(); wsQuotesRef.current = null }
  }

  function connectLogsWS(accessToken) {
    if (wsLogsRef.current) return
    const wsUrl = `${API_BASE.replace('http', 'ws')}/api/v1/ws/logs?token=${accessToken}`
    const ws = new WebSocket(wsUrl)
    ws.onopen = () => setLogs(prev => [...prev, { text: '▶ CONNECTED TO REAL-TIME ENGINE LOG STREAM', time: new Date().toLocaleTimeString(), level: 'info' }])
    ws.onmessage = (event) => {
      const line = event.data
      let level = 'info'
      if (line.includes(' ERROR ') || line.includes('CRITICAL')) level = 'error'
      else if (line.includes(' WARNING ')) level = 'warn'
      setLogs(prev => {
        const next = [...prev, { text: line, time: new Date().toLocaleTimeString(), level }]
        if (next.length > 500) next.shift()
        return next
      })
    }
    ws.onclose = () => { wsLogsRef.current = null; setTimeout(() => connectLogsWS(accessToken), 5000) }
    ws.onerror = (err) => console.error('Logs WS error:', err)
    wsLogsRef.current = ws
  }

  function connectQuotesWS(accessToken) {
    if (wsQuotesRef.current) return
    const wsUrl = `${API_BASE.replace('http', 'ws')}/api/v1/ws/quotes?token=${accessToken}`
    const ws = new WebSocket(wsUrl)
    ws.onopen = () => {
      wsQuotesRef.current = ws
      subscribeQuotes(['NIFTY', 'BANKNIFTY', 'FINNIFTY'])
    }
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'quotes' && data.data) setQuotes(prev => ({ ...prev, ...data.data }))
      } catch { /* ignore */ }
    }
    ws.onclose = () => { wsQuotesRef.current = null; setTimeout(() => connectQuotesWS(accessToken), 5000) }
    wsQuotesRef.current = ws
  }

  function subscribeQuotes(symbols) {
    if (wsQuotesRef.current && wsQuotesRef.current.readyState === WebSocket.OPEN) {
      wsQuotesRef.current.send(JSON.stringify({ action: 'subscribe', symbols }))
    }
  }

  // ── REST fetch helpers ───────────────────────────────────────────────────
  async function fetchStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/status`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) setStatus(await res.json())
    } catch (e) { console.error('Status poll failed:', e) }
  }

  async function fetchPositions() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/positions`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) {
        const data = await res.json()
        setPositions(data.positions || [])
        const syms = (data.positions || []).map(p => p.symbol)
        if (syms.length) subscribeQuotes(syms)
      }
    } catch (e) { console.error('Positions fetch failed:', e) }
  }

  async function fetchTrades() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/trades`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) { const data = await res.json(); setTrades(data.trades || []) }
    } catch (e) { console.error('Trades fetch failed:', e) }
  }

  async function fetchConfig() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/config`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) {
        const data = await res.json()
        setConfig(data)
        setEditedConfig(data)
        // Pre-populate risk from config
        if (data.risk_rules) setEditedRisk({ ...data.risk_rules })
        // Sync client-side username with the canonical user ID (e.g. "admin") resolved from users.json
        if (data.user_id && data.user_id !== userId) {
          setUserId(data.user_id)
          localStorage.setItem('tradebot_user', data.user_id)
        }
      }
    } catch (e) { console.error('Config fetch failed:', e) }
  }

  async function apiPost(path, body) {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(body)
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || 'Request failed')
    return data
  }

  // ── Config save ──────────────────────────────────────────────────────────
  async function handleSaveConfig() {
    setLoading(true)
    try {
      await apiPost('/api/v1/config', {
        user_id: userId,
        settings: {
          entry_start: editedConfig.entry_start,
          entry_end: editedConfig.entry_end,
          candle_period: editedConfig.candle_period,
          paper_trading: editedConfig.paper_trading === 'true' || editedConfig.paper_trading === true,
          nifty_enabled: editedConfig.nifty_enabled === 'true' || editedConfig.nifty_enabled === true,
          banknifty_enabled: editedConfig.banknifty_enabled === 'true' || editedConfig.banknifty_enabled === true,
          risk_rules: editedRisk
        }
      })
      showToast('Configuration saved successfully!', 'success')
      setIsEditing(false)
      fetchConfig()
    } catch (err) {
      showToast(err.message, 'error')
    } finally { setLoading(false) }
  }

  // ── Operator profile save ─────────────────────────────────────────────────
  async function handleSaveOperatorDetails() {
    setLoading(true)
    try {
      const settingsPayload = {
        name: editedOperatorName,
        broker_type: editedOperatorBroker,
        active: editedOperatorActive,
        risk_rules: { ...editedRisk }
      }
      if (editedOperatorPassword.trim()) settingsPayload.password = editedOperatorPassword.trim()
      await apiPost('/api/v1/config', { user_id: userId, settings: settingsPayload })
      showToast('Operator profile updated!', 'success')
      setEditedOperatorPassword('')
      setIsEditingOperator(false)
      fetchConfig()
    } catch (err) {
      showToast(err.message, 'error')
    } finally { setLoading(false) }
  }

  // ── Sidebar quick-toggle (optimistic) ────────────────────────────────────
  async function handleControlCenterChange(key, value) {
    if (!config) return
    const updated = { ...config, [key]: value }
    setConfig(updated); setEditedConfig(updated)
    try {
      await apiPost('/api/v1/config', {
        user_id: userId,
        settings: {
          entry_start: updated.entry_start, entry_end: updated.entry_end,
          candle_period: updated.candle_period, paper_trading: updated.paper_trading,
          nifty_enabled: updated.nifty_enabled, banknifty_enabled: updated.banknifty_enabled,
          [key]: value
        }
      })
      fetchConfig()
    } catch (err) { console.error('Sidebar toggle sync failed:', err) }
  }

  // ── Bot control ──────────────────────────────────────────────────────────
  async function handleStopBot() {
    if (!window.confirm('Send stop signal to the engine?')) return
    try {
      const data = await apiPost('/api/v1/stop', { user_id: userId })
      showToast(data.message || 'Stop signal sent!', 'success')
      fetchStatus()
    } catch (err) { showToast('Stop failed: ' + err.message, 'error') }
  }

  async function handleCloseAll() {
    if (!window.confirm('🚨 EMERGENCY EXIT: Square-off ALL active trades immediately? This is irreversible.')) return
    try {
      const data = await apiPost('/api/v1/close-all', { user_id: userId })
      showToast(data.message || 'All positions closed!', 'success')
      fetchPositions()
    } catch (err) { showToast('Emergency closure failed: ' + err.message, 'error') }
  }

  async function handleCloseSingle(symbol) {
    if (!window.confirm(`Square-off position for ${symbol}?`)) return
    try {
      const data = await apiPost('/api/v1/close-position', { user_id: userId, symbol })
      showToast(data.message || `${symbol} closed!`, 'success')
      fetchPositions()
    } catch (err) { showToast('Close failed: ' + err.message, 'error') }
  }

  // ── Telegram test ─────────────────────────────────────────────────────────
  async function handleTestTelegram() {
    if (!telegramToken || !telegramChatId) { showToast('Enter Token and Chat ID first', 'error'); return }
    setTestingTelegram(true)
    try {
      const url = `https://api.telegram.org/bot${telegramToken}/sendMessage`
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: telegramChatId, text: '✅ TradeBot Web: Telegram connection test successful!' })
      })
      const data = await res.json()
      if (data.ok) showToast('Telegram test message sent!', 'success')
      else showToast('Telegram error: ' + data.description, 'error')
    } catch (err) { showToast('Telegram test failed: ' + err.message, 'error') }
    setTestingTelegram(false)
  }

  // ── Gemini test ───────────────────────────────────────────────────────────
  async function handleTestGemini() {
    if (!geminiKey) { showToast('Enter Gemini API key first', 'error'); return }
    setTestingGemini(true)
    try {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${geminiKey}`
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contents: [{ parts: [{ text: 'Say "TradeBot connection OK" in one sentence.' }] }] })
      })
      const data = await res.json()
      if (data.candidates?.[0]?.content?.parts?.[0]?.text) showToast('Gemini API key is valid! ✓', 'success')
      else showToast('Gemini responded but check your key', 'error')
    } catch (err) { showToast('Gemini test failed: ' + err.message, 'error') }
    setTestingGemini(false)
  }

  // ── Auth handlers ────────────────────────────────────────────────────────
  async function handleRegister(event) {
    event.preventDefault()
    setError(''); setSuccessMessage('')
    if (!userId || !displayName || !password) { setError('Please fill in all fields'); return }
    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, name: displayName, password, broker_type: brokerType })
      })
      if (!response.ok) { const b = await response.json().catch(() => ({})); throw new Error(b.detail || 'Registration failed') }
      setSuccessMessage('Account registered! You can now log in.')
      setIsRegistering(false); setPassword(''); setDisplayName('')
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  async function handleLogin(event) {
    event.preventDefault()
    setError('')
    if (!userId || !password) { setError('Please enter username and password'); return }
    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, password })
      })
      if (!response.ok) { const b = await response.json().catch(() => ({})); throw new Error(b.detail || 'Authentication failed') }
      const data = await response.json()
      setToken(data.access_token)
      localStorage.setItem('tradebot_token', data.access_token)
      localStorage.setItem('tradebot_user', userId)
      setPassword('')
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  function handleLogout() {
    disconnectWebSockets()
    setToken(''); setStatus(null); setPositions([]); setTrades([])
    setConfig(null); setQuotes({}); setLogs([])
    localStorage.removeItem('tradebot_token'); localStorage.removeItem('tradebot_user')
  }

  // ── Derived stats ─────────────────────────────────────────────────────────
  const activePnL = positions.reduce((acc, pos) => {
    const quote = quotes[pos.symbol]
    if (quote?.last_price) {
      const entry = pos.buy_price || pos.price || 0
      const sideMult = pos.side === 'SELL' ? -1 : 1
      return acc + (quote.last_price - entry) * (pos.qty || pos.quantity || 0) * sideMult
    }
    return acc + (pos.pnl || 0)
  }, 0)

  function filterTrades(list) {
    const now = new Date()
    return list.filter(t => {
      const d = new Date(t.timestamp || t.time || now)
      if (activeFilter === 'today') return d.toDateString() === now.toDateString()
      if (activeFilter === 'yesterday') {
        const y = new Date(now); y.setDate(y.getDate() - 1)
        return d.toDateString() === y.toDateString()
      }
      if (activeFilter === 'week') return (now - d) <= 7 * 86400000
      if (activeFilter === 'month') return (now - d) <= 30 * 86400000
      return true
    })
  }

  const periodTrades = filterTrades(trades)
  const periodPnL = periodTrades.reduce((a, t) => a + (t.realized_pnl || t.pnl || 0), 0)
  const wins = periodTrades.filter(t => (t.realized_pnl || t.pnl || 0) > 0).length
  const winRate = periodTrades.length > 0 ? ((wins / periodTrades.length) * 100).toFixed(1) : '0.0'

  const filteredLogs = logs.filter(l => {
    const levelOk = logLevel === 'ALL' || l.level === logLevel.toLowerCase()
    const textOk = !logFilter || l.text.toUpperCase().includes(logFilter.toUpperCase())
    return levelOk && textOk
  })

  function exportTrades() {
    const headers = ['Timestamp', 'Symbol', 'Side', 'Qty', 'Entry Price', 'Exit Price', 'PnL', 'Exit Reason']
    const rows = trades.map(t => [
      t.timestamp || t.time || '',
      t.symbol, t.side || '', t.qty || t.quantity || '',
      t.entry_price || t.price || 0, t.exit_price || 0,
      t.realized_pnl || t.pnl || 0, t.exit_reason || ''
    ])
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `trades_${new Date().toISOString().split('T')[0]}.csv`
    a.click(); URL.revokeObjectURL(url)
  }

  const { score: regPasswordScore, conditions: regPasswordConditions } = getPasswordStrength(password)
  const isBotRunning = !!status?.running

  // ════════════════════════════════════════════════════════════════════════════
  // LOGIN / REGISTER SCREEN
  // ════════════════════════════════════════════════════════════════════════════
  if (!token) {
    return (
      <div className="login-overlay">
        <div className="login-card">
          <div className="login-brand">
            <div className="login-brand-icon">🤖</div>
            <h2>TradeBot <span className="pro-tag">Pro</span></h2>
            <p>Secure Enterprise Control Dashboard</p>
          </div>

          {/* Tab toggle */}
          <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.1)', marginBottom: '16px', paddingBottom: '4px' }}>
            {[['Sign In', false], ['Create Account', true]].map(([label, reg]) => (
              <button key={label} onClick={() => { setIsRegistering(reg); setError(''); setSuccessMessage('') }}
                style={{
                  flex: 1, background: 'none', border: 'none', cursor: 'pointer', padding: '8px', fontWeight: 'bold',
                  color: isRegistering === reg ? 'var(--color-primary)' : 'var(--color-text-muted)',
                  borderBottom: isRegistering === reg ? '2px solid var(--color-primary)' : '2px solid transparent',
                  transition: 'all 0.3s ease', fontFamily: 'var(--font-sans)'
                }}
              >{label}</button>
            ))}
          </div>

          {error && <div className="alert-error" style={{ marginBottom: '12px' }}><span>⚠️</span> {error}</div>}
          {successMessage && (
            <div style={{ background: 'rgba(166,227,161,0.15)', border: '1px solid #a6e3a1', color: '#a6e3a1', borderRadius: '8px', padding: '12px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              ✅ {successMessage}
            </div>
          )}

          {!isRegistering ? (
            <form onSubmit={handleLogin} className="login-form">
              <div className="form-group">
                <label>Operator Username</label>
                <input value={userId} onChange={e => setUserId(e.target.value)} placeholder="Enter username" autoComplete="username" required />
              </div>
              <div className="form-group">
                <label>Security Password</label>
                <div style={{ position: 'relative' }}>
                  <input value={password} onChange={e => setPassword(e.target.value)} type={showLoginPassword ? 'text' : 'password'}
                    placeholder="••••••••" autoComplete="current-password" required style={{ width: '100%', paddingRight: '44px' }} />
                  <button type="button" onMouseDown={() => setShowLoginPassword(true)} onMouseUp={() => setShowLoginPassword(false)} onMouseLeave={() => setShowLoginPassword(false)}
                    style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: showLoginPassword ? 'var(--color-primary)' : 'rgba(255,255,255,0.35)', cursor: 'pointer', padding: '0', display: 'flex', outline: 'none' }}
                    title="Hold to reveal"
                  ><EyeIcon open={showLoginPassword} /></button>
                </div>
              </div>
              <button type="submit" className="btn btn-primary" style={{ marginTop: '12px' }} disabled={loading}>
                {loading ? 'Authenticating…' : 'Enter Dashboard'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleRegister} className="login-form">
              <div className="form-group">
                <label>Desired Username (ID)</label>
                <input value={userId} onChange={e => setUserId(e.target.value)} placeholder="e.g. admin123" required />
              </div>
              <div className="form-group">
                <label>Operator Full Name</label>
                <input value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="e.g. John Doe" required />
              </div>
              <div className="form-group">
                <label>Broker Integration Type</label>
                <select value={brokerType} onChange={e => setBrokerType(e.target.value)}
                  style={{ width: '100%', height: '42px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white', padding: '0 12px', fontSize: '0.9rem', outline: 'none', cursor: 'pointer' }}>
                  <option value="MOCK" style={{ background: '#1e1e2e' }}>Mock Trading (No Real Capital)</option>
                  <option value="ANGEL" style={{ background: '#1e1e2e' }}>Angel One Integration</option>
                  <option value="ZERODHA" style={{ background: '#1e1e2e' }}>Zerodha Kiteconnect</option>
                  <option value="UPSTOX" style={{ background: '#1e1e2e' }}>Upstox Integration</option>
                </select>
              </div>
              <div className="form-group">
                <label>Operator Password</label>
                <div style={{ position: 'relative' }}>
                  <input value={password} onChange={e => setPassword(e.target.value)} type={showRegisterPassword ? 'text' : 'password'}
                    placeholder="••••••••" autoComplete="new-password" required style={{ width: '100%', paddingRight: '44px' }} />
                  <button type="button" onMouseDown={() => setShowRegisterPassword(true)} onMouseUp={() => setShowRegisterPassword(false)} onMouseLeave={() => setShowRegisterPassword(false)}
                    style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: showRegisterPassword ? 'var(--color-primary)' : 'rgba(255,255,255,0.35)', cursor: 'pointer', padding: '0', display: 'flex', outline: 'none' }}
                    title="Hold to reveal"
                  ><EyeIcon open={showRegisterPassword} /></button>
                </div>
                {password && (
                  <div style={{ marginTop: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#a6adc8', marginBottom: '6px' }}>
                      <span>Password Strength:</span>
                      <span style={{ fontWeight: 'bold', color: regPasswordScore <= 1 ? '#f38ba8' : regPasswordScore <= 3 ? '#f9e2af' : regPasswordScore === 4 ? '#89b4fa' : '#a6e3a1' }}>
                        {regPasswordScore <= 1 ? 'Weak' : regPasswordScore <= 3 ? 'Fair' : regPasswordScore === 4 ? 'Good' : 'Strong'}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: '4px', height: '6px', marginBottom: '10px' }}>
                      {[1,2,3,4,5].map(i => (
                        <div key={i} style={{ flex: 1, borderRadius: '3px', backgroundColor: i <= regPasswordScore ? (regPasswordScore <= 1 ? '#f38ba8' : regPasswordScore <= 3 ? '#f9e2af' : regPasswordScore === 4 ? '#89b4fa' : '#a6e3a1') : 'rgba(255,255,255,0.1)', transition: 'all 0.3s' }} />
                      ))}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', fontSize: '0.78rem', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', padding: '8px 10px', borderRadius: '8px' }}>
                      {[
                        [regPasswordConditions.length, 'At least 8 characters'],
                        [regPasswordConditions.upper, 'One uppercase letter (A-Z)'],
                        [regPasswordConditions.lower, 'One lowercase letter (a-z)'],
                        [regPasswordConditions.number, 'One digit (0-9)'],
                        [regPasswordConditions.special, 'One special character (!@#$%^&*)']
                      ].map(([ok, label]) => (
                        <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '8px', color: ok ? '#a6e3a1' : '#a6adc8' }}>
                          <span>{ok ? '✓' : '·'}</span><span>{label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <button type="submit" className="btn btn-primary" style={{ marginTop: '12px' }} disabled={loading || regPasswordScore < 5}>
                {loading ? 'Creating Account…' : 'Register Account'}
              </button>
            </form>
          )}
        </div>
      </div>
    )
  }

  // ════════════════════════════════════════════════════════════════════════════
  // MAIN DASHBOARD
  // ════════════════════════════════════════════════════════════════════════════
  return (
    <div className="app-container">
      {/* Toast */}
      {toast && <Toast msg={toast.msg} type={toast.type} onDone={() => setToast(null)} />}

      {/* ── Desktop Top Header ─────────────────────────────────────────────── */}
      <header className="desktop-header">
        <div className="desktop-brand">
          <span className="brand-logo">🤖</span>
          <h2>TradeBot <span className="pro-tag">Pro</span></h2>
        </div>

        <div className="desktop-status-group" style={{ background: isBotRunning ? 'rgba(166,227,161,0.06)' : 'rgba(243,139,168,0.06)', border: `1px solid ${isBotRunning ? 'rgba(166,227,161,0.2)' : 'rgba(243,139,168,0.2)'}` }}>
          <span className="status-bullet" style={{ background: isBotRunning ? 'var(--color-success)' : 'var(--color-danger)', boxShadow: `0 0 6px ${isBotRunning ? 'var(--color-success)' : 'var(--color-danger)'}` }}></span>
          <span className="status-text" style={{ color: isBotRunning ? 'var(--color-success)' : 'var(--color-danger)' }}>
            {isBotRunning ? 'BOT ACTIVE' : 'BOT IDLE'}
          </span>
          {status?.market_status && (
            <>
              <span style={{ color: 'rgba(255,255,255,0.2)', margin: '0 4px' }}>|</span>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: status.market_status === 'open' ? 'var(--color-success)' : 'var(--color-warning)', textTransform: 'uppercase' }}>
                NSE {status.market_status}
              </span>
            </>
          )}
        </div>

        <div className="desktop-header-right">
          <div className="quick-actions">
            <button className="quick-action-btn" onClick={() => setActiveTab('help')} title="Help">❓</button>
            <button className="quick-action-btn" onClick={() => setActiveTab('settings')} title="Config">⚙️</button>
            <button className="quick-action-btn" onClick={handleLogout} title="Logout">🔒</button>
          </div>
          <div className="operator-header-badge">
            <span className="badge-avatar">👤</span>
            <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
              <span className="badge-name">{config?.name || userId}</span>
              <span style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>{config?.broker_type || 'MOCK'}</span>
            </div>
          </div>
        </div>
      </header>

      {/* ── Mobile Top Header ──────────────────────────────────────────────── */}
      <header className="mobile-header">
        <button className="mobile-toggle-btn" onClick={() => setIsControlCenterOpen(!isControlCenterOpen)}>🎛️</button>
        <div className="mobile-brand">
          <span className="brand-logo-sm">🤖</span>
          <h2>TradeBot <span className="pro-tag">Pro</span></h2>
        </div>
        <button className="mobile-toggle-btn" onClick={() => setIsNavigationOpen(!isNavigationOpen)}>☰</button>
      </header>

      {/* ── LEFT SIDEBAR: Control Center ───────────────────────────────────── */}
      <nav className={`sidebar-control ${isControlCenterOpen ? 'mobile-open' : ''}`}>
        <div className="drawer-close-row">
          <span>CONTROL CENTER</span>
          <button className="drawer-close-btn" onClick={() => setIsControlCenterOpen(false)}>✕</button>
        </div>

        {/* Quick stats row */}
        <div className="control-stats-row">
          <div className="stat-capsule">
            <span className="stat-label">Trades</span>
            <span className="stat-val">{periodTrades.length}/{config?.risk_rules?.max_trades_per_day || 5}</span>
          </div>
          <div className="stat-capsule">
            <span className="stat-label">P&L</span>
            <span className="stat-val" style={{ color: activePnL >= 0 ? '#a6e3a1' : '#f38ba8' }}>
              ₹{activePnL >= 0 ? '+' : ''}{activePnL.toFixed(0)}
            </span>
          </div>
        </div>

        {/* Bot Engine Status */}
        <div className="bot-status-container">
          <div className="status-label-group">
            <span className={`status-dot-pulse ${isBotRunning ? 'active' : 'idle'}`}></span>
            <span className="status-text">{isBotRunning ? 'ACTIVE' : 'IDLE'}</span>
          </div>
          <div className="ai-selection-group">
            <label className="switch-container">
              <input type="checkbox" checked={aiMarketSelection} onChange={e => setAiMarketSelection(e.target.checked)} />
              <span className="switch-slider"></span>
            </label>
            <span className="ai-selection-label">AI SELECTION</span>
          </div>
        </div>

        {/* Start / Stop / Emergency */}
        <div className="control-actions-group">
          <button className="btn-bot-start" onClick={() => { showToast('Engine startup initiated!', 'success'); setStatus(s => ({ ...s, running: true })) }} disabled={isBotRunning}>
            ▶ START BOT
          </button>
          <button className="btn-bot-pause" onClick={handleStopBot} disabled={!isBotRunning}>
            ⏸ PAUSE
          </button>
        </div>
        {positions.length > 0 && (
          <button onClick={handleCloseAll} style={{ width: '100%', marginTop: '6px', padding: '8px', background: 'rgba(243,139,168,0.12)', border: '1px solid rgba(243,139,168,0.3)', borderRadius: '8px', color: '#f38ba8', fontWeight: '700', cursor: 'pointer', fontSize: '0.8rem', transition: 'all 0.2s' }}>
            🚨 EMERGENCY EXIT ({positions.length} pos)
          </button>
        )}

        {/* BROKER SETTINGS */}
        <SidebarSection title="BROKER SETTINGS" icon="◆" defaultOpen={true}>
          <div className="select-container-dark">
            <select value={config?.broker_type || 'MOCK'} onChange={e => handleControlCenterChange('broker_type', e.target.value)} disabled={isBotRunning}>
              <option value="MOCK">MOCK</option>
              <option value="ANGEL">ANGEL ONE</option>
              <option value="ZERODHA">ZERODHA</option>
              <option value="UPSTOX">UPSTOX</option>
              <option value="GROWW">GROWW</option>
            </select>
          </div>
          <label className="checkbox-row-dark">
            <input type="checkbox" checked={!!config?.paper_trading} onChange={e => handleControlCenterChange('paper_trading', e.target.checked)} disabled={isBotRunning} />
            <span className="checkbox-custom"></span>
            <span className="checkbox-label">Paper Trading</span>
          </label>
          <label className="checkbox-row-dark">
            <input type="checkbox" checked={!!config?.use_tsl} onChange={e => handleControlCenterChange('use_tsl', e.target.checked)} disabled={isBotRunning} />
            <span className="checkbox-custom"></span>
            <span className="checkbox-label">Trailing SL</span>
          </label>
          <label className="checkbox-row-dark">
            <input type="checkbox" checked={!!config?.eod_exit} onChange={e => handleControlCenterChange('eod_exit', e.target.checked)} disabled={isBotRunning} />
            <span className="checkbox-custom"></span>
            <span className="checkbox-label">EOD Auto-Exit</span>
          </label>
          <label className="checkbox-row-dark">
            <input type="checkbox" checked={!!config?.kill_after_daily_limit} onChange={e => handleControlCenterChange('kill_after_daily_limit', e.target.checked)} disabled={isBotRunning} />
            <span className="checkbox-custom"></span>
            <span className="checkbox-label">Kill on Daily Limit</span>
          </label>
        </SidebarSection>

        {/* STRATEGY SETTINGS */}
        <SidebarSection title="STRATEGY" icon="✓" defaultOpen={true}>
          <div className="form-group-dark">
            <label>Strategy</label>
            <select value={config?.strategy_name || 'Combined'} onChange={e => handleControlCenterChange('strategy_name', e.target.value)} disabled={isBotRunning}>
              <option value="Combined">Combined</option>
              <option value="Breakout">Breakout</option>
              <option value="Momentum">Momentum</option>
              <option value="ScalpAI">Scalp AI</option>
            </select>
          </div>
          <div className="form-group-dark">
            <label>Candle</label>
            <select value={config?.candle_period || '15m'} onChange={e => handleControlCenterChange('candle_period', e.target.value)} disabled={isBotRunning}>
              <option value="1m">1m</option>
              <option value="3m">3m</option>
              <option value="5m">5m</option>
              <option value="15m">15m</option>
              <option value="30m">30m</option>
            </select>
          </div>
          <div className="form-group-dark">
            <label>Min Signals</label>
            <select value={config?.min_signals || 2} onChange={e => handleControlCenterChange('min_signals', parseInt(e.target.value))} disabled={isBotRunning}>
              {[1,2,3,4].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div className="form-group-dark">
            <label>AI Model</label>
            <select value={config?.ai_model || 'gemini-1.5-flash'} onChange={e => handleControlCenterChange('ai_model', e.target.value)} disabled={isBotRunning}>
              <option value="gemini-1.5-flash">Gemini Flash</option>
              <option value="gemini-1.5-pro">Gemini Pro</option>
              <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
            </select>
          </div>
        </SidebarSection>

        {/* ACTIVE MARKETS */}
        <SidebarSection title="ACTIVE MARKETS" icon="🌐" defaultOpen={true}>
          {[
            { key: 'nifty_enabled', label: 'NIFTY 50', symbol: 'NIFTY' },
            { key: 'banknifty_enabled', label: 'BANK NIFTY', symbol: 'BANKNIFTY' },
            { key: 'finnifty_enabled', label: 'FIN NIFTY', symbol: 'FINNIFTY' }
          ].map(({ key, label, symbol }) => {
            const q = quotes[symbol]
            return (
              <div key={key} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <div>
                  <div style={{ fontSize: '0.78rem', fontWeight: '700', color: 'white' }}>{label}</div>
                  {q?.last_price && <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>₹{q.last_price.toFixed(2)}</div>}
                </div>
                <label className="switch-container" style={{ transform: 'scale(0.85)' }}>
                  <input type="checkbox" checked={!!config?.[key]} onChange={e => handleControlCenterChange(key, e.target.checked)} disabled={isBotRunning} />
                  <span className="switch-slider"></span>
                </label>
              </div>
            )
          })}
        </SidebarSection>

        {/* RISK RULES SUMMARY */}
        <SidebarSection title="RISK RULES" icon="🛡️" defaultOpen={false}>
          {[
            ['Daily Loss Limit', `₹${(config?.risk_rules?.max_daily_loss || 0).toLocaleString('en-IN')}`, '#f38ba8'],
            ['Trade Target', `₹${(config?.risk_rules?.trade_target_rs || 0).toLocaleString('en-IN')}`, '#a6e3a1'],
            ['Trade SL', `₹${(config?.risk_rules?.trade_sl_rs || 0).toLocaleString('en-IN')}`, '#f9e2af'],
            ['Max Trades/Day', `${config?.risk_rules?.max_trades_per_day || 5}`, '#89b4fa'],
          ].map(([lbl, val, clr]) => (
            <div key={lbl} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{lbl}</span>
              <span style={{ fontSize: '0.8rem', fontWeight: '700', color: clr }}>{val}</span>
            </div>
          ))}
          <button onClick={() => setActiveTab('settings')} style={{ width: '100%', marginTop: '8px', padding: '6px', background: 'rgba(137,180,250,0.08)', border: '1px solid rgba(137,180,250,0.2)', borderRadius: '6px', color: 'var(--color-primary)', fontSize: '0.75rem', cursor: 'pointer' }}>
            ⚙️ Edit Risk Rules
          </button>
        </SidebarSection>

        {/* Footer status */}
        <div className="control-footer-status">
          <span className="status-item-indicator text-success"><span className="indicator-dot bg-success"></span>Connected</span>
          <span className={`status-item-indicator ${status?.market_status === 'open' ? 'text-success' : 'text-danger'}`}>
            <span className={`indicator-dot ${status?.market_status === 'open' ? 'bg-success' : 'bg-danger'}`}></span>
            NSE: {status?.market_status === 'open' ? 'Open' : 'Closed'}
          </span>
        </div>
      </nav>

      {/* Mobile backdrop */}
      {(isControlCenterOpen || isNavigationOpen) && (
        <div className="drawer-overlay" onClick={() => { setIsControlCenterOpen(false); setIsNavigationOpen(false) }} />
      )}

      {/* ── MAIN WORKSPACE ────────────────────────────────────────────────── */}
      <main className="main-workspace">
        <header className="workspace-header">
          <div className="header-title">
            <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              {{'overview':'📊','jarvis':'🧠','market':'🌐','positions':'🎯','management':'👥','settings':'⚙️','notifications':'🔔','trades':'📜','logs':'💻','help':'❓'}[activeTab] || ''}
              {activeTab.toUpperCase()}
            </h2>
            <p>TradeBot Pro — Standalone Operations Panel</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => { fetchStatus(); fetchPositions(); fetchTrades(); fetchConfig() }}>
            🔄 Refresh
          </button>
        </header>

        {/* ════ TAB: OVERVIEW ════════════════════════════════════════════════ */}
        {activeTab === 'overview' && (
          <div>
            {/* Date filter row */}
            <div className="filter-tabs-row">
              {[['today','📅 Today'],['yesterday','⏱️ Yesterday'],['week','📆 Past Week'],['month','📁 Past Month'],['all','♾️ All Time']].map(([f,l]) => (
                <button key={f} className={`filter-tab-btn ${activeFilter === f ? 'active' : ''}`} onClick={() => setActiveFilter(f)}>{l}</button>
              ))}
            </div>

            {/* 5 metric cards */}
            <div className="overview-metrics-grid">
              <div className="overview-metric-card border-green">
                <span className="card-lbl">PERIOD P&L</span>
                <span className={`card-val ${periodPnL >= 0 ? 'text-success' : 'text-danger'}`}>₹{periodPnL >= 0 ? '+' : ''}{periodPnL.toFixed(0)}</span>
                <span className="card-status">{periodTrades.length} trades</span>
              </div>
              <div className="overview-metric-card border-blue">
                <span className="card-lbl">TRADES</span>
                <span className="card-val text-primary">{periodTrades.length}</span>
                <span className="card-status">max {config?.risk_rules?.max_trades_per_day || 5}/day</span>
              </div>
              <div className="overview-metric-card border-yellow">
                <span className="card-lbl">WIN RATE</span>
                <span className="card-val text-warning">{winRate}%</span>
                <span className="card-status">{wins}W / {periodTrades.length - wins}L</span>
              </div>
              <div className="overview-metric-card border-pink">
                <span className="card-lbl">ACTIVE P&L</span>
                <span className={`card-val ${activePnL >= 0 ? 'text-success' : 'text-danger'}`}>₹{activePnL >= 0 ? '+' : ''}{activePnL.toFixed(0)}</span>
                <span className="card-status">{positions.length} positions</span>
              </div>
              <div className="overview-metric-card border-cyan">
                <span className="card-lbl">DAILY LIMIT</span>
                <span className="card-val text-cyan">₹{(config?.risk_rules?.max_daily_loss || 0).toLocaleString('en-IN')}</span>
                <span className="card-status">loss guard</span>
              </div>
            </div>

            {/* 2-col chart area */}
            <div className="overview-charts-grid">
              <div className="glass-card chart-card">
                <div className="panel-header"><h3>P&L TREND</h3></div>
                <div className="chart-body-container">
                  <svg className="svg-trend-chart" viewBox="0 0 400 180" width="100%" height="100%">
                    <defs>
                      <linearGradient id="chart-glow" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#a6e3a1" stopOpacity="0.25"/>
                        <stop offset="100%" stopColor="#a6e3a1" stopOpacity="0"/>
                      </linearGradient>
                    </defs>
                    {[50,90,130].map(y => <line key={y} x1="40" y1={y} x2="380" y2={y} stroke="rgba(255,255,255,0.05)" strokeDasharray="3"/>)}
                    {(() => {
                      const pts = trades.slice(-8).map(t => t.realized_pnl || t.pnl || 0)
                      if (pts.length < 2) return <path d="M40 90 L380 90" fill="none" stroke="#a6e3a1" strokeWidth="2.5" opacity="0.4"/>
                      const maxA = Math.max(...pts.map(Math.abs), 1)
                      const xs = pts.map((_, i) => 40 + (i / (pts.length - 1)) * 340)
                      const ys = pts.map(p => 90 - (p / maxA) * 75)
                      const d = `M ${xs[0]} ${ys[0]} ` + xs.slice(1).map((x,i) => `L ${x} ${ys[i+1]}`).join(' ')
                      const area = `${d} L ${xs[xs.length-1]} 90 L ${xs[0]} 90 Z`
                      return (<>
                        <path d={area} fill="url(#chart-glow)"/>
                        <path d={d} fill="none" stroke="#a6e3a1" strokeWidth="2.5"/>
                        {xs.map((x,i) => <circle key={i} cx={x} cy={ys[i]} r="4" fill="#a6e3a1"/>)}
                      </>)
                    })()}
                  </svg>
                </div>
              </div>

              <div className="glass-card chart-card">
                <div className="panel-header"><h3>INSTRUMENT ALLOCATION</h3></div>
                <div className="chart-body-container" style={{ display: 'grid', placeItems: 'center' }}>
                  {(() => {
                    const counts = {}
                    positions.forEach(p => { counts[p.symbol] = (counts[p.symbol] || 0) + 1 })
                    const entries = Object.entries(counts)
                    const colors = ['#89b4fa','#a6e3a1','#f9e2af','#f38ba8','#cba6f7']
                    if (entries.length === 0) return (
                      <div className="empty-allocation-chart-group">
                        <svg width="150" height="150" viewBox="0 0 100 100">
                          <circle cx="50" cy="50" r="40" fill="#89b4fa" opacity="0.3"/>
                          <circle cx="50" cy="50" r="28" fill="#11131c"/>
                          <text x="50" y="48" fill="white" fontSize="7" fontWeight="bold" textAnchor="middle">No Data</text>
                          <text x="50" y="58" fill="white" fontSize="7" textAnchor="middle">—</text>
                        </svg>
                        <span className="allocation-label">No Active Positions</span>
                      </div>
                    )
                    const total = entries.reduce((a, [, v]) => a + v, 0)
                    let startAngle = -90
                    const slices = entries.map(([sym, cnt], i) => {
                      const pct = cnt / total
                      const angle = pct * 360
                      const rad1 = (startAngle * Math.PI) / 180
                      const rad2 = ((startAngle + angle) * Math.PI) / 180
                      const x1 = 50 + 40 * Math.cos(rad1), y1 = 50 + 40 * Math.sin(rad1)
                      const x2 = 50 + 40 * Math.cos(rad2), y2 = 50 + 40 * Math.sin(rad2)
                      const largeArc = angle > 180 ? 1 : 0
                      const d = `M 50 50 L ${x1} ${y1} A 40 40 0 ${largeArc} 1 ${x2} ${y2} Z`
                      startAngle += angle
                      return { sym, pct, d, color: colors[i % colors.length] }
                    })
                    return (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                        <svg width="150" height="150" viewBox="0 0 100 100">
                          {slices.map(s => <path key={s.sym} d={s.d} fill={s.color} opacity="0.85"/>)}
                          <circle cx="50" cy="50" r="24" fill="#11131c"/>
                          <text x="50" y="50" fill="white" fontSize="6" fontWeight="bold" textAnchor="middle" dominantBaseline="middle">{positions.length} pos</text>
                        </svg>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center' }}>
                          {slices.map(s => <span key={s.sym} style={{ fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--color-text-muted)' }}><span style={{ width: '8px', height: '8px', borderRadius: '50%', background: s.color, display: 'inline-block' }}/>{s.sym} {(s.pct*100).toFixed(0)}%</span>)}
                        </div>
                      </div>
                    )
                  })()}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ════ TAB: JARVIS AI ═══════════════════════════════════════════════ */}
        {activeTab === 'jarvis' && (
          <div className="glass-card neural-container">
            <div className="panel-header">
              <h3>🧠 Jarvis Cybernetic Intelligence</h3>
              <span className="badge success status-pulse">Brain Active</span>
            </div>
            <div className="ai-grid">
              <div className="ai-console-pane">
                <div className="neural-radar">
                  <div className="radar-circle"></div>
                  <div className="radar-circle inner"></div>
                  <span className="brain-logo-glow">🧠</span>
                </div>
                <div className="radar-stats">
                  <p>Model: <strong>{config?.ai_model || 'Gemini Flash'}</strong></p>
                  <p>Intel Status: <strong>Monitoring Trades</strong></p>
                  <p>Voice Feed: <strong>Enabled</strong></p>
                  <p>AI Selection: <strong>{aiMarketSelection ? 'Active' : 'Manual'}</strong></p>
                </div>
              </div>
              <div className="ai-chat-history">
                <div className="chat-message bot">
                  <span className="msg-tag">JARVIS</span>
                  <p>System operational. Analyzing tick data for {config?.nifty_enabled ? 'NIFTY' : ''}{config?.banknifty_enabled ? ' & BANKNIFTY' : ''} options. Daily loss guard at ₹{(config?.risk_rules?.max_daily_loss || 0).toLocaleString('en-IN')}.</p>
                </div>
                <div className="chat-message user">
                  <span className="msg-tag">OPERATOR</span>
                  <p>Check portfolio limits</p>
                </div>
                <div className="chat-message bot">
                  <span className="msg-tag">JARVIS</span>
                  <p>Total Risk Deployed: ₹{activePnL < 0 ? Math.abs(activePnL).toFixed(0) : '0.00'}. Maximum Daily Drawdown buffer remaining: ₹{((config?.risk_rules?.max_daily_loss || 15000) + (activePnL < 0 ? activePnL : 0)).toFixed(0)}. System within safety bounds.</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ════ TAB: MARKET ══════════════════════════════════════════════════ */}
        {activeTab === 'market' && (
          <div className="glass-card">
            <div className="panel-header">
              <h3>Live Ticker Tapes</h3>
              <span className="badge success" style={{ fontSize: '0.72rem' }}>● Real-time Feed</span>
            </div>
            <div className="ticker-widget">
              {['NIFTY', 'BANKNIFTY', 'FINNIFTY'].map(symbol => {
                const q = quotes[symbol] || {}
                const ltp = q.last_price || (symbol === 'NIFTY' ? 22450 : symbol === 'BANKNIFTY' ? 47800 : 20900)
                const change = q.change || 0
                const pct = q.change_percent || 0
                return (
                  <div key={symbol} className="ticker-item" style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span className="ticker-symbol">{symbol}</span>
                    <span className="ticker-price">₹{ltp.toFixed(2)}</span>
                    <span className={`ticker-change ${change >= 0 ? 'up' : 'down'}`} style={{ color: change >= 0 ? '#a6e3a1' : '#f38ba8', fontSize: '0.75rem' }}>
                      {change >= 0 ? '▲' : '▼'} {Math.abs(change).toFixed(2)} ({Math.abs(pct).toFixed(2)}%)
                    </span>
                    <span style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)' }}>Vol: {q.volume ? (q.volume / 1000).toFixed(0) + 'K' : '—'}</span>
                  </div>
                )
              })}
            </div>
            {/* Quote grid for active positions */}
            {positions.length > 0 && (
              <div style={{ marginTop: '20px' }}>
                <h4 style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', marginBottom: '12px', textTransform: 'uppercase' }}>Active Position Quotes</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '12px' }}>
                  {positions.map((pos, i) => {
                    const q = quotes[pos.symbol]
                    return (
                      <div key={i} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-glass)', borderRadius: '10px', padding: '12px' }}>
                        <div style={{ fontWeight: '700', fontSize: '0.85rem', marginBottom: '4px' }}>{pos.symbol}</div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>LTP: <strong style={{ color: 'white' }}>₹{q?.last_price?.toFixed(2) || '—'}</strong></div>
                        <div style={{ fontSize: '0.75rem', color: pos.side === 'BUY' ? '#a6e3a1' : '#f38ba8' }}>{pos.side} {pos.qty || pos.quantity} lots</div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ════ TAB: POSITIONS ══════════════════════════════════════════════ */}
        {activeTab === 'positions' && (
          <div className="glass-card">
            <div className="panel-header">
              <h3>Active Trades Monitor</h3>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                {positions.length > 0 && (
                  <button className="btn btn-danger btn-sm" onClick={handleCloseAll}>🚨 Close All</button>
                )}
                <button className="btn btn-secondary btn-sm" onClick={fetchPositions}>🔄 Refresh</button>
              </div>
            </div>
            {positions.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--color-text-muted)' }}>
                <div style={{ fontSize: '3rem', marginBottom: '12px' }}>📭</div>
                No active positions in current sessions.
              </div>
            ) : (
              <div className="table-widget">
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>Contract</th><th>Direction</th><th>Qty</th><th>Entry</th><th>LTP</th><th>Unrealized P&L</th><th style={{ textAlign: 'center' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((pos, idx) => {
                      const q = quotes[pos.symbol]
                      const ltp = q?.last_price || pos.ltp || pos.buy_price || 0
                      const entry = pos.buy_price || pos.price || 0
                      const sideMult = pos.side === 'SELL' ? -1 : 1
                      const pnl = q?.last_price ? (ltp - entry) * (pos.qty || pos.quantity || 0) * sideMult : (pos.pnl || 0)
                      return (
                        <tr key={idx}>
                          <td style={{ fontWeight: 'bold' }}>{pos.symbol}</td>
                          <td><span className={`badge ${pos.side === 'BUY' ? 'success' : 'danger'}`}>{pos.side}</span></td>
                          <td>{pos.qty || pos.quantity}</td>
                          <td>₹{entry.toFixed(2)}</td>
                          <td>₹{ltp.toFixed(2)}</td>
                          <td className={`pnl-value ${pnl >= 0 ? 'positive' : 'negative'}`}>₹{pnl.toFixed(2)}</td>
                          <td style={{ textAlign: 'center' }}>
                            <button className="btn btn-danger btn-sm" onClick={() => handleCloseSingle(pos.symbol)}>⚡ Close</button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ════ TAB: MANAGEMENT ════════════════════════════════════════════ */}
        {activeTab === 'management' && (
          <div>
            {/* Summary cards */}
            <div className="overview-metrics-grid">
              {[
                ['TOTAL USERS', '1', 'border-blue', 'text-primary'],
                ['ACTIVE', config?.active ? '1' : '0', 'border-green', 'text-success'],
                ['INACTIVE', config?.active ? '0' : '1', 'border-pink', 'text-danger'],
                ['ACTIVE RATE', config?.active ? '100%' : '0%', 'border-yellow', 'text-warning'],
              ].map(([lbl, val, border, cls]) => (
                <div key={lbl} className={`overview-metric-card ${border}`}>
                  <span className="card-lbl">{lbl}</span>
                  <span className={`card-val ${cls}`}>{val}</span>
                  <span className="card-status">Stable</span>
                </div>
              ))}
            </div>

            {/* Users table */}
            <div className="glass-card" style={{ marginBottom: '20px' }}>
              <div className="panel-header">
                <h3>👥 USER MANAGEMENT</h3>
                <button className="btn btn-secondary btn-sm" onClick={() => alert('Only one primary operator profile is supported.')}>+ Add User</button>
              </div>
              <div className="table-widget">
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>NAME</th><th>USER ID</th><th>DESIGNATION</th><th>BROKER</th><th>STATUS</th><th>DAILY LIMIT</th><th>LAST LOGIN</th><th style={{ textAlign: 'center' }}>ACTIONS</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style={{ fontWeight: 'bold', color: 'white' }}>{config?.name || userId}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{config?.user_id || userId}</td>
                      <td><span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontWeight: '600' }}>Operator</span></td>
                      <td><span className="badge" style={{ background: 'rgba(137,180,250,0.15)', color: '#89b4fa', border: '1px solid rgba(137,180,250,0.3)' }}>{config?.broker_type || 'MOCK'}</span></td>
                      <td><span className={`badge ${config?.active ? 'success' : 'danger'}`}>{config?.active ? '☑ Active' : '☒ Inactive'}</span></td>
                      <td style={{ fontWeight: '600' }}>₹{(config?.risk_rules?.max_daily_loss || 15000).toLocaleString('en-IN')}</td>
                      <td style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>Session Active</td>
                      <td style={{ textAlign: 'center' }}>
                        <button onClick={() => { setEditedOperatorName(config?.name || userId); setEditedOperatorBroker(config?.broker_type || 'MOCK'); setEditedOperatorActive(config?.active ?? true); setEditedRisk({ ...config?.risk_rules }); setIsEditingOperator(true) }}
                          style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-glass)', borderRadius: '8px', padding: '6px 12px', cursor: 'pointer', color: 'white', fontSize: '0.8rem' }}
                          title="Edit profile">✏️ Edit</button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Credentials Section */}
            <div className="glass-card">
              <div className="panel-header">
                <h3>🔑 BROKER CREDENTIALS</h3>
                <div style={{ display: 'flex', gap: '10px' }}>
                  {isEditingCreds ? (
                    <>
                      <button className="btn btn-success btn-sm" onClick={async () => {
                        setLoading(true)
                        try {
                          await apiPost('/api/v1/config', { user_id: userId, settings: { credentials: editedCreds } })
                          showToast('Credentials updated!', 'success'); setIsEditingCreds(false); fetchConfig()
                        } catch (err) { showToast(err.message, 'error') }
                        setLoading(false)
                      }} disabled={loading}>{loading ? 'Saving…' : '💾 Save'}</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => setIsEditingCreds(false)}>Cancel</button>
                    </>
                  ) : (
                    <button className="btn btn-secondary btn-sm" onClick={() => { setEditedCreds(config?.credentials || {}); setIsEditingCreds(true) }}>✏️ Edit Credentials</button>
                  )}
                </div>
              </div>
              {isBotRunning && (
                <div style={{ background: 'rgba(249,226,175,0.1)', border: '1px solid rgba(249,226,175,0.3)', borderRadius: '8px', padding: '10px 14px', marginBottom: '16px', fontSize: '0.8rem', color: '#f9e2af', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  🔒 Bot is running — stop the bot before editing credentials.
                </div>
              )}
              <div className="settings-form" style={{ gridTemplateColumns: '1fr 1fr' }}>
                {[
                  ['API Key', 'api_key', true],
                  ['API Secret', 'api_secret', true],
                  ['Client ID', 'client_id', false],
                  ['Broker Password', 'password', true],
                  ['TOTP Secret', 'totp_secret', true],
                ].map(([label, key, masked]) => (
                  <div className="form-group" key={key}>
                    <label>{label}</label>
                    {masked ? (
                      <MaskedInput
                        value={isEditingCreds ? (editedCreds[key] || '') : (config?.credentials?.[key] ? '••••••••••••' : '')}
                        onChange={e => setEditedCreds(prev => ({ ...prev, [key]: e.target.value }))}
                        disabled={!isEditingCreds || isBotRunning}
                        placeholder={isEditingCreds ? `Enter ${label}` : config?.credentials?.[key] ? '•••••• (set)' : 'Not configured'}
                      />
                    ) : (
                      <input
                        value={isEditingCreds ? (editedCreds[key] || '') : (config?.credentials?.[key] || '')}
                        onChange={e => setEditedCreds(prev => ({ ...prev, [key]: e.target.value }))}
                        disabled={!isEditingCreds || isBotRunning}
                        placeholder={`Enter ${label}`}
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Edit Operator Modal */}
            {isEditingOperator && (
              <div className="login-overlay" style={{ background: 'rgba(0,0,0,0.75)', zIndex: 999 }}>
                <div className="login-card" style={{ maxWidth: '520px', width: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
                  <div className="login-brand" style={{ marginBottom: '20px' }}>
                    <div className="login-brand-icon" style={{ fontSize: '2.5rem' }}>👤</div>
                    <h2>Edit Operator Profile</h2>
                    <p>Modify operator details and risk parameters</p>
                  </div>

                  <form onSubmit={e => { e.preventDefault(); handleSaveOperatorDetails() }} className="login-form" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div className="form-group">
                      <label>Operator Full Name</label>
                      <input value={editedOperatorName} onChange={e => setEditedOperatorName(e.target.value)} placeholder="Full name" required style={{ height: '42px', borderRadius: '10px' }} />
                    </div>
                    <div className="form-group">
                      <label>Username (Read-only)</label>
                      <input value={config?.user_id || userId} disabled style={{ height: '42px', borderRadius: '10px', background: 'rgba(255,255,255,0.02)', cursor: 'not-allowed' }} />
                    </div>
                    <div className="form-group">
                      <label>Designation</label>
                      <select style={{ width: '100%', height: '42px', borderRadius: '10px', background: '#11131c', border: '1px solid var(--border-glass)', color: 'white', padding: '0 12px', fontSize: '0.9rem', cursor: 'pointer' }}>
                        <option>Operator</option>
                        <option>Senior Operator</option>
                        <option>Risk Manager</option>
                        <option>Admin</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Broker Integration</label>
                      <select value={editedOperatorBroker} onChange={e => setEditedOperatorBroker(e.target.value)}
                        style={{ width: '100%', height: '42px', borderRadius: '10px', background: '#11131c', border: '1px solid var(--border-glass)', color: 'white', padding: '0 12px', fontSize: '0.9rem', cursor: 'pointer' }}>
                        {['MOCK','ANGEL','ZERODHA','UPSTOX','GROWW'].map(b => <option key={b} value={b}>{b}</option>)}
                      </select>
                    </div>

                    {/* Risk Rules */}
                    <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '14px' }}>
                      <h4 style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', marginBottom: '12px', textTransform: 'uppercase' }}>🛡️ Risk Parameters</h4>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                        {[
                          ['Total Capital (₹)', 'total_capital'],
                          ['Trade Capital (₹)', 'trade_capital'],
                          ['Max Trades/Day', 'max_trades_per_day'],
                          ['Max Daily Loss (₹)', 'max_daily_loss'],
                          ['Trade Target (₹)', 'trade_target_rs'],
                          ['Trade SL (₹)', 'trade_sl_rs'],
                        ].map(([lbl, key]) => (
                          <div className="form-group" key={key} style={{ margin: 0 }}>
                            <label style={{ fontSize: '0.75rem' }}>{lbl}</label>
                            <input type="number" value={editedRisk[key] || ''} onChange={e => setEditedRisk(prev => ({ ...prev, [key]: parseFloat(e.target.value) }))} min="0" style={{ height: '38px', borderRadius: '8px', fontSize: '0.85rem' }} />
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="form-group">
                      <label>New Password (leave blank to keep)</label>
                      <div style={{ position: 'relative' }}>
                        <input type={showEditPassword ? 'text' : 'password'} value={editedOperatorPassword} onChange={e => setEditedOperatorPassword(e.target.value)} placeholder="Leave blank to keep unchanged" style={{ height: '42px', borderRadius: '10px', width: '100%', paddingRight: '44px' }} />
                        <button type="button" onMouseDown={() => setShowEditPassword(true)} onMouseUp={() => setShowEditPassword(false)} onMouseLeave={() => setShowEditPassword(false)}
                          style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: showEditPassword ? 'var(--color-primary)' : 'rgba(255,255,255,0.35)', cursor: 'pointer', padding: '0', display: 'flex', outline: 'none' }}>
                          <EyeIcon open={showEditPassword} />
                        </button>
                      </div>
                    </div>

                    <label className="checkbox-row-dark" style={{ cursor: 'pointer' }}>
                      <input type="checkbox" checked={editedOperatorActive} onChange={e => setEditedOperatorActive(e.target.checked)} />
                      <span className="checkbox-custom" style={{ width: '20px', height: '20px', background: '#11131c' }}></span>
                      <span className="checkbox-label" style={{ fontSize: '0.9rem', marginLeft: '6px' }}>Account Active</span>
                    </label>

                    <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                      <button type="submit" className="btn btn-primary" style={{ flex: 1, height: '44px' }} disabled={loading}>{loading ? 'Saving…' : '💾 Save Profile'}</button>
                      <button type="button" className="btn btn-secondary" style={{ flex: 1, height: '44px' }} onClick={() => setIsEditingOperator(false)}>Cancel</button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ════ TAB: SETTINGS (Config) ═══════════════════════════════════════ */}
        {activeTab === 'settings' && (
          <div>
            {/* Lock banner when bot running */}
            {isBotRunning && (
              <div style={{ background: 'rgba(243,139,168,0.1)', border: '1px solid rgba(243,139,168,0.3)', borderRadius: '12px', padding: '14px 20px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '1.5rem' }}>🔒</span>
                <div>
                  <div style={{ fontWeight: '700', color: '#f38ba8', fontSize: '0.9rem' }}>Configuration Locked — Bot Running</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>Stop the bot engine before modifying strategy or risk parameters.</div>
                </div>
              </div>
            )}

            {/* Strategy Settings Card */}
            <div className="glass-card" style={{ marginBottom: '20px' }}>
              <div className="panel-header">
                <h3>⚙️ Strategy Configuration</h3>
                <div style={{ display: 'flex', gap: '10px' }}>
                  {!isEditing ? (
                    <button className="btn btn-primary btn-sm" onClick={() => { setIsEditing(true); setEditedConfig({ ...config }) }} disabled={isBotRunning}>✍️ Edit</button>
                  ) : (
                    <>
                      <button className="btn btn-success btn-sm" onClick={handleSaveConfig} disabled={loading}>{loading ? 'Saving…' : '💾 Save'}</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => { setIsEditing(false); setEditedConfig(config) }}>Cancel</button>
                    </>
                  )}
                  <button className="btn btn-secondary btn-sm" onClick={fetchConfig}>🔄 Fetch</button>
                </div>
              </div>
              {!config ? (
                <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--color-text-muted)' }}>Settings unavailable — check backend connection.</div>
              ) : (
                <div className="settings-form">
                  <div className="form-group">
                    <label>Market Open (Read-only)</label>
                    <input value={config.market_open || ''} disabled />
                  </div>
                  <div className="form-group">
                    <label>Market Close (Read-only)</label>
                    <input value={config.market_close || ''} disabled />
                  </div>
                  <div className="form-group">
                    <label>Entry Start Window</label>
                    <input value={isEditing ? (editedConfig?.entry_start || '') : (config.entry_start || '')} onChange={e => setEditedConfig(p => ({ ...p, entry_start: e.target.value }))} disabled={!isEditing} placeholder="e.g. 09:30" />
                  </div>
                  <div className="form-group">
                    <label>Entry End Window</label>
                    <input value={isEditing ? (editedConfig?.entry_end || '') : (config.entry_end || '')} onChange={e => setEditedConfig(p => ({ ...p, entry_end: e.target.value }))} disabled={!isEditing} placeholder="e.g. 14:30" />
                  </div>
                  <div className="form-group">
                    <label>Candle Period</label>
                    <select value={isEditing ? (editedConfig?.candle_period || '15m') : (config.candle_period || '15m')} onChange={e => setEditedConfig(p => ({ ...p, candle_period: e.target.value }))} disabled={!isEditing}>
                      {['1m','3m','5m','15m','30m'].map(v => <option key={v} value={v}>{v}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>AI Model</label>
                    <select value={isEditing ? (editedConfig?.ai_model || 'gemini-1.5-flash') : (config.ai_model || 'gemini-1.5-flash')} onChange={e => setEditedConfig(p => ({ ...p, ai_model: e.target.value }))} disabled={!isEditing}>
                      <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                      <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                      <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Nifty Options</label>
                    <select value={isEditing ? String(!!editedConfig?.nifty_enabled) : String(!!config.nifty_enabled)} onChange={e => setEditedConfig(p => ({ ...p, nifty_enabled: e.target.value === 'true' }))} disabled={!isEditing}>
                      <option value="true">Enabled</option><option value="false">Disabled</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>BankNifty Options</label>
                    <select value={isEditing ? String(!!editedConfig?.banknifty_enabled) : String(!!config.banknifty_enabled)} onChange={e => setEditedConfig(p => ({ ...p, banknifty_enabled: e.target.value === 'true' }))} disabled={!isEditing}>
                      <option value="true">Enabled</option><option value="false">Disabled</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Paper Trading Mode</label>
                    <select value={isEditing ? String(!!editedConfig?.paper_trading) : String(!!config.paper_trading)} onChange={e => setEditedConfig(p => ({ ...p, paper_trading: e.target.value === 'true' }))} disabled={!isEditing}
                      style={{ color: (isEditing ? editedConfig?.paper_trading : config.paper_trading) ? 'var(--color-warning)' : 'var(--color-success)' }}>
                      <option value="true">🟡 Paper Trading (Mock Orders)</option>
                      <option value="false">🟢 Live Trading (Real Capital)</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>EOD Auto-Exit</label>
                    <select value={isEditing ? String(!!editedConfig?.eod_exit) : String(!!config.eod_exit)} onChange={e => setEditedConfig(p => ({ ...p, eod_exit: e.target.value === 'true' }))} disabled={!isEditing}>
                      <option value="true">Enabled — auto-square at 3:15 PM</option>
                      <option value="false">Disabled</option>
                    </select>
                  </div>
                </div>
              )}
            </div>

            {/* Risk Rules Card */}
            <div className="glass-card">
              <div className="panel-header">
                <h3>🛡️ Risk Management Rules</h3>
                {!isEditing && <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Click Edit above to modify</span>}
              </div>
              <div className="settings-form">
                {[
                  ['Total Capital (₹)', 'total_capital', 'Full account capital available'],
                  ['Trade Capital (₹)', 'trade_capital', 'Per-trade capital allocation'],
                  ['Max Trades / Day', 'max_trades_per_day', 'Daily trade limit'],
                  ['Max Daily Loss (₹)', 'max_daily_loss', 'Bot halts when exceeded'],
                  ['Trade Target (₹)', 'trade_target_rs', 'Per-trade profit target'],
                  ['Trade SL (₹)', 'trade_sl_rs', 'Per-trade stop loss amount'],
                ].map(([lbl, key, hint]) => (
                  <div className="form-group" key={key}>
                    <label>{lbl} <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', fontWeight: '400' }}>— {hint}</span></label>
                    <input
                      type="number"
                      value={isEditing ? (editedRisk[key] || '') : (config?.risk_rules?.[key] || '')}
                      onChange={e => setEditedRisk(p => ({ ...p, [key]: parseFloat(e.target.value) }))}
                      disabled={!isEditing || isBotRunning}
                      min="0"
                      step={key.includes('trades') ? '1' : '100'}
                    />
                  </div>
                ))}
              </div>

              {/* 1:2 SL:Target ratio indicator */}
              {config?.risk_rules && (() => {
                const sl = config.risk_rules.trade_sl_rs || 1
                const tgt = config.risk_rules.trade_target_rs || 1
                const ratio = (tgt / sl).toFixed(2)
                const good = tgt >= sl * 1.5
                return (
                  <div style={{ margin: '16px 0', padding: '12px 16px', background: good ? 'rgba(166,227,161,0.08)' : 'rgba(243,139,168,0.08)', border: `1px solid ${good ? 'rgba(166,227,161,0.25)' : 'rgba(243,139,168,0.25)'}`, borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '1.2rem' }}>{good ? '✅' : '⚠️'}</span>
                    <div>
                      <div style={{ fontWeight: '700', fontSize: '0.85rem', color: good ? '#a6e3a1' : '#f38ba8' }}>Risk:Reward Ratio — 1:{ratio}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{good ? 'Good ratio — Target is ≥1.5× the Stop Loss' : 'Consider increasing target or reducing SL'}</div>
                    </div>
                  </div>
                )
              })()}
            </div>
          </div>
        )}

        {/* ════ TAB: NOTIFICATIONS ══════════════════════════════════════════ */}
        {activeTab === 'notifications' && (
          <div>
            {/* Telegram Card */}
            <div className="glass-card" style={{ marginBottom: '20px' }}>
              <div className="panel-header">
                <h3>📨 Telegram Alert Broadcast</h3>
                <div style={{ display: 'flex', gap: '10px' }}>
                  {isEditingNotif ? (
                    <>
                      <button className="btn btn-success btn-sm" onClick={() => { setIsEditingNotif(false); showToast('Telegram settings saved locally', 'success') }}>💾 Save</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => setIsEditingNotif(false)}>Cancel</button>
                    </>
                  ) : (
                    <button className="btn btn-secondary btn-sm" onClick={() => setIsEditingNotif(true)}>✏️ Edit</button>
                  )}
                </div>
              </div>

              <div className="settings-form">
                <div className="form-group">
                  <label>Telegram Bot Token</label>
                  <MaskedInput
                    value={telegramToken}
                    onChange={e => setTelegramToken(e.target.value)}
                    disabled={!isEditingNotif}
                    placeholder="Enter bot token from @BotFather"
                  />
                </div>
                <div className="form-group">
                  <label>Telegram Chat ID</label>
                  <input value={telegramChatId} onChange={e => setTelegramChatId(e.target.value)} disabled={!isEditingNotif} placeholder="e.g. 8005538457" />
                </div>
              </div>
              <div style={{ marginTop: '16px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                <button className="btn btn-primary btn-sm" onClick={handleTestTelegram} disabled={testingTelegram || !telegramToken || !telegramChatId}>
                  {testingTelegram ? '⏳ Testing…' : '📤 Send Test Message'}
                </button>
                <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center' }}>
                  {telegramToken && telegramChatId ? '🟢 Credentials configured' : '🔴 Credentials not set'}
                </div>
              </div>
            </div>

            {/* Gemini AI Key Card */}
            <div className="glass-card">
              <div className="panel-header">
                <h3>🧠 Gemini AI Integration</h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Powers Jarvis Intelligence</span>
              </div>
              <div className="settings-form" style={{ gridTemplateColumns: '1fr' }}>
                <div className="form-group">
                  <label>Gemini API Key</label>
                  <MaskedInput
                    value={geminiKey}
                    onChange={e => setGeminiKey(e.target.value)}
                    placeholder="Enter Google AI Studio API key (AIza...)"
                  />
                </div>
              </div>
              <div style={{ marginTop: '16px', display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
                <button className="btn btn-primary btn-sm" onClick={handleTestGemini} disabled={testingGemini || !geminiKey}>
                  {testingGemini ? '⏳ Testing…' : '🧪 Test Connection'}
                </button>
                <button className="btn btn-success btn-sm" onClick={() => { showToast('Gemini key saved locally', 'success') }} disabled={!geminiKey}>
                  💾 Save Key
                </button>
                <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                  {geminiKey ? '🟢 API key configured' : '🔴 Not configured'}
                </div>
              </div>
              <div style={{ marginTop: '16px', padding: '12px', background: 'rgba(137,180,250,0.05)', borderRadius: '8px', fontSize: '0.78rem', color: 'var(--color-text-muted)', lineHeight: '1.5' }}>
                💡 Get your free API key at <a href="https://aistudio.google.com/" target="_blank" rel="noreferrer" style={{ color: 'var(--color-primary)' }}>Google AI Studio</a>. The Gemini key enables AI market analysis, trade commentary, and smart alerts via Jarvis.
              </div>
            </div>
          </div>
        )}

        {/* ════ TAB: TRADES (History) ════════════════════════════════════════ */}
        {activeTab === 'trades' && (
          <div>
            {/* Metric summary cards */}
            <div className="overview-metrics-grid" style={{ marginBottom: '20px' }}>
              <div className="overview-metric-card border-green">
                <span className="card-lbl">PERIOD P&L</span>
                <span className={`card-val ${periodPnL >= 0 ? 'text-success' : 'text-danger'}`}>₹{periodPnL >= 0 ? '+' : ''}{periodPnL.toFixed(0)}</span>
                <span className="card-status">{activeFilter}</span>
              </div>
              <div className="overview-metric-card border-blue">
                <span className="card-lbl">WIN RATE</span>
                <span className="card-val text-primary">{winRate}%</span>
                <span className="card-status">{wins}W {periodTrades.length - wins}L</span>
              </div>
              <div className="overview-metric-card border-yellow">
                <span className="card-lbl">MAX TRADE P&L</span>
                <span className="card-val text-warning">
                  ₹{periodTrades.length > 0 ? Math.max(...periodTrades.map(t => t.realized_pnl || t.pnl || 0)).toFixed(0) : '0'}
                </span>
                <span className="card-status">best trade</span>
              </div>
              <div className="overview-metric-card border-pink">
                <span className="card-lbl">MAX DRAWDOWN</span>
                <span className="card-val text-danger">
                  ₹{periodTrades.length > 0 ? Math.abs(Math.min(...periodTrades.map(t => t.realized_pnl || t.pnl || 0))).toFixed(0) : '0'}
                </span>
                <span className="card-status">worst trade</span>
              </div>
            </div>

            <div className="glass-card">
              <div className="panel-header" style={{ flexWrap: 'wrap', gap: '12px' }}>
                <h3>📜 Trade History Log</h3>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                  {/* Date filter */}
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {[['today','Today'],['week','Week'],['month','Month'],['all','All']].map(([f,l]) => (
                      <button key={f} onClick={() => setActiveFilter(f)} style={{ padding: '4px 10px', borderRadius: '6px', fontSize: '0.75rem', cursor: 'pointer', background: activeFilter === f ? 'var(--color-primary)' : 'rgba(255,255,255,0.05)', border: `1px solid ${activeFilter === f ? 'var(--color-primary)' : 'rgba(255,255,255,0.1)'}`, color: activeFilter === f ? '#0d0f18' : 'var(--color-text-muted)', fontWeight: activeFilter === f ? '700' : '400' }}>{l}</button>
                    ))}
                  </div>
                  <input value={tradeSearch} onChange={e => setTradeSearch(e.target.value)} placeholder="Filter symbol / side…" className="terminal-search" style={{ width: '180px', height: '32px' }} />
                  <button className="btn btn-secondary btn-sm" onClick={fetchTrades}>🔄 Reload</button>
                  <button className="btn btn-secondary btn-sm" onClick={exportTrades} style={{ color: '#a6e3a1', borderColor: 'rgba(166,227,161,0.3)' }}>📥 Export CSV</button>
                </div>
              </div>

              {trades.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--color-text-muted)' }}>
                  <div style={{ fontSize: '3rem', marginBottom: '12px' }}>📭</div>
                  No historical records found.
                </div>
              ) : (
                <div style={{ display: 'flex', gap: '0' }}>
                  <div className="table-widget" style={{ flex: 1 }}>
                    <table className="custom-table">
                      <thead>
                        <tr>
                          <th>Timestamp</th><th>Contract</th><th>Type</th><th>Qty</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {periodTrades
                          .filter(t => !tradeSearch || (t.symbol || '').toUpperCase().includes(tradeSearch.toUpperCase()) || (t.side || '').toUpperCase().includes(tradeSearch.toUpperCase()) || (t.exit_reason || '').toUpperCase().includes(tradeSearch.toUpperCase()))
                          .map((trade, idx) => {
                            const pnl = trade.realized_pnl || trade.pnl || 0
                            return (
                              <tr key={idx} onClick={() => setSelectedTrade(trade)} style={{ cursor: 'pointer', background: selectedTrade === trade ? 'rgba(137,180,250,0.06)' : '' }}>
                                <td style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>{trade.timestamp || trade.time || '—'}</td>
                                <td style={{ fontWeight: 'bold' }}>{trade.symbol}</td>
                                <td><span className={`badge ${trade.side === 'BUY' ? 'success' : 'danger'}`}>{trade.side || 'BUY'}</span></td>
                                <td>{trade.qty || trade.quantity}</td>
                                <td>₹{(trade.entry_price || trade.price || 0).toFixed(2)}</td>
                                <td>₹{(trade.exit_price || 0).toFixed(2)}</td>
                                <td className={`pnl-value ${pnl >= 0 ? 'positive' : 'negative'}`}>₹{pnl.toFixed(2)}</td>
                                <td><span className={`badge ${pnl >= 0 ? 'success' : 'danger'}`} style={{ fontSize: '0.7rem' }}>{trade.exit_reason || 'EXIT'}</span></td>
                              </tr>
                            )
                          })}
                      </tbody>
                    </table>
                  </div>
                  {/* Trade detail sidebar */}
                  {selectedTrade && (
                    <div style={{ width: '240px', borderLeft: '1px solid var(--border-glass)', padding: '16px', flexShrink: 0 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '14px' }}>
                        <h4 style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>Trade Details</h4>
                        <button onClick={() => setSelectedTrade(null)} style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer', fontSize: '1rem' }}>✕</button>
                      </div>
                      {[
                        ['Symbol', selectedTrade.symbol],
                        ['Side', selectedTrade.side],
                        ['Qty', selectedTrade.qty || selectedTrade.quantity],
                        ['Entry', `₹${(selectedTrade.entry_price || selectedTrade.price || 0).toFixed(2)}`],
                        ['Exit', `₹${(selectedTrade.exit_price || 0).toFixed(2)}`],
                        ['P&L', `₹${(selectedTrade.realized_pnl || selectedTrade.pnl || 0).toFixed(2)}`],
                        ['Reason', selectedTrade.exit_reason || '—'],
                        ['Time', selectedTrade.timestamp || selectedTrade.time || '—'],
                      ].map(([k, v]) => (
                        <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid rgba(255,255,255,0.04)', fontSize: '0.8rem' }}>
                          <span style={{ color: 'var(--color-text-muted)' }}>{k}</span>
                          <span style={{ fontWeight: '600', color: k === 'P&L' ? ((selectedTrade.realized_pnl || 0) >= 0 ? '#a6e3a1' : '#f38ba8') : 'white' }}>{v}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ════ TAB: LOGS (Console) ══════════════════════════════════════════ */}
        {activeTab === 'logs' && (
          <div className="terminal-widget">
            <div className="terminal-header">
              <div className="terminal-dots"></div>
              <div className="terminal-title">operator@tradebot-engine:~ <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.75rem', marginLeft: '8px' }}>({filteredLogs.length}/{logs.length} lines)</span></div>
              <div className="terminal-actions">
                {/* Level filters */}
                <div style={{ display: 'flex', gap: '4px', marginRight: '8px' }}>
                  {['ALL','INFO','WARN','ERROR'].map(lvl => (
                    <button key={lvl} onClick={() => setLogLevel(lvl)} style={{
                      padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem', cursor: 'pointer', fontWeight: '700',
                      background: logLevel === lvl ? (lvl === 'ERROR' ? 'rgba(243,139,168,0.25)' : lvl === 'WARN' ? 'rgba(249,226,175,0.25)' : 'rgba(137,180,250,0.15)') : 'rgba(255,255,255,0.05)',
                      border: `1px solid ${logLevel === lvl ? (lvl === 'ERROR' ? '#f38ba8' : lvl === 'WARN' ? '#f9e2af' : '#89b4fa') : 'rgba(255,255,255,0.1)'}`,
                      color: logLevel === lvl ? (lvl === 'ERROR' ? '#f38ba8' : lvl === 'WARN' ? '#f9e2af' : '#89b4fa') : 'var(--color-text-muted)'
                    }}>{lvl}</button>
                  ))}
                </div>
                <input value={logFilter} onChange={e => setLogFilter(e.target.value)} placeholder="Grep filter…" className="terminal-search" />
                {/* Compact mode */}
                <button onClick={() => setCompactLogs(c => !c)} title="Toggle compact mode" style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem', cursor: 'pointer', background: compactLogs ? 'rgba(137,180,250,0.15)' : 'rgba(255,255,255,0.05)', border: `1px solid ${compactLogs ? '#89b4fa' : 'rgba(255,255,255,0.1)'}`, color: compactLogs ? '#89b4fa' : 'var(--color-text-muted)' }}>⊡ Compact</button>
                {/* Auto-scroll toggle */}
                <button onClick={() => setAutoScroll(a => !a)} title="Toggle auto-scroll" style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem', cursor: 'pointer', background: autoScroll ? 'rgba(166,227,161,0.15)' : 'rgba(255,255,255,0.05)', border: `1px solid ${autoScroll ? '#a6e3a1' : 'rgba(255,255,255,0.1)'}`, color: autoScroll ? '#a6e3a1' : 'var(--color-text-muted)' }}>↓ Auto-scroll</button>
                <button className="btn btn-secondary btn-sm" style={{ height: '26px', padding: '0 10px', borderRadius: '6px', fontSize: '0.72rem' }} onClick={() => setLogs([])}>Clear</button>
              </div>
            </div>
            <div className="terminal-body">
              {filteredLogs.map((log, idx) => (
                <div key={idx} className={`log-line ${log.level}`} style={{ fontSize: compactLogs ? '0.72rem' : '0.8rem', padding: compactLogs ? '1px 0' : '2px 0' }}>
                  {!compactLogs && <span className="log-time">[{log.time}]</span>}
                  <span className="log-content">{log.text}</span>
                </div>
              ))}
              <div ref={terminalEndRef} />
            </div>
            {/* Log stats footer */}
            <div style={{ padding: '6px 16px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', gap: '16px', fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
              <span style={{ color: '#f38ba8' }}>ERR: {logs.filter(l => l.level === 'error').length}</span>
              <span style={{ color: '#f9e2af' }}>WARN: {logs.filter(l => l.level === 'warn').length}</span>
              <span style={{ color: '#89b4fa' }}>INFO: {logs.filter(l => l.level === 'info').length}</span>
              <span style={{ marginLeft: 'auto' }}>Buffer: {logs.length}/500</span>
            </div>
          </div>
        )}

        {/* ════ TAB: HELP ═══════════════════════════════════════════════════ */}
        {activeTab === 'help' && (
          <div className="glass-card">
            <div className="panel-header"><h3>❓ Operator Manual</h3></div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '8px 0' }}>
              <p>Welcome to <strong>TradeBot Pro</strong> Enterprise Standalone Control Dashboard.</p>

              {[
                ['🚀 Getting Started', [
                  'Login with your username and password created during registration.',
                  'Configure broker credentials in Management → Broker Credentials.',
                  'Set your risk rules in Settings → Risk Management Rules.',
                  'Toggle Active Markets in the left sidebar (NIFTY/BANKNIFTY).',
                  'Click START BOT in the Control Center to begin trading.'
                ]],
                ['🛡️ Safety & Risk Rules', [
                  'Daily Loss Limit: Bot halts automatically when daily loss exceeds this threshold.',
                  'EOD Auto-Exit: All open positions are squared-off at 3:15 PM when enabled.',
                  'Kill on Daily Limit: Bot terminates completely when daily loss breached.',
                  '1:2 Risk:Reward — maintain a target that is ≥1.5× your stop loss.'
                ]],
                ['🧠 Jarvis AI Integration', [
                  'Add your Gemini API key in Notifications tab to enable AI features.',
                  'AI Market Selection automatically picks NIFTY or BANKNIFTY based on momentum.',
                  'Jarvis monitors trades and generates real-time commentary and alerts.'
                ]],
                ['📨 Telegram Alerts', [
                  'Create a Telegram bot via @BotFather to get a bot token.',
                  'Get your Chat ID by messaging @userinfobot.',
                  'Use Test Message in Notifications tab to verify the connection.'
                ]],
                ['💻 Console / Logs Tab', [
                  'Real-time WebSocket log stream from the bot engine.',
                  'Use level filters (INFO/WARN/ERROR) to focus on specific messages.',
                  'Grep filter works like terminal grep — case insensitive substring match.',
                  'Compact mode reduces line height for higher density viewing.'
                ]]
              ].map(([title, items]) => (
                <div key={title}>
                  <h4 style={{ marginBottom: '8px', color: 'var(--color-primary)' }}>{title}</h4>
                  <ul style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    {items.map((item, i) => <li key={i} style={{ fontSize: '0.88rem', color: 'var(--color-text-muted)', lineHeight: '1.5' }}>{item}</li>)}
                  </ul>
                </div>
              ))}

              <div style={{ marginTop: '8px', padding: '12px 16px', background: 'rgba(137,180,250,0.06)', border: '1px solid rgba(137,180,250,0.15)', borderRadius: '10px', fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
                <strong style={{ color: 'var(--color-primary)' }}>TradeBot Pro v2.2.0</strong> — Secure Enterprise Standalone Control Dashboard.<br />
                Backend API: <code style={{ color: '#a6e3a1', fontSize: '0.75rem' }}>{API_BASE}</code>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ── RIGHT SIDEBAR: Navigation ──────────────────────────────────────── */}
      <nav className={`sidebar-nav ${isNavigationOpen ? 'mobile-open' : ''}`}>
        <div className="drawer-close-row">
          <span>NAVIGATION</span>
          <button className="drawer-close-btn" onClick={() => setIsNavigationOpen(false)}>✕</button>
        </div>

        <ul className="sidebar-menu">
          {[
            { id: 'overview', name: 'Overview', icon: '📊' },
            { id: 'jarvis', name: 'Jarvis AI', icon: '🧠' },
            { id: 'market', name: 'Market Analysis', icon: '🌐' },
            { id: 'positions', name: 'Active Trades', icon: '🎯', badge: positions.length || null },
            { id: 'management', name: 'Management', icon: '👥' },
            { id: 'settings', name: 'Config', icon: '⚙️' },
            { id: 'notifications', name: 'Notifications', icon: '🔔' },
            { id: 'trades', name: 'Trade History', icon: '📜', badge: periodTrades.length || null },
            { id: 'logs', name: 'Console', icon: '💻', badge: logs.filter(l => l.level === 'error').length || null },
            { id: 'help', name: 'Help', icon: '❓' }
          ].map((item) => (
            <li key={item.id} className={`menu-item ${activeTab === item.id ? 'active' : ''}`}>
              <button onClick={() => { setActiveTab(item.id); setIsNavigationOpen(false) }}>
                <span className="menu-icon">{item.icon}</span>
                <span>{item.name}</span>
                {item.badge ? (
                  <span style={{ marginLeft: 'auto', background: item.id === 'logs' ? 'rgba(243,139,168,0.2)' : 'rgba(137,180,250,0.2)', color: item.id === 'logs' ? '#f38ba8' : '#89b4fa', borderRadius: '99px', padding: '2px 7px', fontSize: '0.68rem', fontWeight: '700' }}>{item.badge}</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>

        {/* Sidebar footer */}
        <div className="sidebar-footer">
          <div className="user-badge">
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <div className="user-info" style={{ margin: 0 }}>
                <p style={{ margin: 0 }}>{config?.name || userId}</p>
                <span>{config?.user_id || userId} · {config?.broker_type || 'MOCK'}</span>
              </div>
            </div>
            <button className="logout-btn" onClick={handleLogout} title="Log Out">🚪</button>
          </div>
          <div className="sidebar-version-tag">v2.2.0 · {isBotRunning ? <span style={{ color: '#a6e3a1' }}>● Live</span> : <span style={{ color: '#7f849c' }}>● Idle</span>}</div>
        </div>
      </nav>

      <style>{`
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}

export default App
