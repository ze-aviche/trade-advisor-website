# Architecture Diagrams - Trading Advisor Web Application

## 1. System Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           TRADING ADVISOR SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────────┐ │
│  │   FRONTEND      │    │    BACKEND      │    │        EXTERNAL             │ │
│  │   (Vue.js)      │◄──►│   (Flask)       │◄──►│         APIs                │ │
│  │                 │    │                 │    │                             │ │
│  │ • WebSocket     │    │ • REST API      │    │ • Polygon API               │ │
│  │   Client        │    │ • WebSocket     │    │ • Market Data               │ │
│  │ • Real-time UI  │    │   Server        │    │ • Gap-up Detection          │ │
│  │ • Live Updates  │    │ • Price Thread  │    │ • Real-time Feeds           │ │
│  │ • Charts        │    │ • Gap Detection │    │ • Historical Data           │ │
│  │ • Responsive    │    │ • Caching       │    │ • Company Info              │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────────┘ │
│           │                       │                                             │
│           │                       │                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────────┐ │
│  │   BROWSER       │    │   BACKGROUND    │    │        STORAGE              │ │
│  │   STORAGE       │    │   THREADS       │    │                             │ │
│  │                 │    │                 │    │ • Local Cache               │ │
│  │ • Local Cache   │    │ • Price Updates │    │ • Session Data              │ │
│  │ • Session Data  │    │ • Gap Detection │    │ • User Preferences          │ │
│  │ • User Prefs    │    │ • WebSocket     │    │ • Real-time Cache           │ │
│  │ • Real-time     │    │   Broadcasting  │    │ • Price History             │ │
│  │   Cache         │    │ • Error Handling│    │ • Stock Subscriptions       │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 2. WebSocket Communication Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   CLIENT    │    │   SERVER    │    │  EXTERNAL   │    │   CACHE     │
│  (Browser)  │    │  (Flask)    │    │    API      │    │   SYSTEM    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       │ 1. Connect        │                   │                   │
       │──────────────────►│                   │                   │
       │                   │                   │                   │
       │ 2. Subscribe      │                   │                   │
       │──────────────────►│                   │                   │
       │                   │ 3. Fetch Data     │                   │
       │                   │──────────────────►│                   │
       │                   │                   │                   │
       │                   │ 4. Cache Data     │                   │
       │                   │──────────────────►│                   │
       │                   │                   │                   │
       │                   │ 5. Price Updates  │                   │
       │                   │◄──────────────────│                   │
       │                   │                   │                   │
       │ 6. Broadcast      │                   │                   │
       │◄──────────────────│                   │                   │
       │                   │                   │                   │
       │ 7. Update UI      │                   │                   │
       │ (Vue.js)          │                   │                   │
       │                   │                   │                   │
```

## 3. Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────────┐ │
│  │   USER INPUT    │    │   FRONTEND      │    │        BACKEND              │ │
│  │                 │    │   PROCESSING    │    │        PROCESSING           │ │
│  │ • Stock Search  │───►│ • Vue.js        │───►│ • Flask Routes              │ │
│  │ • Refresh Data  │    │ • WebSocket     │    │ • WebSocket Events          │ │
│  │ • Analyze Stock │    │ • HTTP Client   │    │ • Polygon API Calls         │ │
│  │ • Chat Message  │    │ • State Mgmt    │    │ • Gap Detection             │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────────┘ │
│           │                       │                                             │
│           │                       │                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────────┐ │
│  │   REAL-TIME     │    │   CACHING       │    │        EXTERNAL             │ │
│  │   UPDATES       │    │   SYSTEM        │    │        DATA SOURCES         │ │
│  │                 │    │                 │    │                             │ │
│  │ • Price Updates │◄───│ • Price Cache   │◄───│ • Polygon Market Data       │ │
│  │ • Live Charts   │    │ • Stock Cache   │    │ • Real-time Feeds           │ │
│  │ • Notifications │    │ • Session Cache │    │ • Historical Data           │ │
│  │ • Status Alerts │    │ • User Cache    │    │ • Company Information       │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 4. Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           COMPONENT INTERACTIONS                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   VUE.JS    │    │  WEBSOCKET  │    │   FLASK     │    │  POLYGON    │     │
│  │   APP       │◄──►│   CLIENT    │◄──►│   SERVER    │◄──►│    API      │     │
│  │             │    │             │    │             │    │             │     │
│  │ • Components│    │ • Events    │    │ • Routes    │    │ • Market    │     │
│  │ • State     │    │ • Messages  │    │ • Handlers  │    │   Data      │     │
│  │ • Methods   │    │ • Connection│    │ • Threading │    │ • Real-time │     │
│  │ • Lifecycle │    │ • Reconnect │    │ • Caching   │    │ • Historical│     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
│           │                   │                   │                   │         │
│           │                   │                   │                   │         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   BROWSER   │    │   STORAGE   │    │  THREADING  │    │   CACHING   │     │
│  │   STORAGE   │    │   SYSTEM    │    │   SYSTEM    │    │   SYSTEM    │     │
│  │             │    │             │    │             │    │             │     │
│  │ • Local     │    │ • Session   │    │ • Price     │    │ • Memory    │     │
│  │   Storage   │    │   Storage   │    │   Updates   │    │   Cache     │     │
│  │ • IndexedDB │    │ • Cookies   │    │ • Gap       │    │ • Redis     │     │
│  │ • Cache API │    │ • Local     │    │   Detection │    │ • Database  │     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 5. Real-time Update Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            REAL-TIME UPDATE FLOW                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   FRONTEND  │    │   BACKEND   │    │  POLYGON    │    │   CACHE     │     │
│  │             │    │             │    │    API      │    │   SYSTEM    │     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
│           │                   │                   │                   │         │
│           │                   │ 1. Price Thread   │                   │         │
│           │                   │    (Every 1s)     │                   │         │
│           │                   │──────────────────►│                   │         │
│           │                   │                   │                   │         │
│           │                   │ 2. Get Current    │                   │         │
│           │                   │    Prices         │                   │         │
│           │                   │◄──────────────────│                   │         │
│           │                   │                   │                   │         │
│           │                   │ 3. Calculate      │                   │         │
│           │                   │    Changes        │                   │         │
│           │                   │──────────────────►│                   │         │
│           │                   │                   │                   │         │
│           │ 4. Broadcast      │                   │                   │         │
│           │◄──────────────────│                   │                   │         │
│           │                   │                   │                   │         │
│           │ 5. Update UI      │                   │                   │         │
│           │    (Vue.js)       │                   │                   │         │
│           │                   │                   │                   │         │
```

## 6. Gap-up Detection Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           GAP-UP DETECTION FLOW                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   FRONTEND  │    │   BACKEND   │    │  POLYGON    │    │   FILTERING │     │
│  │             │    │             │    │    API      │    │   SYSTEM    │     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
│           │                   │                   │                   │         │
│           │ 1. Request        │                   │                   │         │
│           │    Gap-ups        │                   │                   │         │
│           │──────────────────►│                   │                   │         │
│           │                   │ 2. Get Gainers    │                   │         │
│           │                   │──────────────────►│                   │         │
│           │                   │                   │                   │         │
│           │                   │ 3. Filter Stocks  │                   │         │
│           │                   │    (CS, $1+)      │                   │         │
│           │                   │──────────────────►│                   │         │
│           │                   │                   │                   │         │
│           │                   │ 4. Calculate      │                   │         │
│           │                   │    Gaps           │                   │         │
│           │                   │                   │                   │         │
│           │                   │ 5. Return         │                   │         │
│           │                   │    Results        │                   │         │
│           │◄──────────────────│◄──────────────────│                   │         │
│           │                   │                   │                   │         │
│           │ 6. Auto-subscribe │                   │                   │         │
│           │    to Stocks      │                   │                   │         │
│           │──────────────────►│                   │                   │         │
```

## 7. Security Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            SECURITY ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   CLIENT    │    │   GATEWAY   │    │   BACKEND   │    │   EXTERNAL  │     │
│  │   SECURITY  │    │   SECURITY  │    │   SECURITY  │    │    API      │     │
│  │             │    │             │    │             │    │   SECURITY  │     │
│  │ • HTTPS     │    │ • CORS      │    │ • API Key   │    │ • Rate      │     │
│  │ • CSP       │    │ • Rate      │    │   Mgmt      │    │   Limiting  │     │
│  │ • XSS       │    │   Limiting  │    │ • Input     │    │ • Auth      │     │
│  │   Protection│    │ • Validation│    │   Validation│    │ • SSL/TLS   │     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
│           │                   │                   │                   │         │
│           │                   │                   │                   │         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   DATA      │    │   NETWORK   │    │   ACCESS    │    │   AUDIT     │     │
│  │   SECURITY  │    │   SECURITY  │    │   CONTROL   │    │   LOGGING   │     │
│  │             │    │             │    │             │    │             │     │
│  │ • Encryption│    │ • Firewall  │    │ • Auth      │    │ • Logs      │     │
│  │ • Hashing   │    │ • VPN       │    │ • AuthZ     │    │ • Monitoring│     │
│  │ • Sanitize  │    │ • SSL/TLS   │    │ • Sessions  │    │ • Alerts    │     │
│  │ • Validate  │    │ • DDoS      │    │ • Tokens    │    │ • Reports   │     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 8. Performance Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PERFORMANCE ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   FRONTEND  │    │   BACKEND   │    │   CACHING   │    │   DATABASE  │     │
│  │   OPTIMIZ.  │    │   OPTIMIZ.  │    │   SYSTEM    │    │   OPTIMIZ.  │     │
│  │             │    │             │    │             │    │             │     │
│  │ • Debouncing│    │ • Threading │    │ • Memory    │    │ • Indexing  │     │
│  │ • Lazy Load │    │ • Async     │    │   Cache     │    │ • Query     │     │
│  │ • Code Split│    │ • Pooling   │    │ • Redis     │    │   Optimiz.  │     │
│  │ • Minify    │    │ • Compression│   │ • CDN       │    │ • Connection│     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
│           │                   │                   │                   │         │
│           │                   │                   │                   │         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   NETWORK   │    │   MEMORY    │    │   CPU       │    │   STORAGE   │     │
│  │   OPTIMIZ.  │    │   OPTIMIZ.  │    │   OPTIMIZ.  │    │   OPTIMIZ.  │     │
│  │             │    │             │    │             │    │             │     │
│  │ • CDN       │    │ • Garbage   │    │ • Multi-    │    │ • SSD       │     │
│  │ • Compression│   │   Collection│    │   Threading │    │ • RAID      │     │
│  │ • HTTP/2    │    │ • Memory    │    │ • Load      │    │ • Backup    │     │
│  │ • WebSocket │    │   Pooling   │    │   Balancing │    │ • Archival  │     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 9. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            DEPLOYMENT ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   LOAD      │    │   WEB       │    │   APP       │    │   DATABASE  │     │
│  │   BALANCER  │    │   SERVER    │    │   SERVER    │    │   SERVER    │     │
│  │             │    │             │    │             │    │             │     │
│  │ • Nginx     │    │ • Nginx     │    │ • Flask     │    │ • PostgreSQL│     │
│  │ • HAProxy   │    │ • Apache    │    │ • Gunicorn  │    │ • Redis     │     │
│  │ • Cloud     │    │ • CDN       │    │ • uWSGI     │    │ • MongoDB   │     │
│  │   Load Bal. │    │ • SSL       │    │ • Docker    │    │ • Elastic   │     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
│           │                   │                   │                   │         │
│           │                   │                   │                   │         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   MONITORING│    │   LOGGING   │    │   BACKUP    │    │   SECURITY  │     │
│  │   SYSTEM    │    │   SYSTEM    │    │   SYSTEM    │    │   SYSTEM    │     │
│  │             │    │             │    │             │    │             │     │
│  │ • Prometheus│    │ • ELK Stack │    │ • Automated │    │ • Firewall  │     │
│  │ • Grafana   │    │ • Logrotate │    │   Backups   │    │ • WAF       │     │
│  │ • Alerting  │    │ • Centralized│   │ • Disaster  │    │ • DDoS      │     │
│  │ • Metrics   │    │   Logging   │    │   Recovery  │    │   Protection│     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 10. Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             ERROR HANDLING FLOW                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   FRONTEND  │    │   BACKEND   │    │  EXTERNAL   │    │   FALLBACK  │     │
│  │   ERRORS    │    │   ERRORS    │    │    API      │    │   SYSTEM    │     │
│  │             │    │             │    │   ERRORS    │    │             │     │
│  │ • Network   │    │ • API       │    │ • Rate      │    │ • Mock Data │     │
│  │   Errors    │    │   Errors    │    │   Limits    │    │ • Cached    │     │
│  │ • JS Errors │    │ • Database  │    │ • Timeout   │    │   Data      │     │
│  │ • UI Errors │    │   Errors    │    │ • Auth      │    │ • Offline   │     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
│           │                   │                   │                   │         │
│           │                   │                   │                   │         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   ERROR     │    │   RECOVERY  │    │   LOGGING   │    │   ALERTING  │     │
│  │   HANDLING  │    │   MECHANISM │    │   SYSTEM    │    │   SYSTEM    │     │
│  │             │    │             │    │             │    │             │     │
│  │ • Try-Catch │    │ • Retry     │    │ • Error     │    │ • Email     │     │
│  │ • Fallbacks │    │   Logic     │    │   Logs      │    │   Alerts    │     │
│  │ • Graceful  │    │ • Circuit   │    │ • Stack     │    │ • SMS       │     │
│  │   Degradation│   │   Breaker   │    │   Traces    │    │ • Slack     │     │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

*These diagrams provide visual representations of the system architecture, data flows, and component interactions for the Trading Advisor Web Application.* 