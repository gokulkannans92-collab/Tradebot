"""
REST API Server

FastAPI-based REST API for external integrations and control.
Includes JWT authentication for secure API access.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException, status, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from src.api.auth import (
    TokenResponse, TokenRequest, create_access_token, 
    authenticate_user, get_current_user, TOKEN_EXPIRATION_MINUTES
)

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="TradeBot API",
    description="REST API for TradeBot trading operations",
    version="1.0.0"
)

# CORS middleware - configurable via environment
import os
_raw_origins = os.getenv("API_ALLOWED_ORIGINS", "").split(",") if os.getenv("API_ALLOWED_ORIGINS") else ["http://localhost:3000", "http://localhost:8000", "http://localhost:5173", "http://127.0.0.1:5173"]
# Clean origins: strip whitespace and trailing slashes
_allowed_origins = [origin.strip().rstrip("/") for origin in _raw_origins if origin.strip()]

# In production, restrict to specific origins
if os.getenv("ENVIRONMENT", "development") == "production":
    if not os.getenv("API_ALLOWED_ORIGINS"):
        _allowed_origins = []
        logger.warning("PRODUCTION: No CORS origins configured - restricting to same-origin only")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins if _allowed_origins else ["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting ──────────────────────────────────────────────────────────
import time
from collections import defaultdict

class RateLimiter:
    """Simple in-memory rate limiter for API endpoints."""
    
    def __init__(self, requests_per_minute: int = 30):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = None  # Lazy init for thread safety
    
    def _get_lock(self):
        if self._lock is None:
            import threading
            self._lock = threading.Lock()
        return self._lock
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed for client_id."""
        now = time.time()
        window_start = now - 60
        
        with self._get_lock():
            # Clean old requests outside window
            self.requests[client_id] = [
                t for t in self.requests[client_id] if t > window_start
            ]
            
            if len(self.requests[client_id]) >= self.requests_per_minute:
                return False
            
            self.requests[client_id].append(now)
            return True

# Global rate limiter instance
_rate_limiter = RateLimiter(requests_per_minute=30)

async def rate_limit_check(client_id: str = "default"):
    """Dependency for rate limiting."""
    if not _rate_limiter.is_allowed(client_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Max 30 requests per minute."
        )

# ── Request Models ──────────────────────────────────────────────────────

class TradeRequest(BaseModel):
    """Request to place a trade."""
    user_id: str
    symbol: str
    side: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: int = Field(..., gt=0)
    price: Optional[float] = None


class CloseTradeRequest(BaseModel):
    """Request to close a trade."""
    user_id: str
    symbol: str


class CloseAllRequest(BaseModel):
    """Request to close all positions."""
    user_id: str


class ConfigUpdateRequest(BaseModel):
    """Request to update user configuration."""
    user_id: str
    settings: Dict[str, Any]


# ── Response Models ────────────────────────────────────────────────────

class TradeResponse(BaseModel):
    """Trade operation response."""
    success: bool
    message: str
    trade_id: Optional[str] = None


class StatusResponse(BaseModel):
    """Bot status response."""
    running: bool
    sessions: int
    active_positions: int
    market_status: str
    timestamp: str


class PositionsResponse(BaseModel):
    """Positions response."""
    positions: List[Dict[str, Any]]


class TradesResponse(BaseModel):
    """Trades history response."""
    trades: List[Dict[str, Any]]
    total: int


class StatsResponse(BaseModel):
    """Statistics response."""
    stats: Dict[str, Any]


# ── Global State (using FastAPI app state for thread-safety) ──────────

@dataclass
class APIState:
    """API state management class for thread-safe access to global state."""
    
    bot_running: bool = False
    sessions: List = field(default_factory=list)
    data_provider: Any = None
    
    @classmethod
    def get_state(cls) -> 'APIState':
        """Get current API state from FastAPI app state."""
        return cls(
            bot_running=getattr(app.state, 'bot_running', False),
            sessions=getattr(app.state, 'sessions', []),
            data_provider=getattr(app.state, 'data_provider', None)
        )
    
    def save_state(self):
        """Save state to FastAPI app state."""
        app.state.bot_running = self.bot_running
        app.state.sessions = self.sessions
        app.state.data_provider = self.data_provider


def get_api_state() -> Dict[str, Any]:
    """Get API state from FastAPI app state - thread-safe."""
    return {
        "bot_running": app.state.bot_running if hasattr(app.state, "bot_running") else False,
        "sessions": app.state.sessions if hasattr(app.state, "sessions") else [],
        "data_provider": app.state.data_provider if hasattr(app.state, "data_provider") else None
    }


def set_api_state(bot_running: bool, sessions: List = None, data_provider = None):
    """Set API state in FastAPI app state - thread-safe."""
    app.state.bot_running = bot_running
    app.state.sessions = sessions or []
    app.state.data_provider = data_provider


# Initialize app state
app.state.bot_running = False
app.state.sessions = []
app.state.data_provider = None


# ── Health Check ────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    """Root endpoint."""
    return {"message": "TradeBot API", "version": "1.0.0", "status": "running"}


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "bot_running": get_api_state()["bot_running"]
    }


# ── WebSockets Endpoints ──────────────────────────────────────────────────
import asyncio
import collections
from fastapi import WebSocket, WebSocketDisconnect

def get_recent_logs(file_path: str, count: int = 100) -> List[str]:
    """Retrieve the last N lines from the log file safely and efficiently."""
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return list(collections.deque(f, count))
    except Exception as e:
        logger.error(f"Error reading historical logs: {e}")
        return [f"ERROR: Failed to read historical logs: {str(e)}"]


async def tail_log_file(websocket: WebSocket, log_file_path: str):
    """Tail the log file and stream new lines to the WebSocket client."""
    # 1. Send recent log history first
    history = get_recent_logs(log_file_path, 100)
    for line in history:
        await websocket.send_text(line.strip("\n"))
    
    # 2. Wait for log file if it doesn't exist yet
    if not os.path.exists(log_file_path):
        logger.info(f"Log file {log_file_path} not found. Waiting for creation...")
        while not os.path.exists(log_file_path):
            await asyncio.sleep(1.0)
    
    # 3. Stream new log lines as they are appended
    try:
        with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
            # Seek to current end of file
            f.seek(0, os.SEEK_END)
            position = f.tell()
            
            while True:
                # Check for file rotation/truncation
                try:
                    current_size = os.path.getsize(log_file_path)
                    if current_size < position:
                        logger.info("Log file rotation/truncation detected. Reopening.")
                        f.close()
                        f = open(log_file_path, "r", encoding="utf-8", errors="replace")
                        position = 0
                except Exception:
                    pass
                
                line = f.readline()
                if line:
                    await websocket.send_text(line.strip("\n"))
                    position = f.tell()
                else:
                    await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        logger.info("Log WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Error streaming logs: {e}")


async def quote_streamer(websocket: WebSocket, subscribed_symbols: set):
    """Stream live quotes for subscribed symbols to the WebSocket client."""
    try:
        while True:
            if subscribed_symbols:
                state = get_api_state()
                dp = state.get("data_provider")
                
                if dp:
                    quotes_data = {}
                    for symbol in list(subscribed_symbols):
                        try:
                            quote = dp.get_quote(symbol)
                            if quote:
                                quotes_data[symbol] = quote
                        except Exception as e:
                            logger.error(f"Error fetching quote for {symbol} in WS streamer: {e}")
                    
                    if quotes_data:
                        await websocket.send_json({
                            "type": "quotes",
                            "timestamp": datetime.now().isoformat(),
                            "data": quotes_data
                        })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Data provider not initialized. Connect sessions or start bot."
                    })
            
            await asyncio.sleep(1.0)  # Stream quotes every 1 second
    except WebSocketDisconnect:
        logger.info("Quote WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Error in quote streamer loop: {e}")


@app.websocket("/api/v1/ws/logs")
async def websocket_logs(websocket: WebSocket, token: Optional[str] = None):
    """
    WebSocket endpoint for real-time system logs.
    Requires authentication token passed as query parameter.
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication token is required")
        return
        
    try:
        from src.api.auth import verify_token
        verify_token(token)
    except ValueError as e:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(e))
        return
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return
        
    await websocket.accept()
    
    from src.utils.paths import get_path
    log_file_path = get_path("trade_bot.log")
    
    await tail_log_file(websocket, log_file_path)


@app.websocket("/api/v1/ws/quotes")
async def websocket_quotes(websocket: WebSocket, token: Optional[str] = None):
    """
    WebSocket endpoint for live market quote subscriptions.
    Requires authentication token passed as query parameter.
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication token is required")
        return
        
    try:
        from src.api.auth import verify_token
        verify_token(token)
    except ValueError as e:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(e))
        return
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return
        
    await websocket.accept()
    
    subscribed_symbols = set()
    streamer_task = asyncio.create_task(quote_streamer(websocket, subscribed_symbols))
    
    try:
        while True:
            # Expect client payload: {"action": "subscribe" | "unsubscribe", "symbols": ["NIFTY", ...]}
            data = await websocket.receive_json()
            action = data.get("action")
            symbols = data.get("symbols", [])
            
            if action == "subscribe":
                for symbol in symbols:
                    subscribed_symbols.add(symbol.upper())
                await websocket.send_json({
                    "type": "info",
                    "message": f"Subscribed to {list(symbols)}"
                })
            elif action == "unsubscribe":
                for symbol in symbols:
                    subscribed_symbols.discard(symbol.upper())
                await websocket.send_json({
                    "type": "info",
                    "message": f"Unsubscribed from {list(symbols)}"
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown action: {action}"
                })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Error in quotes WebSocket: {e}")
    finally:
        streamer_task.cancel()



# ── Authentication Endpoints ────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Registration request model."""
    user_id: str
    name: str
    password: str
    broker_type: str = "MOCK"


@app.post("/api/auth/register", tags=["Auth"])
def register(
    request: RegisterRequest,
    rate_limit: None = Depends(rate_limit_check)
):
    """
    Register a new user profile.
    """
    if not request.user_id or not request.name or not request.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id, name, and password are required"
        )
        
    import re
    
    # 1. Alphanumeric + Underscore check for user_id to sanitize inputs and prevent SQL/Filesystem exploits
    if not re.match(r"^[a-zA-Z0-9_]+$", request.user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username (ID) must contain only alphanumeric characters and underscores"
        )
        
    # 2. Strict password strength validation to prevent weak credential sniping
    password = request.password
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one uppercase letter"
        )
    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one lowercase letter"
        )
    if not re.search(r"[0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one numerical digit"
        )
    if not re.search(r"[^A-Za-z0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one special character"
        )
    
    from src.config import UserManager
    from src.utils.security import get_password_hash
    
    # Check if duplicate user exists
    existing = UserManager.get_user(request.user_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    hashed_pwd = get_password_hash(request.password)
    
    # Construct user dictionary (matching users.json schema exactly)
    new_user = {
        "user_id": request.user_id,
        "name": request.name,
        "active": True,
        "broker_type": request.broker_type.upper(),
        "login_password": hashed_pwd,
        "credentials": {
            "api_key": "",
            "api_secret": "",
            "client_id": "",
            "password": "",
            "totp_secret": ""
        },
        "risk_rules": {
            "total_capital": 100000.0,
            "trade_capital": 100000.0,
            "max_trades_per_day": 5,
            "max_daily_loss": 15000.0,
            "trade_target_rs": 10000.0,
            "trade_sl_rs": 1000.0
        }
    }
    
    success = UserManager.add_user(new_user)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user profile"
        )
        
    return {"success": True, "message": "User registered successfully"}


@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(
    request: TokenRequest,
    rate_limit: None = Depends(rate_limit_check)
):
    """
    Login endpoint to obtain JWT access token.
    
    Required for all protected endpoints.
    
    Args:
        request: TokenRequest with user_id and password
        
    Returns:
        TokenResponse with access_token, token_type, and expires_in
    """
    # Validate input
    if not request.user_id or not request.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id and password are required"
        )
    
    # Authenticate user
    if not authenticate_user(request.user_id, request.password):
        logger.warning(f"Failed login attempt for user: {request.user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Resolve the canonical user_id (e.g. user_001) from users.json to prevent fallback / mismatch issues when logging in via full name.
    from src.config import UserManager
    users = UserManager.load_users()
    user_data = next(
        (u for u in users if u.get("user_id") == request.user_id or u.get("name") == request.user_id),
        None
    )
    canonical_user_id = user_data.get("user_id") if user_data else request.user_id
    
    # Create access token
    access_token = create_access_token(canonical_user_id)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=TOKEN_EXPIRATION_MINUTES * 60  # in seconds
    )


# ── Status Endpoints ───────────────────────────────────────────────────

@app.get("/api/v1/status", response_model=StatusResponse, tags=["Status"])
def get_status(
    current_user: str = Depends(get_current_user),
    rate_limit: None = Depends(rate_limit_check)
):
    """Get current bot status."""
    active_positions = 0
    state = get_api_state()
    if state["sessions"]:
        for session in state["sessions"]:
            if hasattr(session, 'nifty_tracker'):
                active_positions += len(session.nifty_tracker.active_trades)
            if hasattr(session, 'bn_tracker'):
                active_positions += len(session.bn_tracker.active_trades)
    
    # Determine market status
    from src.config import Settings
    now = datetime.now().time()
    if Settings.MARKET_OPEN <= now <= Settings.MARKET_CLOSE:
        market_status = "open"
    else:
        market_status = "closed"
    
    return StatusResponse(
        running=state["bot_running"],
        sessions=len(state["sessions"]),
        active_positions=active_positions,
        market_status=market_status,
        timestamp=datetime.now().isoformat()
    )


# ── Positions Endpoints ────────────────────────────────────────────────

@app.get("/api/v1/positions", response_model=PositionsResponse, tags=["Positions"])
def get_all_positions(
    current_user: str = Depends(get_current_user),
    rate_limit: None = Depends(rate_limit_check)
):
    """
    Get all active positions across sessions.
    
    **Requires Authentication**: Bearer token required
    """
    positions = []
    state = get_api_state()
    
    if state["sessions"]:
        for session in state["sessions"]:
            if hasattr(session, 'get_active_trades'):
                try:
                    session_positions = session.get_active_trades()
                    for pos in session_positions:
                        pos["user_id"] = session.user_id
                    positions.extend(session_positions)
                except Exception as e:
                    logger.error(f"Failed to get positions for {current_user}: {e}")
    
    return PositionsResponse(positions=positions)


@app.get("/api/v1/positions/{user_id}", response_model=PositionsResponse, tags=["Positions"])
def get_user_positions(
    user_id: str,
    current_user: str = Depends(get_current_user),
    rate_limit: None = Depends(rate_limit_check)
):
    """
    Get positions for a specific user.
    
    **Requires Authentication**: Bearer token required
    **Access Control**: Can only view own positions unless admin
    """
    # Check authorization: users can only view their own positions
    if current_user != user_id:
        logger.warning(f"User {current_user} tried to access positions for {user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's positions"
        )
    
    positions = []
    state = get_api_state()
    
    if state["sessions"]:
        for session in state["sessions"]:
            if session.user_id == user_id:
                if hasattr(session, 'get_active_trades'):
                    positions = session.get_active_trades()
                break
    
    return PositionsResponse(positions=positions)


# ── Trades Endpoints ────────────────────────────────────────────────────

@app.get("/api/v1/trades", response_model=TradesResponse, tags=["Trades"])
def get_trades(
    current_user: str = Depends(get_current_user),
    user_id: str = None,
    from_date: str = None,
    to_date: str = None,
    limit: int = 100,
    rate_limit: None = Depends(rate_limit_check)
):
    """
    Get trade history.
    
    **Requires Authentication**: Bearer token required
    **Access Control**: Can only view own trades
    """
    from src.persistence.database import get_database
    
    # Check authorization
    if user_id and current_user != user_id:
        logger.warning(f"User {current_user} tried to access trades for {user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's trades"
        )
    
    db = get_database()
    trades = db.get_trades(user_id=user_id or current_user, from_date=from_date, to_date=to_date, limit=limit)
    
    return TradesResponse(trades=trades, total=len(trades))


@app.get("/api/v1/trades/{user_id}", response_model=TradesResponse, tags=["Trades"])
def get_user_trades(
    user_id: str,
    current_user: str = Depends(get_current_user),
    from_date: str = None,
    to_date: str = None,
    limit: int = 50,
    rate_limit: None = Depends(rate_limit_check)
):
    """
    Get trades for a specific user.
    
    **Requires Authentication**: Bearer token required
    **Access Control**: Can only view own trades
    """
    from src.persistence.database import get_database
    
    # Check authorization
    if current_user != user_id:
        logger.warning(f"User {current_user} tried to access trades for {user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's trades"
        )
    
    db = get_database()
    trades = db.get_trades(user_id=user_id, from_date=from_date, to_date=to_date, limit=limit)
    
    return TradesResponse(trades=trades, total=len(trades))


# ── Statistics Endpoints ────────────────────────────────────────────────

@app.get("/api/v1/stats", response_model=StatsResponse, tags=["Stats"])
def get_stats(
    current_user: str = Depends(get_current_user),
    user_id: str = None,
    date: str = None,
    rate_limit: None = Depends(rate_limit_check)
):
    """
    Get trading statistics.
    
    **Requires Authentication**: Bearer token required
    **Access Control**: Can only view own stats
    """
    from src.persistence.database import get_database
    
    # Check authorization
    if user_id and current_user != user_id:
        logger.warning(f"User {current_user} tried to access stats for {user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's statistics"
        )
    
    db = get_database()
    
    # If no user_id specified, use current user
    user_id = user_id or current_user
    stats = db.get_trade_stats(user_id, date)
    
    return StatsResponse(stats=stats)


# ── Control Endpoints ──────────────────────────────────────────────────

@app.post("/api/v1/stop", tags=["Control"])
def stop_bot(
    request: CloseAllRequest,
    current_user: str = Depends(get_current_user),
    rate_limit: None = Depends(rate_limit_check)
):
    """
    Stop the trading bot.
    
    **Requires Authentication**: Bearer token required
    **Security**: Critical operation - only authenticated users can stop the bot
    """
    state = get_api_state()
    if not state["bot_running"]:
        raise HTTPException(status_code=400, detail="Bot is not running")
    
    # Write stop trigger file
    from src.utils.paths import get_path
    stop_file = get_path(".stop_trigger")
    
    try:
        with open(stop_file, "w") as f:
            f.write(f"stop:api:user:{current_user}")
        logger.info(f"Stop signal sent by user: {current_user}")
        return {"success": True, "message": "Stop signal sent"}
    except Exception as e:
        logger.error(f"Failed to stop bot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop: {str(e)}")


@app.post("/api/v1/close-position", response_model=TradeResponse, tags=["Control"])
def close_position(
    request: CloseTradeRequest,
    current_user: str = Depends(get_current_user),
    rate_limit: None = Depends(rate_limit_check)
):
    """
    Close a specific position.
    
    **Requires Authentication**: Bearer token required
    **Access Control**: Can only close own positions
    **Security**: Critical operation
    """
    # Check authorization
    if current_user != request.user_id:
        logger.warning(f"User {current_user} tried to close position for {request.user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot close other user's positions"
        )
    
    state = get_api_state()
    if not state["sessions"]:
        raise HTTPException(status_code=400, detail="No active sessions")
    
    # Find session
    session = None
    for s in state["sessions"]:
        if s.user_id == request.user_id:
            session = s
            break
    
    if not session:
        raise HTTPException(status_code=404, detail="User session not found")
    
    # Close position
    try:
        # Get current LTP
        quote = session.broker.get_quote(request.symbol)
        ltp = quote.get("last_price", 0) if quote else 0
        
        # Find and close in tracker
        for tracker in [getattr(session, 'nifty_tracker', None), getattr(session, 'bn_tracker', None)]:
            if tracker and request.symbol in tracker.active_trades:
                tracker.close_trade(request.symbol, ltp, "API_CLOSE")
                logger.info(f"Position {request.symbol} closed by API user: {current_user}")
                return TradeResponse(
                    success=True,
                    message=f"Position {request.symbol} closed",
                    trade_id=request.symbol
                )
        
        raise HTTPException(status_code=404, detail="Position not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Close position failed for {current_user}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/close-all", response_model=TradeResponse, tags=["Control"])
def close_all_positions(
    request: CloseAllRequest,
    current_user: str = Depends(get_current_user),
    rate_limit: None = Depends(rate_limit_check)
):
    """
    Close all positions for a user.
    
    **Requires Authentication**: Bearer token required
    **Access Control**: Can only close own positions
    **Security**: Critical operation
    """
    # Check authorization
    if current_user != request.user_id:
        logger.warning(f"User {current_user} tried to close all positions for {request.user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot close other user's positions"
        )
    
    state = get_api_state()
    if not state["sessions"]:
        raise HTTPException(status_code=400, detail="No active sessions")
    
    # Find session
    session = None
    for s in state["sessions"]:
        if s.user_id == request.user_id:
            session = s
            break
    
    if not session:
        raise HTTPException(status_code=404, detail="User session not found")
    
    try:
        session.close_all()
        logger.info(f"All positions closed by API user: {current_user}")
        return TradeResponse(
            success=True,
            message=f"All positions closed for {request.user_id}"
        )
    except Exception as e:
        logger.error(f"Close all failed for {current_user}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Config Endpoints ───────────────────────────────────────────────────

@app.get("/api/v1/config", tags=["Config"])
def get_config(
    current_user: str = Depends(get_current_user),
    rate_limit: None = Depends(rate_limit_check)
):
    """
    Get configuration for the current user.
    
    **Requires Authentication**: Bearer token required
    """
    from src.config import Settings, UserManager
    
    user = UserManager.get_user(current_user)
    if user:
        # Load user-specific settings from users.json
        strategy = user.get("strategy", {})
        broker_settings = user.get("broker_settings", {})
        instruments = user.get("instruments", {})
        
        return {
            "market_open": str(Settings.MARKET_OPEN),
            "market_close": str(Settings.MARKET_CLOSE),
            "entry_start": strategy.get("entry_start", str(Settings.ENTRY_START)),
            "entry_end": strategy.get("entry_end", str(Settings.ENTRY_END)),
            "candle_period": broker_settings.get("candle_period", str(Settings.CANDLE_PERIOD_SECONDS)),
            "paper_trading": broker_settings.get("paper_trading", Settings.PAPER_TRADING),
            "nifty_enabled": instruments.get("nifty_enabled", Settings.NIFTY_OPTIONS_STRATEGY),
            "banknifty_enabled": instruments.get("banknifty_enabled", Settings.BANKNIFTY_ENABLED),
            # Operator / User profile fields
            "name": user.get("name", current_user),
            "user_id": user.get("user_id", current_user),
            "broker_type": user.get("broker_type", "MOCK"),
            "active": user.get("active", True),
            "risk_rules": user.get("risk_rules", {
                "total_capital": 100000.0,
                "trade_capital": 100000.0,
                "max_trades_per_day": 5,
                "max_daily_loss": 15000.0,
                "trade_target_rs": 10000.0,
                "trade_sl_rs": 1000.0
            })
        }
        
    # Fallback to global Settings
    return {
        "market_open": str(Settings.MARKET_OPEN),
        "market_close": str(Settings.MARKET_CLOSE),
        "entry_start": str(Settings.ENTRY_START),
        "entry_end": str(Settings.ENTRY_END),
        "candle_period": Settings.CANDLE_PERIOD_SECONDS,
        "paper_trading": Settings.PAPER_TRADING,
        "nifty_enabled": Settings.NIFTY_OPTIONS_STRATEGY,
        "banknifty_enabled": Settings.BANKNIFTY_ENABLED,
        # Fallbacks
        "name": current_user,
        "user_id": current_user,
        "broker_type": "MOCK",
        "active": True,
        "risk_rules": {
            "total_capital": 100000.0,
            "trade_capital": 100000.0,
            "max_trades_per_day": 5,
            "max_daily_loss": 15000.0,
            "trade_target_rs": 10000.0,
            "trade_sl_rs": 1000.0
        }
    }


@app.post("/api/v1/config", tags=["Config"])
def update_config(
    request: ConfigUpdateRequest,
    current_user: str = Depends(get_current_user),
    rate_limit: None = Depends(rate_limit_check)
):
    """
    Update global configuration for the user in users.json.
    
    **Requires Authentication**: Bearer token required
    """
    # Check authorization: users can only update their own config
    if current_user != request.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update other user's configuration"
        )
    
    from src.config import UserManager
    
    # Check if user exists
    user = UserManager.get_user(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build deep merge updates matching users.json schema
    updates = {}
    
    # Operator profile fields
    if "name" in request.settings:
        updates["name"] = request.settings["name"]
    if "broker_type" in request.settings:
        updates["broker_type"] = request.settings["broker_type"].upper()
    if "active" in request.settings:
        updates["active"] = request.settings["active"]
    if "risk_rules" in request.settings:
        updates["risk_rules"] = request.settings["risk_rules"]
    if "password" in request.settings and request.settings["password"].strip():
        from src.utils.security import get_password_hash
        updates["login_password"] = get_password_hash(request.settings["password"].strip())
    
    # Strategy updates
    strategy_updates = {}
    if "entry_start" in request.settings:
        strategy_updates["entry_start"] = request.settings["entry_start"]
    if "entry_end" in request.settings:
        strategy_updates["entry_end"] = request.settings["entry_end"]
    if strategy_updates:
        updates["strategy"] = strategy_updates
        
    # Broker settings updates
    broker_updates = {}
    if "paper_trading" in request.settings:
        broker_updates["paper_trading"] = request.settings["paper_trading"]
    if "candle_period" in request.settings:
        broker_updates["candle_period"] = str(request.settings["candle_period"])
    if broker_updates:
        updates["broker_settings"] = broker_updates
        
    # Instruments updates
    inst_updates = {}
    if "nifty_enabled" in request.settings:
        inst_updates["nifty_enabled"] = request.settings["nifty_enabled"]
    if "banknifty_enabled" in request.settings:
        inst_updates["banknifty_enabled"] = request.settings["banknifty_enabled"]
    if inst_updates:
        updates["instruments"] = inst_updates
        
    success = UserManager.update_user(request.user_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update configuration in users.json")
        
    return {"success": True, "message": "Configuration updated successfully"}


# ── Market Data Endpoints ───────────────────────────────────────────────

@app.get("/api/v1/quote/{symbol}", tags=["Market Data"])
def get_quote(
    symbol: str,
    current_user: str = Depends(get_current_user),
    rate_limit: None = Depends(rate_limit_check)
):
    """
    Get quote for a symbol.
    
    **Requires Authentication**: Bearer token required
    """
    state = get_api_state()
    if not state["data_provider"]:
        raise HTTPException(status_code=503, detail="Data provider not available")
    
    try:
        quote = state["data_provider"].get_quote(symbol)
        if not quote:
            raise HTTPException(status_code=404, detail="Symbol not found")
        return quote
    except Exception as e:
        logger.error(f"Failed to get quote for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Start Server ────────────────────────────────────────────────────────

def start_api_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    ssl_cert: str = None,
    ssl_key: str = None
):
    """
    Start the API server.
    
    Args:
        host: Host to bind to
        port: Port to listen on
        reload: Enable auto-reload (development only)
        ssl_cert: Path to SSL certificate file (PEM)
        ssl_key: Path to SSL private key file (PEM)
    
    Example:
        # HTTP (development)
        start_api_server()
        
        # HTTPS (production with self-signed cert)
        start_api_server(ssl_cert="cert.pem", ssl_key="key.pem")
        
        # HTTPS (production with real cert)
        start_api_server(ssl_cert="/path/to/fullchain.pem", ssl_key="/path/to/privkey.pem")
    """
    import os
    
    ssl_config = {}
    environment = os.getenv("ENVIRONMENT", "development")
    
    if ssl_cert and ssl_key:
        if os.path.exists(ssl_cert) and os.path.exists(ssl_key):
            ssl_config = {
                "ssl_certfile": ssl_cert,
                "ssl_keyfile": ssl_key,
            }
            logger.info(f"Starting API server with HTTPS on {host}:{port}")
        else:
            if environment == "production":
                raise RuntimeError(f"PRODUCTION MODE: SSL cert/key not found at {ssl_cert}, {ssl_key}. HTTPS is required in production!")
            else:
                logger.warning(f"SSL cert/key not found, falling back to HTTP: {ssl_cert}, {ssl_key}")
    elif environment == "production":
        raise RuntimeError("PRODUCTION MODE: No SSL configuration provided. HTTPS is required!")
    
    uvicorn.run(
        "src.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        **ssl_config
    )


if __name__ == "__main__":
    start_api_server()