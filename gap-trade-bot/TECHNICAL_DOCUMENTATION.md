# Technical Documentation - Trading Advisor Web Application

## Table of Contents
1. [System Architecture Overview](#system-architecture-overview)
2. [Backend Architecture](#backend-architecture)
3. [Frontend Architecture](#frontend-architecture)
4. [WebSocket Implementation](#websocket-implementation)
5. [Data Flow Diagrams](#data-flow-diagrams)
6. [Real-time Features](#real-time-features)
7. [API Documentation](#api-documentation)
8. [Database & Caching](#database--caching)
9. [Security Considerations](#security-considerations)
10. [Performance Optimization](#performance-optimization)
11. [Deployment Guide](#deployment-guide)
12. [Troubleshooting Guide](#troubleshooting-guide)

---

## System Architecture Overview

The Trading Advisor Web Application is a **real-time trading dashboard** built with a **hybrid architecture** that combines:

- **Flask Backend** (Python) - REST API + WebSocket server
- **Vue.js Frontend** (JavaScript) - Reactive UI with WebSocket client
- **Polygon API** - Real-time market data
- **WebSocket Technology** - Live price updates
- **Enhanced Polling** - Fallback and system monitoring

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRADING ADVISOR SYSTEM                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │   FRONTEND      │    │    BACKEND      │    │  EXTERNAL   │ │
│  │   (Vue.js)      │◄──►│   (Flask)       │◄──►│    APIs     │ │
│  │                 │    │                 │    │             │ │
│  │ • WebSocket     │    │ • REST API      │    │ • Polygon   │ │
│  │   Client        │    │ • WebSocket     │    │ • Market    │ │
│  │ • Real-time UI  │    │   Server        │    │   Data      │ │
│  │ • Live Updates  │    │ • Price Thread  │    │ • Gap-ups   │ │
│  │ • Charts        │    │ • Gap Detection │    │ • Real-time │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
│           │                       │                            │
│           │                       │                            │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │   BROWSER       │    │   BACKGROUND    │                   │
│  │   STORAGE       │    │   THREADS       │                   │
│  │                 │    │                 │                   │
│  │ • Local Cache   │    │ • Price Updates │                   │
│  │ • Session Data  │    │ • Gap Detection │                   │
│  │ • User Prefs    │    │ • WebSocket     │                   │
│  └─────────────────┘    └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Backend Architecture

### Flask Application Structure

```
backend/
├── app.py                 # Main Flask application
├── gap_up_detector.py     # Polygon API integration
├── config.py             # Configuration settings
├── requirements.txt       # Python dependencies
└── .env                  # Environment variables
```

### Backend Components

#### 1. Flask-SocketIO Server
```python
# Core Flask setup with WebSocket support
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
```

**Key Features:**
- **REST API Endpoints** - HTTP-based data retrieval
- **WebSocket Server** - Real-time bidirectional communication
- **CORS Support** - Cross-origin resource sharing
- **Async Mode** - Threading for concurrent connections

#### 2. Real-time Price Update System

```python
def start_price_update_thread():
    """Background thread for real-time price updates"""
    def price_update_worker():
        while True:
            if active_stocks and REAL_DATA_AVAILABLE:
                for ticker in active_stocks:
                    current_price = get_current_price(ticker, polygon_client)
                    if current_price is not None:
                        # Calculate price changes
                        previous_price = price_cache.get(ticker, current_price)
                        change = current_price - previous_price
                        change_percent = (change / previous_price) * 100
                        
                        # Broadcast to all clients
                        broadcast_price_update(ticker, {
                            'price': round(current_price, 2),
                            'change': round(change, 2),
                            'change_percent': round(change_percent, 2)
                        })
                        
                        # Update cache
                        price_cache[ticker] = current_price
            time.sleep(1)  # Update every second
```

**Architecture Diagram:**

```
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────┐ │
│  │   FLASK APP     │    │  WEBSOCKET      │    │  THREAD │ │
│  │                 │    │   SERVER        │    │  POOL   │ │
│  │ • REST API      │◄──►│ • Socket.IO     │◄──►│ • Price │ │
│  │ • Routes        │    │ • Events        │    │   Updates│ │
│  │ • Endpoints     │    │ • Broadcasting  │    │ • Gap    │ │
│  │ • CORS          │    │ • Connections   │    │   Detection│ │
│  └─────────────────┘    └─────────────────┘    └─────────┘ │
│           │                       │                        │
│           │                       │                        │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────┐ │
│  │   POLYGON API   │    │   CACHE SYSTEM  │    │  GLOBAL │ │
│  │   INTEGRATION   │    │                 │    │  STATE  │ │
│  │                 │    │ • Price Cache   │    │         │ │
│  │ • REST Client   │    │ • Stock Data    │    │ • Active│ │
│  │ • Real-time     │    │ • Market Data   │    │   Stocks│ │
│  │   Data          │    │ • Session Info  │    │ • Config│ │
│  └─────────────────┘    └─────────────────┘    └─────────┘ │
└─────────────────────────────────────────────────────────────┘
```

#### 3. Gap-Up Detection Engine

```python
def get_gap_up_stocks():
    """Real-time gap-up stock detection"""
    try:
        polygon_client = get_polygon_client()
        
        # Get current gainers
        tickers = polygon_client.get_snapshot_direction("stocks", direction="gainers")
        
        gap_up_stocks = []
        for item in tickers:
            ticker = extract_ticker(item)
            if ticker:
                details = polygon_client.get_ticker_details(ticker)
                
                # Filter for common stocks with $1+ price
                if details.type == "CS":
                    previous_close = get_previous_close_price(ticker, polygon_client)
                    current_price = get_current_price(ticker, polygon_client)
                    
                    if previous_close >= 1:
                        gap_percent = ((current_price - previous_close) / previous_close) * 100
                        
                        # Only include 2%+ gaps
                        if gap_percent >= 2:
                            stock_info = {
                                'ticker': ticker,
                                'company_name': details.name,
                                'price': round(current_price, 2),
                                'change': round(current_price - previous_close, 2),
                                'change_percent': round(gap_percent, 2),
                                'gap_percent': round(gap_percent, 2),
                                'volume': getattr(details, 'volume', 0),
                                'market_cap': getattr(details, 'market_cap', 'N/A'),
                                'sector': getattr(details, 'sic_description', 'N/A')
                            }
                            gap_up_stocks.append(stock_info)
        
        return gap_up_stocks
    except Exception as e:
        print(f"Error in get_gap_up_stocks: {e}")
        return []
```

---

## Frontend Architecture

### Vue.js Application Structure

```
frontend/
├── index.html          # Main HTML template
├── app.js             # Vue.js application logic
└── styles.css         # Custom styling
```

### Frontend Components

#### 1. Vue.js Application Setup

```javascript
const { createApp } = Vue;

createApp({
    data() {
        return {
            // Dashboard data
            stats: { totalTrades: 0, winRate: 0, totalPnl: 0 },
            gapUps: [],
            trades: [],
            
            // WebSocket connection
            socket: null,
            socketConnected: false,
            subscribedStocks: new Set(),
            livePrices: {},
            
            // UI state
            activeTab: 'dashboard',
            loading: { stats: false, gapUps: false, trades: false },
            
            // System status
            systemStatus: {
                connected: false,
                realDataAvailable: false,
                websocketConnected: false
            }
        }
    },
    
    mounted() {
        this.initializeApp();
    }
}).mount('#app');
```

#### 2. WebSocket Client Implementation

```javascript
initializeSocket() {
    if (typeof io === 'undefined') {
        console.error('Socket.IO not loaded');
        return;
    }
    
    this.socket = io('http://localhost:5000');
    
    // Connection events
    this.socket.on('connect', () => {
        console.log('Connected to WebSocket server');
        this.socketConnected = true;
        this.systemStatus.websocketConnected = true;
        
        // Auto-subscribe to gap-up stocks
        if (this.gapUps.length > 0) {
            const tickers = this.gapUps.map(stock => stock.ticker);
            this.subscribeToStocks(tickers);
        }
    });
    
    // Price update events
    this.socket.on('price_update', (data) => {
        this.handlePriceUpdate(data);
    });
    
    // Subscription events
    this.socket.on('subscribed', (data) => {
        data.stocks.forEach(ticker => this.subscribedStocks.add(ticker));
    });
}
```

#### 3. Real-time UI Updates

```javascript
handlePriceUpdate(data) {
    const { ticker, data: priceData } = data;
    
    // Update live prices
    this.livePrices[ticker] = priceData;
    
    // Update gap-up stocks display
    const stockIndex = this.gapUps.findIndex(stock => stock.ticker === ticker);
    if (stockIndex !== -1) {
        this.gapUps[stockIndex] = {
            ...this.gapUps[stockIndex],
            price: priceData.price,
            change: priceData.change,
            change_percent: priceData.change_percent
        };
    }
}
```

**Frontend Architecture Diagram:**

```
┌─────────────────────────────────────────────────────────────┐
│                   FRONTEND ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────┐
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────┐ │
│  │   VUE.JS APP    │    │  WEBSOCKET      │    │   UI    │ │
│  │                 │    │   CLIENT        │    │ COMPONENTS│ │
│  │ • Reactive Data │◄──►│ • Socket.IO     │◄──►│ • Cards │ │
│  │ • State Mgmt    │    │ • Events        │    │ • Charts│ │
│  │ • Lifecycle     │    │ • Subscriptions │    │ • Tables│ │
│  │ • Methods       │    │ • Reconnection  │    │ • Forms │ │
│  └─────────────────┘    └─────────────────┘    └─────────┘ │
│           │                       │                        │
│           │                       │                        │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────┐ │
│  │   HTTP CLIENT   │    │   LOCAL STORAGE │    │  STYLING│ │
│  │                 │    │                 │    │         │ │
│  │ • Fetch API     │    │ • Cache         │    │ • CSS   │ │
│  │ • REST Calls    │    │ • Session Data  │    │ • Tailwind│ │
│  │ • Error Handling│    │ • User Prefs    │    │ • Custom│ │
│  └─────────────────┘    └─────────────────┘    └─────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## WebSocket Implementation

### WebSocket Technology Stack

- **Backend**: Flask-SocketIO with threading
- **Frontend**: Socket.IO client library
- **Protocol**: WebSocket over HTTP upgrade
- **Transport**: Long polling fallback

### WebSocket Event Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   CLIENT    │    │   SERVER    │    │  EXTERNAL   │
│  (Browser)  │    │  (Flask)    │    │    API      │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       │ 1. Connect        │                   │
       │──────────────────►│                   │
       │                   │                   │
       │ 2. Subscribe      │                   │
       │──────────────────►│                   │
       │                   │ 3. Fetch Data     │
       │                   │──────────────────►│
       │                   │                   │
       │                   │ 4. Price Updates  │
       │                   │◄──────────────────│
       │                   │                   │
       │ 5. Broadcast      │                   │
       │◄──────────────────│                   │
       │                   │                   │
       │ 6. UI Update      │                   │
       │ (Vue.js)          │                   │
       │                   │                   │
```

### WebSocket Events

#### Backend Events (Flask-SocketIO)

```python
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f"Client connected: {request.sid}")
    emit('connected', {'status': 'connected', 'timestamp': datetime.now().isoformat()})

@socketio.on('subscribe_stocks')
def handle_subscribe_stocks(data):
    """Subscribe to real-time updates for specific stocks"""
    global active_stocks
    stocks = data.get('stocks', [])
    active_stocks.update(stocks)
    print(f"Subscribed to stocks: {stocks}")
    emit('subscribed', {'stocks': list(active_stocks)})

def broadcast_price_update(ticker, price_data):
    """Broadcast price update to all connected clients"""
    socketio.emit('price_update', {
        'ticker': ticker,
        'data': price_data,
        'timestamp': datetime.now().isoformat()
    })
```

#### Frontend Events (Socket.IO Client)

```javascript
// Connection events
socket.on('connect', () => {
    this.socketConnected = true;
    this.systemStatus.websocketConnected = true;
});

socket.on('disconnect', () => {
    this.socketConnected = false;
    this.systemStatus.websocketConnected = false;
});

// Data events
socket.on('price_update', (data) => {
    this.handlePriceUpdate(data);
});

socket.on('subscribed', (data) => {
    data.stocks.forEach(ticker => this.subscribedStocks.add(ticker));
});

// Emit events
socket.emit('subscribe_stocks', { stocks: tickers });
socket.emit('unsubscribe_stocks', { stocks: tickers });
```

---

## Data Flow Diagrams

### 1. Application Startup Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   BROWSER   │    │   BACKEND   │    │  POLYGON    │
│             │    │             │    │     API     │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       │ 1. Load Page      │                   │
       │──────────────────►│                   │
       │                   │                   │
       │ 2. Initialize     │                   │
       │    Vue.js         │                   │
       │                   │                   │
       │ 3. Connect        │                   │
       │    WebSocket      │                   │
       │──────────────────►│                   │
       │                   │ 4. Start Price    │
       │                   │    Thread         │
       │                   │──────────────────►│
       │                   │                   │
       │ 5. Load Initial   │                   │
       │    Data           │                   │
       │──────────────────►│                   │
       │                   │ 6. Fetch Gap-ups  │
       │                   │──────────────────►│
       │                   │                   │
       │ 7. Return Data    │                   │
       │◄──────────────────│◄──────────────────│
       │                   │                   │
       │ 8. Subscribe to   │                   │
       │    Stocks         │                   │
       │──────────────────►│                   │
```

### 2. Real-time Price Update Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   FRONTEND  │    │   BACKEND   │    │  POLYGON    │
│             │    │             │    │     API     │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       │                   │ 1. Price Thread   │
       │                   │    (Every 1s)     │
       │                   │──────────────────►│
       │                   │                   │
       │                   │ 2. Get Current    │
       │                   │    Prices         │
       │                   │◄──────────────────│
       │                   │                   │
       │                   │ 3. Calculate      │
       │                   │    Changes        │
       │                   │                   │
       │ 4. Broadcast      │                   │
       │◄──────────────────│                   │
       │                   │                   │
       │ 5. Update UI      │                   │
       │    (Vue.js)       │                   │
       │                   │                   │
```

### 3. Gap-up Detection Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   FRONTEND  │    │   BACKEND   │    │  POLYGON    │
│             │    │             │    │     API     │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       │ 1. Request        │                   │
       │    Gap-ups        │                   │
       │──────────────────►│                   │
       │                   │ 2. Get Gainers    │
       │                   │──────────────────►│
       │                   │                   │
       │                   │ 3. Filter Stocks  │
       │                   │    (CS, $1+)      │
       │                   │                   │
       │                   │ 4. Calculate      │
       │                   │    Gaps           │
       │                   │                   │
       │                   │ 5. Return         │
       │                   │    Results        │
       │◄──────────────────│◄──────────────────│
       │                   │                   │
       │ 6. Auto-subscribe │                   │
       │    to Stocks      │                   │
       │──────────────────►│                   │
```

---

## Real-time Features

### 1. Live Price Updates

**Frequency**: Every 1 second for subscribed stocks
**Technology**: WebSocket with fallback to polling
**Data**: Price, change, change percentage, volume

```javascript
// Real-time price display
<div class="text-2xl font-bold" :class="getPriceColor(stock)">
    ${{ stock.price }}
    <span v-if="livePrices[stock.ticker]" class="text-sm ml-1" 
          :class="getPriceChangeColor(livePrices[stock.ticker].change_percent)">
        {{ livePrices[stock.ticker].change_percent >= 0 ? '+' : '' }}{{ livePrices[stock.ticker].change_percent.toFixed(2) }}%
    </span>
</div>
```

### 2. Enhanced Polling System

**System Status**: Every 30 seconds
**Gap-ups Data**: Every 30 seconds
**Dashboard Data**: Every 5 minutes

```javascript
startPeriodicUpdates() {
    // Update system status every 30 seconds
    setInterval(() => {
        this.checkSystemStatus();
    }, 30000);
    
    // Update dashboard data every 5 minutes
    setInterval(() => {
        this.loadDashboardData();
    }, 300000);
    
    // Enhanced polling for gap-ups every 30 seconds
    setInterval(() => {
        this.loadGapUps();
    }, 30000);
}
```

### 3. Smart Subscriptions

**Automatic**: Subscribe to gap-up stocks when detected
**Dynamic**: Add/remove stocks based on user activity
**Efficient**: Only track active stocks

```javascript
subscribeToStocks(tickers) {
    if (this.socket && this.socketConnected) {
        this.socket.emit('subscribe_stocks', { stocks: tickers });
    }
}

// Auto-subscribe when gap-ups are loaded
if (this.socketConnected && data.data.length > 0) {
    const tickers = data.data.map(stock => stock.ticker);
    this.subscribeToStocks(tickers);
}
```

---

## API Documentation

### REST API Endpoints

#### Health Check
```http
GET /api/health
```
**Response:**
```json
{
    "status": "healthy",
    "timestamp": "2025-07-29T17:30:00.000Z",
    "version": "1.0.0",
    "real_data_available": true,
    "websocket_connected": true,
    "active_stocks_count": 7
}
```

#### Gap-up Stocks
```http
GET /api/gap-ups
```
**Response:**
```json
{
    "success": true,
    "data": [
        {
            "ticker": "NEGG",
            "company_name": "Newegg Commerce Inc",
            "price": 56.19,
            "change": 17.19,
            "change_percent": 44.06,
            "gap_percent": 43.78,
            "volume": 1234567,
            "market_cap": "2.5B",
            "sector": "Consumer Electronics",
            "list_date": "2020-09-18"
        }
    ],
    "timestamp": "2025-07-29T17:30:00.000Z",
    "source": "real"
}
```

#### Trade History
```http
GET /api/trades
```
**Response:**
```json
{
    "success": true,
    "trades": [...],
    "summary": {
        "total_trades": 3,
        "winning_trades": 2,
        "losing_trades": 1,
        "total_pnl": 1087.50,
        "win_rate": 66.67
    }
}
```

### WebSocket Events

#### Client to Server
```javascript
// Subscribe to stocks
socket.emit('subscribe_stocks', { stocks: ['AAPL', 'TSLA'] });

// Unsubscribe from stocks
socket.emit('unsubscribe_stocks', { stocks: ['AAPL'] });
```

#### Server to Client
```javascript
// Price update
socket.on('price_update', {
    ticker: 'AAPL',
    data: {
        price: 150.25,
        change: 2.50,
        change_percent: 1.67,
        volume: 1000000
    },
    timestamp: '2025-07-29T17:30:00.000Z'
});

// Subscription confirmation
socket.on('subscribed', { stocks: ['AAPL', 'TSLA'] });
```

---

## Database & Caching

### In-Memory Caching System

```python
# Global variables for real-time data
active_stocks = set()        # Currently subscribed stocks
price_cache = {}            # Price history cache
websocket_connected = False  # Connection status
```

### Cache Management

```python
def update_price_cache(ticker, price_data):
    """Update price cache with new data"""
    price_cache[ticker] = price_data['price']
    price_cache[f"{ticker}_change"] = price_data['change']
    price_cache[f"{ticker}_change_percent"] = price_data['change_percent']
    price_cache[f"{ticker}_volume"] = price_data.get('volume', 0)

def get_cached_price(ticker):
    """Get cached price data"""
    return {
        'price': price_cache.get(ticker),
        'change': price_cache.get(f"{ticker}_change"),
        'change_percent': price_cache.get(f"{ticker}_change_percent"),
        'volume': price_cache.get(f"{ticker}_volume")
    }
```

### Frontend Caching

```javascript
// Local storage for user preferences
localStorage.setItem('user_preferences', JSON.stringify({
    refreshInterval: 30000,
    autoSubscribe: true,
    theme: 'dark'
}));

// Session storage for temporary data
sessionStorage.setItem('last_gap_ups', JSON.stringify(gapUps));
```

---

## Security Considerations

### 1. API Key Management

```python
# Environment variable loading
from dotenv import load_dotenv
load_dotenv()

# Secure API key access
api_key = os.environ.get('POLYGON_API_KEY')
if not api_key:
    # Fallback to default key (development only)
    api_key = "default_key_for_development"
```

### 2. CORS Configuration

```python
# CORS setup for frontend communication
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"])
```

### 3. WebSocket Security

```python
# WebSocket connection validation
@socketio.on('connect')
def handle_connect():
    # Validate client connection
    client_ip = request.remote_addr
    print(f"Client connected from: {client_ip}")
    
    # Rate limiting could be added here
    emit('connected', {'status': 'connected'})
```

### 4. Input Validation

```python
@app.route('/api/analyze', methods=['POST'])
def analyze_stocks():
    try:
        data = request.get_json()
        tickers = data.get('tickers', [])
        
        # Validate input
        if not tickers or not isinstance(tickers, list):
            return jsonify({'success': False, 'error': 'Invalid tickers'}), 400
        
        # Sanitize ticker symbols
        sanitized_tickers = [ticker.upper().strip() for ticker in tickers if ticker]
        
        # Process analysis
        analysis = []
        for ticker in sanitized_tickers:
            # ... analysis logic
            pass
        
        return jsonify({'success': True, 'data': analysis})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

---

## Performance Optimization

### 1. Backend Optimizations

#### Threading for Price Updates
```python
def start_price_update_thread():
    """Start background thread for price updates"""
    thread = threading.Thread(target=price_update_worker, daemon=True)
    thread.start()
    print("✅ Real-time price update thread started")
```

#### Efficient Caching
```python
# Use sets for O(1) lookup
active_stocks = set()

# Cache frequently accessed data
price_cache = {}
market_data_cache = {}
```

#### Connection Pooling
```python
# Reuse Polygon client
polygon_client = None

def get_polygon_client():
    global polygon_client
    if polygon_client is None:
        api_key = os.environ.get('POLYGON_API_KEY')
        polygon_client = RESTClient(api_key)
    return polygon_client
```

### 2. Frontend Optimizations

#### Debounced Updates
```javascript
// Debounce frequent updates
let updateTimeout;
function debouncedUpdate(data) {
    clearTimeout(updateTimeout);
    updateTimeout = setTimeout(() => {
        this.updateUI(data);
    }, 100);
}
```

#### Efficient DOM Updates
```javascript
// Use Vue.js reactivity for efficient updates
this.gapUps = this.gapUps.map(stock => {
    if (stock.ticker === ticker) {
        return { ...stock, ...priceData };
    }
    return stock;
});
```

#### Memory Management
```javascript
// Clean up subscriptions on component unmount
beforeUnmount() {
    if (this.socket) {
        this.socket.disconnect();
    }
    clearInterval(this.updateIntervals);
}
```

### 3. Network Optimizations

#### WebSocket Compression
```python
# Enable compression for WebSocket messages
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', compress=True)
```

#### Efficient Data Transfer
```python
# Minimize data payload
def broadcast_price_update(ticker, price_data):
    socketio.emit('price_update', {
        't': ticker,  # Shortened key
        'p': price_data['price'],
        'c': price_data['change'],
        'cp': price_data['change_percent']
    })
```

---

## Deployment Guide

### 1. Production Setup

#### Environment Configuration
```bash
# Create production environment file
cat > .env << EOF
FLASK_ENV=production
SECRET_KEY=your-secure-secret-key
POLYGON_API_KEY=your-production-api-key
DATABASE_URL=your-database-url
EOF
```

#### WebSocket Production Server
```python
# Use production WSGI server
if __name__ == '__main__':
    socketio.run(app, 
                host='0.0.0.0', 
                port=5000, 
                debug=False,
                use_reloader=False)
```

### 2. Docker Deployment

#### Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

EXPOSE 5000 3000

CMD ["python", "backend/app.py"]
```

#### Docker Compose
```yaml
version: '3.8'
services:
  backend:
    build: .
    ports:
      - "5000:5000"
    environment:
      - POLYGON_API_KEY=${POLYGON_API_KEY}
    volumes:
      - ./backend:/app/backend
  
  frontend:
    image: nginx:alpine
    ports:
      - "3000:80"
    volumes:
      - ./frontend:/usr/share/nginx/html
```

### 3. Cloud Deployment

#### Heroku
```bash
# Create Procfile
echo "web: python backend/app.py" > Procfile

# Deploy to Heroku
heroku create trading-advisor-app
heroku config:set POLYGON_API_KEY=your-api-key
git push heroku main
```

#### AWS EC2
```bash
# Install dependencies
sudo apt update
sudo apt install python3-pip nginx

# Setup application
pip3 install -r backend/requirements.txt

# Configure nginx
sudo nano /etc/nginx/sites-available/trading-advisor
```

---

## Troubleshooting Guide

### 1. WebSocket Connection Issues

#### Check Connection Status
```javascript
// Browser console
console.log('Socket connected:', this.socketConnected);
console.log('WebSocket URL:', this.socket?.io?.uri);
```

#### Backend Logs
```bash
# Check WebSocket server logs
tail -f backend/app.log | grep -i websocket
```

#### Network Testing
```bash
# Test WebSocket endpoint
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Version: 13" \
     -H "Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==" \
     http://localhost:5000/socket.io/
```

### 2. API Issues

#### Polygon API Problems
```python
# Test API connection
def test_polygon_connection():
    try:
        client = get_polygon_client()
        response = client.get_ticker_details("AAPL")
        print("✅ Polygon API connection successful")
        return True
    except Exception as e:
        print(f"❌ Polygon API error: {e}")
        return False
```

#### Rate Limiting
```python
# Implement rate limiting
from functools import wraps
import time

def rate_limit(calls=60, period=60):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Rate limiting logic
            return f(*args, **kwargs)
        return wrapped
    return decorator
```

### 3. Performance Issues

#### Memory Leaks
```python
# Monitor memory usage
import psutil
import os

def log_memory_usage():
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    print(f"Memory usage: {memory_info.rss / 1024 / 1024:.2f} MB")
```

#### CPU Usage
```bash
# Monitor CPU usage
top -p $(pgrep -f "python.*app.py")
```

### 4. Common Error Solutions

#### Port Already in Use
```bash
# Find and kill process using port
lsof -ti:5000 | xargs kill -9
lsof -ti:3000 | xargs kill -9
```

#### Module Import Errors
```bash
# Reinstall dependencies
pip uninstall -r backend/requirements.txt
pip install -r backend/requirements.txt
```

#### CORS Errors
```python
# Update CORS configuration
CORS(app, origins=["*"], methods=["GET", "POST", "OPTIONS"])
```

---

## Conclusion

The Trading Advisor Web Application implements a sophisticated real-time trading dashboard with:

- **Hybrid Architecture**: WebSocket + Enhanced Polling + Fallback
- **Real-time Updates**: Every 1 second for subscribed stocks
- **Live Gap-up Detection**: Real market data from Polygon API
- **Responsive UI**: Vue.js with real-time indicators
- **Scalable Backend**: Flask with threading and caching
- **Production Ready**: Security, performance, and deployment considerations

The system provides a robust foundation for real-time trading applications with comprehensive error handling, performance optimization, and deployment strategies.

---

*This documentation should be updated as the application evolves and new features are added.* 