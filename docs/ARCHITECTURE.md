# TradeBot Technical Architecture Overview

## 1. Project Structure

```
TradeBot/
├── main.py                    # CLI mode entry point (runs trading bot standalone)
├── gui_launcher.py            # GUI entry point (runs dashboard)
├── build_app.py             # Build script for packaging
│
├── src/
│   ├── app.py               # TradeBotApp - Central application container
│   │
│   ├── ui/                 # User Interface (Tkinter/CustomTkinter)
│   │   ├── dashboard_gui.py     # Main dashboard window
│   │   ├── gui_launcher.py      # Login screen
│   │   ├── first_run_wizard.py  # First-run setup
│   │   ├── shared.py           # UI utilities, themes, colors
│   │   ├── shared_state.py     # Global state (Tkinter variables)
│   │   ├── responsive.py       # Responsive sizing utilities
│   │   ├── helpers.py         # Background workers
│   │   │
│   │   ├── views/
│   │   │   ├── overview_view.py      # Dashboard home
│   │   │   ├── trades_view.py       # Active trades
│   │   │   ├── management_view.py  # User management
│   │   │   ├── config_view.py       # Settings
│   │   │   ├── logs_view.py       # Trade history
│   │   │   ├── console_view.py     # Live console
│   │   │   ├── notifications_view.py
│   │   │   ├── help_view.py
│   │   │   └── base.py
│   │   │
│   │   └── dashboard/layout/
│   │       ├── sidebar_manager.py   # Left sidebar
│   │       ├── header_manager.py  # Top header
│   │       ├── footer_manager.py  # Bottom footer
│   │       └── constants.py
│   │
│   ├── config/             # Configuration
│   ├── broker/             # Broker integrations
│   ├── engine/             # Trading engine
│   ├── strategy/            # Trading strategies
│   ├── trade/             # Trade execution
│   ├── risk/               # Risk management
│   ├── data/              # Market data
│   ├── persistence/       # Database
│   ├── api/               # REST API
│   └── utils/             # Utilities
```

---

## 2. Architecture Flow

### Application Startup

```
┌─────────────────────────────────────────────────────────────────────┐
│                    APPLICATION STARTUP                              │
└─────────────────────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│ Option A: CLI Mode                                        │
│   main.py → TradeBotApp → trading_loop                  │
└────────────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│ Option B: GUI Mode                                       │
│   gui_launcher.py → LoginView → dashboard_gui.py           │
│                           ↓                               │
│                    (subprocess)                          │
│                           ↓                               │
│                    TradeBotApp (background)              │
└────────────────────────────────────────────────────────────┘
```

### Startup Paths

**CLI Mode (headless trading):**
```
main.py
    ↓
TradeBotApp.initialize()
    ↓
MarketDataProvider, UserSessions, Strategies
    ↓
Trading Loop (run method)
```

**GUI Mode:**
```
gui_launcher.py
    ↓
LoginView (authenticate)
    ↓
TradeBotGUI (dashboard - subprocess.Popen)
    ↓
    ├─ main.py runs as background process
    └─ Communicates via:
        - Files: .active_trades, .trade_commands.json
        - SharedState: Tkinter variables in memory
```

---

## 3. Module Connections

### Key Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA FLOW DIAGRAM                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Input (UI)                                                │
│       ↓                                                         │
│  ┌────────────────┐    ┌───────────────┐                       │
│  │ shared_state  │ ←→ │ TradeBotGUI  │ ←→ Views                │
│  │ (Tk.Var)       │    └───────────────┘                       │
│  └───────┬────────┘              ↓                              │
│          ↓                         ↓                              │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │ .env file       │    │ .trade_commands  │ ← UI → Backend      │
│  │ (settings)     │    │ .active_trades   │                      │
│  └────────┬────────┘    └────────┬────────┘                     │
│           ↓                       ↓                              │
│  ┌─────────────────────────────────────────────────┐            │
│  │ TradeBotApp (background process) │ ← main.py    │
│  │                                 │                       │
│  │  ┌───────────┐  ┌───────────┐   │                       │
│  │  │Strategy  │→ │Trade Exec │→  │ Broker              │
│  │  └───────────┘  └───────────┘   │                       │
│  │  ┌───────────┐  ┌───────────┐   │                       │
│  │  │Data Prov. │→ │Risk Mgr   │   │                       │
│  │  └───────────┘  └───────────┘   │                       │
│  └─────────────────────────────────────────���───────┘            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Shared State Usage

**`shared_state.py`** - Central state container:
- `SharedState` class with Tkinter variables
- Variables for: broker, strategy, paper_trading, use_tsl, candle_timeframe, min_signals, nifty_lots, etc.
- Auto-persists to `user_preferences.json` on change
- Used by: sidebar, config_view, and all views that need shared config

---

## 4. UI Flow

### Navigation Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TAB STRUCTURE                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  TradeBotGUI                                                 │
│  ├─ Header (clock, title)                                  │
│  ├─ Left Sidebar (settings panels)                         │
│  │   ├─ Broker Connection                               │
│  │   ├─ Strategy Settings                             │
│  │   ├─ Risk Management                              │
│  │   └─ Instruments                                 │
│  ├─ Center Content (dynamic - views)                   │
│  │   ├─ Overview (stats + charts)      [default]      │
│  │   ├─ Active Trades                              │
│  │   ├─ Management (users)                         │
│  │   ├─ Config (settings)                         │
│  │   ├─ Trade History                             │
│  │   ├─ Notifications                              │
│  │   ├─ Console (live logs)                      │
│  │   └─ Help                                     │
│  └─ Right Sidebar (trading controls)                  │
│      ├─ Bot Start/Stop                               │
│      ├─ Market toggles                             │
│      └─ Position limits                           │
└─────────────────────────────────────────────────────────────┘
```

### Tab Switching Mechanism

```python
# dashboard_gui.py: _switch_tab()
def _switch_tab(self, name):
    # Lazily create view only when first accessed
    if name not in self.views:
        self.views[name] = self.view_factories[name](self._view_container)

    # Hide all, show selected (grid-based)
    for v in self.views.values():
        v.grid_remove()
    self.views[name].grid(row=0, column=0, sticky="nsew")
```

---

## 5. Data Flow Details

### UI → Backend Communication

| Mechanism | Files/Variables | Purpose |
|-----------|----------------|---------|
| **Command file** | `.trade_commands.json` | UI sends commands (CLOSE_TRADE, CLOSE_ALL) |
| **Active trades** | `.active_trades` | Backend writes open positions |
| **Shared state** | `SharedState` class | In-memory config sync |
| **Subprocess** | `subprocess.Popen` | Bot process management |

### File Communication Example

```python
# UI sends close command:
cmd = {"command": "CLOSE_TRADE", "symbol": "NIFTY23300CE"}
with open(".trade_commands.json", "w") as f:
    json.dump(cmd, f)

# Bot checks file each iteration:
with open(".trade_commands.json", "r") as f:
    cmd = json.load(f)
# Execute command, then clear file
```

---

## 6. Event Handling

### Start Bot Flow

```
User clicks "Start Bot"
    ↓
TradeBotGUI._start_bot()
    ↓
subprocess.Popen([python, main.py, --bot, --markets NIFTY,BANKNIFTY])
    ↓
    → LAUNCHED_FROM_DASHBOARD=1 set in env
    ↓
main.py runs (headless, no file logging)
    ↓
TradeBotApp.initialize()
    ↓
MarketDataProvider connects
    ↓
Trading loop starts (run method)
    ↓
Console auto-switches to show logs
```

### Stop Bot Flow

```
User clicks "Stop Bot"
    ↓
Write to .stop_trigger file
    ↓
Bot loop checks: if os.path.exists(stop_trigger)
    ↓
Shutdown sequence → remove file → exit loop
```

---

## 7. Background Processes

### Trading Loop (`src/engine/trading_loop.py`)

```python
# Main loop in TradeBotApp.run()
while self._running:
    # 1. Holiday check
    # 2. Market hours check
    # 3. Check exits for all sessions
    # 4. Update_trades_cache()
    # 5. Check stop trigger
    # 6. EOD exit check
    time.sleep(loop_interval)
```

### Console Refresh Loop (`src/ui/views/console_view.py`)

```python
# Automatic log refresh every 3 seconds
def _refresh_loop(self):
    self._append_new_logs()
    self.after(3000, self._refresh_loop)
```

---

## 8. External Integrations

### Broker APIs

| Broker | File | Authentication |
|--------|------|--------------|
| Angel One | `src/broker/angel_broker.py` | SmartAPI keys + TOTP |
| Zerodha | `src/broker/zerodha_broker.py` | API key + secret |
| Upstox | `src/broker/upstox_broker.py` | API key + secret |
| Mock | `src/broker/mock_broker.py` | Paper trading |

### Market Data

- NSE India WebSocket (primary)
- Angel One SmartAPI
- Zerodha Kite

---

## 9. Issues / Risks Identified

### Current UI Issues (Fixed)

1. **Layout inconsistency** - Mixed pack/grid managers → Unified to grid with weight=1 for center
2. **Scrolling** - Some views use CTkFrame → Changed to CTkScrollableFrame
3. **Duplicate code** - trades_view.py had ~288 lines duplicate (removed)

### Potential Design Risks

| Issue | Description | Impact |
|-------|-------------|--------|
| **State sync lag** | shared_state saves on every change | None (acceptable) |
| **File lock** | Both UI and bot write `.active_trades` | Low (careful timing) |
| **No IPC** | Uses files, not pipes/process comm | Console latency acceptable |

---

## 10. Summary - End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        COMPLETE FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. STARTUP                                                     │
│     gui_launcher.py → Login (user/password) → TradeBotGUI       │
│                                                                  │
│  2. USER ACTION: Start Bot                                     │
│     Click Start → subprocess.Popen(main.py) → TradeBotApp runs     │
│                                                                  │
│  3. TRADING LOOP (every 5 seconds)                              │
│     Check market open → Get signals → Execute trades → Update cache   │
│                                                                  │
│  4. DATA SYNC                                                   │
│     Bot writes .active_trades → UI reads → Display in Views    │
│                                                                  │
│  5. USER ACTION: Stop Bot                                      │
│     Click Stop → Create .stop_trigger → Bot exits cleanly    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Takeaways

- **Dual-mode**: CLI (`main.py`) and GUI (`gui_launcher.py`)
- **Background bot**: Runs as subprocess, communicates via files
- **Shared state**: Tkinter variables in `shared_state.py`
- **Lazy loading**: Views created only when first accessed
- **Grid-based layout**: Center column weight=1 for full expansion

---

## File Inventory

| Component | Key Files |
|-----------|----------|
| **Entry Points** | `main.py`, `gui_launcher.py` |
| **Application Core** | `src/app.py` |
| **UI** | `src/ui/dashboard_gui.py`, `src/ui/views/*.py` |
| **State** | `src/ui/shared_state.py` |
| **Engine** | `src/engine/trading_loop.py`, `src/engine/signal_processor.py` |
| **Brokers** | `src/broker/angel_broker.py`, `src/broker/zerodha_broker.py` |
| **Strategies** | `src/strategy/*.py` |
| **Risk** | `src/risk/risk_manager.py` |
| **Data** | `src/data/market_data_provider.py` |

---

*Generated: April 2026*