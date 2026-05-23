import { useEffect, useState, useRef } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL

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
      }
    } catch (err) {
      console.error('Failed config fetch:', err)
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
      {/* Sidebar Panel */}
      <nav className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-logo">🤖</div>
          <div className="brand-text">
            <h1>TradeBot</h1>
            <span>Terminal Core</span>
          </div>
        </div>

        <ul className="sidebar-menu">
          <li className={`menu-item ${activeTab === 'overview' ? 'active' : ''}`}>
            <button onClick={() => setActiveTab('overview')}>
              <span className="menu-icon">📊</span>
              <span>Overview</span>
            </button>
          </li>
          <li className={`menu-item ${activeTab === 'positions' ? 'active' : ''}`}>
            <button onClick={() => setActiveTab('positions')}>
              <span className="menu-icon">🎯</span>
              <span>Active Trades</span>
              {positions.length > 0 && (
                <span className="badge primary" style={{ marginLeft: 'auto', padding: '2px 6px', borderRadius: '6px' }}>
                  {positions.length}
                </span>
              )}
            </button>
          </li>
          <li className={`menu-item ${activeTab === 'trades' ? 'active' : ''}`}>
            <button onClick={() => setActiveTab('trades')}>
              <span className="menu-icon">📜</span>
              <span>Trade Logs</span>
            </button>
          </li>
          <li className={`menu-item ${activeTab === 'logs' ? 'active' : ''}`}>
            <button onClick={() => setActiveTab('logs')}>
              <span className="menu-icon">💻</span>
              <span>System Terminal</span>
            </button>
          </li>
          <li className={`menu-item ${activeTab === 'settings' ? 'active' : ''}`}>
            <button onClick={() => setActiveTab('settings')}>
              <span className="menu-icon">⚙️</span>
              <span>Configurations</span>
            </button>
          </li>
        </ul>

        <div className="sidebar-footer">
          <div className="user-badge">
            <div className="user-info">
              <p>{userId}</p>
              <span>Dashboard Admin</span>
            </div>
            <button className="logout-btn" onClick={handleLogout} title="Log Out">
              🚪
            </button>
          </div>
        </div>
      </nav>

      {/* Primary Content Workspace */}
      <main className="main-workspace">
        <header className="workspace-header">
          <div className="header-title">
            <h2>{activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} Control</h2>
            <p>TradeBot Core Service Integration Dashboard</p>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <span className={`badge status-pulse ${status?.running ? 'success' : 'danger'}`}>
              Bot: {status?.running ? 'Active' : 'Offline'}
            </span>
            <span className={`badge ${status?.market_status === 'open' ? 'success' : 'warning'}`}>
              Market: {status?.market_status || 'Offline'}
            </span>
          </div>
        </header>

        {/* Tab Render Switch */}
        {activeTab === 'overview' && (
          <div>
            {/* Top row metrics cards */}
            <div className="metrics-row">
              <div className="glass-card primary">
                <div className="metric-header">
                  <span>Engine P&L (Active)</span>
                  <span className="metric-icon">💰</span>
                </div>
                <div className={`metric-value ${activePnL >= 0 ? 'success' : 'danger'}`} style={{ color: activePnL >= 0 ? '#a6e3a1' : '#f38ba8' }}>
                  ₹{activePnL.toFixed(2)}
                </div>
                <div className="metric-sub">Across {positions.length} open position(s)</div>
              </div>

              <div className="glass-card success">
                <div className="metric-header">
                  <span>Index Price (NIFTY)</span>
                  <span className="metric-icon">📈</span>
                </div>
                <div className="metric-value">
                  {quotes['NIFTY'] ? `₹${quotes['NIFTY'].last_price.toFixed(2)}` : 'Loading…'}
                </div>
                <div className="metric-sub">Streaming Live via WebSockets</div>
              </div>

              <div className="glass-card warning">
                <div className="metric-header">
                  <span>Active Sessions</span>
                  <span className="metric-icon">👥</span>
                </div>
                <div className="metric-value">{status?.sessions ?? 0}</div>
                <div className="metric-sub">Broker pipelines connected</div>
              </div>
            </div>

            {/* Dashboard grid panel splits */}
            <div className="dashboard-grid">
              {/* Positions quick look */}
              <div className="glass-card">
                <div className="panel-header">
                  <h3>Active Sub-Positions</h3>
                  <button className="btn btn-secondary btn-sm" onClick={fetchPositions}>🔄 Force Pull</button>
                </div>
                {positions.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--color-text-muted)' }}>
                    No active positions currently running.
                  </div>
                ) : (
                  <div className="table-widget">
                    <table className="custom-table">
                      <thead>
                        <tr>
                          <th>Symbol</th>
                          <th>Side</th>
                          <th>Qty</th>
                          <th>Entry Price</th>
                          <th>LTP</th>
                          <th>P&L</th>
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
                              <td className={`pnl-value ${calculatedPnl >= 0 ? 'positive' : 'negative'}`}>
                                ₹{calculatedPnl.toFixed(2)}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Bot Controller Panels */}
              <div className="glass-card danger">
                <div className="panel-header">
                  <h3>Safety Controls</h3>
                  <span className="metric-icon">🚨</span>
                </div>
                <div className="controls-list">
                  <div className="control-item">
                    <div className="control-info">
                      <h4>Shutdown Bot</h4>
                      <p>Stops strategy signals engine</p>
                    </div>
                    <button className="btn btn-danger btn-sm" onClick={handleStopBot} disabled={!status?.running}>
                      Stop
                    </button>
                  </div>

                  <div className="control-item">
                    <div className="control-info">
                      <h4>Emergency Squaring-off</h4>
                      <p>Exits ALL active broker contracts</p>
                    </div>
                    <button className="btn btn-danger btn-sm" onClick={handleCloseAll} disabled={positions.length === 0}>
                      Square-Off
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Positions Workspace */}
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

        {/* Tab 3: Historical Trades Logs */}
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

        {/* Tab 4: System Console Logging Terminal */}
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
                  <label>Market Session Open</label>
                  <input value={config.market_open || ''} disabled />
                </div>
                <div className="form-group">
                  <label>Market Session Close</label>
                  <input value={config.market_close || ''} disabled />
                </div>
                <div className="form-group">
                  <label>Entry Start Window</label>
                  <input value={config.entry_start || ''} disabled />
                </div>
                <div className="form-group">
                  <label>Entry End Window</label>
                  <input value={config.entry_end || ''} disabled />
                </div>
                <div className="form-group">
                  <label>Candle Period Interval (Seconds)</label>
                  <input value={config.candle_period || ''} disabled />
                </div>
                <div className="form-group">
                  <label>Options Strategy Status</label>
                  <select value={config.nifty_enabled ? 'true' : 'false'} disabled>
                    <option value="true">Nifty Options Enabled</option>
                    <option value="false">Disabled</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>BankNifty Integration</label>
                  <select value={config.banknifty_enabled ? 'true' : 'false'} disabled>
                    <option value="true">BankNifty Enabled</option>
                    <option value="false">Disabled</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Sandbox / Paper Trading Mode</label>
                  <select value={config.paper_trading ? 'true' : 'false'} style={{ color: config.paper_trading ? 'var(--color-warning)' : 'var(--color-success)' }} disabled>
                    <option value="true">🟡 Paper Trading Active (Mock Orders)</option>
                    <option value="false">🟢 Live Market Trading Active (Real Capital)</option>
                  </select>
                </div>
              </form>
            )}
          </div>
        )}
      </main>
    </div>
  )
}

export default App
