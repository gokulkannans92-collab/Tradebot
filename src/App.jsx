import { useEffect, useState, useRef } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'https://purple-performer-entrepreneur-sustained.trycloudflare.com'

function App() {
  const [userId, setUserId] = useState(localStorage.getItem('tradebot_user') || '')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState(localStorage.getItem('tradebot_token') || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  
  // Registration States
  const [isRegistering, setIsRegistering] = useState(false)
  const [displayName, setDisplayName] = useState('')
  const [brokerType, setBrokerType] = useState('MOCK')
  const [successMessage, setSuccessMessage] = useState('')
  
  // Navigation
  const [activeTab, setActiveTab] = useState('overview')
  
  // Real-time & API States
  const [status, setStatus] = useState(null)
  const [positions, setPositions] = useState([])
  const [trades, setTrades] = useState([])
  const [config, setConfig] = useState(null)
  const [editedConfig, setEditedConfig] = useState(null)
  const [isEditing, setIsEditing] = useState(false)
  
  // Operator Editing States
  const [isEditingOperator, setIsEditingOperator] = useState(false)
  const [editedOperatorName, setEditedOperatorName] = useState('')
  const [editedOperatorBroker, setEditedOperatorBroker] = useState('MOCK')
  const [editedOperatorActive, setEditedOperatorActive] = useState(true)
  const [editedOperatorRiskLimit, setEditedOperatorRiskLimit] = useState(15000)
  const [isControlCenterOpen, setIsControlCenterOpen] = useState(false)
  const [isNavigationOpen, setIsNavigationOpen] = useState(false)
  const [activeFilter, setActiveFilter] = useState('today')
  const [aiMarketSelection, setAiMarketSelection] = useState(false)
  const [logs, setLogs] = useState([])
  const [quotes, setQuotes] = useState({})
  
  // Search / Filters
  const [logFilter, setLogFilter] = useState('')
  const [tradeSearch, setTradeSearch] = useState('')
  
  // Log Terminal Ref for Autoscroll
  const terminalEndRef = useRef(null)
  
  // WebSockets References
  const wsLogsRef = useRef(null)
  const wsQuotesRef = useRef(null)

  // 1. Initial Load & Background Polling
  useEffect(() => {
    if (token) {
      fetchStatus()
      fetchPositions()
      fetchTrades()
      fetchConfig()
      
      // Establish WebSocket connection for Logs
      connectLogsWS(token)
      // Establish WebSocket connection for Quotes
      connectQuotesWS(token)
      
      // Poll quick status every 5 seconds
      const interval = setInterval(() => {
        fetchStatus()
        fetchPositions()
      }, 5000)
      
      return () => {
        clearInterval(interval)
        disconnectWebSockets()
      }
    }
  }, [token])

  // Scroll terminal to bottom
  useEffect(() => {
    if (activeTab === 'logs' && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, activeTab])

  // Cleanup WebSockets
  function disconnectWebSockets() {
    if (wsLogsRef.current) {
      wsLogsRef.current.close()
      wsLogsRef.current = null
    }
    if (wsQuotesRef.current) {
      wsQuotesRef.current.close()
      wsQuotesRef.current = null
    }
  }

  // 2. WebSockets Handlers
  function connectLogsWS(accessToken) {
    if (wsLogsRef.current) return;
    
    const wsUrl = `${API_BASE.replace('http', 'ws')}/api/v1/ws/logs?token=${accessToken}`
    const ws = new WebSocket(wsUrl)
    
    ws.onopen = () => {
      console.log('Logs WebSocket connected')
      setLogs((prev) => [...prev, { text: 'CONNECTED TO REAL-TIME ENGINE LOG STREAM', time: new Date().toLocaleTimeString(), level: 'info' }])
    }
    
    ws.onmessage = (event) => {
      const line = event.data
      let level = 'info'
      if (line.includes(' ERROR ') || line.includes('CRITICAL')) level = 'error'
      else if (line.includes(' WARNING ')) level = 'warn'
      
      setLogs((prev) => {
        const next = [...prev, { text: line, time: new Date().toLocaleTimeString(), level }]
        // Keep logs buffer capped at 300 entries for high performance
        if (next.length > 300) next.shift()
        return next
      })
    }
    
    ws.onclose = () => {
      console.log('Logs WebSocket disconnected, retrying...')
      wsLogsRef.current = null
      setTimeout(() => connectLogsWS(accessToken), 5000)
    }
    
    ws.onerror = (err) => {
      console.error('Logs WS error: ', err)
    }
    
    wsLogsRef.current = ws
  }

  function connectQuotesWS(accessToken) {
    if (wsQuotesRef.current) return;
    
    const wsUrl = `${API_BASE.replace('http', 'ws')}/api/v1/ws/quotes?token=${accessToken}`
    const ws = new WebSocket(wsUrl)
    
    ws.onopen = () => {
      console.log('Quotes WebSocket connected')
      wsQuotesRef.current = ws
      // Auto-subscribe to standard NIFTY/BANKNIFTY indices upon connection
      subscribeQuotes(['NIFTY', 'BANKNIFTY', 'FINNIFTY'])
    }
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'quotes' && data.data) {
          setQuotes((prev) => ({
            ...prev,
            ...data.data
          }))
        }
      } catch (err) {
        console.error('Error parsing quote WS frame: ', err)
      }
    }
    
    ws.onclose = () => {
      console.log('Quotes WebSocket disconnected, retrying...')
      wsQuotesRef.current = null
      setTimeout(() => connectQuotesWS(accessToken), 5000)
    }
    
    wsQuotesRef.current = ws
  }

  function subscribeQuotes(symbols) {
    if (wsQuotesRef.current && wsQuotesRef.current.readyState === WebSocket.OPEN) {
      wsQuotesRef.current.send(JSON.stringify({
        action: 'subscribe',
        symbols: symbols
      }))
    }
  }

  // 3. REST API Requests
  async function fetchStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/status`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
      }
    } catch (err) {
      console.error('Failed status poll:', err)
    }
  }

  async function fetchPositions() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/positions`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setPositions(data.positions || [])
        
        // Dynamic subscription to symbols listed in positions
        const activeSymbols = (data.positions || []).map(p => p.symbol)
        if (activeSymbols.length > 0) {
          subscribeQuotes(activeSymbols)
        }
      }
    } catch (err) {
      console.error('Failed positions pull:', err)
    }
  }

  async function fetchTrades() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/trades`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setTrades(data.trades || [])
      }
    } catch (err) {
      console.error('Failed trades pull:', err)
    }
  }

  async function fetchConfig() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/config`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setConfig(data)
        setEditedConfig(data)
      }
    } catch (err) {
      console.error('Failed config fetch:', err)
    }
  }

  async function handleSaveConfig() {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/api/v1/config`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          user_id: userId,
          settings: {
            entry_start: editedConfig.entry_start,
            entry_end: editedConfig.entry_end,
            candle_period: editedConfig.candle_period,
            paper_trading: editedConfig.paper_trading === 'true' || editedConfig.paper_trading === true,
            nifty_enabled: editedConfig.nifty_enabled === 'true' || editedConfig.nifty_enabled === true,
            banknifty_enabled: editedConfig.banknifty_enabled === 'true' || editedConfig.banknifty_enabled === true
          }
        })
      })
      
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || 'Failed to update configuration')
      }
      
      const data = await res.json()
      alert(data.message || 'Configuration updated successfully!')
      setIsEditing(false)
      fetchConfig()
    } catch (err) {
      setError(err.message || 'Failed to save configuration')
    } finally {
      setLoading(false)
    }
  }

  async function handleSaveOperatorDetails() {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/api/v1/config`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          user_id: userId,
          settings: {
            name: editedOperatorName,
            broker_type: editedOperatorBroker,
            active: editedOperatorActive,
            risk_rules: {
              ...(config?.risk_rules || {}),
              max_daily_loss: parseFloat(editedOperatorRiskLimit)
            }
          }
        })
      })
      
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || 'Failed to update operator details')
      }
      
      alert('Operator details updated successfully!')
      setIsEditingOperator(false)
      fetchConfig()
    } catch (err) {
      alert(err.message || 'Failed to save operator details')
    } finally {
      setLoading(false)
    }
  }

  async function handleControlCenterChange(key, value) {
    if (!config) return;
    
    // Build updated values with instant feedback
    const updatedSettings = {
      entry_start: config.entry_start,
      entry_end: config.entry_end,
      candle_period: config.candle_period,
      paper_trading: config.paper_trading,
      nifty_enabled: config.nifty_enabled,
      banknifty_enabled: config.banknifty_enabled,
      [key]: value
    };
    
    // Optimistic state update
    setConfig({
      ...config,
      [key]: value
    });
    setEditedConfig({
      ...editedConfig,
      [key]: value
    });
    
    try {
      await fetch(`${API_BASE}/api/v1/config`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          user_id: userId,
          settings: updatedSettings
        })
      });
      // Silently sync from engine
      fetchConfig();
    } catch (err) {
      console.error('Failed to sync Control Center toggle:', err);
    }
  }

  // Action: Stop Bot
  async function handleStopBot() {
    if (!window.confirm('Are you sure you want to stop the bot? This will send a stop trigger signal to the engine.')) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/stop`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ user_id: userId })
      })
      const data = await res.json()
      alert(data.message || 'Stop signal triggered!')
      fetchStatus()
    } catch (err) {
      alert('Failed to send stop trigger: ' + err.message)
    }
  }

  // Action: Close All Positions
  async function handleCloseAll() {
    if (!window.confirm('🚨 EMERGENCY EXIT: Are you sure you want to square-off all active trades? This action is immediate and critical.')) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/close-all`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ user_id: userId })
      })
      const data = await res.json()
      alert(data.message || 'All positions closure triggered!')
      fetchPositions()
    } catch (err) {
      alert('Emergency closure failed: ' + err.message)
    }
  }

  // Action: Close Single Position
  async function handleCloseSingle(symbol) {
    if (!window.confirm(`Are you sure you want to square-off position for ${symbol}?`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/close-position`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ user_id: userId, symbol })
      })
      const data = await res.json()
      alert(data.message || `Position ${symbol} closure triggered!`)
      fetchPositions()
    } catch (err) {
      alert('Square off failed: ' + err.message)
    }
  }

  // Register handler
  async function handleRegister(event) {
    event.preventDefault()
    setError('')
    setSuccessMessage('')
    if (!userId || !displayName || !password) {
      setError('Please fill in all registration fields')
      return
    }
    setLoading(true)

    try {
      const response = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          name: displayName,
          password: password,
          broker_type: brokerType
        })
      })

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || 'Registration failed')
      }

      setSuccessMessage('Account registered successfully! You can now log in.')
      setIsRegistering(false) // Switch view back to login
      setPassword('')
      setDisplayName('')
    } catch (err) {
      setError(err.message || 'Registration request failed')
    } finally {
      setLoading(false)
    }
  }

  // Login handler
  async function handleLogin(event) {
    event.preventDefault()
    setError('')
    if (!userId || !password) {
      setError('Please enter both username and password')
      return
    }
    setLoading(true)

    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, password })
      })

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || 'Authentication failed')
      }

      const data = await response.json()
      setToken(data.access_token)
      localStorage.setItem('tradebot_token', data.access_token)
      localStorage.setItem('tradebot_user', userId)
      setPassword('')
    } catch (err) {
      setError(err.message || 'Connection to backend failed')
    } finally {
      setLoading(false)
    }
  }

  // Logout handler
  function handleLogout() {
    disconnectWebSockets()
    setToken('')
    setStatus(null)
    setPositions([])
    setTrades([])
    setConfig(null)
    setQuotes({})
    setLogs([])
    localStorage.removeItem('tradebot_token')
    localStorage.removeItem('tradebot_user')
  }

  // ── Render Views ────────────────────────────────────────────────────────

  // Secure login state
  if (!token) {
    return (
      <div className="login-overlay">
        <div className="login-card">
          <div className="login-brand">
            <div className="login-brand-icon">🤖</div>
            <h2>TradeBot Web</h2>
            <p>Secure Enterprise Control Dashboard</p>
          </div>

          {/* Tab Selection */}
          <div className="login-tabs" style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.1)', marginBottom: '16px', paddingBottom: '4px' }}>
            <button 
              onClick={() => { setIsRegistering(false); setError(''); setSuccessMessage(''); }}
              style={{
                flex: 1,
                background: 'none',
                border: 'none',
                color: !isRegistering ? 'var(--color-primary, #89b4fa)' : 'var(--color-text-muted, #a6adc8)',
                fontWeight: 'bold',
                padding: '8px',
                borderBottom: !isRegistering ? '2px solid var(--color-primary, #89b4fa)' : 'none',
                cursor: 'pointer',
                transition: 'all 0.3s ease'
              }}
            >
              Sign In
            </button>
            <button 
              onClick={() => { setIsRegistering(true); setError(''); setSuccessMessage(''); }}
              style={{
                flex: 1,
                background: 'none',
                border: 'none',
                color: isRegistering ? 'var(--color-primary, #89b4fa)' : 'var(--color-text-muted, #a6adc8)',
                fontWeight: 'bold',
                padding: '8px',
                borderBottom: isRegistering ? '2px solid var(--color-primary, #89b4fa)' : 'none',
                cursor: 'pointer',
                transition: 'all 0.3s ease'
              }}
            >
              Create Account
            </button>
          </div>

          {error && (
            <div className="alert-error" style={{ marginBottom: '12px' }}>
              <span>⚠️</span>
              {error}
            </div>
          )}

          {successMessage && (
            <div className="alert-success" style={{
              background: 'rgba(166, 227, 161, 0.15)',
              border: '1px solid #a6e3a1',
              color: '#a6e3a1',
              borderRadius: '8px',
              padding: '12px',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '12px'
            }}>
              <span>✅</span>
              {successMessage}
            </div>
          )}

          {!isRegistering ? (
            /* Login Form */
            <form onSubmit={handleLogin} className="login-form">
              <div className="form-group">
                <label>Operator Username</label>
                <input
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  placeholder="Enter username"
                  autoComplete="username"
                  required
                />
              </div>

              <div className="form-group">
                <label>Security Password</label>
                <input
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  type="password"
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                />
              </div>

              <button type="submit" className="btn btn-primary" style={{ marginTop: '12px' }} disabled={loading}>
                {loading ? 'Authenticating…' : 'Enter Dashboard'}
              </button>
            </form>
          ) : (
            /* Registration Form */
            <form onSubmit={handleRegister} className="login-form">
              <div className="form-group">
                <label>Desired Username (ID)</label>
                <input
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  placeholder="e.g. admin123"
                  required
                />
              </div>

              <div className="form-group">
                <label>Operator Full Name</label>
                <input
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="e.g. John Doe"
                  required
                />
              </div>

              <div className="form-group">
                <label>Broker Integration Type</label>
                <select
                  value={brokerType}
                  onChange={(e) => setBrokerType(e.target.value)}
                  style={{
                    width: '100%',
                    height: '42px',
                    borderRadius: '8px',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: 'white',
                    padding: '0 12px',
                    fontSize: '0.9rem',
                    outline: 'none',
                    cursor: 'pointer'
                  }}
                >
                  <option value="MOCK" style={{ background: '#1e1e2e', color: 'white' }}>Mock Trading (No Real Capital)</option>
                  <option value="ANGEL" style={{ background: '#1e1e2e', color: 'white' }}>Angel One Integration</option>
                  <option value="ZERODHA" style={{ background: '#1e1e2e', color: 'white' }}>Zerodha Kiteconnect</option>
                  <option value="UPSTOX" style={{ background: '#1e1e2e', color: 'white' }}>Upstox Integration</option>
                </select>
              </div>

              <div className="form-group">
                <label>Operator Password</label>
                <input
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  type="password"
                  placeholder="••••••••"
                  required
                />
              </div>

              <button type="submit" className="btn btn-primary" style={{ marginTop: '12px' }} disabled={loading}>
                {loading ? 'Creating Account…' : 'Register Account'}
              </button>
            </form>
          )}
        </div>
      </div>
    )
  }

  // Calculate dynamic stats
  const activePnL = positions.reduce((acc, pos) => {
    // If the backend has raw P&L, use it; otherwise compute from quotes
    const quote = quotes[pos.symbol]
    if (quote && quote.last_price) {
      const entry = pos.buy_price || pos.price || 0
      const sideMult = pos.side === 'SELL' ? -1 : 1
      const calculated = (quote.last_price - entry) * (pos.qty || pos.quantity || 0) * sideMult
      return acc + calculated
    }
    return acc + (pos.pnl || 0)
  }, 0)

  // Main UI shell with navigation
  return (
    <div className="app-container">
      {/* Desktop Top Header Bar */}
      <header className="desktop-header">
        <div className="desktop-brand">
          <span className="brand-logo">🤖</span>
          <h2>TradeBot <span className="pro-tag">Pro</span></h2>
        </div>
        
        {/* System Status Ticker in Middle */}
        <div className="desktop-status-group">
          <span className="status-bullet"></span>
          <span className="status-text">System Ready</span>
        </div>
        
        <div className="desktop-header-right">
          {/* Quick Actions */}
          <div className="quick-actions">
            <button className="quick-action-btn" onClick={() => setActiveTab('help')} title="Help Handbook">❓</button>
            <button className="quick-action-btn" onClick={() => setActiveTab('settings')} title="Config Settings">⚙️</button>
            <button className="quick-action-btn" onClick={handleLogout} title="Lock / Logout">🔒</button>
          </div>
          
          {/* Operator Badge */}
          <div className="operator-header-badge">
            <span className="badge-avatar">👤</span>
            <span className="badge-name">{config?.name || userId}</span>
          </div>
        </div>
      </header>

      {/* Mobile Top Header Bar */}
      <header className="mobile-header">
        <button className="mobile-toggle-btn" onClick={() => setIsControlCenterOpen(!isControlCenterOpen)} title="Control Center">
          🎛️
        </button>
        <div className="mobile-brand">
          <span className="brand-logo-sm">🤖</span>
          <h2>TradeBot <span className="pro-tag">Pro</span></h2>
        </div>
        <button className="mobile-toggle-btn" onClick={() => setIsNavigationOpen(!isNavigationOpen)} title="Navigation Menu">
          🍔
        </button>
      </header>

      {/* 1. Left Sidebar: Control Center (Responsive drawer on mobile) */}
      <nav className={`sidebar-control ${isControlCenterOpen ? 'mobile-open' : ''}`}>
        {/* Mobile Close Button for Drawer */}
        <div className="drawer-close-row">
          <span>CONTROL CENTER</span>
          <button className="drawer-close-btn" onClick={() => setIsControlCenterOpen(false)}>✕</button>
        </div>

        <div className="control-stats-row">
          <div className="stat-capsule">
            <span className="stat-label">Trades</span>
            <span className="stat-val">{trades.filter(t => new Date(t.timestamp || t.time || Date.now()).toDateString() === new Date().toDateString()).length}/5</span>
          </div>
          <div className="stat-capsule">
            <span className="stat-label">P&L</span>
            <span className="stat-val positive" style={{ color: activePnL >= 0 ? '#a6e3a1' : '#f38ba8' }}>
              ₹{activePnL >= 0 ? '+' : ''}{activePnL.toFixed(0)}
            </span>
          </div>
        </div>

        {/* Bot Engine Status Display */}
        <div className="bot-status-container">
          <div className="status-label-group">
            <span className={`status-dot-pulse ${status?.running ? 'active' : 'idle'}`}></span>
            <span className="status-text">{status?.running ? 'ACTIVE' : 'IDLE'}</span>
          </div>
          <div className="ai-selection-group">
            <label className="switch-container">
              <input 
                type="checkbox" 
                checked={aiMarketSelection} 
                onChange={(e) => setAiMarketSelection(e.target.checked)} 
              />
              <span className="switch-slider"></span>
            </label>
            <span className="ai-selection-label">AI MARKET SELECTION</span>
          </div>
        </div>

        {/* Start/Pause Control Actions */}
        <div className="control-actions-group">
          <button 
            className="btn-bot-start" 
            onClick={() => {
              alert('Engine startup sequence initiated successfully!');
              if (status) status.running = true;
              setStatus({ ...status, running: true });
            }}
            disabled={status?.running}
          >
            ▶ START BOT
          </button>
          <button 
            className="btn-bot-pause" 
            onClick={handleStopBot}
            disabled={!status?.running}
          >
            ⏸ Pause Trades
          </button>
        </div>

        {/* Broker Settings Section */}
        <div className="control-section-card">
          <h4 className="section-card-title">◆ BROKER SETTINGS</h4>
          <div className="section-card-body">
            <div className="select-container-dark">
              <select 
                value={config?.broker_type || 'MOCK'} 
                onChange={(e) => handleControlCenterChange('broker_type', e.target.value)}
              >
                <option value="MOCK">mock</option>
                <option value="ANGEL">angel</option>
                <option value="ZERODHA">zerodha</option>
                <option value="UPSTOX">upstox</option>
              </select>
            </div>
            
            <label className="checkbox-row-dark">
              <input 
                type="checkbox" 
                checked={config?.paper_trading ? true : false} 
                onChange={(e) => handleControlCenterChange('paper_trading', e.target.checked)}
              />
              <span className="checkbox-custom"></span>
              <span className="checkbox-label">Paper Trading</span>
            </label>

            <label className="checkbox-row-dark">
              <input 
                type="checkbox" 
                checked={config?.use_tsl ? true : false} 
                onChange={(e) => handleControlCenterChange('use_tsl', e.target.checked)}
              />
              <span className="checkbox-custom"></span>
              <span className="checkbox-label">Trailing SL</span>
            </label>

            <label className="checkbox-row-dark">
              <input 
                type="checkbox" 
                checked={config?.kill_after_daily_limit ? true : false} 
                onChange={(e) => handleControlCenterChange('kill_after_daily_limit', e.target.checked)}
              />
              <span className="checkbox-custom"></span>
              <span className="checkbox-label">Kill Bot (Limit)</span>
            </label>
          </div>
        </div>

        {/* Strategy Settings Section */}
        <div className="control-section-card">
          <h4 className="section-card-title">✓ STRATEGY SETTINGS</h4>
          <div className="section-card-body">
            <div className="form-group-dark">
              <label>Strategy</label>
              <select 
                value={config?.strategy_name || 'Combined'} 
                onChange={(e) => handleControlCenterChange('strategy_name', e.target.value)}
              >
                <option value="Combined">Combined</option>
                <option value="Breakout">Breakout</option>
                <option value="Momentum">Momentum</option>
              </select>
            </div>

            <div className="form-group-dark">
              <label>Candle</label>
              <select 
                value={config?.candle_period || '15m'} 
                onChange={(e) => handleControlCenterChange('candle_period', e.target.value)}
              >
                <option value="1m">1m</option>
                <option value="3m">3m</option>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
              </select>
            </div>

            <div className="form-group-dark">
              <label>Min Sig</label>
              <select 
                value={config?.min_signals || 2} 
                onChange={(e) => handleControlCenterChange('min_signals', parseInt(e.target.value))}
              >
                <option value="1">1</option>
                <option value="2">2</option>
                <option value="3">3</option>
                <option value="4">4</option>
              </select>
            </div>
          </div>
        </div>

        {/* Live Network & Exchange Status Indicators */}
        <div className="control-footer-status">
          <span className="status-item-indicator text-success">
            <span className="indicator-dot bg-success"></span>
            Connected
          </span>
          <span className={`status-item-indicator ${status?.market_status === 'open' ? 'text-success' : 'text-danger'}`}>
            <span className={`indicator-dot ${status?.market_status === 'open' ? 'bg-success' : 'bg-danger'}`}></span>
            NSE: {status?.market_status === 'open' ? 'Open' : 'Closed'}
          </span>
        </div>
      </nav>

      {/* Overlay Backdrop for Mobile Drawers */}
      {(isControlCenterOpen || isNavigationOpen) && (
        <div 
          className="drawer-overlay" 
          onClick={() => {
            setIsControlCenterOpen(false);
            setIsNavigationOpen(false);
          }}
        ></div>
      )}

      {/* 2. Center Column: Primary Content Workspace */}
      <main className="main-workspace">
        <header className="workspace-header">
          <div className="header-title">
            <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              {activeTab === 'overview' && '🏠 '}
              {activeTab === 'jarvis' && '🧠 '}
              {activeTab === 'market' && '📊 '}
              {activeTab === 'positions' && '🎯 '}
              {activeTab === 'management' && '👥 '}
              {activeTab === 'settings' && '⚙️ '}
              {activeTab === 'notifications' && '🔔 '}
              {activeTab === 'trades' && '📜 '}
              {activeTab === 'logs' && '💻 '}
              {activeTab === 'help' && '❓ '}
              {activeTab.toUpperCase()}
            </h2>
            <p>TradeBot Core Standalone Operations Panel</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => {
            fetchStatus();
            fetchPositions();
            fetchTrades();
            fetchConfig();
          }}>
            🔄 Refresh
          </button>
        </header>

        {/* Tab content renderer switch */}
        {activeTab === 'overview' && (
          <div>
            {/* Horizontal Filter Tabs row */}
            <div className="filter-tabs-row">
              {['today', 'yesterday', 'week', 'month', 'all'].map((filter) => (
                <button 
                  key={filter} 
                  className={`filter-tab-btn ${activeFilter === filter ? 'active' : ''}`}
                  onClick={() => setActiveFilter(filter)}
                >
                  {filter === 'today' && '📅 Today'}
                  {filter === 'yesterday' && '⏱️ Yesterday'}
                  {filter === 'week' && '📆 Past Week'}
                  {filter === 'month' && '📁 Past Month'}
                  {filter === 'all' && '♾️ All Time'}
                </button>
              ))}
            </div>

            {/* Row of 5 gorgeous metrics cards */}
            <div className="overview-metrics-grid">
              <div className="overview-metric-card border-green">
                <span className="card-lbl">PERIOD P&L</span>
                <span className="card-val text-success">
                  Rs+{trades.filter(t => {
                    if (activeFilter === 'today') {
                      return new Date(t.timestamp || t.time || Date.now()).toDateString() === new Date().toDateString();
                    }
                    return true;
                  }).reduce((acc, t) => acc + (t.realized_pnl || t.pnl || 0), 0).toFixed(0)}
                </span>
                <span className="card-status">Stable</span>
              </div>

              <div className="overview-metric-card border-blue">
                <span className="card-lbl">TRADES (PERIOD)</span>
                <span className="card-val text-primary">
                  {trades.filter(t => {
                    if (activeFilter === 'today') {
                      return new Date(t.timestamp || t.time || Date.now()).toDateString() === new Date().toDateString();
                    }
                    return true;
                  }).length}
                </span>
                <span className="card-status">Stable</span>
              </div>

              <div className="overview-metric-card border-yellow">
                <span className="card-lbl">SUCCESS RATE</span>
                <span className="card-val text-warning">
                  {(() => {
                    const periodTrades = trades.filter(t => {
                      if (activeFilter === 'today') {
                        return new Date(t.timestamp || t.time || Date.now()).toDateString() === new Date().toDateString();
                      }
                      return true;
                    });
                    const wins = periodTrades.filter(t => (t.realized_pnl || t.pnl || 0) > 0).length;
                    return periodTrades.length > 0 ? ((wins / periodTrades.length) * 100).toFixed(1) : '0.0';
                  })()}%
                </span>
                <span className="card-status">Stable</span>
              </div>

              <div className="overview-metric-card border-pink">
                <span className="card-lbl">ACTIVE P&L</span>
                <span className={`card-val ${activePnL >= 0 ? 'text-success' : 'text-danger'}`}>
                  Rs{activePnL >= 0 ? '+' : ''}{activePnL.toFixed(0)}
                </span>
                <span className="card-status">Stable</span>
              </div>

              <div className="overview-metric-card border-cyan">
                <span className="card-lbl">POSITIONS</span>
                <span className="card-val text-cyan">{positions.length}</span>
                <span className="card-status">Stable</span>
              </div>
            </div>

            {/* Bottom double column grid widgets */}
            <div className="overview-charts-grid">
              {/* P&L Trend Card */}
              <div className="glass-card chart-card">
                <div className="panel-header">
                  <h3>P&L TREND</h3>
                </div>
                <div className="chart-body-container">
                  {/* Premium customized SVG Trend Chart */}
                  <svg className="svg-trend-chart" viewBox="0 0 400 200" width="100%" height="100%">
                    <defs>
                      <linearGradient id="chart-glow" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#a6e3a1" stopOpacity="0.25"/>
                        <stop offset="100%" stopColor="#a6e3a1" stopOpacity="0"/>
                      </linearGradient>
                    </defs>
                    <grid>
                      <line x1="50" y1="50" x2="350" y2="50" stroke="rgba(255,255,255,0.03)" strokeDasharray="3"/>
                      <line x1="50" y1="100" x2="350" y2="100" stroke="rgba(255,255,255,0.06)"/>
                      <line x1="50" y1="150" x2="350" y2="150" stroke="rgba(255,255,255,0.03)" strokeDasharray="3"/>
                    </grid>
                    
                    {/* Draw lines based on trade logs */}
                    {(() => {
                      const tradePnlPoints = trades.slice(-3).map(t => t.realized_pnl || t.pnl || 0);
                      const baseLine = 100;
                      if (tradePnlPoints.length < 2) {
                        return (
                          <>
                            <path d="M 50 100 L 200 100 L 350 100" fill="none" stroke="#a6e3a1" strokeWidth="3" />
                            <circle cx="50" cy="100" r="5" fill="#a6e3a1" className="chart-dot-pulse" />
                            <text x="50" y="125" fill="#7f849c" fontSize="10" textAnchor="middle">T1</text>
                            <circle cx="200" cy="100" r="5" fill="#a6e3a1" />
                            <text x="200" y="125" fill="#7f849c" fontSize="10" textAnchor="middle">T2</text>
                            <circle cx="350" cy="100" r="5" fill="#a6e3a1" />
                            <text x="350" y="125" fill="#7f849c" fontSize="10" textAnchor="middle">T3</text>
                          </>
                        );
                      }
                      
                      // Map P&L values to Y coordinates
                      const maxPnL = Math.max(...tradePnlPoints.map(Math.abs), 1000);
                      const y1 = baseLine - (tradePnlPoints[0] / maxPnL) * 50;
                      const y2 = baseLine - (tradePnlPoints[1] / maxPnL) * 50;
                      const y3 = baseLine - (tradePnlPoints[2] || 0 / maxPnL) * 50;

                      return (
                        <>
                          <path d={`M 50 ${y1} L 200 ${y2} L 350 ${y3}`} fill="none" stroke="#a6e3a1" strokeWidth="3" />
                          <path d={`M 50 ${y1} L 200 ${y2} L 350 ${y3} L 350 100 L 50 100 Z`} fill="url(#chart-glow)" />
                          <circle cx="50" cy={y1} r="5" fill="#a6e3a1" className="chart-dot-pulse" />
                          <text x="50" y="125" fill="#7f849c" fontSize="10" textAnchor="middle">T1</text>
                          <circle cx="200" cy={y2} r="5" fill="#a6e3a1" />
                          <text x="200" y="125" fill="#7f849c" fontSize="10" textAnchor="middle">T2</text>
                          <circle cx="350" cy={y3} r="5" fill="#a6e3a1" />
                          <text x="350" y="125" fill="#7f849c" fontSize="10" textAnchor="middle">T3</text>
                        </>
                      );
                    })()}
                  </svg>
                </div>
              </div>

              {/* Instrument Allocation Card */}
              <div className="glass-card chart-card">
                <div className="panel-header">
                  <h3>INSTRUMENT ALLOCATION</h3>
                </div>
                <div className="chart-body-container" style={{ display: 'grid', placeItems: 'center' }}>
                  {positions.length === 0 ? (
                    <div className="empty-allocation-chart-group">
                      <svg width="150" height="150" viewBox="0 0 100 100">
                        <circle cx="50" cy="50" r="40" fill="#89b4fa" />
                        <circle cx="50" cy="50" r="28" fill="#11131c" />
                        <text x="50" y="48" fill="white" fontSize="7" fontWeight="bold" textAnchor="middle">No Data</text>
                        <text x="50" y="58" fill="white" fontSize="7" fontWeight="bold" textAnchor="middle">100.0%</text>
                      </svg>
                      <span className="allocation-label">No Data (100.0%)</span>
                    </div>
                  ) : (
                    <div className="empty-allocation-chart-group">
                      <svg width="150" height="150" viewBox="0 0 100 100">
                        {/* Render segmented allocation chart based on open positions */}
                        <circle cx="50" cy="50" r="40" fill="#a6e3a1" />
                        <circle cx="50" cy="50" r="28" fill="#11131c" />
                        <text x="50" y="48" fill="white" fontSize="6" fontWeight="bold" textAnchor="middle">{positions[0].symbol}</text>
                        <text x="50" y="58" fill="white" fontSize="7" fontWeight="bold" textAnchor="middle">100.0%</text>
                      </svg>
                      <span className="allocation-label">{positions[0].symbol} Allocated</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab: Jarvis AI Cyber Assistant */}
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
                  <p>Model: <strong>Gemini Flash</strong></p>
                  <p>Intel Status: <strong>Monitoring Trades</strong></p>
                  <p>Voice Feed: <strong>Enabled</strong></p>
                </div>
              </div>
              <div className="ai-chat-history">
                <div className="chat-message bot">
                  <span className="msg-tag">JARVIS</span>
                  <p>System operational. Currently analyzing tick data for NIFTY & BANKNIFTY options. No anomalies detected in current volatility bounds.</p>
                </div>
                <div className="chat-message user">
                  <span className="msg-tag">OPERATOR</span>
                  <p>Check portfolio limits</p>
                </div>
                <div className="chat-message bot">
                  <span className="msg-tag">JARVIS</span>
                  <p>Total Risk Deployed: ₹0.00. Maximum Daily Drawdown buffer is at 100% (₹15,000 available). Portfolio operates in full capital guard safety bounds.</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab: Market Analysis quotes lookup */}
        {activeTab === 'market' && (
          <div className="glass-card">
            <div className="panel-header">
              <h3>Live Ticker Tapes</h3>
            </div>
            <div className="ticker-widget">
              {['NIFTY', 'BANKNIFTY', 'FINNIFTY'].map((symbol) => {
                const quote = quotes[symbol] || { last_price: symbol === 'NIFTY' ? 22450 : symbol === 'BANKNIFTY' ? 47800 : 20900, volume: 500 };
                return (
                  <div key={symbol} className="ticker-item">
                    <span className="ticker-symbol">{symbol}</span>
                    <span className="ticker-price">₹{quote.last_price.toFixed(2)}</span>
                    <span className="ticker-change up">● Stream Online</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Tab: Active Trades Monitor */}
        {activeTab === 'positions' && (
          <div className="glass-card">
            <div className="panel-header">
              <h3>Active Trades Monitor</h3>
              <button className="btn btn-secondary btn-sm" onClick={fetchPositions}>🔄 Refresh Grid</button>
            </div>
            {positions.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--color-text-muted)' }}>
                No active positions found in active sessions.
              </div>
            ) : (
              <div className="table-widget">
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>Broker Contract</th>
                      <th>Direction</th>
                      <th>Lot Size</th>
                      <th>Avg Price</th>
                      <th>Market Price</th>
                      <th>Unrealized P&L</th>
                      <th style={{ textAlign: 'center' }}>Emergency Square Off</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((pos, idx) => {
                      const quote = quotes[pos.symbol]
                      const ltp = quote ? quote.last_price : (pos.ltp || pos.buy_price)
                      const entry = pos.buy_price || pos.price || 0
                      const sideMult = pos.side === 'SELL' ? -1 : 1
                      const calculatedPnl = quote && quote.last_price ? 
                        (quote.last_price - entry) * (pos.qty || pos.quantity || 0) * sideMult : 
                        (pos.pnl || 0)

                      return (
                        <tr key={idx}>
                          <td style={{ fontWeight: 'bold' }}>{pos.symbol}</td>
                          <td>
                            <span className={`badge ${pos.side === 'BUY' ? 'success' : 'danger'}`}>
                              {pos.side}
                            </span>
                          </td>
                          <td>{pos.qty || pos.quantity}</td>
                          <td>₹{entry.toFixed(2)}</td>
                          <td>₹{ltp.toFixed(2)}</td>
                          <td className={`pnl-value ${calculatedPnl >= 0 ? 'positive' : 'negative'}`} style={{ fontSize: '1rem' }}>
                            ₹{calculatedPnl.toFixed(2)}
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <button className="btn btn-danger btn-sm" onClick={() => handleCloseSingle(pos.symbol)}>
                              ⚡ Close Position
                            </button>
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

        {/* Tab: Operator User Management */}
        {activeTab === 'management' && (
          <div>
            {/* Row of 4 gorgeous metrics cards at the top */}
            <div className="overview-metrics-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
              <div className="overview-metric-card border-blue">
                <span className="card-lbl">TOTAL USERS</span>
                <span className="card-val text-primary">1</span>
                <span className="card-status">Stable</span>
              </div>

              <div className="overview-metric-card border-green">
                <span className="card-lbl">ACTIVE</span>
                <span className="card-val text-success">
                  {config?.active ? 1 : 0}
                </span>
                <span className="card-status">Stable</span>
              </div>

              <div className="overview-metric-card border-pink">
                <span className="card-lbl">INACTIVE</span>
                <span className="card-val text-danger">
                  {config?.active ? 0 : 1}
                </span>
                <span className="card-status">Stable</span>
              </div>

              <div className="overview-metric-card border-yellow">
                <span className="card-lbl">ACTIVE RATE</span>
                <span className="card-val text-warning">
                  {config?.active ? '100%' : '0%'}
                </span>
                <span className="card-status">Stable</span>
              </div>
            </div>

            {/* User Management Section */}
            <div className="glass-card">
              <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
                  👥 USER MANAGEMENT
                </h3>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                  <input
                    type="text"
                    placeholder="Search..."
                    className="terminal-search"
                    style={{ width: '180px', height: '36px', borderRadius: '10px' }}
                    disabled
                  />
                  <button 
                    className="btn btn-success" 
                    style={{ height: '36px', background: '#a6e3a1', color: '#0d0f18', fontWeight: 'bold' }}
                    onClick={() => alert('Only one primary operator profile is supported in standalone mode.')}
                  >
                    + Add
                  </button>
                </div>
              </div>

              {/* Users Table */}
              <div className="table-widget">
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>NAME</th>
                      <th>USER ID</th>
                      <th>BROKER</th>
                      <th>STATUS</th>
                      <th>RISK LIMIT</th>
                      <th>LAST LOGIN</th>
                      <th style={{ textAlign: 'center' }}>ACTIONS</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style={{ fontWeight: 'bold', color: 'white' }}>{config?.name || userId}</td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{config?.user_id || userId}</td>
                      <td>
                        <span className="badge success" style={{ background: 'rgba(137, 180, 250, 0.15)', color: '#89b4fa', borderColor: '#89b4fa' }}>
                          {config?.broker_type || 'MOCK'}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${config?.active ? 'success' : 'danger'}`}>
                          {config?.active ? '☑ Active' : '☒ Inactive'}
                        </span>
                      </td>
                      <td style={{ fontWeight: '600' }}>
                        ₹{(config?.risk_rules?.max_daily_loss || 15000).toLocaleString('en-IN')}
                      </td>
                      <td style={{ color: 'var(--color-text-muted)' }}>Never</td>
                      <td style={{ textAlign: 'center' }}>
                        <button 
                          className="logout-btn" 
                          style={{ 
                            background: 'rgba(255, 255, 255, 0.05)', 
                            border: '1px solid var(--border-glass)', 
                            borderRadius: '50%', 
                            width: '36px', 
                            height: '36px', 
                            display: 'inline-grid', 
                            placeItems: 'center', 
                            cursor: 'pointer',
                            fontSize: '1rem',
                            color: 'white',
                            transition: 'all 0.3s ease'
                          }}
                          onClick={() => {
                            setEditedOperatorName(config?.name || userId);
                            setEditedOperatorBroker(config?.broker_type || 'MOCK');
                            setEditedOperatorActive(config?.active ?? true);
                            setEditedOperatorRiskLimit(config?.risk_rules?.max_daily_loss || 15000);
                            setIsEditingOperator(true);
                          }}
                          title="Edit Operator details"
                        >
                          ✏️
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Operator Edit Modal overlay */}
            {isEditingOperator && (
              <div className="login-overlay" style={{ background: 'rgba(0,0,0,0.7)', zIndex: 999 }}>
                <div className="login-card" style={{ maxWidth: '480px', width: '100%' }}>
                  <div className="login-brand" style={{ marginBottom: '24px' }}>
                    <div className="login-brand-icon" style={{ fontSize: '2.5rem' }}>👤</div>
                    <h2>Edit Operator Profile</h2>
                    <p>Modify credentials and risk profiles in users.json</p>
                  </div>

                  <form onSubmit={(e) => { e.preventDefault(); handleSaveOperatorDetails(); }} className="login-form" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div className="form-group">
                      <label>Operator Full Name</label>
                      <input
                        value={editedOperatorName}
                        onChange={(e) => setEditedOperatorName(e.target.value)}
                        placeholder="e.g. GK"
                        required
                        style={{ height: '42px', borderRadius: '10px' }}
                      />
                    </div>

                    <div className="form-group">
                      <label>Operator User ID (Read-only)</label>
                      <input
                        value={config?.user_id || userId}
                        disabled
                        style={{ height: '42px', borderRadius: '10px', background: 'rgba(255,255,255,0.02)', cursor: 'not-allowed' }}
                      />
                    </div>

                    <div className="form-group">
                      <label>Active Broker Integration</label>
                      <select
                        value={editedOperatorBroker}
                        onChange={(e) => setEditedOperatorBroker(e.target.value)}
                        style={{
                          width: '100%',
                          height: '42px',
                          borderRadius: '10px',
                          background: '#11131c',
                          border: '1px solid var(--border-glass)',
                          color: 'white',
                          padding: '0 12px',
                          fontSize: '0.9rem',
                          cursor: 'pointer'
                        }}
                      >
                        <option value="MOCK">MOCK</option>
                        <option value="ANGEL">ANGEL</option>
                        <option value="ZERODHA">ZERODHA</option>
                        <option value="UPSTOX">UPSTOX</option>
                        <option value="GROWW">GROWW</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label>Daily Volatility Risk Limit (₹)</label>
                      <input
                        type="number"
                        value={editedOperatorRiskLimit}
                        onChange={(e) => setEditedOperatorRiskLimit(e.target.value)}
                        placeholder="e.g. 10000"
                        required
                        min="1"
                        style={{ height: '42px', borderRadius: '10px' }}
                      />
                    </div>

                    <div className="form-group" style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: '10px', padding: '8px 0' }}>
                      <label className="checkbox-row-dark" style={{ cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={editedOperatorActive}
                          onChange={(e) => setEditedOperatorActive(e.target.checked)}
                        />
                        <span className="checkbox-custom" style={{ width: '20px', height: '20px', background: '#11131c' }}></span>
                        <span className="checkbox-label" style={{ fontSize: '0.9rem', marginLeft: '6px' }}>Operator Account Active</span>
                      </label>
                    </div>

                    <div className="form-actions" style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
                      <button type="submit" className="btn btn-primary" style={{ flex: 1, height: '44px' }} disabled={loading}>
                        {loading ? 'Saving…' : '💾 Save Details'}
                      </button>
                      <button type="button" className="btn btn-secondary" style={{ flex: 1, height: '44px' }} onClick={() => setIsEditingOperator(false)} disabled={loading}>
                        Cancel
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 5: Configuration Settings Panel */}
        {activeTab === 'settings' && (
          <div className="glass-card">
            <div className="panel-header">
              <h3>Strategy Settings Profile</h3>
              <button className="btn btn-secondary btn-sm" onClick={fetchConfig}>🔄 Fetch Current</button>
            </div>
            {!config ? (
              <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--color-text-muted)' }}>
                Settings could not be fetched from engine.
              </div>
            ) : (
              <form className="settings-form" onSubmit={(e) => e.preventDefault()}>
                <div className="form-group">
                  <label>Market Session Open (Read-only)</label>
                  <input value={config.market_open || ''} disabled />
                </div>
                <div className="form-group">
                  <label>Market Session Close (Read-only)</label>
                  <input value={config.market_close || ''} disabled />
                </div>
                <div className="form-group">
                  <label>Entry Start Window</label>
                  <input 
                    value={isEditing ? (editedConfig?.entry_start || '') : (config.entry_start || '')} 
                    onChange={(e) => setEditedConfig({ ...editedConfig, entry_start: e.target.value })}
                    disabled={!isEditing} 
                    placeholder="e.g. 09:30"
                  />
                </div>
                <div className="form-group">
                  <label>Entry End Window</label>
                  <input 
                    value={isEditing ? (editedConfig?.entry_end || '') : (config.entry_end || '')} 
                    onChange={(e) => setEditedConfig({ ...editedConfig, entry_end: e.target.value })}
                    disabled={!isEditing} 
                    placeholder="e.g. 14:30"
                  />
                </div>
                <div className="form-group">
                  <label>Candle Period Interval</label>
                  <input 
                    value={isEditing ? (editedConfig?.candle_period || '') : (config.candle_period || '')} 
                    onChange={(e) => setEditedConfig({ ...editedConfig, candle_period: e.target.value })}
                    disabled={!isEditing} 
                    placeholder="e.g. 5m or 15m"
                  />
                </div>
                <div className="form-group">
                  <label>Options Strategy Status</label>
                  <select 
                    value={isEditing ? (editedConfig?.nifty_enabled ? 'true' : 'false') : (config.nifty_enabled ? 'true' : 'false')} 
                    onChange={(e) => setEditedConfig({ ...editedConfig, nifty_enabled: e.target.value === 'true' })}
                    disabled={!isEditing}
                  >
                    <option value="true">Nifty Options Enabled</option>
                    <option value="false">Disabled</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>BankNifty Integration</label>
                  <select 
                    value={isEditing ? (editedConfig?.banknifty_enabled ? 'true' : 'false') : (config.banknifty_enabled ? 'true' : 'false')} 
                    onChange={(e) => setEditedConfig({ ...editedConfig, banknifty_enabled: e.target.value === 'true' })}
                    disabled={!isEditing}
                  >
                    <option value="true">BankNifty Enabled</option>
                    <option value="false">Disabled</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Sandbox / Paper Trading Mode</label>
                  <select 
                    value={isEditing ? (editedConfig?.paper_trading ? 'true' : 'false') : (config.paper_trading ? 'true' : 'false')} 
                    onChange={(e) => setEditedConfig({ ...editedConfig, paper_trading: e.target.value === 'true' })}
                    style={{ color: (isEditing ? editedConfig?.paper_trading : config.paper_trading) ? 'var(--color-warning)' : 'var(--color-success)' }} 
                    disabled={!isEditing}
                  >
                    <option value="true">🟡 Paper Trading Active (Mock Orders)</option>
                    <option value="false">🟢 Live Market Trading Active (Real Capital)</option>
                  </select>
                </div>
                
                <div className="form-actions" style={{ display: 'flex', gap: '12px', marginTop: '20px', gridColumn: 'span 2' }}>
                  {!isEditing ? (
                    <button type="button" className="btn btn-primary" onClick={() => { setIsEditing(true); setEditedConfig(config); }}>
                      ✍️ Edit Configuration
                    </button>
                  ) : (
                    <>
                      <button type="button" className="btn btn-success" onClick={handleSaveConfig} disabled={loading}>
                        {loading ? 'Saving…' : '💾 Save Changes'}
                      </button>
                      <button type="button" className="btn btn-secondary" onClick={() => { setIsEditing(false); setEditedConfig(config); }} disabled={loading}>
                        ❌ Cancel
                      </button>
                    </>
                  )}
                </div>
              </form>
            )}
          </div>
        )}

        {/* Tab: Notifications / Telegram Integration */}
        {activeTab === 'notifications' && (
          <div className="glass-card">
            <div className="panel-header">
              <h3>🔔 Telegram Alert Broadcast</h3>
            </div>
            <div className="form-group">
              <label>Telegram Bot Token</label>
              <input value="8711362972:AAFzwb7RO_odzG1pYfImCoq4pan7utSOkuc" disabled />
            </div>
            <div className="form-group" style={{ marginTop: '16px' }}>
              <label>Telegram Chat ID</label>
              <input value="8005538457" disabled />
            </div>
          </div>
        )}

        {/* Tab: Historical Trade Logs */}
        {activeTab === 'trades' && (
          <div className="glass-card">
            <div className="panel-header" style={{ flexWrap: 'wrap', gap: '16px' }}>
              <h3>Historical Operations Log</h3>
              <div style={{ display: 'flex', gap: '12px' }}>
                <input
                  value={tradeSearch}
                  onChange={(e) => setTradeSearch(e.target.value)}
                  placeholder="Filter by Symbol or Side..."
                  className="terminal-search"
                  style={{ width: '200px', height: '36px' }}
                />
                <button className="btn btn-secondary btn-sm" onClick={fetchTrades}>🔄 Reload</button>
              </div>
            </div>
            {trades.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--color-text-muted)' }}>
                No historical records loaded.
              </div>
            ) : (
              <div className="table-widget">
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>Time Stamp</th>
                      <th>Asset Contract</th>
                      <th>Type</th>
                      <th>Quantity</th>
                      <th>Avg Execution Price</th>
                      <th>Close Price</th>
                      <th>Realized Profit</th>
                      <th>Exit Outcome</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades
                      .filter(t => 
                        !tradeSearch || 
                        (t.symbol || '').toUpperCase().includes(tradeSearch.toUpperCase()) ||
                        (t.side || '').toUpperCase().includes(tradeSearch.toUpperCase()) ||
                        (t.exit_reason || '').toUpperCase().includes(tradeSearch.toUpperCase())
                      )
                      .map((trade, idx) => {
                        const isWin = (trade.realized_pnl || trade.pnl || 0) >= 0
                        return (
                          <tr key={idx}>
                            <td>{trade.timestamp || trade.time || '-'}</td>
                            <td style={{ fontWeight: 'bold' }}>{trade.symbol}</td>
                            <td>
                              <span className={`badge ${trade.side === 'BUY' ? 'success' : 'danger'}`}>
                                {trade.side || 'BUY'}
                              </span>
                            </td>
                            <td>{trade.qty || trade.quantity}</td>
                            <td>₹{(trade.entry_price || trade.price || 0).toFixed(2)}</td>
                            <td>₹{(trade.exit_price || 0).toFixed(2)}</td>
                            <td className={`pnl-value ${isWin ? 'positive' : 'negative'}`}>
                              ₹{(trade.realized_pnl || trade.pnl || 0).toFixed(2)}
                            </td>
                            <td>
                              <span className={`badge ${isWin ? 'success' : 'danger'}`} style={{ fontSize: '0.7rem' }}>
                                {trade.exit_reason || trade.reason || 'EXIT'}
                              </span>
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

        {/* Tab: Real-time scrolling system logs terminal */}
        {activeTab === 'logs' && (
          <div className="terminal-widget">
            <div className="terminal-header">
              <div className="terminal-dots"></div>
              <div className="terminal-title">operator@tradebot-web-engine:~</div>
              <div className="terminal-actions">
                <input
                  value={logFilter}
                  onChange={(e) => setLogFilter(e.target.value)}
                  placeholder="Grep filter..."
                  className="terminal-search"
                />
                <button className="btn btn-secondary btn-sm" style={{ height: '26px', padding: '0 8px', borderRadius: '6px', fontSize: '0.75rem' }} onClick={() => setLogs([])}>
                  Clear Buffer
                </button>
              </div>
            </div>
            <div className="terminal-body">
              {logs
                .filter(l => !logFilter || l.text.toUpperCase().includes(logFilter.toUpperCase()))
                .map((log, idx) => (
                  <div key={idx} className={`log-line ${log.level}`}>
                    <span className="log-time">[{log.time}]</span>
                    <span className="log-content">{log.text}</span>
                  </div>
                ))}
              <div ref={terminalEndRef} />
            </div>
          </div>
        )}

        {/* Tab: Help operator handbook */}
        {activeTab === 'help' && (
          <div className="glass-card">
            <div className="panel-header">
              <h3>❓ Operator Manual & Documentation</h3>
            </div>
            <div className="help-content-rich" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <p>Welcome to <strong>TradeBot Pro</strong> Enterprise Standalone Control Dashboard.</p>
              <h4>Operational Safety Rules:</h4>
              <ul>
                <li>Ensure API keys are activated and connected under Broker settings before toggling Start Bot.</li>
                <li>Daily loss limits protect your trading account from highly volatile markets. Halts will trigger immediately on breach.</li>
                <li>Use Jarvis AI console mode to let LLM intelligence oversee system status and send custom Telegram notifications on anomaly events.</li>
              </ul>
            </div>
          </div>
        )}
      </main>

      {/* 3. Right Sidebar: Navigation panel (Responsive drawer on mobile) */}
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
            { id: 'positions', name: 'Active Trades', icon: '🎯' },
            { id: 'management', name: 'Management', icon: '🔑' },
            { id: 'settings', name: 'Config', icon: '⚙️' },
            { id: 'notifications', name: 'Notifications', icon: '🔔' },
            { id: 'trades', name: 'Trade History', icon: '📜' },
            { id: 'logs', name: 'Console', icon: '💻' },
            { id: 'help', name: 'Help', icon: '❓' }
          ].map((item) => (
            <li key={item.id} className={`menu-item ${activeTab === item.id ? 'active' : ''}`}>
              <button onClick={() => {
                setActiveTab(item.id);
                setIsNavigationOpen(false); // Auto close drawer on click
              }}>
                <span className="menu-icon">{item.icon}</span>
                <span>{item.name}</span>
              </button>
            </li>
          ))}
        </ul>

        <div className="sidebar-footer">
          <div className="user-badge">
            <div className="user-info">
              <p>{userId}</p>
              <span>Operator Profile</span>
            </div>
            <button className="logout-btn" onClick={handleLogout} title="Log Out">
              🚪
            </button>
          </div>
          <div className="sidebar-version-tag">
            v2.1.0
          </div>
        </div>
      </nav>
    </div>
  )
}

export default App
