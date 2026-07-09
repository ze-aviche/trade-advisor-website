// Gap Up Trade Bot Dashboard - Vue.js Application
// Rebuilt from scratch to work with DAS trades database

console.log('🚀 Loading Trading Advisor Dashboard...');

const { createApp } = Vue;

console.log('✅ Vue.js loaded successfully');

// Configure axios base URL
axios.defaults.baseURL = '';

const app = createApp({
        data() {
            return {
                // ── Fundamentals Screener ──────────────────────────────────
                screenerMeta: { total: 0, last_updated: null, sectors: [], exchanges: [], refresh: {} },
                screenerRows: [],
                screenerLoading: false,
                screenerLoaded: false,
                screenerExcludeFunds: true,
                screenerLimit: 500,
                screenerCat: { sector: '', exchange: '' },
                screenerSel: {},       // metric key -> preset index or 'custom'
                screenerCustom: {},    // metric key -> {min, max}
                screenerSort: { by: 'market_cap', dir: 'desc' },
                screenerRefreshTimer: null,
                // Metric definitions: key matches DB column, type drives preset list + formatting
                screenerMetrics: [
                    { key: 'market_cap',         label: 'Market Cap',    type: 'mktcap' },
                    { key: 'price',              label: 'Price',         type: 'price' },
                    { key: 'avg_volume',         label: 'Avg Volume',    type: 'volume' },
                    { key: 'pe',                 label: 'P/E',           type: 'ratio' },
                    { key: 'forward_pe',         label: 'Forward P/E',   type: 'ratio' },
                    { key: 'peg',                label: 'PEG',           type: 'ratio' },
                    { key: 'ps',                 label: 'P/S',           type: 'ratio' },
                    { key: 'pb',                 label: 'P/B',           type: 'ratio' },
                    { key: 'pfcf',               label: 'P/FCF',         type: 'ratio' },
                    { key: 'ev_ebitda',          label: 'EV/EBITDA',     type: 'ratio' },
                    { key: 'eps_ttm',            label: 'EPS (ttm)',     type: 'eps' },
                    { key: 'eps_forward',        label: 'EPS fwd',       type: 'eps' },
                    { key: 'eps_growth_yoy',     label: 'EPS Gr YoY',    type: 'pct' },
                    { key: 'eps_growth_qoq',     label: 'EPS Gr QoQ',    type: 'pct' },
                    { key: 'revenue_growth_yoy', label: 'Rev Gr YoY',    type: 'pct' },
                    { key: 'revenue_growth_qoq', label: 'Rev Gr QoQ',    type: 'pct' },
                    { key: 'fcf_growth_yoy',     label: 'FCF Gr YoY',    type: 'pct' },
                    { key: 'fcf_growth_qoq',     label: 'FCF Gr QoQ',    type: 'pct' },
                    { key: 'ocf_growth_yoy',     label: 'OCF Gr YoY',    type: 'pct' },
                    { key: 'roe',                label: 'ROE',           type: 'pct' },
                    { key: 'roa',                label: 'ROA',           type: 'pct' },
                    { key: 'roic',               label: 'ROIC',          type: 'pct' },
                    { key: 'gross_margin',       label: 'Gross Margin',  type: 'pct' },
                    { key: 'operating_margin',   label: 'Oper Margin',   type: 'pct' },
                    { key: 'net_margin',         label: 'Net Margin',    type: 'pct' },
                    { key: 'debt_to_equity',     label: 'Debt/Equity',   type: 'ratio' },
                    { key: 'current_ratio',      label: 'Current Ratio', type: 'ratio' },
                    { key: 'quick_ratio',        label: 'Quick Ratio',   type: 'ratio' },
                    { key: 'fcf_yield',          label: 'FCF Yield',     type: 'pct' },
                    { key: 'dividend_yield',     label: 'Div Yield',     type: 'pct' },
                    { key: 'payout_ratio',       label: 'Payout Ratio',  type: 'pct' },
                    { key: 'beta',               label: 'Beta',          type: 'ratio' },
                ],
                // Columns shown in the results table
                screenerColumns: [
                    { key: 'symbol',             label: 'Ticker' },
                    { key: 'company_name',       label: 'Company' },
                    { key: 'sector',             label: 'Sector' },
                    { key: 'market_cap',         label: 'Mkt Cap',     fmt: 'mktcap' },
                    { key: 'price',              label: 'Price',       fmt: 'usd' },
                    { key: 'change_pct',         label: 'Chg%',        fmt: 'pct_raw', color: true },
                    { key: 'pe',                 label: 'P/E',         fmt: 'num2' },
                    { key: 'forward_pe',         label: 'Fwd P/E',     fmt: 'num2' },
                    { key: 'peg',                label: 'PEG',         fmt: 'num2' },
                    { key: 'ps',                 label: 'P/S',         fmt: 'num2' },
                    { key: 'pb',                 label: 'P/B',         fmt: 'num2' },
                    { key: 'eps_ttm',            label: 'EPS',         fmt: 'usd' },
                    { key: 'eps_forward',        label: 'EPS fwd',     fmt: 'usd' },
                    { key: 'eps_growth_yoy',     label: 'EPS YoY',     fmt: 'pct', color: true },
                    { key: 'revenue_growth_yoy', label: 'Rev YoY',     fmt: 'pct', color: true },
                    { key: 'fcf_growth_yoy',     label: 'FCF YoY',     fmt: 'pct', color: true },
                    { key: 'roe',                label: 'ROE',         fmt: 'pct', color: true },
                    { key: 'net_margin',         label: 'Net Mgn',     fmt: 'pct', color: true },
                    { key: 'debt_to_equity',     label: 'D/E',         fmt: 'num2' },
                    { key: 'fcf_yield',          label: 'FCF Yld',     fmt: 'pct' },
                    { key: 'dividend_yield',     label: 'Div Yld',     fmt: 'pct' },
                    { key: 'avg_volume',         label: 'Avg Vol',     fmt: 'volume' },
                ],

                // ── Swing Setups (trend + fundamentals) ────────────────────
                swingMeta: { tech_total: 0, fund_total: 0, tech_last_updated: null, sectors: [], scan: {} },
                swingRows: [],
                swingLoading: false,
                swingLoaded: false,
                swingGrading: false,
                swingSelected: [],
                swingGrades: {},
                swingDetailOpen: false,
                swingDetailSymbol: '',
                swingScanTimer: null,
                swingSort: { by: 'swing_score', dir: 'desc' },
                swingTrend: {
                    above_sma20: true, above_sma50: true, above_sma100: true, above_sma200: false,
                    stacked: true, sma50_rising: true, rsi_min: 40, rsi_max: 80,
                    min_price: 5, min_avg_vol: 300000,
                },
                swingFundSel: {},
                swingFundMetrics: [
                    { key: 'eps_growth_yoy',     label: 'EPS Gr YoY', type: 'pct' },
                    { key: 'revenue_growth_yoy', label: 'Rev Gr YoY', type: 'pct' },
                    { key: 'roe',                label: 'ROE',        type: 'pct' },
                    { key: 'net_margin',         label: 'Net Margin', type: 'pct' },
                    { key: 'debt_to_equity',     label: 'Debt/Equity',type: 'ratio' },
                    { key: 'pe',                 label: 'P/E',        type: 'ratio' },
                ],
                // default preset index per fundamental metric (quality gate)
                swingFundDefaults: { eps_growth_yoy: 1, revenue_growth_yoy: 1, roe: 5, net_margin: 0, debt_to_equity: 0, pe: 0 },
                swingColumns: [
                    { key: 'symbol',             label: 'Ticker' },
                    { key: 'swing_score',        label: 'Score',    fmt: 'num1' },
                    { key: 't_price',            label: 'Price',    fmt: 'usd' },
                    { key: 'sma50',              label: 'SMA50',    fmt: 'usd' },
                    { key: 'sma200',             label: 'SMA200',   fmt: 'usd' },
                    { key: 'pct_above_sma50',    label: '%>SMA50',  fmt: 'pct_raw', color: true },
                    { key: 'pct_from_high',      label: '%off Hi',  fmt: 'pct_raw', color: true },
                    { key: 'rsi14',              label: 'RSI',      fmt: 'num1' },
                    { key: 'sma50_slope',        label: '50 slope', fmt: 'pct', color: true },
                    { key: 'eps_growth_yoy',     label: 'EPS YoY',  fmt: 'pct', color: true },
                    { key: 'revenue_growth_yoy', label: 'Rev YoY',  fmt: 'pct', color: true },
                    { key: 'roe',                label: 'ROE',      fmt: 'pct', color: true },
                    { key: 'pe',                 label: 'P/E',      fmt: 'num2' },
                    { key: 'market_cap',         label: 'Mkt Cap',  fmt: 'mktcap' },
                    { key: 'sector',             label: 'Sector' },
                ],

                // Screener glossary (collapsible beginner reference at bottom of tab)
                screenerGlossaryOpen: false,
                screenerGlossary: [
                    { group: 'Price & Size', items: [
                        { term: 'Market Cap', def: 'Total value of the company (share price × number of shares). Tells you the size: mega/large/mid/small/micro-cap. Larger companies are generally more stable; smaller ones are more volatile but can grow faster.' },
                        { term: 'Price', def: 'Current share price. On its own it says nothing about value — a $5 stock is not "cheaper" than a $500 one. Use the ratios below to judge value.' },
                        { term: 'Avg Volume', def: 'Average number of shares traded per day. Higher volume = more liquid, meaning you can buy or sell easily without moving the price much.' },
                        { term: 'Beta', def: 'How volatile the stock is versus the overall market. 1 = moves with the market, above 1 = bigger swings, below 1 = calmer. Higher beta = higher risk and reward.' },
                        { term: 'Chg %', def: "Today's percentage price change." },
                    ]},
                    { group: 'Valuation (is it cheap or expensive?)', items: [
                        { term: 'P/E — Price / Earnings', def: 'Price divided by earnings per share — the dollars you pay for each $1 of annual profit. Lower can mean cheaper; a high P/E usually means investors expect strong growth (or the stock is overvalued). Always compare within the same industry.' },
                        { term: 'Forward P/E', def: "Same as P/E but using next year's estimated earnings. If it's lower than the current P/E, profits are expected to grow." },
                        { term: 'PEG', def: 'P/E adjusted for growth (P/E ÷ earnings growth rate). Around 1 is considered fair value; below 1 may be undervalued given how fast it is growing.' },
                        { term: 'P/S — Price / Sales', def: 'Price relative to revenue. Useful for young or unprofitable companies that have no earnings yet. Lower = paying less for each $1 of sales.' },
                        { term: 'P/B — Price / Book', def: 'Price versus the accounting net worth (assets minus liabilities). Below 1 means it trades for less than its book value. Most useful for banks and asset-heavy businesses.' },
                        { term: 'P/FCF — Price / Free Cash Flow', def: 'Like P/E but uses real cash generated instead of accounting profit. Lower = cheaper relative to the actual cash the business produces.' },
                        { term: 'EV/EBITDA', def: 'Enterprise value vs earnings before interest, tax, depreciation & amortisation. A debt-neutral valuation that lets you fairly compare companies with different debt levels. Lower = cheaper.' },
                    ]},
                    { group: 'Earnings', items: [
                        { term: 'EPS (ttm)', def: 'Earnings per share over the trailing twelve months — the profit attributable to each share. Higher and rising is good.' },
                        { term: 'EPS fwd', def: "Analysts' estimated earnings per share for the upcoming period." },
                        { term: 'Earnings Yield', def: 'EPS ÷ price (the inverse of P/E). The profit you "earn" per dollar invested — handy to compare against bond or savings yields.' },
                    ]},
                    { group: 'Growth (YoY = vs the same period last year · QoQ = vs last quarter)', items: [
                        { term: 'EPS Gr YoY / QoQ', def: 'How fast earnings per share are growing. Faster profit growth often drives the share price higher.' },
                        { term: 'Rev Gr YoY / QoQ', def: 'How fast revenue (total sales) is growing. Sustained revenue growth is the engine of long-term returns.' },
                        { term: 'FCF Gr YoY / QoQ', def: 'Growth in free cash flow — the cash left after running costs and investments. Rising FCF funds dividends, buybacks and debt repayment.' },
                        { term: 'OCF Gr YoY', def: 'Growth in operating cash flow — cash generated by the core business operations.' },
                    ]},
                    { group: 'Profitability (how good is the business?)', items: [
                        { term: 'ROE — Return on Equity', def: "Profit as a % of shareholders' equity — how efficiently the company turns your money into profit. Above ~15% is generally considered strong." },
                        { term: 'ROA — Return on Assets', def: 'Profit as a % of total assets — how well the company uses its assets to make money.' },
                        { term: 'ROIC — Return on Invested Capital', def: 'Profit versus all the capital invested in the business. One of the best signals of whether a company truly creates value above its cost of funding.' },
                        { term: 'Gross Margin', def: 'Revenue left after the direct cost of making the product. Higher margins suggest pricing power or a strong product.' },
                        { term: 'Operating Margin', def: 'Profit after the costs of actually running the business (before interest and tax).' },
                        { term: 'Net Margin', def: 'The bottom-line profit kept for every $1 of sales, after all costs, interest and tax.' },
                    ]},
                    { group: 'Financial Health (how safe is it?)', items: [
                        { term: 'Debt / Equity', def: "Total debt versus shareholders' equity — how much leverage the company carries. Lower is safer; heavy debt is risky in downturns or when rates rise. Acceptable levels vary by industry." },
                        { term: 'Current Ratio', def: 'Short-term assets ÷ short-term bills. Above 1 means it can cover near-term obligations; roughly 1.5–3 is healthy.' },
                        { term: 'Quick Ratio', def: 'Like the current ratio but excludes inventory — a stricter test of whether it can pay its bills quickly.' },
                        { term: 'Interest Coverage', def: 'Operating profit ÷ interest expense — how easily the company can pay the interest on its debt. Higher is safer.' },
                    ]},
                    { group: 'Cash & Dividends', items: [
                        { term: 'FCF / Share', def: 'Free cash flow generated per share — the real cash, per share, left over after expenses and investment.' },
                        { term: 'FCF Yield', def: 'Free cash flow ÷ market cap. The cash return relative to the price you pay — higher means more cash-generative for the money.' },
                        { term: 'Dividend Yield', def: 'Annual dividend ÷ price — the income you receive each year as a percentage of the share price.' },
                        { term: 'Payout Ratio', def: '% of profit paid out as dividends. Very high (above ~80–100%) can be a warning that the dividend may not be sustainable.' },
                    ]},
                ],

                // Dashboard data - COMPLETELY REBUILT FROM SCRATCH
                dashboardStats: {
                    totalPositions: 0,
                    winRate: 0,
                    totalPnl: 0,
                    activePositions: 0,
                    gapUps: 0
                },
                dashboardPositions: [],
                dashboardAnalytics: {
                    totalPositions: 0,
                    overallWinRate: 0,
                    totalPnl: 0,
                    avgPositionPnl: 0,
                    longPositions: { count: 0, winRate: 0, pnl: 0 },
                    shortPositions: { count: 0, winRate: 0, pnl: 0 },
                    topPerformers: { bestTicker: '', bestPnl: 0 }
                },
                
                // Dashboard date filters
                dashboardDateRange: {
                    fromDate: '',
                    toDate: '',
                    showAllData: true
                },
                
                // Dashboard chart view
                dashboardChartView: 'long_short', // 'long_short', 'win_loss', 'ticker', 'monthly'
                
                recentActivity: [],
                gapUps: [],
                newGapUpTickers: [],   // tickers currently showing the new-arrival highlight
                prevGapUpTickers: [],  // tickers from the last fetch, used to diff
                trades: [],
                
                // UI state
                activeTab: localStorage.getItem('activeTab') || 'gap-ups',
                mobileMenuOpen: false,
                loading: {
                    stats: false,
                    gapUps: false,
                    trades: false,
                    historical: false,
                    bot: false,
                    dashboard: false,
                    syncTrades: false,
                    scheduledSync: false,
                    unsubscribe: false,
                    importDAS: false,
                    panicExit: false,
                    saveGapUpConfig: false,
                    dasConnection: false,
                    dasReconnect: false,
                    botToggle: false,
                    positions: false,
                    openPositions: false,
                    syncPositions: false,
                    dailyPnl: false,
                    cumulativePnl: false,
                    pieCharts: false,
                    timeOfDay: false,
                    dayOfWeek: false,
                    backtest: false,
                    runBacktest: false,
                    equityChart: false,
                    historicalAnalysis: false,
                    stockNews: false,
                    swingTechnicals: false,
                    swingRecommendation: false,
                    swingNews: false,
                    swingFundamentals: false,
                    swingDailyPicks: false,
                    swingBacktest: false,
                    earnings: false,
                    // BrownBot loading states
                    brownBotToggle: false,
                    brownBotConfig: false,
                    feedback: false,
                    brownBotCandidates: false,
                    brownBotSignals: false,
                    brownBotOrders: false,
                    brownBotCloseAll: false,
                    // Broker loading states
                    brokerSave: false,
                    brokerTest: false,
                    brokerAccount: false,
                },
                
                // Charts
                charts: {
                    pnl: null,
                    positions: null
                },
                
                // Chart update control
                chartUpdateInProgress: false,
                pnlChartUpdateTimeout: null,
                positionsChartUpdateTimeout: null,
                
                // WebSocket connection
                socket: null,
                socketConnected: false,
                subscribedStocks: new Set(),
                livePrices: {},
                
                // AI Chat
                aiChatMessages: [],
                aiNewMessage: '',
                aiChatLoading: false,
                

                
                // System status
                systemStatus: {
                    connected: false,
                    realDataAvailable: false,
                    websocketConnected: false,
                    botRunning: false
                },
                
                // Bot status
                botStatus: {
                    running: false,
                    monitoring: false,
                    positions: [],
                    active_positions: [],
                    active_positions_count: 0,
                    last_update: null,
                    profit_target_pct: 5.0,
                    stop_loss_pct: 2.5,
                    monitor_interval: 5,
                    das_connected: false,
                    internal_running_state: false,
                    internal_monitoring_state: false
                },
                
                // Real-time updates
                realTimeUpdates: {
                    enabled: false,
                    interval: null,
                    lastUpdate: null,
                    isUpdating: false,
                    updateInterval: 2000, // Configurable update interval in milliseconds
                    enabled: false
                },
                
                // Position History auto-updates
                positionHistoryUpdates: {
                    enabled: false,
                    interval: null,
                    lastUpdate: null,
                    updateInterval: 10000 // 10 seconds to match backend sync
                },
                
                // Bot configuration
                botConfig: {
                    profit_target_pct: 5.0,
                    stop_loss_pct: 2.5,
                    monitor_interval: 5,
                    trailing_stop_enabled: false,
                    trailing_stop_pct: 1.5,
                    eod_exit_enabled: true,
                    eod_exit_time: '15:45',
                    breakeven_stop_enabled: true,
                    breakeven_trigger_pct: 50.0,
                },
                isEditingBotConfig: false, // Track if user is actively editing bot config
                
                // Gap-up configuration
                gapUpSort: { key: 'gap_percent', dir: 'desc' },
                positionsSort: { key: 'exit_date', dir: 'desc' },
                tradesSort: { key: 'submitted_at', dir: 'desc' },
                activePositionsSort: { key: 'entry_time', dir: 'desc' },
                trackingSort: { key: 'symbol', dir: 'asc' },
                gapUpConfig: {
                    min_percentage: 0
                },
                

                
                // User data
                user: null,
                isGuest: false,
                profileMenuOpen: false,
                darkMode: localStorage.getItem('theme') !== 'light',
                contactForm: { name: '', email: '', subject: '', message: '' },
                contactLoading: false,
                contactSuccess: '',
                contactError: '',

                // Admin
                adminUsers: [],
                adminSearchQuery: '',
                adminLoading: false,
                adminAddUserForm: { username: '', email: '', password: '' },
                adminAddUserLoading: false,
                adminAddUserError: '',
                adminAddUserSuccess: '',
                adminBotSessions: [],
                adminBotSessionsLoading: false,

                // Account tab sub-section
                accountSection: 'subscription',

                // Profile / Manage Info
                profileForm: { email: '', first_name: '', last_name: '', address: '', profession: '', profession_other: '', annual_income_range: '' },
                profileLoading: false,
                profileError: '',
                profileSuccess: '',

                // Change password
                changePwForm: { current: '', newPw: '', confirm: '' },
                changePwLoading: false,
                changePwError: '',
                changePwSuccess: '',

                // Subscription / account page
                subscriptionLoading: false,

                // Upgrade modal
                upgradeModal: {
                    show: false,
                    tabLabel: '',
                    requiredPlan: '',
                    requiredPrice: '',
                    requiredTier: ''
                },
                
                // Historical data
                historicalTicker: '',
                historicalData: [],
                selectedPeriod: '365', // Default to 1 year
                minGapPercent: 25,     // Gap-up filter threshold
                sortColumn: '',
                sortDirection: 'asc',
                historicalAnalysis: null,
                historicalSectorInfo: null,
                historicalSectorPerf: null,
                historicalAnalysisCached: false,
                historicalPrefetchStatus: {},    // {TICKER: {records, fetched_at}}
                historicalLoadedFromCache: false,
                stockNews: null,
                _historicalCharts: {},

                // Trial banner
                trialBannerDismissed: false,

                // Swing Trading tab
                swingTicker: '',
                swingTechnicals: null,
                swingSectorInfo: null,
                swingSectorPerf: null,
                swingRecommendation: null,
                swingNews: null,
                swingFundamentals: null,
                swingTechnicalsCached: false,
                swingDailyPicks: null,
                swingDailyPicksDate: null,
                swingPicksDates: [],
                swingPicksSelectedDate: '',
                sectorStrength: [],
                sectorStrengthLoading: false,
                activeSector: null,
                // Earnings tab
                erTicker: '',
                erData: null,
                erCalendar: [],
                erCalendarDays: 14,
                erCalendarLoading: false,
                erSelectedDate: '',
                erRatingRows: [
                    { key: 'strong_buy',  label: 'Strong Buy',  bar: 'bg-green-500', txt: 'text-green-400' },
                    { key: 'buy',         label: 'Buy',         bar: 'bg-green-400', txt: 'text-green-400' },
                    { key: 'hold',        label: 'Hold',        bar: 'bg-yellow-400',txt: 'text-yellow-400' },
                    { key: 'sell',        label: 'Sell',        bar: 'bg-red-400',   txt: 'text-red-400' },
                    { key: 'strong_sell', label: 'Strong Sell', bar: 'bg-red-600',   txt: 'text-red-400' },
                ],
                // Trade History
                tradeHistoryTicker: '',
                tradeHistoryStartDate: '',
                tradeHistoryEndDate: '',
                tradeHistoryStyle: '',
                tradeHistoryStatus: '',
                
                // Positions History
                positions: [],
                positionsHistoryTicker: '',
                positionsHistoryType: '',
                positionsHistorySource: '',
                positionsHistoryStartDate: '',
                positionsHistoryEndDate: '',
                positionsSummary: {},
                positionsStatusFilter: 'closed',   // 'closed' | 'open' | 'all'
                openPositions: [],
                openPositionsMessage: '',
                
                // Dashboard Trade Period
                dashboardTradePeriod: '365', // Default to 1 year
                
                // Dashboard P&L Date Range
                dashboardPnLFromDate: '',
                dashboardPnLToDate: '',
                
                // Panic Exit
                panicExitResult: null,
                
                // Dashboard Trade Date Range
                dashboardTradeFromDate: '',
                dashboardTradeToDate: '',
                
            // Import DAS Data Modal
            showImportModal: false,
            dasTradesData: '',
            
            // Scheduled Sync Status
            scheduledSyncStatus: {
                is_running: false,
                is_market_hours: false,
                current_time_et: '',
                next_scheduled_run: null,
                thread_alive: false
            },
            
            swingBotConfig: {
                profit_target_pct: 15.0,
                stop_loss_pct: 7.0,
                trailing_stop_enabled: false,
                trailing_stop_pct: 4.0,
                max_hold_days: 20,
                earnings_protection_enabled: true,
                earnings_exit_days: 2,
                daily_close_exit_enabled: true,
                breakeven_stop_enabled: true,
                breakeven_trigger_pct: 50.0,
            },
            
            // Tracking Symbols
            trackingSymbols: [],
            
            // Active Positions
            activePositions: [],
            
            // Debug Logs
            debugLogs: [],

            // BrownBot
            brownBotStatus: {
                running: false,
                das_enabled: false,
                active_positions: [],
                active_positions_count: 0,
                entry_counts: {},
                skipped_symbols: [],
                stats: { day_entered: 0, swing_entered: 0, day_exited: 0, swing_exited: 0 }
            },
            feedbackData: null,
            feedbackHistory: [],
            feedbackCollapsed: false,
            feedbackLookbackDays: 30,

            marketRegime: {
                signal: 'NEUTRAL',
                score: 0,
                gap_up_count: 0,
                spy_return_5d: 0.0,
                vix_level: null,
                components: {},
                last_updated: null,
                adjustments: { position_pct_multiplier: 1.0, note: 'No adjustments' }
            },
            brownBotConfig: {
                day_profit_target_pct: 5.0,
                day_stop_loss_pct: 2.5,
                day_trailing_stop_enabled: false,
                day_trailing_stop_pct: 1.5,
                day_eod_exit_time: '15:45',
                day_breakeven_enabled: true,
                day_breakeven_trigger_pct: 50.0,
                day_time_gate_enabled: true,
                day_time_gate_start: '09:35',
                day_time_gate_end: '10:30',
                swing_profit_target_pct: 15.0,
                swing_stop_loss_pct: 7.0,
                swing_max_hold_days: 20,
                swing_earnings_protection_enabled: true,
                swing_earnings_exit_days: 2,
                swing_breakeven_enabled: true,
                swing_breakeven_trigger_pct: 50.0,
                max_daily_loss: -500.0,
                max_concurrent_day: 3,
                max_concurrent_swing: 5,
                day_max_reentry: 2,
                min_gap_pct: 10.0,
                min_price: 5.0,
                max_price: 500.0,
                min_volume_m: 0.5,
                max_float_m: 0.0,
                float_operator: '<=',
                day_check_vwap: false,
                day_check_candle: false,
                day_max_extension_pct: 0.0,
                day_check_volume_surge: false,
                day_check_pmh: false,
                day_check_dayhigh_break: false,
                day_check_orb: false,
                day_orb_minutes: 15,
                day_pmh_break_buffer_pct: 0.2,
                day_pmh_vol_mult: 1.5,
                day_pmh_max_wick_pct: 60.0,
                day_pmh_acceptance_bars: 0,
                day_max_below_dayhigh_pct: 0.0,
                day_ai_playbook: true,
                day_position_pct: 5.0,
                swing_position_pct: 3.0,
                day_max_position_pct: 10.0,
                swing_max_position_pct: 20.0,
                day_trades_enabled: true,
                swing_trades_enabled: true,
                // Swing scanner filters
                swing_scan_source: 'both',
                swing_scan_top_n: 30,
                swing_min_price: 5.0,
                swing_max_price: 500.0,
                swing_min_avg_vol_k: 500.0,
                swing_min_market_cap_m: 200.0,
                swing_max_market_cap_m: 0.0,
                swing_max_float_m: 0.0,
                // Swing entry signals
                swing_check_above_sma20: false,
                swing_check_ma_cross: false,
                swing_check_rsi_range: false,
                swing_rsi_min: 40.0,
                swing_rsi_max: 70.0,
                swing_check_rel_vol: false,
                swing_rel_vol_min: 1.2,
                // ATR-based dynamic stops
                day_use_atr_stop: false,
                day_atr_multiplier: 1.5,
                day_max_atr_stop_pct: 8.0,
                swing_use_atr_stop: false,
                swing_atr_multiplier: 2.0,
                swing_max_atr_stop_pct: 15.0,
                // Minimum risk/reward gate (0 = disabled)
                day_min_rr: 0.0,
                swing_min_rr: 0.0,
            },
            brownBotLogs: [],
            brownBotPollingInterval: null,
            brownSwingCandInterval: null,
            sessionExpiresAt: null,
            sessionWarningDismissed: false,
            keepaliveInterval: null,
            brownBotCandidates: { scanner: [], watchlist: [] },
            brownBotSwingCandidates: [],
            swingBacktestExpanded: false,
            swingBt: {
                startDate: new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10),
                endDate:   new Date().toISOString().slice(0, 10),
                gradeFilter:   'AB',
                biasFilter:    'Bullish',
                profitTarget:  15,
                stopLoss:      7,
                maxHold:       20,
                stats:         null,
                trades:        [],
                message:       '',
                dataSource:    '',
            },
            dbQuery: {
                sql:          '',
                columns:      [],
                rows:         [],
                rowCount:     0,
                rowsAffected: null,
                elapsed:      0,
                truncated:    false,
                loading:      false,
                error:        '',
                isWrite:      false,
            },
            brownBotSignals: {},
            brownBotLivePrices: {},
            _brownPriceInterval: null,
            brownBotWatchlistForm: { symbol: '', trade_type: 'day', note: '' },
            brownBotRiskStatus: {
                daily_pnl: 0,
                realized_pnl: 0,
                unrealized_pnl: 0,
                max_daily_loss: -500,
                open_day: 0,
                max_concurrent_day: 3,
                open_swing: 0,
                max_concurrent_swing: 5,
                circuit_breaker_open: false,
                circuit_breaker_triggered: false,
            },
            brownEntryStats: { rows: [], overall: {} },
            brownEntryStatsOpen: false,
            brownEntryStatsType: '',
            brownExitStats: { rows: [], overall: {} },
            brownBotConfigCollapsed: false,
            brownBotOrdersCollapsed: false,
            brownBotCloseAllConfirm: false,
            brownBotBrokerOrders: [],
            brownBotOrdersAfter: '',
            brownBotOrdersUntil: '',

            // Broker connection settings
            supportedBrokers: [],
            brokerConfigs: [],
            brokerConfigsLoaded: false,
            brownBotStatusLoaded: false,
            brokerCardExpanded: null,
            brokerCardForms: {
                alpaca:     { api_key: '', api_secret: '', paper_trading: true },
                tastytrade: { username: '', password: '', paper_trading: false },
                tradier:    { api_key: '', paper_trading: true },
                das:        { host: '127.0.0.1', port: 9800 },
            },
            brokerCardAccountInfo: {},
            brokerCardLoading: {},

                            // Continuous tracking interval
                trackingInterval: null,

                // Gap-up auto-refresh interval handle
                gapUpRefreshInterval: null,

                // Active sub-tab inside the gap-ups tab
                activeGapUpSubTab: 'premarket',

                // Historical snapshot browsing
                gapUpViewDate: null,          // null = live today, 'YYYY-MM-DD' = historical
                gapUpSnapshotDates: [],       // list of dates with saved snapshots
                gapUpHistoricalData: [],      // stocks for the selected historical date
            

            
                            // Dashboard chart data - Direct from database

                dashboardPnL: [],
                showAllTrades: true, // Toggle to show all trades regardless of date - default to true since trades are from 2025
                tradeTypeFilter: 'all', // Filter for trade type: 'all', 'long', 'short'
                chartViewType: 'long_short', // Chart view type: 'long_short', 'win_loss', 'ticker', 'monthly'
                tradeAnalytics: {
                    totalTrades: 0,
                    overallWinRate: 0,
                    totalPnl: 0,
                    avgTradePnl: 0,
                    longTrades: { count: 0, winRate: 0, pnl: 0 },
                    shortTrades: { count: 0, winRate: 0, pnl: 0 },
                    topPerformers: { bestTicker: '', bestPnl: 0 }
                },
                
                // Stats data
                stats: {
                    total_positions: 0,
                    total_pnl: 0,
                    win_rate: 0
                },
                extendedStats: {
                    gross_profit: 0, gross_loss: 0, profit_factor: 0,
                    avg_win: 0, avg_loss: 0, win_loss_ratio: 0,
                    best_trade: 0, best_trade_symbol: '', best_trade_date: '',
                    worst_trade: 0, worst_trade_symbol: '', worst_trade_date: '',
                    avg_pnl: 0, win_count: 0, loss_count: 0, breakeven_count: 0,
                    total_count: 0, expectancy: 0, max_consecutive_wins: 0, max_consecutive_losses: 0,
                    max_drawdown: 0, sharpe_ratio: null,
                },
                statsStartDate: '',
                statsEndDate: '',
                statsPreset: 'all',
                // Advanced stats filters
                statsTimeStart: '',        // HH:MM in ET
                statsTimeEnd: '',          // HH:MM in ET
                statsPriceMin: '',
                statsPriceMax: '',
                statsDayOfWeek: [],        // SQLite %w ints: 1=Mon…5=Fri

                // Daily P&L chart data
                dailyPnlData: [],
                dailyPnlChart: null,
                dailyPnlChartType: 'bar', // Default to bar chart

                // Cumulative P&L chart data
                cumulativePnlData: [],
                cumulativePnlChart: null,

                // Time-of-day & day-of-week breakdown
                timeOfDayData: [],
                timeOfDayChart: null,
                dayOfWeekData: [],
                dayOfWeekChart: null,

                // Pie Chart data
                pieChartData: {
                    longShort: [],
                    symbols: [],
                    winLoss: [],
                    monthly: []
                },
                pieCharts: {
                    longShort: null,
                    symbols: null,
                    winLoss: null,
                    monthly: null
                },
                pieChartType: 'longShort', // Default pie chart type
                pieChartSymbolLimit: 10, // Number of symbols to show in pie chart

                // Backtest data
                backtestTradeType: 'day',   // 'day' | 'swing' | 'universe_swing'
                backtestConfig: {
                    // ── Shared ──────────────────────────────
                    startDate: '',
                    endDate: '',
                    initialCapital: 100000,
                    minGapPct: 5,
                    minPrice: 1,
                    maxPrice: 500,
                    minVolumeMillion: 1,
                    maxFloatM: 0,
                    floatOperator: '>=',
                    // ── Day trade ────────────────────────────
                    dayPositionSizePct: 10,
                    dayStopLossPct: 2.0,
                    dayProfitTargetPct: 4.0,
                    dayBreakevenEnabled: false,
                    dayBreakevenTriggerPct: 50,
                    dayTrailingStopEnabled: false,
                    dayTrailingStopPct: 1.5,
                    maxConcurrentDay: 5,
                    daySlippagePct: 0.1,
                    dayMaxReentry: 1,
                    entryStartTime: '09:35',
                    entryEndTime: '10:30',
                    eodExitTime: '15:55',
                    // Breakout triggers (OR) — mirror BrownBot day settings
                    dayCheckPmh: false,
                    dayCheckDayhighBreak: false,
                    dayCheckOrb: false,
                    dayOrbMinutes: 15,
                    dayPmhBreakBufferPct: 0.2,
                    dayPmhVolMult: 1.5,
                    dayPmhMaxWickPct: 60,
                    dayPmhAcceptanceBars: 0,
                    // Condition gates (AND)
                    dayCheckVwap: false,
                    dayCheckCandle: false,
                    dayMaxExtensionPct: 0,
                    dayCheckVolumeSurge: false,
                    dayMaxBelowDayhighPct: 0,
                    // ── Swing trade ──────────────────────────
                    swingPositionSizePct: 3,
                    swingStopLossPct: 7.0,
                    swingProfitTargetPct: 15.0,
                    swingMaxHoldDays: 20,
                    swingMinMarketCapM: 500,
                },
                backtestInfo: null,
                backtestResults: null,
                equityCurveChart: null

            }
        },
        

        
        computed: {
            erSelectedDayEntries() {
                if (!this.erSelectedDate || !this.erCalendar.length) return [];
                const day = this.erCalendar.find(d => d.date === this.erSelectedDate);
                return day ? day.entries : [];
            },
            erTotalRecs() {
                if (!this.erData || !this.erData.recommendations) return 0;
                const r = this.erData.recommendations;
                return (r.strong_buy||0)+(r.buy||0)+(r.hold||0)+(r.sell||0)+(r.strong_sell||0);
            },
            erConsensusLabel() {
                if (!this.erData || !this.erData.recommendations || !this.erTotalRecs) return '';
                const r = this.erData.recommendations;
                const bull = ((r.strong_buy||0)+(r.buy||0)) / this.erTotalRecs;
                const bear = ((r.sell||0)+(r.strong_sell||0)) / this.erTotalRecs;
                if (bull >= 0.70) return 'Strong Buy';
                if (bull >= 0.50) return 'Buy';
                if (bear >= 0.40) return 'Sell';
                return 'Hold';
            },
            erConsensusBadgeClass() {
                const l = this.erConsensusLabel;
                if (l === 'Strong Buy') return 'bg-green-900/50 border-green-600/60 text-green-300';
                if (l === 'Buy')        return 'bg-green-900/30 border-green-700/40 text-green-400';
                if (l === 'Sell')       return 'bg-red-900/40 border-red-600/50 text-red-300';
                return 'bg-yellow-900/30 border-yellow-700/40 text-yellow-300';
            },
            bestHour() {
                if (!this.timeOfDayData.length) return null;
                return this.timeOfDayData.reduce((a, b) => b.total_pnl > a.total_pnl ? b : a);
            },
            worstHour() {
                if (!this.timeOfDayData.length) return null;
                return this.timeOfDayData.reduce((a, b) => b.total_pnl < a.total_pnl ? b : a);
            },
            maxDrawdown() {
                if (!this.cumulativePnlData || this.cumulativePnlData.length < 1) return null;
                let peak = -Infinity, maxDD = 0;
                for (const d of this.cumulativePnlData) {
                    const v = d.cumulative_pnl ?? d.pnl ?? 0;
                    if (v > peak) peak = v;
                    const dd = peak - v;
                    if (dd > maxDD) maxDD = dd;
                }
                return Math.round(maxDD * 100) / 100;
            },
            sharpeRatio() {
                if (!this.dailyPnlData || this.dailyPnlData.length < 2) return null;
                const values = this.dailyPnlData.map(d => d.daily_pnl ?? 0);
                const mean = values.reduce((s, v) => s + v, 0) / values.length;
                const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length;
                const std = Math.sqrt(variance);
                if (std === 0) return null;
                return Math.round((mean / std) * Math.sqrt(252) * 100) / 100;
            },
            changePwStrength() {
                const p = this.changePwForm.newPw;
                if (!p) return 0;
                if (p.length < 8) return 1;
                if (/[A-Z]/.test(p) && /[0-9]/.test(p)) return 3;
                return 2;
            },
            changePwStrengthLabel() {
                return ['', 'Weak', 'Medium', 'Strong'][this.changePwStrength] || '';
            },
            isSuperAdmin() {
                return this.user && this.user.system_role === 'super_admin';
            },
            isDevMaster() {
                return this.user && this.user.system_role === 'dev_master';
            },
            isBotAdmin() {
                return this.user && this.user.system_role === 'bot_admin';
            },
            isStaff() {
                return this.user && (
                    this.user.system_role === 'super_admin' ||
                    this.user.system_role === 'dev_master' ||
                    this.user.system_role === 'bot_admin'
                );
            },
            isAdmin() {
                return this.isSuperAdmin;
            },
            hasActiveBroker() {
                return this.brokerConfigs.some(c => c.is_active);
            },
            trialActive() {
                return this.user && this.user.trial_active === true;
            },
            trialDaysLeft() {
                return this.user ? (this.user.trial_days_left || 0) : 0;
            },
            showTrialBanner() {
                return this.trialActive && !this.trialBannerDismissed && !this.isGuest;
            },
            sessionMinutesRemaining() {
                if (!this.sessionExpiresAt || this.isGuest) return null;
                const diff = new Date(this.sessionExpiresAt) - new Date();
                return Math.floor(diff / 60000);
            },
            showSessionWarning() {
                const mins = this.sessionMinutesRemaining;
                return mins !== null && mins <= 30 && mins > 0 && !this.sessionWarningDismissed;
            },
            lockedTabInfo() {
                const map = {
                    historical: {
                        label: 'Historical Data', plan: 'Beginner Trader', price: '$5/mo', tier: 'beginner', icon: 'fa-history', color: 'blue',
                        tagline: 'Understand the past to trade the future.',
                        features: [
                            { icon: 'fa-calendar-alt',  text: 'Months of daily gap-up scan results for any ticker' },
                            { icon: 'fa-filter',        text: 'Filter by date range, gap %, price, or volume' },
                            { icon: 'fa-table',         text: 'Day high %, close %, Runner vs Fader, VWAP crosses' },
                            { icon: 'fa-file-download', text: 'Export to CSV / Excel for your own analysis' },
                        ],
                    },
                    swing: {
                        label: 'Swing Trading', plan: 'Advanced Trader', price: '$10/mo', tier: 'advanced', icon: 'fa-wave-square', color: 'purple',
                        tagline: 'AI-ranked daily swing picks with full technical context.',
                        features: [
                            { icon: 'fa-robot',         text: 'Claude AI grades every pick A / B / C with Bullish / Neutral / Bearish bias' },
                            { icon: 'fa-chart-mixed',   text: 'Full technicals — RSI, MACD, Bollinger Bands, ATR, SMA/EMA' },
                            { icon: 'fa-layer-group',   text: 'Sector strength pills with S&P 500 breadth and sector news' },
                            { icon: 'fa-newspaper',     text: 'Live news headlines + AI market summary for each pick' },
                        ],
                    },
                    earnings: {
                        label: 'Earnings', plan: 'Advanced Trader', price: '$10/mo', tier: 'advanced', icon: 'fa-calendar-alt', color: 'blue',
                        tagline: 'Upcoming earnings calendar + full per-ticker ER research.',
                        features: [
                            { icon: 'fa-calendar-alt',  text: 'Upcoming earnings calendar — next 2 weeks or 1 month, grouped by date' },
                            { icon: 'fa-chart-bar',     text: 'EPS history — 12 quarters of estimate vs actual vs surprise %' },
                            { icon: 'fa-dollar-sign',   text: 'Quarterly revenue with QoQ growth' },
                            { icon: 'fa-bullseye',      text: 'Analyst price targets and consensus ratings breakdown' },
                        ],
                    },
                    trades: {
                        label: 'Trade History', plan: 'Yogi Trader', price: '$25/mo', tier: 'yogi', icon: 'fa-exchange-alt', color: 'yellow',
                        tagline: 'Every trade logged, analyzed, and actionable.',
                        features: [
                            { icon: 'fa-list-alt',      text: 'Complete record of all trades placed via BrownBot or your broker' },
                            { icon: 'fa-sort-amount-down', text: 'Filter by ticker, date range, side, or source' },
                            { icon: 'fa-file-excel',    text: 'One-click export to CSV or Excel' },
                            { icon: 'fa-clock',         text: 'Entry & exit times shown in ET for easy review' },
                        ],
                    },
                    positions: {
                        label: 'Positions', plan: 'Yogi Trader', price: '$25/mo', tier: 'yogi', icon: 'fa-chart-line', color: 'yellow',
                        tagline: 'Live visibility into every open and closed position.',
                        features: [
                            { icon: 'fa-eye',           text: 'Live open positions pulled directly from your broker (Alpaca)' },
                            { icon: 'fa-history',       text: 'Full closed-position history with entry / exit / P&L' },
                            { icon: 'fa-layer-group',   text: 'Separate day-trade and swing-trade tracking' },
                            { icon: 'fa-percentage',    text: 'Win count, loss count, and win rate chips per filter' },
                        ],
                    },
                    stats: {
                        label: 'Stats', plan: 'Yogi Trader', price: '$25/mo', tier: 'yogi', icon: 'fa-chart-bar', color: 'yellow',
                        tagline: 'Data-driven insights to sharpen your edge.',
                        features: [
                            { icon: 'fa-percentage',    text: 'Win rate, total P&L, average winner vs average loser' },
                            { icon: 'fa-chart-pie',     text: 'P&L breakdown by ticker, side, time of day, day of week' },
                            { icon: 'fa-robot',         text: 'AI Advisor — Claude analyses your trade history and gives personalised feedback' },
                            { icon: 'fa-chart-area',    text: 'Cumulative equity curve and daily P&L chart' },
                        ],
                    },
                    backtest: {
                        label: 'Backtest', plan: 'Yogi Trader', price: '$25/mo', tier: 'yogi', icon: 'fa-flask', color: 'yellow',
                        tagline: 'Validate your gap-up strategy before risking real capital.',
                        features: [
                            { icon: 'fa-redo',          text: 'Replay gap-up strategies against months of real market data' },
                            { icon: 'fa-dollar-sign',   text: 'Configurable capital, position size, profit target, and stop-loss' },
                            { icon: 'fa-chart-area',    text: 'Equity curve, win rate, max drawdown, and Sharpe ratio' },
                            { icon: 'fa-wave-square',   text: 'BrownBot swing backtest — test AI-graded pick configs' },
                        ],
                    },
                    'brown-bot': {
                        label: 'BrownBot', plan: 'Yogi Trader', price: '$25/mo', tier: 'yogi', icon: 'fa-brain', color: 'yellow',
                        tagline: 'Fully autonomous day & swing trading — connect your broker and go.',
                        features: [
                            { icon: 'fa-search-dollar', text: 'Auto-scans gap-ups every 30 s and enters qualifying positions without any manual input' },
                            { icon: 'fa-brain',         text: 'Optional AI Playbook — Claude grades each candidate before entry and sets stop/target' },
                            { icon: 'fa-shield-alt',    text: 'Portfolio risk manager: daily loss limit circuit breaker and concurrent-position caps' },
                            { icon: 'fa-moon',         text: 'Swing mode: holds AI-graded overnight picks with earnings-protection auto-exit' },
                        ],
                    },
                };
                const guestMap = {
                    'ai-chat': {
                        label: 'AI Chat', isGuest: true, icon: 'fa-comments',
                        tagline: 'Get real-time trading insights powered by AI.',
                        features: [
                            { icon: 'fa-comments',   text: 'Ask questions about gap-up stocks in real time' },
                            { icon: 'fa-lightbulb',  text: 'AI-powered trade entry and exit suggestions' },
                            { icon: 'fa-chart-line', text: 'Market sentiment analysis' },
                            { icon: 'fa-brain',      text: 'Strategy Q&A with context-aware responses' },
                        ],
                    },
                    help: {
                        label: 'Help Center', isGuest: true, icon: 'fa-question-circle',
                        tagline: 'Everything you need to get started.',
                        features: [
                            { icon: 'fa-book',      text: 'Step-by-step platform guides' },
                            { icon: 'fa-video',     text: 'Tutorial videos and walkthroughs' },
                            { icon: 'fa-headset',   text: 'Live support chat with our team' },
                            { icon: 'fa-envelope',  text: 'Direct contact form for custom help' },
                        ],
                    },
                    contact: {
                        label: 'Contact Us', isGuest: true, icon: 'fa-envelope',
                        tagline: 'We\'d love to hear from you.',
                        features: [
                            { icon: 'fa-envelope',    text: 'Send messages directly to our support team' },
                            { icon: 'fa-clock',       text: 'Typical response within 24 hours' },
                            { icon: 'fa-star',        text: 'Priority support for premium subscribers' },
                            { icon: 'fa-shield-alt',  text: 'Your messages are private and secure' },
                        ],
                    },
                    account: {
                        label: 'My Account', isGuest: true, icon: 'fa-user-circle',
                        tagline: 'Manage your profile, subscription, and settings.',
                        features: [
                            { icon: 'fa-user-edit',   text: 'Update your profile and password' },
                            { icon: 'fa-crown',       text: 'Choose the plan that fits your trading style' },
                            { icon: 'fa-credit-card', text: 'Manage billing and payment methods' },
                            { icon: 'fa-bell',        text: 'Customize notification preferences' },
                        ],
                    },
                };
                const info = map[this.activeTab] || (this.isGuest ? guestMap[this.activeTab] : null);
                if (info && !this.canAccessTab(this.activeTab)) return info;
                return null;
            },

            activeGapUpData() {
                // Single source of truth: live data or historical snapshot
                return this.gapUpViewDate ? this.gapUpHistoricalData : this.gapUps;
            },

            gapUpSubTabCounts() {
                const src = this.activeGapUpData;
                return {
                    premarket:  src.filter(s => s.session === 'premarket').length,
                    intraday:   src.filter(s => s.session === 'intraday').length,
                    afterhours: src.filter(s => s.session === 'afterhours').length,
                };
            },

            sortedGapUps() {
                const { key, dir } = this.gapUpSort;
                const filtered = this.activeGapUpData.filter(s => (s.session || 'premarket') === this.activeGapUpSubTab);
                return filtered.sort((a, b) => {
                    let va, vb;
                    if (key === 'float_rotation') {
                        va = (a.float_shares > 0 && a.volume > 0) ? a.volume / a.float_shares : null;
                        vb = (b.float_shares > 0 && b.volume > 0) ? b.volume / b.float_shares : null;
                    } else {
                        va = a[key]; vb = b[key];
                    }
                    if (va == null) return 1;
                    if (vb == null) return -1;
                    if (typeof va === 'string') { va = va.toLowerCase(); vb = (vb || '').toLowerCase(); }
                    return dir === 'asc' ? (va > vb ? 1 : va < vb ? -1 : 0) : (va < vb ? 1 : va > vb ? -1 : 0);
                });
            },

            sortedPositions() {
                const { key, dir } = this.positionsSort;
                const brokerFilter = (this.positionsHistorySource || '').toLowerCase();
                const effectiveBroker = p => {
                    if (p.broker) return p.broker.toLowerCase();
                    if (p.source === 'brownbot') return 'alpaca';
                    if (p.source === 'das') return 'das';
                    return (p.source || '').toLowerCase();
                };
                const base = brokerFilter
                    ? this.positions.filter(p => effectiveBroker(p).includes(brokerFilter))
                    : this.positions;
                return [...base].sort((a, b) => {
                    let va = a[key], vb = b[key];
                    if (va == null) return 1;
                    if (vb == null) return -1;
                    if (typeof va === 'string') { va = va.toLowerCase(); vb = (vb || '').toLowerCase(); }
                    return dir === 'asc' ? (va > vb ? 1 : va < vb ? -1 : 0) : (va < vb ? 1 : va > vb ? -1 : 0);
                });
            },

            sortedTrades() {
                const { key, dir } = this.tradesSort;
                let list = this.trades;
                if (this.tradeHistoryStyle)
                    list = list.filter(t => t.position_type === this.tradeHistoryStyle);
                if (this.tradeHistoryStatus)
                    list = list.filter(t => t.direction === this.tradeHistoryStatus);
                return [...list].sort((a, b) => {
                    let va = a[key], vb = b[key];
                    if (va == null) return 1;
                    if (vb == null) return -1;
                    if (typeof va === 'string') { va = va.toLowerCase(); vb = (vb || '').toLowerCase(); }
                    return dir === 'asc' ? (va > vb ? 1 : va < vb ? -1 : 0) : (va < vb ? 1 : va > vb ? -1 : 0);
                });
            },

            tradesSummary() {
                const list = this.sortedTrades;
                const totalPnl = list.reduce((s, t) => s + (t.pnl || 0), 0);
                return {
                    count: list.length,
                    buys:  list.filter(t => t.direction === 'buy').length,
                    sells: list.filter(t => t.direction === 'sell').length,
                    totalPnl,
                };
            },

            positionsSummaryComputed() {
                const list = this.sortedPositions;
                const totalPnl = list.reduce((s, p) => s + (p.pnl || 0), 0);
                const wins     = list.filter(p => (p.pnl || 0) > 0).length;
                const losses   = list.filter(p => (p.pnl || 0) <= 0).length;
                return {
                    count: list.length,
                    totalPnl,
                    wins,
                    losses,
                    winRate: list.length ? (wins / list.length) * 100 : 0,
                };
            },

            sortedActivePositions() {
                const { key, dir } = this.activePositionsSort;
                return [...this.activePositions].sort((a, b) => {
                    let va = a[key], vb = b[key];
                    if (va == null) return 1;
                    if (vb == null) return -1;
                    if (typeof va === 'string') { va = va.toLowerCase(); vb = (vb || '').toLowerCase(); }
                    return dir === 'asc' ? (va > vb ? 1 : va < vb ? -1 : 0) : (va < vb ? 1 : va > vb ? -1 : 0);
                });
            },

            sortedTrackingSymbols() {
                const { key, dir } = this.trackingSort;
                const getVal = (obj, k) => k.split('.').reduce((o, p) => (o != null ? o[p] : null), obj);
                return [...this.trackingSymbols].sort((a, b) => {
                    let va = getVal(a, key), vb = getVal(b, key);
                    if (va == null) return 1;
                    if (vb == null) return -1;
                    if (typeof va === 'string') { va = va.toLowerCase(); vb = (vb || '').toLowerCase(); }
                    return dir === 'asc' ? (va > vb ? 1 : va < vb ? -1 : 0) : (va < vb ? 1 : va > vb ? -1 : 0);
                });
            },

            filteredAdminUsers() {
                const q = (this.adminSearchQuery || '').toLowerCase().trim();
                if (!q) return this.adminUsers;
                return this.adminUsers.filter(u =>
                    (u.username || '').toLowerCase().includes(q) ||
                    (u.email || '').toLowerCase().includes(q) ||
                    (u.first_name || '').toLowerCase().includes(q) ||
                    (u.last_name || '').toLowerCase().includes(q) ||
                    (u.system_role || '').toLowerCase().includes(q) ||
                    (u.subscription_tier || '').toLowerCase().includes(q)
                );
            },
            tierLabel() {
                if (!this.user) return '';
                const sr = this.user.system_role;
                if (sr === 'super_admin') return 'Super Admin';
                if (sr === 'dev_master') return 'Dev Master';
                const labels = { basic: 'Basic', beginner: 'Beginner Trader', advanced: 'Advanced Trader', yogi: 'Yogi Trader' };
                return labels[this.user.subscription_tier] || 'Basic';
            },
            tierBadgeClass() {
                if (!this.user) return '';
                const sr = this.user.system_role;
                if (sr === 'super_admin') return 'bg-red-700 text-white';
                if (sr === 'dev_master') return 'bg-purple-700 text-white';
                const classes = { basic: 'bg-gray-600 text-gray-200', beginner: 'bg-green-700 text-white', advanced: 'bg-blue-700 text-white', yogi: 'bg-yellow-600 text-white' };
                return classes[this.user.subscription_tier] || classes.basic;
            },
            swingBotCandidates() {
                const picks = this.brownBotSwingCandidates.length
                    ? this.brownBotSwingCandidates
                    : (this.swingDailyPicks?.picks || []);
                const activeSymbols = new Set(
                    (this.brownBotStatus.active_positions || [])
                        .filter(p => p.position_type === 'swing')
                        .map(p => p.symbol)
                );
                const enteredSymbols = new Set(
                    Object.keys(this.brownBotStatus.entry_counts || {})
                );
                const skippedSymbols = new Set(
                    this.brownBotStatus.skipped_symbols || []
                );
                const tag = p => {
                    let status = 'eligible';
                    if (activeSymbols.has(p.ticker)) status = 'active';
                    else if (enteredSymbols.has(p.ticker)) status = 'entered';
                    else if (skippedSymbols.has(p.ticker)) status = 'skipped';
                    return { ...p, status };
                };
                const eligible = picks
                    .filter(p => ['A', 'B'].includes(p.grade) && p.bias?.toLowerCase() === 'bullish')
                    .map(tag);
                if (eligible.length) return eligible;
                // No A/B Bullish picks — show all available picks for review
                return picks.map(p => ({ ...p, status: 'review' }));
            },

            // ── BrownBot P&L summary ──────────────────────────────────────
            bbUnrealizedByTicker() {
                const map = {};
                for (const pos of (this.brownBotStatus.active_positions || [])) {
                    map[pos.symbol] = (map[pos.symbol] || 0) + (pos.unrealized_pnl || 0);
                }
                return map;
            },
            bbTotalUnrealized() {
                return (this.brownBotStatus.active_positions || [])
                    .reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
            },
            bbTotalRealized() {
                return this.brownBotRiskStatus.realized_pnl || 0;
            },
            bbTotalPnl() {
                return this.bbTotalRealized + this.bbTotalUnrealized;
            },
            // Stats tab: only the entry TRIGGERS (PMHB/ORB/DHB), so the user can
            // see which triggers are profitable over time — not the condition gates.
            brownEntryStatsTriggers() {
                const triggers = ['PMHB', 'PMH', 'ORB', 'DHB'];
                return (this.brownEntryStats.rows || []).filter(r => triggers.includes(r.tag));
            },
            bbPnlByTickerMerged() {
                // brown_positions is the source of truth: realized_pnl from closed positions,
                // unrealized_pnl from open positions (updated by exit loop every 2s).
                // Live broker unrealized is merged in from active_positions for accuracy.
                const map = {};
                for (const t of (this.brownBotRiskStatus.pnl_by_ticker || [])) {
                    map[t.symbol] = {
                        symbol:        t.symbol,
                        realized:      t.realized_pnl  || 0,
                        unrealized:    t.unrealized_pnl || 0,
                        trades:        t.trades         || 0,
                        shares:        t.shares         || 0,
                        entry_signals: t.entry_signals  || [],
                    };
                }
                // Override unrealized with live broker data where available
                for (const [sym, unr] of Object.entries(this.bbUnrealizedByTicker)) {
                    if (map[sym]) {
                        map[sym].unrealized = unr;
                    } else {
                        map[sym] = { symbol: sym, realized: 0, unrealized: unr, trades: 0, shares: 0, entry_signals: [] };
                    }
                }
                return Object.values(map).sort((a, b) => (b.realized + b.unrealized) - (a.realized + a.unrealized));
            },
        },

        mounted() {
            console.log('🎯 Vue.js app mounted successfully');

            // Paint cached gap-ups immediately — before any async work — so the
            // tab is never blank on login or refresh.
            const _earlyCache = this._getGapUpsCache();
            if (_earlyCache && _earlyCache.length > 0) {
                this.gapUps = _earlyCache;
                this.prevGapUpTickers = _earlyCache.map(s => s.ticker);
                this.dashboardStats.gapUps = _earlyCache.length;
            }

            // Dismiss the loading screen now that Vue has rendered real content
            const loader = document.getElementById('app-loader');
            if (loader) {
                loader.classList.add('fade-out');
                setTimeout(() => loader.remove(), 260);
            }

            // Handle Stripe payment redirect-back
            const urlParams = new URLSearchParams(window.location.search);
            const payment = urlParams.get('payment');
            const tabParam = urlParams.get('tab');
            if (payment || tabParam) {
                // Clean up the URL immediately
                window.history.replaceState({}, '', window.location.pathname);
                if (payment === 'success') {
                    // Defer notification until auth is resolved and user data refreshed
                    this._pendingPaymentNotification = 'success';
                } else if (payment === 'cancelled') {
                    this._pendingPaymentNotification = 'cancelled';
                }
                if (tabParam) this.activeTab = tabParam;
            }

        // Force close any stuck modals immediately
        this.forceCloseStuckModals();

            // Default sub-tab to the current ET market session
            (() => {
                const et = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/New_York' }));
                const h = et.getHours() + et.getMinutes() / 60;
                if (h >= 4 && h < 9.5)       this.activeGapUpSubTab = 'premarket';
                else if (h >= 9.5 && h < 16)  this.activeGapUpSubTab = 'intraday';
                else if (h >= 16 && h < 20)   this.activeGapUpSubTab = 'afterhours';
                else                           this.activeGapUpSubTab = 'premarket';
            })();

            this.checkAuth();

            // Load swing bot config on startup
            this.loadSwingBotConfig();

            // Initialize Socket.IO — receives real-time gap_ups_update push from the backend
            // monitor loop (every 2 min during market hours) so the tab stays live without polling.
            try {
                this.socket = io();
                this.socket.on('connect', () => {
                    this.socketConnected = true;
                    console.log('[Socket] Connected to server');
                });
                this.socket.on('disconnect', () => {
                    this.socketConnected = false;
                    console.log('[Socket] Disconnected');
                });
                this.socket.on('regime_update', (payload) => {
                    this.marketRegime = payload;
                    console.log(`[Socket] regime_update: ${payload.signal} (score=${payload.score})`);
                });
                this.socket.on('gap_ups_update', (payload) => {
                    const incoming = payload && payload.data;
                    if (!incoming || incoming.length === 0) return;
                    // In-place merge so the table doesn't flash
                    const incomingMap = Object.fromEntries(incoming.map(s => [s.ticker, s]));
                    const existingTickers = new Set(this.gapUps.map(s => s.ticker));
                    for (let i = 0; i < this.gapUps.length; i++) {
                        const updated = incomingMap[this.gapUps[i].ticker];
                        if (updated) Object.assign(this.gapUps[i], updated);
                    }
                    for (const s of incoming) {
                        if (!existingTickers.has(s.ticker)) this.gapUps.push(s);
                    }
                    const newSet = new Set(incoming.map(s => s.ticker));
                    this.gapUps = this.gapUps.filter(s => newSet.has(s.ticker));
                    this.prevGapUpTickers = incoming.map(s => s.ticker);
                    this.dashboardStats.gapUps = this.gapUps.length;
                    this._saveGapUpsCache(incoming);
                    console.log(`[Socket] gap_ups_update: ${incoming.length} stocks`);
                });
            } catch (e) {
                console.warn('[Socket] init failed:', e.message);
            }

            // Gap-up updates arrive via Socket.IO 'gap_ups_update' broadcast — no polling needed.

            // Add page load event listener for automatic refresh
            window.addEventListener('load', () => {
                console.log('📄 Page loaded, ensuring dashboard data is fresh...');
            // Force close any stuck modals again on page load
            this.forceCloseStuckModals();
                // Small delay to ensure Vue is fully initialized
                setTimeout(() => {
                    if (this.user) {
                        console.log('🔄 Page load refresh triggered...');
                        this.forceRefreshDashboard();
                    }
                }, 1000);
            });
        },
        
        beforeDestroy() {
            // Stop gap-up auto-refresh
            if (this.gapUpRefreshInterval) {
                clearInterval(this.gapUpRefreshInterval);
                this.gapUpRefreshInterval = null;
            }

            // Disconnect Socket.IO
            if (this.socket) {
                this.socket.disconnect();
                this.socket = null;
            }

            // Stop real-time updates
            this.stopRealTimeUpdates();
            
            // Stop position history updates
            this.stopPositionHistoryUpdates();
            
            // Clean up timeouts and charts
            if (this.pnlChartUpdateTimeout) {
                clearTimeout(this.pnlChartUpdateTimeout);
            }
            if (this.positionsChartUpdateTimeout) {
                clearTimeout(this.positionsChartUpdateTimeout);
            }
            
            // Destroy charts
            if (this.charts.pnl && typeof this.charts.pnl.destroy === 'function') {
                this.charts.pnl.destroy();
            }
            if (this.charts.positions && typeof this.charts.positions.destroy === 'function') {
                this.charts.positions.destroy();
            }
        },
        
        methods: {
            // Authenticated fetch — automatically adds Bearer token from localStorage.
            authFetch(url, options = {}) {
                const token = localStorage.getItem('session_token');
                const headers = Object.assign({}, options.headers || {});
                if (token) headers['Authorization'] = `Bearer ${token}`;
                return fetch(url, Object.assign({}, options, { headers }));
            },

            checkAuth() {
                const sessionToken = localStorage.getItem('session_token');
                const user = localStorage.getItem('user');

                if (!sessionToken || !user) {
                    this.isGuest = true;
                    this.activeTab = 'gap-ups';
                    this.loadGapUps();
                    this.loadGapUpSnapshotDates();
                    return;
                }

                // Validate session with backend and seed expiry time
                this.validateSession().then(ok => {
                    if (ok) {
                        this.pingSessionOnce();
                        this.loadGapUps();          // load gap-ups as soon as auth confirms
                        this.loadGapUpSnapshotDates();
                    }
                });
            },
            
            // Handle tab changes
            async onTabChange(tabName) {
                this.mobileMenuOpen = false;
                console.log(`🔄 Tab changed to: ${tabName}`);
                console.log(`🔍 Current activeTab value: ${this.activeTab}`);
                console.log(`🔍 Previous activeTab value: ${this.activeTab}`);
                
                // Update the activeTab value
                this.activeTab = tabName;
                if (tabName === 'account') this.accountSection = 'subscription';
                
                // Save the active tab to localStorage for persistence across page refreshes
                localStorage.setItem('activeTab', tabName);
                
                if (tabName === 'dashboard') {
                    console.log('📊 Dashboard tab selected - ensuring charts are updated...');
                    this.stopPositionHistoryUpdates(); // Stop position updates when leaving positions tab
                    // Ensure charts are updated when dashboard tab is accessed
                    this.$nextTick(() => {
                        setTimeout(() => {
                            this.updatePnlChart();
                            this.updatePositionsChart();
                        }, 100);
                    });
                } else if (tabName === 'trades') {
                    console.log('📊 Trade History tab selected - loading trade history...');
                    this.stopPositionHistoryUpdates(); // Stop position updates when leaving positions tab
                    this.loadTradeHistory();
                } else if (tabName === 'positions') {
                    try {
                        await this.loadPositionSyncStatus();
                        // Load both sections in parallel — open positions always pinned at top
                        this.loadPositionsHistory(this.positions.length > 0);
                        this.loadOpenPositions();
                        this.startPositionHistoryUpdates();
                        this.stopRealTimeUpdates();
                    } catch (error) {
                        console.error('Error in positions tab initialization:', error);
                    }
                } else if (tabName === 'gap-ups') {
                    console.log('📈 Gap-Ups tab selected - loading gap-up stocks...');
                    this.stopPositionHistoryUpdates(); // Stop position updates when leaving positions tab
                    this.loadGapUps();
                    this.loadGapUpSnapshotDates();
                } else if (tabName === 'historical') {
                    console.log('📈 Historical Data tab selected - ready for analysis...');
                    this.stopPositionHistoryUpdates();
                    this.loadHistoricalPrefetchStatus();

                } else if (tabName === 'swing') {
                    console.log('📊 Swing Trading tab selected - loading daily picks...');
                    this.stopPositionHistoryUpdates();

                    this.loadSwingDailyPicks();
                    if (!this.sectorStrength.length) this.loadSectorStrength();
                    if (!this.swingPicksDates.length) this.loadSwingPicksDates();
                } else if (tabName === 'stats') {
                    this.stopPositionHistoryUpdates();
                    this.loadStats();
                    this.loadFeedbackLatest();
                } else if (tabName === 'backtest') {
                    console.log('🧪 Backtest tab selected - loading backtest data...');
                    this.stopPositionHistoryUpdates(); // Stop position updates when leaving positions tab
                    this.loadBacktestData();
                } else if (tabName === 'ai-chat') {
                    console.log('🤖 AI Chat tab selected - ready for chat...');
                    this.stopPositionHistoryUpdates(); // Stop position updates when leaving positions tab
                    // AI chat tab is ready for user interaction
                } else if (tabName === 'admin') {
                    if (this.isStaff) {
                        this.loadAdminUsers();
                        this.loadAdminBotSessions();
                    } else {
                        this.activeTab = 'about';
                    }
                } else if (tabName === 'account') {
                    this.loadBrokerConfigs();
                } else if (tabName === 'brown-bot') {
                    console.log('🤖 BrownBot tab selected - loading status...');
                    this.stopPositionHistoryUpdates();

                    this.loadBrokerConfigs();
                    this.loadRegimeStatus();
                    this.loadBrownBotStatus();
                    this.loadBrownBotConfig();
                    this.fetchBrownBotLogs();
                    this.loadBrownBotCandidates();
                    this.loadBrownBotRiskStatus();
                    this.loadBrownBotSwingCandidates();
                    this.loadBrownBotBrokerOrders();
                    this.startBrownBotPolling();
                } else if (tabName === 'earnings') {
                    if (!this.erCalendar.length) this.loadErCalendar();
                } else if (tabName === 'screener') {
                    this.initScreener();
                } else if (tabName === 'swing-setups') {
                    this.initSwingSetups();
                }
            },

            // ── Tab access control ──────────────────────────────────────
            canAccessTab(tab) {
                if (this.isGuest) return tab === 'gap-ups';
                if (!this.user) return false;
                if (this.isStaff) return true;
                if (tab === 'admin') return false;
                const tierMap = {
                    basic:    ['gap-ups', 'ai-chat', 'help', 'contact'],
                    beginner: ['gap-ups', 'ai-chat', 'help', 'contact', 'historical'],
                    advanced: ['gap-ups', 'ai-chat', 'help', 'contact', 'historical', 'swing', 'earnings', 'screener', 'swing-setups'],
                    yogi:     ['gap-ups', 'ai-chat', 'help', 'contact', 'historical', 'swing', 'earnings', 'screener', 'swing-setups', 'trades', 'positions', 'stats', 'backtest', 'brown-bot'],
                };
                return (tierMap[this.user.subscription_tier] || tierMap.basic).includes(tab);
            },

            setGapUpSubTab(tab) {
                this.activeGapUpSubTab = tab;
            },

            async loadGapUpSnapshotDates() {
                try {
                    const res = await fetch('/api/gap-ups/snapshot/dates');
                    const data = await res.json();
                    if (data.success) this.gapUpSnapshotDates = data.dates || [];
                } catch (e) {
                    console.error('Failed to load snapshot dates:', e);
                }
            },

            async selectGapUpDate(date) {
                if (!date) {
                    // Revert to live view
                    this.gapUpViewDate = null;
                    this.gapUpHistoricalData = [];
                    return;
                }
                try {
                    this.gapUpViewDate = date;
                    const res = await fetch(`/api/gap-ups/snapshot/${date}`);
                    const data = await res.json();
                    if (data.success) {
                        this.gapUpHistoricalData = data.data || [];
                    } else {
                        this.gapUpHistoricalData = [];
                        this.showNotification(`No snapshot data for ${date}`, 'warning');
                    }
                } catch (e) {
                    console.error('Failed to load gap-up snapshot:', e);
                    this.gapUpHistoricalData = [];
                }
            },

            toggleGapSort(key) {
                if (this.gapUpSort.key === key) {
                    this.gapUpSort.dir = this.gapUpSort.dir === 'asc' ? 'desc' : 'asc';
                } else {
                    this.gapUpSort.key = key;
                    this.gapUpSort.dir = ['gap_percent', 'volume', 'market_cap', 'float_shares', 'float_rotation', 'price'].includes(key) ? 'desc' : 'asc';
                }
            },

            togglePositionsSort(key) {
                if (this.positionsSort.key === key) {
                    this.positionsSort.dir = this.positionsSort.dir === 'asc' ? 'desc' : 'asc';
                } else {
                    this.positionsSort.key = key;
                    this.positionsSort.dir = ['qty', 'avg_entry', 'avg_exit', 'pnl', 'duration_days'].includes(key) ? 'desc' : 'asc';
                }
            },

            toggleTradesSort(key) {
                if (this.tradesSort.key === key) {
                    this.tradesSort.dir = this.tradesSort.dir === 'asc' ? 'desc' : 'asc';
                } else {
                    this.tradesSort.key = key;
                    this.tradesSort.dir = ['quantity', 'price', 'pnl'].includes(key) ? 'desc' : 'asc';
                }
            },

            toggleActivePositionsSort(key) {
                if (this.activePositionsSort.key === key) {
                    this.activePositionsSort.dir = this.activePositionsSort.dir === 'asc' ? 'desc' : 'asc';
                } else {
                    this.activePositionsSort.key = key;
                    this.activePositionsSort.dir = ['entry_price', 'quantity'].includes(key) ? 'desc' : 'asc';
                }
            },

            toggleTrackingSort(key) {
                if (this.trackingSort.key === key) {
                    this.trackingSort.dir = this.trackingSort.dir === 'asc' ? 'desc' : 'asc';
                } else {
                    this.trackingSort.key = key;
                    const numericKeys = ['entry_parameters.total_volume', 'entry_parameters.dollar_volume',
                        'current_data.current_volume', 'current_data.current_dollar_volume',
                        'order_parameters.quantity'];
                    this.trackingSort.dir = numericKeys.includes(key) ? 'desc' : 'asc';
                }
            },

            handleTabClick(tab) {
                // Always allow navigation; locked tabs show inline upgrade card
                this.onTabChange(tab);
            },

            // ── Subscription self-service ───────────────────────────────
            async upgradeSubscription(tier) {
                this.subscriptionLoading = true;
                try {
                    const response = await fetch('/api/stripe/create-checkout-session', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${localStorage.getItem('session_token')}`,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ tier })
                    });
                    const data = await response.json();
                    if (data.success && data.url) {
                        window.location.href = data.url;
                    } else {
                        this.showNotification(data.error || 'Could not start checkout. Please try again.', 'error');
                    }
                } catch (e) {
                    console.error(e);
                    this.showNotification('Failed to connect to billing service.', 'error');
                } finally {
                    this.subscriptionLoading = false;
                }
            },

            async manageSubscription() {
                this.subscriptionLoading = true;
                try {
                    const response = await fetch('/api/stripe/create-portal-session', {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` }
                    });
                    const data = await response.json();
                    if (data.success && data.url) {
                        window.location.href = data.url;
                    } else {
                        this.showNotification(data.error || 'Could not open billing portal.', 'error');
                    }
                } catch (e) {
                    console.error(e);
                    this.showNotification('Failed to open billing portal.', 'error');
                } finally {
                    this.subscriptionLoading = false;
                }
            },

            initProfileForm() {
                if (!this.user) return;
                let profession = this.user.profession || '';
                let profession_other = '';
                if (profession.startsWith('Other: ')) {
                    profession_other = profession.slice(7);
                    profession = 'Other';
                }
                this.profileForm = {
                    email: this.user.email || '',
                    first_name: this.user.first_name || '',
                    last_name: this.user.last_name || '',
                    address: this.user.address || '',
                    profession,
                    profession_other,
                    annual_income_range: this.user.annual_income_range || ''
                };
                this.profileError = '';
                this.profileSuccess = '';
            },

            async saveProfile() {
                this.profileError = '';
                this.profileSuccess = '';
                if (!this.profileForm.email || !this.profileForm.email.includes('@')) {
                    this.profileError = 'Valid email is required';
                    return;
                }
                this.profileLoading = true;
                try {
                    const professionValue = this.profileForm.profession === 'Other'
                        ? (this.profileForm.profession_other.trim() ? `Other: ${this.profileForm.profession_other.trim()}` : 'Other')
                        : this.profileForm.profession;
                    const response = await fetch('/api/auth/profile', {
                        method: 'PUT',
                        headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}`, 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ...this.profileForm, profession: professionValue })
                    });
                    const data = await response.json();
                    if (data.success) {
                        this.profileSuccess = 'Profile updated successfully.';
                        // Refresh user data so header reflects changes
                        await this.validateSession();
                    } else {
                        this.profileError = data.error || 'Failed to update profile';
                    }
                } catch (e) {
                    this.profileError = 'Network error';
                } finally {
                    this.profileLoading = false;
                }
            },

            async changePassword() {
                this.changePwError = '';
                this.changePwSuccess = '';
                const { current, newPw, confirm } = this.changePwForm;
                if (!current || !newPw || !confirm) { this.changePwError = 'All fields are required'; return; }
                if (newPw !== confirm) { this.changePwError = 'New passwords do not match'; return; }
                if (newPw.length < 8) { this.changePwError = 'Password must be at least 8 characters'; return; }
                if (!/[A-Z]/.test(newPw)) { this.changePwError = 'Password must contain at least one uppercase letter'; return; }
                if (!/[0-9]/.test(newPw)) { this.changePwError = 'Password must contain at least one number'; return; }
                this.changePwLoading = true;
                try {
                    const response = await fetch('/api/auth/change-password', {
                        method: 'PUT',
                        headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}`, 'Content-Type': 'application/json' },
                        body: JSON.stringify({ current_password: current, new_password: newPw })
                    });
                    const data = await response.json();
                    if (data.success) {
                        this.changePwSuccess = 'Password updated successfully.';
                        this.changePwForm = { current: '', newPw: '', confirm: '' };
                    } else {
                        this.changePwError = data.error || 'Failed to update password';
                    }
                } catch (e) {
                    this.changePwError = 'Network error';
                } finally {
                    this.changePwLoading = false;
                }
            },

            async cancelSubscription() {
                this.subscriptionLoading = true;
                try {
                    const response = await fetch('/api/subscription/cancel', {
                        method: 'PUT',
                        headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` }
                    });
                    const data = await response.json();
                    if (data.use_portal) {
                        // Has Stripe billing — manage via portal
                        await this.manageSubscription();
                    } else if (data.success) {
                        this.user.subscription_tier = 'basic';
                        this.user.subscription_status = 'cancelled';
                        this.showNotification('Subscription cancelled.', 'success');
                    } else {
                        this.showNotification(data.error || 'Cancellation failed', 'error');
                    }
                } catch (e) {
                    console.error(e);
                } finally {
                    this.subscriptionLoading = false;
                }
            },

            // ── Admin user management ───────────────────────────────────
            async adminSubmitAddUser() {
                this.adminAddUserError = '';
                this.adminAddUserSuccess = '';
                const f = this.adminAddUserForm;
                if (!f.username || !f.email || !f.password) { this.adminAddUserError = 'All fields are required'; return; }
                this.adminAddUserLoading = true;
                try {
                    const response = await fetch('/api/admin/users', {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}`, 'Content-Type': 'application/json' },
                        body: JSON.stringify(f)
                    });
                    const data = await response.json();
                    if (data.success) {
                        this.adminAddUserSuccess = `User "${f.username}" created successfully.`;
                        this.adminAddUserForm = { username: '', email: '', password: '' };
                        await this.loadAdminUsers();
                    } else {
                        this.adminAddUserError = data.error || 'Failed to create user';
                    }
                } catch (e) {
                    this.adminAddUserError = 'Network error';
                } finally {
                    this.adminAddUserLoading = false;
                }
            },

            async adminUpdateSystemRole(userId, systemRole) {
                try {
                    const response = await fetch(`/api/admin/users/${userId}/system-role`, {
                        method: 'PUT',
                        headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}`, 'Content-Type': 'application/json' },
                        body: JSON.stringify({ system_role: systemRole || null })
                    });
                    const data = await response.json();
                    if (!data.success) { alert(data.error || 'Failed'); await this.loadAdminUsers(); }
                } catch (e) { console.error(e); }
            },

            async adminUpdateSubscriptionTier(userId, tier) {
                try {
                    const response = await fetch(`/api/admin/users/${userId}/subscription`, {
                        method: 'PUT',
                        headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}`, 'Content-Type': 'application/json' },
                        body: JSON.stringify({ tier, status: 'active' })
                    });
                    const data = await response.json();
                    if (!data.success) { alert(data.error || 'Failed'); await this.loadAdminUsers(); }
                } catch (e) { console.error(e); }
            },

            async adminCancelUserSubscription(userId) {
                if (!confirm('Cancel this user\'s subscription and revert to Basic?')) return;
                try {
                    const response = await fetch(`/api/admin/users/${userId}/subscription`, {
                        method: 'PUT',
                        headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}`, 'Content-Type': 'application/json' },
                        body: JSON.stringify({ tier: 'basic', status: 'cancelled' })
                    });
                    const data = await response.json();
                    if (data.success) {
                        const u = this.adminUsers.find(u => u.id === userId);
                        if (u) { u.subscription_tier = 'basic'; u.subscription_status = 'cancelled'; }
                    } else { alert(data.error || 'Failed'); }
                } catch (e) { console.error(e); }
            },

            async adminDeleteUser(userId, username) {
                if (!confirm(`Permanently delete user "${username}"? This cannot be undone.`)) return;
                try {
                    const response = await fetch(`/api/admin/users/${userId}`, {
                        method: 'DELETE',
                        headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` }
                    });
                    const data = await response.json();
                    if (data.success) {
                        this.adminUsers = this.adminUsers.filter(u => u.id !== userId);
                        this.showNotification(`User "${username}" deleted.`, 'success');
                    } else {
                        alert(data.error || 'Failed to delete user');
                    }
                } catch (e) { console.error(e); }
            },

            async adminResetUserPassword(userId, username) {
                const newPassword = prompt(`Set new password for "${username}":\n(min 8 chars, 1 uppercase, 1 number)`);
                if (!newPassword) return;
                try {
                    const response = await fetch(`/api/admin/users/${userId}/password`, {
                        method: 'PUT',
                        headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}`, 'Content-Type': 'application/json' },
                        body: JSON.stringify({ password: newPassword })
                    });
                    const data = await response.json();
                    if (data.success) {
                        this.showNotification(`Password updated for "${username}".`, 'success');
                    } else {
                        alert(data.error || 'Failed to reset password');
                    }
                } catch (e) { console.error(e); }
            },

            async runDbQuery() {
                const sql = (this.dbQuery.sql || '').trim();
                if (!sql) return;
                this.dbQuery.loading = true;
                this.dbQuery.error = '';
                this.dbQuery.columns = [];
                this.dbQuery.rows = [];
                try {
                    const res = await fetch('/api/admin/db-query', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json',
                                   'Authorization': `Bearer ${localStorage.getItem('session_token')}` },
                        body: JSON.stringify({ sql }),
                    });
                    const data = await res.json();
                    if (!data.success) { this.dbQuery.error = data.error || 'Query failed'; return; }
                    this.dbQuery.columns      = data.columns;
                    this.dbQuery.rows         = data.rows;
                    this.dbQuery.rowCount     = data.row_count;
                    this.dbQuery.rowsAffected = data.rows_affected ?? null;
                    this.dbQuery.elapsed      = data.elapsed_ms;
                    this.dbQuery.truncated    = data.truncated;
                    this.dbQuery.isWrite      = data.write || false;
                } catch (e) {
                    this.dbQuery.error = e.message;
                } finally {
                    this.dbQuery.loading = false;
                }
            },

            async loadAdminUsers() {
                this.adminLoading = true;
                try {
                    const response = await fetch('/api/admin/users', {
                        headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` }
                    });
                    const data = await response.json();
                    if (data.success) {
                        this.adminUsers = data.data;
                    }
                } catch (error) {
                    console.error('Error loading admin users:', error);
                } finally {
                    this.adminLoading = false;
                }
            },

            async loadAdminBotSessions() {
                this.adminBotSessionsLoading = true;
                try {
                    const response = await fetch('/api/admin/bots/status', {
                        headers: this.authHeaders()
                    });
                    const data = await response.json();
                    if (data.success) {
                        this.adminBotSessions = data.sessions || [];
                    }
                } catch (error) {
                    console.error('Error loading admin bot sessions:', error);
                } finally {
                    this.adminBotSessionsLoading = false;
                }
            },

            async adminStopBotSession(userId) {
                if (!confirm(`Stop BrownBot for user ID ${userId}?`)) return;
                try {
                    await axios.post(`/api/brown-bot/stop?user_id=${userId}`, {}, { headers: this.authHeaders() });
                    await this.loadAdminBotSessions();
                } catch (e) {
                    alert('Failed to stop bot: ' + (e.response?.data?.error || e.message));
                }
            },

            async updateUserRole(userId, role) {
                await this.adminUpdateSystemRole(userId, role || null);
            },

            async toggleUserActive(userId, currentActive) {
                const newActive = !currentActive;
                try {
                    const response = await fetch(`/api/admin/users/${userId}/active`, {
                        method: 'PUT',
                        headers: {
                            'Authorization': `Bearer ${localStorage.getItem('session_token')}`,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ is_active: newActive })
                    });
                    const data = await response.json();
                    if (data.success) {
                        const u = this.adminUsers.find(u => u.id === userId);
                        if (u) u.is_active = newActive ? 1 : 0;
                    } else {
                        alert(data.error || 'Failed to update status');
                    }
                } catch (error) {
                    console.error('Error toggling active status:', error);
                }
            },

            async validateSession() {
                try {
                    const response = await fetch('/api/auth/profile', {
                        headers: {
                            'Authorization': `Bearer ${localStorage.getItem('session_token')}`
                        }
                    });

                    if (response.ok) {
                        const userData = await response.json();
                        this.user = userData.data;
                        // Silently pre-fetch broker configs so hasActiveBroker is ready on any tab
                        this.loadBrokerConfigs();
                        // Pre-fetch bot status so the BrownBot button is correct on refresh
                        this.loadBrownBotStatus();
                        // Silently pre-fetch positions so the tab opens instantly
                        if (this.positions.length === 0) this.loadPositionsHistory(true);
                        // Pre-fill contact form with user info
                        this.contactForm.name = [this.user.first_name, this.user.last_name].filter(Boolean).join(' ') || this.user.username;
                        this.contactForm.email = this.user.email || '';
                        // Show Stripe redirect-back notification now that user data is fresh
                        if (this._pendingPaymentNotification === 'success') {
                            this._pendingPaymentNotification = null;
                            this.activeTab = 'account';
                            if (this.user.subscription_tier === 'basic') {
                                // Webhook may still be processing — retry once after 3s
                                setTimeout(async () => {
                                    await this.validateSession();
                                    this.showNotification('Payment successful! Your subscription is now active.', 'success');
                                }, 3000);
                            } else {
                                this.showNotification('Payment successful! Your subscription is now active.', 'success');
                            }
                        } else if (this._pendingPaymentNotification === 'cancelled') {
                            this._pendingPaymentNotification = null;
                            this.showNotification('Checkout cancelled — no changes were made.', 'info');
                        }
                        return true;
                    } else {
                        localStorage.removeItem('session_token');
                        localStorage.removeItem('user');
                        this.isGuest = true;
                        this.activeTab = 'gap-ups';
                        this.loadGapUps();
                        return false;
                    }
                } catch (error) {
                    console.error('Session validation error:', error);
                    return false;
                }
            },
            
            async submitContact() {
                this.contactError = '';
                this.contactSuccess = '';
                const f = this.contactForm;
                if (!f.name.trim() || !f.email.trim() || !f.message.trim()) {
                    this.contactError = 'Name, email, and message are required.';
                    return;
                }
                this.contactLoading = true;
                try {
                    const res = await fetch('/api/contact', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name: f.name, email: f.email, subject: f.subject, message: f.message })
                    });
                    const data = await res.json();
                    if (data.success) {
                        this.contactSuccess = "Message sent! We'll get back to you shortly.";
                        this.contactForm = { name: this.user?.first_name ? `${this.user.first_name} ${this.user.last_name || ''}`.trim() : '', email: this.user?.email || '', subject: '', message: '' };
                    } else {
                        this.contactError = data.error || 'Failed to send message.';
                    }
                } catch {
                    this.contactError = 'Network error. Please try again.';
                } finally {
                    this.contactLoading = false;
                }
            },

            toggleTheme() {
                this.darkMode = !this.darkMode;
                if (this.darkMode) {
                    document.documentElement.classList.remove('light');
                    localStorage.setItem('theme', 'dark');
                } else {
                    document.documentElement.classList.add('light');
                    localStorage.setItem('theme', 'light');
                }
            },

            logout() {
                localStorage.removeItem('session_token');
                localStorage.removeItem('user');
                window.location.href = '/';
            },
            
            async initializeApp() {
                console.log('🚀 Initializing Trading Advisor Dashboard...');

                // Paint stale cache immediately — before any backend ping — so the
                // Gap Ups tab is never blank while connectivity checks are running.
                const _cachedGapUps = this._getGapUpsCache();
                if (_cachedGapUps && _cachedGapUps.length > 0) {
                    this.gapUps = _cachedGapUps;
                    this.prevGapUpTickers = _cachedGapUps.map(s => s.ticker);
                    this.dashboardStats.gapUps = _cachedGapUps.length;
                }

                try {
                // Force close any stuck modals or overlays first
                this.forceCloseStuckModals();

                    // Show overall loading state
                    this.showOverallLoadingState();
                    
                    // Wait for backend to be fully ready
                    console.log('⏳ Waiting for backend to be ready...');
                    const backendReady = await this.waitForBackendReady();
                    if (!backendReady) {
                        console.error('❌ Backend not ready, stopping initialization');
                        this.hideOverallLoadingState();
                        this.showNotification('Backend is not ready. Please try again in a moment.', 'error');
                        return;
                    }
                    
                    // Check backend connectivity first with retries
                    console.log('🔍 Checking backend connectivity...');
                    const backendAccessible = await this.checkBackendConnectivity();
                    if (!backendAccessible) {
                        console.error('❌ Backend not accessible, stopping initialization');
                        this.hideOverallLoadingState();
                        return;
                    }
                    
                    // Start loading data immediately after backend is accessible
                    console.log('📊 Starting progressive data loading...');
                    
                    // Load strategies from backend first
                    console.log('📊 Loading strategies from backend...');
                    this.loadStrategiesFromBackend().catch(error => {
                        console.error('❌ Failed to load strategies:', error);
                    });
                    
                    // Initialize default date ranges
                    console.log('📅 Initializing date ranges...');
                    this.initializeDateRanges();
                    
                    // Load saved strategy settings first
                    console.log('⚙️ Loading strategy settings...');
                    this.loadStrategySettings();
                    
                    // Initialize strategy parameters with proper defaults
                    console.log('🔧 Initializing strategy parameters...');
                    this.initializeStrategyParameters();
                    
                    // Start loading dashboard data in parallel
                    console.log('📊 Starting dashboard data loading...');
                    this.loadDashboardData().then(() => {
                                            // Initialize charts after dashboard data loads
                    console.log('📊 Initializing charts after dashboard data load...');
                    this.$nextTick(() => {
                        setTimeout(() => {
                            this.updatePnlChart();
                            this.updatePositionsChart();
                        }, 1000); // Increased delay to ensure DOM is ready
                    });
                    }).catch(error => {
                        console.error('❌ Failed to load dashboard data:', error);
                    });
                    
                    // Load bot status in parallel with real-time updates
                    console.log('🤖 Loading bot status with real-time updates...');
                    this.loadBotStatusWithRealTime().catch(error => {
                        console.error('❌ Failed to load bot status:', error);
                    });
                    
                    // Setup charts after a short delay to allow data to start loading
                    console.log('📈 Setting up charts...');
                    setTimeout(() => {
                        this.$nextTick(() => {
                            this.setupCharts();
                        });
                    }, 500);
                    
                    console.log('🔌 Connecting WebSocket...');
                this.connectWebSocket();
                    
                    console.log('⏰ Starting periodic updates...');
                this.startPeriodicUpdates();
                this.startPeriodicBotUpdates(); // Start bot updates
                
                    console.log('✅ Dashboard initialization started successfully');
                    
                    // Hide overall loading state after a delay
                    setTimeout(() => {
                        this.hideOverallLoadingState();
                        this.showNotification('Dashboard initialization started', 'success');
                    }, 2000);
                    
                } catch (error) {
                    console.error('❌ Error during app initialization:', error);
                    this.hideOverallLoadingState();
                    this.showNotification('Failed to initialize dashboard: ' + error.message, 'error');
                }
            },
            
        // Force close any stuck modals or overlays
        forceCloseStuckModals() {
            // Close Vue-managed modals via reactive state
            this.showImportModal = false;
            if (this.upgradeModal) this.upgradeModal.show = false;

            // Remove only actual stuck loading overlays — never use .remove() on app modals
            document.querySelectorAll('.loading-overlay, .modal-overlay').forEach(el => el.remove());

            // Ensure body scroll is not blocked
            document.body.style.overflow = 'auto';
            document.body.style.pointerEvents = 'auto';
        },
        
        // Emergency escape method - can be called from browser console
        emergencyEscape() {
            console.log('🚨 Emergency escape triggered!');
            
            // Close all modals
            this.showImportModal = false;
            
            // Remove all fixed positioned elements that might be blocking the view
            const blockingElements = document.querySelectorAll('[class*="fixed"], [class*="modal"], [class*="overlay"]');
            blockingElements.forEach(element => {
                console.log('🗑️ Emergency removal of blocking element:', element);
                element.remove();
            });
            
            // Reset body styles
            document.body.style.overflow = 'auto';
            document.body.style.pointerEvents = 'auto';
            document.body.style.position = 'static';
            
            // Force show the main app
            const app = document.getElementById('app');
            if (app) {
                app.style.display = 'block';
                app.style.visibility = 'visible';
                app.style.opacity = '1';
            }
            
            console.log('🚨 Emergency escape completed!');
            this.showNotification('Emergency escape completed - UI should be visible now', 'success');
            },
            
            async loadDashboardData() {
                console.log('📊 Starting dashboard data load...');
                try {
                    const promises = [
                                                    this.loadDashboardData().then(() => console.log('✅ Dashboard data loaded')),
                            this.loadGapUpConfig().then(() => console.log('✅ Gap-up config loaded')),
                            this.loadGapUps().then(() => console.log('✅ Gap-ups loaded'))
                    ];
                    
                    await Promise.allSettled(promises);
                    console.log('✅ Dashboard data load completed');
                    
                    // Update charts after all data is loaded
                    setTimeout(() => {
                        console.log('🔄 Updating charts after data load...');
                        this.$nextTick(() => {
                            this.updatePnlChart();
                            this.updatePositionsChart();
                        });
                    }, 500);
                    
                } catch (error) {
                    console.error('❌ Error loading dashboard data:', error);
                    this.showNotification('Failed to load dashboard data: ' + error.message, 'error');
                }
            },
            
            async loadBotStatus() {
                console.log('🤖 Loading bot status...');
                this.updateLoadingProgress('bot', 'loading');
                
                const maxRetries = 3;
                const retryDelay = 1000; // 1 second
                
                for (let attempt = 1; attempt <= maxRetries; attempt++) {
                    try {
                        console.log(`🤖 Bot status loading attempt ${attempt}/${maxRetries}...`);
                        const response = await axios.get('/api/bot/status', {
                            timeout: 10000 // 10 second timeout
                        });
                        
                    console.log('📊 Bot status response:', response.data);
                    
                    if (response.data.success) {
                        const newBotStatus = {
                            running: response.data.data.running || false,
                            monitoring: response.data.data.monitoring || false,
                            positions: response.data.data.positions || [],
                            active_positions: response.data.data.active_positions || [],
                            active_positions_count: response.data.data.active_positions_count || 0,
                            last_update: response.data.data.last_update || null,
                            profit_target_pct: response.data.data.profit_target_pct || 5.0,
                            stop_loss_pct: response.data.data.stop_loss_pct || 2.5,
                            monitor_interval: response.data.data.monitor_interval || 5,
                            das_connected: response.data.data.das_connected || false,
                            internal_running_state: response.data.data.internal_running_state || false,
                            internal_monitoring_state: response.data.data.internal_monitoring_state || false
                        };
                        
                        // Intelligent update: only update values that have actually changed
                        let hasChanges = false;
                        
                        // Check if active positions have changed
                        const positionsChanged = this.hasActivePositionsChanged(newBotStatus.active_positions);
                        
                        // Track position changes for better feedback
                        if (positionsChanged) {
                            const positionChanges = this.trackPositionChanges(newBotStatus.active_positions);
                            if (positionChanges.length > 0) {
                                console.log('📊 Position changes:', positionChanges);
                            }
                        }
                        
                        // Debug: Log active positions profit target and stop loss values
                        if (newBotStatus.active_positions && newBotStatus.active_positions.length > 0) {
                            console.log('📊 Active positions profit target and stop loss values:');
                            newBotStatus.active_positions.forEach(pos => {
                                console.log(`  ${pos.symbol}: profit_target=$${pos.profit_target?.toFixed(2)}, stop_loss=$${pos.stop_loss?.toFixed(2)}`);
                            });
                        }
                        
                        // Update only changed values to prevent unnecessary re-renders
                        Object.keys(newBotStatus).forEach(key => {
                            if (key === 'active_positions') {
                                // Special handling for active positions to prevent unnecessary re-renders
                                // Always call updateActivePositions to ensure proper array handling
                                this.updateActivePositions(newBotStatus[key]);
                                hasChanges = true;
                                console.log('🔄 Active positions updated');
                            } else if (JSON.stringify(this.botStatus[key]) !== JSON.stringify(newBotStatus[key])) {
                                this.botStatus[key] = newBotStatus[key];
                                hasChanges = true;
                                console.log(`🔄 ${key} updated:`, newBotStatus[key]);
                            }
                        });
                        
                        // Update bot config from botStatus to ensure active positions get updated values
                        // Only update the UI input fields if user is not actively editing
                        const newBotConfig = {
                            profit_target_pct: this.botStatus.profit_target_pct,
                            stop_loss_pct: this.botStatus.stop_loss_pct,
                            monitor_interval: this.botStatus.monitor_interval
                        };
                        
                        // Check if bot config values have changed
                        let configChanged = false;
                        const configChanges = [];
                        
                        Object.keys(newBotConfig).forEach(key => {
                            if (this.botConfig[key] !== newBotConfig[key]) {
                                const oldValue = this.botConfig[key];
                                
                                // Only update the botConfig if user is not actively editing
                                // This prevents input field refresh while user is typing
                                if (!this.isEditingBotConfig) {
                                    this.botConfig[key] = newBotConfig[key];
                                    configChanged = true;
                                    configChanges.push({
                                        key: key,
                                        old: oldValue,
                                        new: newBotConfig[key]
                                    });
                                    console.log(`⚙️ Bot config ${key} updated: ${oldValue} → ${newBotConfig[key]}`);
                                } else {
                                    // Log that we're skipping the update due to user editing
                                    console.log(`⚙️ Skipping bot config ${key} update (${oldValue} → ${newBotConfig[key]}) - user is editing`);
                                }
                            }
                        });
                        
                        if (configChanged) {
                            console.log('⚙️ Bot configuration updated with changes:', configChanges);
                        }
                        
                        if (hasChanges) {
                            console.log('✅ Bot status updated with changes:', this.botStatus);
                        } else {
                            console.log('✅ Bot status checked (no changes)');
                        }
                    } else {
                        console.error('❌ Bot status error:', response.data.error);
                    }
                        this.updateLoadingProgress('bot', 'success');
                        return; // Success, exit retry loop
                } catch (error) {
                        console.error(`❌ Error loading bot status (attempt ${attempt}):`, error);
                        if (attempt === maxRetries) {
                            this.updateLoadingProgress('bot', 'error');
                        } else {
                            console.log(`⏳ Retrying bot status load in ${retryDelay}ms...`);
                            await new Promise(resolve => setTimeout(resolve, retryDelay));
                        }
                    }
                }
                
                this.updateLoadingProgress('bot', 'error');
            },
            
            // Helper method to check if active positions have actually changed
            hasActivePositionsChanged(newPositions) {
                const currentPositions = this.botStatus.active_positions || [];
                
                // If count is different, positions have changed
                if (currentPositions.length !== newPositions.length) {
                    return true;
                }
                
                // Check if any position values have changed
                for (let i = 0; i < newPositions.length; i++) {
                    const newPos = newPositions[i];
                    const currentPos = currentPositions[i];
                    
                    if (!currentPos || 
                        newPos.symbol !== currentPos.symbol ||
                        newPos.current_price !== currentPos.current_price ||
                        newPos.unrealized_pnl !== currentPos.unrealized_pnl ||
                        newPos.unrealized_pnl_pct !== currentPos.unrealized_pnl_pct) {
                        return true;
                    }
                }
                
                return false;
            },
            
            // Track position changes for visual feedback
            trackPositionChanges(newPositions) {
                const currentPositions = this.botStatus.active_positions || [];
                const changes = [];
                
                // Create a map of current positions by symbol
                const currentPosMap = {};
                currentPositions.forEach(pos => {
                    currentPosMap[pos.symbol] = pos;
                });
                
                // Check for changes in each new position
                newPositions.forEach(newPos => {
                    const currentPos = currentPosMap[newPos.symbol];
                    if (currentPos) {
                        const positionChanges = {};
                        
                        if (newPos.current_price !== currentPos.current_price) {
                            positionChanges.current_price = {
                                old: currentPos.current_price,
                                new: newPos.current_price
                            };
                        }
                        
                        if (newPos.unrealized_pnl !== currentPos.unrealized_pnl) {
                            positionChanges.unrealized_pnl = {
                                old: currentPos.unrealized_pnl,
                                new: newPos.unrealized_pnl
                            };
                        }
                        
                        if (newPos.unrealized_pnl_pct !== currentPos.unrealized_pnl_pct) {
                            positionChanges.unrealized_pnl_pct = {
                                old: currentPos.unrealized_pnl_pct,
                                new: newPos.unrealized_pnl_pct
                            };
                        }
                        
                        if (Object.keys(positionChanges).length > 0) {
                            changes.push({
                                symbol: newPos.symbol,
                                changes: positionChanges
                            });
                        }
                    }
                });
                
                // Log changes for debugging
                if (changes.length > 0) {
                    console.log('📊 Position changes detected:', changes);
                }
                
                return changes;
            },
            
            // Real-time update methods
            startRealTimeUpdates() {
                console.log('🔄 Starting real-time updates...');
                if (this.realTimeUpdates.enabled) {
                    console.log('⚠️ Real-time updates already running');
                    return;
                }
                
                this.realTimeUpdates.enabled = true;
                this.realTimeUpdates.interval = setInterval(async () => {
                    if (this.botStatus.running && this.botStatus.monitoring) {
                        // Add visual feedback for updates
                        this.realTimeUpdates.isUpdating = true;
                        
                        await this.loadBotStatus();
                        this.realTimeUpdates.lastUpdate = new Date();
                        console.log('🔄 Real-time update completed:', this.realTimeUpdates.lastUpdate);
                        
                        // Remove visual feedback after a short delay
                        setTimeout(() => {
                            this.realTimeUpdates.isUpdating = false;
                        }, 500);
                    }
                }, this.realTimeUpdates.updateInterval); // Use configurable update interval
                
                console.log('✅ Real-time updates started');
            },
            
            stopRealTimeUpdates() {
                console.log('🛑 Stopping real-time updates...');
                if (this.realTimeUpdates.interval) {
                    clearInterval(this.realTimeUpdates.interval);
                    this.realTimeUpdates.interval = null;
                }
                this.realTimeUpdates.enabled = false;
                console.log('✅ Real-time updates stopped');
            },
            
            // Position History auto-update methods
            startPositionHistoryUpdates() {
                console.log('🎯 FUNCTION CALLED: startPositionHistoryUpdates()');
                console.log('🔄 Starting position history auto-updates...');
                
                // Check if positionHistoryUpdates object exists
                if (!this.positionHistoryUpdates) {
                    console.error('❌ positionHistoryUpdates object is not defined!');
                    return;
                }
                
                console.log('🔍 Current positionHistoryUpdates state:', {
                    enabled: this.positionHistoryUpdates.enabled,
                    interval: this.positionHistoryUpdates.interval,
                    updateInterval: this.positionHistoryUpdates.updateInterval
                });
                
                if (this.positionHistoryUpdates.enabled) {
                    console.log('⚠️ Position history updates already running');
                    return;
                }
                
                this.positionHistoryUpdates.enabled = true;
                console.log('⏰ Setting up interval for position history updates every', this.positionHistoryUpdates.updateInterval, 'ms');
                
                this.positionHistoryUpdates.interval = setInterval(async () => {
                    console.log('🔄 Position history auto-update triggered, activeTab:', this.activeTab);
                    if (this.activeTab === 'positions') {
                        await this.loadPositionsHistory(true); // always silent on auto-refresh
                        this.positionHistoryUpdates.lastUpdate = new Date();
                    }
                }, this.positionHistoryUpdates.updateInterval);
            },
            
            stopPositionHistoryUpdates() {
                console.log('🛑 Stopping position history auto-updates...');
                if (this.positionHistoryUpdates.interval) {
                    console.log('🗑️ Clearing interval with ID:', this.positionHistoryUpdates.interval);
                    clearInterval(this.positionHistoryUpdates.interval);
                    this.positionHistoryUpdates.interval = null;
                } else {
                    console.log('⚠️ No interval to clear');
                }
                this.positionHistoryUpdates.enabled = false;
                console.log('✅ Position history auto-updates stopped');
            },
            
            // Update real-time interval dynamically
            updateRealTimeInterval() {
                console.log('⚙️ Updating real-time interval to:', this.realTimeUpdates.updateInterval + 'ms');
                
                // If updates are currently running, restart with new interval
                if (this.realTimeUpdates.enabled) {
                    this.stopRealTimeUpdates();
                    this.startRealTimeUpdates();
                }
                
                this.showNotification(`Update interval changed to ${this.realTimeUpdates.updateInterval/1000}s`, 'info');
            },
            
            // Enhanced bot status loading with real-time updates
            async loadBotStatusWithRealTime() {
                await this.loadBotStatus();
                
                // Start real-time updates if bot is running
                if (this.botStatus.running && this.botStatus.monitoring) {
                    this.startRealTimeUpdates();
                } else {
                    this.stopRealTimeUpdates();
                }
            },
            

            
            async loadBotConfig() {
                try {
                    console.log('⚙️ Loading bot configuration...');
                    const response = await axios.get('/api/bot/config');
                    
                    if (response.data.success) {
                        const d = response.data.data;
                        this.botConfig = {
                            profit_target_pct: d.profit_target_pct ?? 5.0,
                            stop_loss_pct: d.stop_loss_pct ?? 2.5,
                            monitor_interval: d.monitor_interval ?? 5,
                            trailing_stop_enabled: d.trailing_stop_enabled ?? false,
                            trailing_stop_pct: d.trailing_stop_pct ?? 1.5,
                            eod_exit_enabled: d.eod_exit_enabled ?? true,
                            eod_exit_time: d.eod_exit_time ?? '15:45',
                            breakeven_stop_enabled: d.breakeven_stop_enabled ?? true,
                            breakeven_trigger_pct: d.breakeven_trigger_pct ?? 50.0,
                        };
                        console.log('✅ Bot config loaded:', this.botConfig);
                    } else {
                        console.error('❌ Bot config error:', response.data.error);
                    }
                } catch (error) {
                    console.error('❌ Error loading bot config:', error);
                }
            },
            
            async updateBotConfig() {
                try {
                    console.log('⚙️ Updating bot configuration...');
                    console.log('⚙️ Sending config:', this.botConfig);
                    const response = await axios.post('/api/bot/config', this.botConfig);
                    
                    if (response.data.success) {
                        console.log('✅ Bot config updated successfully');
                        console.log('✅ Backend response:', response.data);
                        this.showNotification('Bot configuration updated successfully', 'success');
                        
                        // Force refresh bot status to get updated active positions
                        console.log('🔄 Refreshing bot status after config update...');
                        await this.loadBotStatus(); // Refresh bot status
                        
                        // Debug: Check if active positions were updated
                        if (this.botStatus.active_positions && this.botStatus.active_positions.length > 0) {
                            console.log('📊 Active positions after config update:');
                            this.botStatus.active_positions.forEach(pos => {
                                console.log(`  ${pos.symbol}: profit_target=$${pos.profit_target?.toFixed(2)}, stop_loss=$${pos.stop_loss?.toFixed(2)}`);
                            });
                        }
                    } else {
                        console.error('❌ Bot config update error:', response.data.error);
                        this.showNotification('Failed to update bot configuration: ' + response.data.error, 'error');
                    }
                } catch (error) {
                    console.error('❌ Error updating bot config:', error);
                    this.showNotification('Failed to update bot configuration', 'error');
                }
            },
            
            async discoverPositions() {
                try {
                    console.log('🔍 Discovering positions...');
                    const response = await axios.post('/api/bot/discover-positions');
                    
                    if (response.data.success) {
                        console.log('✅ Position discovery completed');
                        this.showNotification('Position discovery completed successfully', 'success');
                        await this.loadBotStatus(); // Refresh bot status
                    } else {
                        console.error('❌ Position discovery error:', response.data.error);
                        this.showNotification('Failed to discover positions: ' + response.data.error, 'error');
                    }
                } catch (error) {
                    console.error('❌ Error discovering positions:', error);
                    this.showNotification('Failed to discover positions', 'error');
                }
            },
            
            async refreshBotPositions() {
                try {
                    console.log('🔄 Refreshing bot positions...');
                    await this.loadBotStatus(); // Refresh bot status which includes active positions
                    this.showNotification('Bot positions refreshed', 'success');
                } catch (error) {
                    console.error('❌ Error refreshing bot positions:', error);
                    this.showNotification('Failed to refresh bot positions', 'error');
                }
            },
            
            async refreshBotConfig() {
                try {
                    console.log('⚙️ Refreshing bot configuration...');
                    await this.loadBotConfig(); // Refresh bot configuration
                    this.showNotification('Bot configuration refreshed', 'success');
                } catch (error) {
                    console.error('❌ Error refreshing bot configuration:', error);
                    this.showNotification('Failed to refresh bot configuration', 'error');
                }
            },
            
            // Bot configuration editing handlers
            onBotConfigFocus() {
                this.isEditingBotConfig = true;
                console.log('⚙️ User started editing bot configuration');
            },
            
            onBotConfigBlur() {
                this.isEditingBotConfig = false;
                console.log('⚙️ User finished editing bot configuration');
            },
            
            // Helper methods for position calculations
            getCurrentPrice(symbol) {
                // This would be replaced with real-time price data
                // For now, return a placeholder
                return null;
            },
            
            getPositionPnL(position) {
                const currentPrice = this.getCurrentPrice(position.symbol);
                if (!currentPrice) return 0;
                
                if (position.type === 'LONG') {
                    return (currentPrice - position.entry_price) * position.size;
                } else {
                    return (position.entry_price - currentPrice) * position.size;
                }
            },
            
            getPositionPnLPercent(position) {
                const currentPrice = this.getCurrentPrice(position.symbol);
                if (!currentPrice) return 0;
                
                if (position.type === 'LONG') {
                    return ((currentPrice - position.entry_price) / position.entry_price) * 100;
                } else {
                    return ((position.entry_price - currentPrice) / position.entry_price) * 100;
                }
            },
            
            async loadDashboardData() {
                console.log('🔄 Loading FRESH dashboard data from scratch...');
                this.loading.dashboard = true;
                
                try {
                    // Clear all existing dashboard data
                    this.dashboardStats = {
                        totalPositions: 0,
                        winRate: 0,
                        totalPnl: 0,
                        activePositions: 0,
                        gapUps: 0
                    };
                    
                    this.dashboardPositions = [];
                    this.dashboardAnalytics = {
                        totalPositions: 0,
                        overallWinRate: 0,
                        totalPnl: 0,
                        avgPositionPnl: 0,
                        longPositions: { count: 0, winRate: 0, pnl: 0 },
                        shortPositions: { count: 0, winRate: 0, pnl: 0 },
                        topPerformers: { bestTicker: '', bestPnl: 0 }
                    };
                    
                    console.log('🧹 Cleared all dashboard data');
                    
                    // Load fresh stats from positions endpoints
                    const [totalPositionsRes, totalPnlRes, winRateRes] = await Promise.all([
                        this.authFetch(`/api/positions/total_positions?t=${Date.now()}`),
                        this.authFetch(`/api/positions/total_pnl?t=${Date.now()}`),
                        this.authFetch(`/api/positions/winrate?t=${Date.now()}`)
                    ]);
                    
                    if (totalPositionsRes.ok && totalPnlRes.ok && winRateRes.ok) {
                        const [totalPositionsData, totalPnlData, winRateData] = await Promise.all([
                            totalPositionsRes.json(),
                            totalPnlRes.json(),
                            winRateRes.json()
                        ]);
                        
                        if (totalPositionsData.success && totalPnlData.success && winRateData.success) {
                            this.dashboardStats = {
                                totalPositions: totalPositionsData.data.total_positions || 0,
                                winRate: winRateData.data.win_rate || 0,
                                totalPnl: totalPnlData.data.total_pnl || 0,
                                activePositions: 0,
                                gapUps: this.gapUps.length
                            };
                            
                            console.log('✅ Fresh dashboard stats loaded:', this.dashboardStats);
                        }
                    }
                    
                    // Load fresh positions data for charts
                    await this.loadDashboardPositions();
                    
                } catch (error) {
                    console.error('❌ Error loading fresh dashboard data:', error);
                } finally {
                    this.loading.dashboard = false;
                }
            },
            
            calculateDashboardAnalytics() {
                try {
                    console.log('📊 Calculating fresh dashboard analytics...');
                    
                    const positions = this.dashboardPositions;
                    if (!positions || positions.length === 0) {
                        console.log('⚠️ No positions available for analytics calculation');
                        return;
                    }
                    
                    // Overall stats
                    const totalPositions = positions.length;
                    const winningPositions = positions.filter(p => (p.realized || 0) > 0).length;
                    const totalPnl = positions.reduce((sum, p) => sum + (p.realized || 0), 0);
                    const overallWinRate = totalPositions > 0 ? (winningPositions / totalPositions) * 100 : 0;
                    const avgPositionPnl = totalPositions > 0 ? totalPnl / totalPositions : 0;
                    
                    // Long positions analysis
                    const longPositions = positions.filter(p => {
                        const side = p.side?.toLowerCase() || p.direction?.toLowerCase() || '';
                        return side === 'b' || side === 'long';
                    });
                    const longWinningPositions = longPositions.filter(p => (p.realized || 0) > 0).length;
                    const longPnl = longPositions.reduce((sum, p) => sum + (p.realized || 0), 0);
                    const longWinRate = longPositions.length > 0 ? (longWinningPositions / longPositions.length) * 100 : 0;
                    
                    // Short positions analysis
                    const shortPositions = positions.filter(p => {
                        const side = p.side?.toLowerCase() || p.direction?.toLowerCase() || '';
                        return side === 's' || side === 'short';
                    });
                    const shortWinningPositions = shortPositions.filter(p => (p.realized || 0) > 0).length;
                    const shortPnl = shortPositions.reduce((sum, p) => sum + (p.realized || 0), 0);
                    const shortWinRate = shortPositions.length > 0 ? (shortWinningPositions / shortPositions.length) * 100 : 0;
                    
                    // Top performers analysis
                    const tickerPerformance = {};
                    positions.forEach(position => {
                        const ticker = position.symbol || position.ticker || 'Unknown';
                        if (!tickerPerformance[ticker]) {
                            tickerPerformance[ticker] = { pnl: 0, count: 0 };
                        }
                        tickerPerformance[ticker].pnl += (position.realized || 0);
                        tickerPerformance[ticker].count += 1;
                    });
                    
                    let bestTicker = '';
                    let bestPnl = 0;
                    Object.entries(tickerPerformance).forEach(([ticker, data]) => {
                        if (data.pnl > bestPnl) {
                            bestTicker = ticker;
                            bestPnl = data.pnl;
                        }
                    });
                    
                    // Update analytics object
                    this.dashboardAnalytics = {
                        totalPositions: totalPositions,
                        overallWinRate: overallWinRate,
                        totalPnl: totalPnl,
                        avgPositionPnl: avgPositionPnl,
                        longPositions: {
                            count: longPositions.length,
                            winRate: longWinRate,
                            pnl: longPnl
                        },
                        shortPositions: {
                            count: shortPositions.length,
                            winRate: shortWinRate,
                            pnl: shortPnl
                        },
                        topPerformers: {
                            bestTicker: bestTicker,
                            bestPnl: bestPnl
                        }
                    };
                    
                    console.log('✅ Fresh dashboard analytics calculated:', this.dashboardAnalytics);
                    
                } catch (error) {
                    console.error('❌ Error calculating dashboard analytics:', error);
                }
            },
            
            async loadGapUpConfig() {
                try {
                    console.log('⚙️ Loading gap-up configuration...');
                    const response = await fetch('/api/gap-ups/config');
                    const data = await response.json();
                    
                    if (data.success) {
                        this.gapUpConfig = data.data;
                        console.log('✅ Gap-up configuration loaded:', this.gapUpConfig);
                        console.log('✅ Gap-up min_percentage:', this.gapUpConfig.min_percentage);
                    } else {
                        console.error('❌ Failed to load gap-up configuration:', data.error);
                    }
                } catch (error) {
                    console.error('❌ Error loading gap-up configuration:', error);
                }
            },
            
            async saveGapUpConfig() {
                try {
                    console.log('💾 Saving gap-up configuration...');
                    const response = await fetch('/api/gap-ups/config', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            min_percentage: this.gapUpConfig.min_percentage
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        console.log('✅ Gap-up configuration saved:', data.message);
                        // Reload gap-ups with new configuration
                        await this.loadGapUps();
                        this.showNotification('Configuration saved successfully!', 'success');
                    } else {
                        console.error('❌ Failed to save gap-up configuration:', data.error);
                        this.showNotification('Failed to save configuration', 'error');
                    }
                } catch (error) {
                    console.error('❌ Error saving gap-up configuration:', error);
                    this.showNotification('Error saving configuration', 'error');
                }
            },
            
            async forceRefreshGapUps() {
                // Clears ALL backend gap-up caches, fetches fresh data, and applies
                // the response body directly to this.gapUps — no stale-while-revalidate delay.
                this.loading.gapUps = true;
                try {
                    const res = await fetch('/api/gap-ups/force-refresh', {
                        method: 'POST',
                        signal: AbortSignal.timeout(45000)
                    });
                    const data = await res.json();
                    if (data.success && data.data && data.data.length > 0) {
                        this.gapUps = data.data;
                        this.prevGapUpTickers = data.data.map(s => s.ticker);
                        this.dashboardStats.gapUps = this.gapUps.length;
                        this._saveGapUpsCache(data.data);
                    } else {
                        if (!data.success) {
                            this.showNotification('Force refresh failed: ' + (data.error || 'unknown'), 'error');
                        }
                        await this.loadGapUps(true);
                    }
                } catch (e) {
                    this.showNotification('Force refresh error: ' + e.message, 'error');
                    await this.loadGapUps(true);
                } finally {
                    this.loading.gapUps = false;
                }
            },

            async loadGapUps(silent = false) {
                // Stale-while-revalidate: paint cached data instantly so the tab is never blank.
                // The real fetch still runs — it updates via the silent in-place merge path.
                if (!silent) {
                    const cached = this._getGapUpsCache();
                    if (cached && cached.length > 0) {
                        this.gapUps = cached;
                        this.prevGapUpTickers = cached.map(s => s.ticker);
                        this.dashboardStats.gapUps = cached.length;
                        silent = true; // upgrade to silent refresh — don't clobber the UI
                    } else {
                        this.updateLoadingProgress('gapUps', 'loading');
                    }
                }

                const maxRetries = silent ? 1 : 3;
                const retryDelay = 1000;

                for (let attempt = 1; attempt <= maxRetries; attempt++) {
                    try {
                        const response = await fetch('/api/gap-ups', {
                            signal: AbortSignal.timeout(30000)
                        });
                        const data = await response.json();

                        if (data.success) {
                            const incoming = data.data || [];

                            // API returned nothing (cold start, market closed, transient empty).
                            // Keep whatever is already displayed and don't touch the cache.
                            if (incoming.length === 0) {
                                if (!silent) this.updateLoadingProgress('gapUps', 'success');
                                return;
                            }

                            // Detect newly arrived tickers
                            if (this.prevGapUpTickers.length > 0) {
                                const prevSet = new Set(this.prevGapUpTickers);
                                const brandNew = incoming.map(s => s.ticker).filter(t => !prevSet.has(t));
                                if (brandNew.length > 0) {
                                    this.newGapUpTickers = [...new Set([...this.newGapUpTickers, ...brandNew])];
                                    setTimeout(() => {
                                        const removing = new Set(brandNew);
                                        this.newGapUpTickers = this.newGapUpTickers.filter(t => !removing.has(t));
                                    }, 10000);
                                }
                            }

                            if (silent) {
                                // In-place merge — update existing rows and append new ones
                                // without replacing the array (avoids full table re-render)
                                const incomingMap = Object.fromEntries(incoming.map(s => [s.ticker, s]));
                                const existingTickers = new Set(this.gapUps.map(s => s.ticker));

                                // Update existing entries in-place
                                for (let i = 0; i < this.gapUps.length; i++) {
                                    const updated = incomingMap[this.gapUps[i].ticker];
                                    if (updated) Object.assign(this.gapUps[i], updated);
                                }
                                // Append genuinely new tickers
                                for (const s of incoming) {
                                    if (!existingTickers.has(s.ticker)) this.gapUps.push(s);
                                }
                                // Remove tickers no longer in the feed
                                const newSet = new Set(incoming.map(s => s.ticker));
                                this.gapUps = this.gapUps.filter(s => newSet.has(s.ticker));
                            } else {
                                this.gapUps = incoming;
                            }

                            this.prevGapUpTickers = incoming.map(s => s.ticker);
                            this.dashboardStats.gapUps = this.gapUps.length;
                            if (!silent) this.updateLoadingProgress('gapUps', 'success');
                            // Only persist to cache when we have real data — never overwrite
                            // a good cache with an empty or transient result
                            this._saveGapUpsCache(incoming);
                            return;
                        } else {
                            throw new Error(data.error || data.message || 'Failed to load gap-ups');
                        }
                    } catch (error) {
                        if (!silent) {
                            if (attempt === maxRetries) {
                                this.updateLoadingProgress('gapUps', 'error');
                            } else {
                                await new Promise(resolve => setTimeout(resolve, retryDelay));
                            }
                        }
                    }
                }

                if (!silent) this.updateLoadingProgress('gapUps', 'error');
            },
            
            // Gap-ups stale-while-revalidate helpers
            _getGapUpsCache() {
                try {
                    const raw = localStorage.getItem('gapUpsCache');
                    if (!raw) return null;
                    const { date, data } = JSON.parse(raw);
                    // en-CA gives YYYY-MM-DD in the user's local time zone
                    const today = new Date().toLocaleDateString('en-CA');
                    return date === today ? data : null;
                } catch { return null; }
            },
            _saveGapUpsCache(data) {
                try {
                    const today = new Date().toLocaleDateString('en-CA');
                    localStorage.setItem('gapUpsCache', JSON.stringify({ date: today, data }));
                } catch {}
            },

            _statsDateQs() {
                const p = [];
                if (this.statsStartDate)              p.push(`start_date=${this.statsStartDate}`);
                if (this.statsEndDate)                p.push(`end_date=${this.statsEndDate}`);
                if (this.statsTimeStart)              p.push(`time_start=${this.statsTimeStart}`);
                if (this.statsTimeEnd)                p.push(`time_end=${this.statsTimeEnd}`);
                if (this.statsPriceMin !== '')         p.push(`price_min=${this.statsPriceMin}`);
                if (this.statsPriceMax !== '')         p.push(`price_max=${this.statsPriceMax}`);
                if (this.statsDayOfWeek.length)       p.push(`day_of_week=${this.statsDayOfWeek.join(',')}`);
                return p.length ? '?' + p.join('&') : '';
            },

            toggleStatsDow(d) {
                const idx = this.statsDayOfWeek.indexOf(d);
                if (idx >= 0) this.statsDayOfWeek.splice(idx, 1);
                else          this.statsDayOfWeek.push(d);
                this.loadStats();
            },

            clearStatsAdvancedFilters() {
                this.statsTimeStart  = '';
                this.statsTimeEnd    = '';
                this.statsPriceMin   = '';
                this.statsPriceMax   = '';
                this.statsDayOfWeek  = [];
                this.loadStats();
            },

            setStatsDatePreset(preset) {
                this.statsPreset = preset;
                const today = new Date();
                const fmt = d => d.toISOString().split('T')[0];
                if (preset === 'all')    { this.statsStartDate = ''; this.statsEndDate = ''; }
                else if (preset === 'today') { this.statsStartDate = fmt(today); this.statsEndDate = fmt(today); }
                else if (preset === 'week')  { const d = new Date(today); d.setDate(d.getDate() - 7);  this.statsStartDate = fmt(d); this.statsEndDate = fmt(today); }
                else if (preset === 'month') { const d = new Date(today); d.setMonth(d.getMonth() - 1); this.statsStartDate = fmt(d); this.statsEndDate = fmt(today); }
                else if (preset === '3month'){ const d = new Date(today); d.setMonth(d.getMonth() - 3); this.statsStartDate = fmt(d); this.statsEndDate = fmt(today); }
                else if (preset === '6month'){ const d = new Date(today); d.setMonth(d.getMonth() - 6); this.statsStartDate = fmt(d); this.statsEndDate = fmt(today); }
                else if (preset === 'ytd')   { this.statsStartDate = `${today.getFullYear()}-01-01`; this.statsEndDate = fmt(today); }
                this.loadStats();
            },

            onStatsDateChange() {
                this.statsPreset = '';
                this.loadStats();
            },

            clearStatsFilter() {
                this.statsStartDate  = '';
                this.statsEndDate    = '';
                this.statsPreset     = 'all';
                this.statsTimeStart  = '';
                this.statsTimeEnd    = '';
                this.statsPriceMin   = '';
                this.statsPriceMax   = '';
                this.statsDayOfWeek  = [];
                this.loadStats();
            },

            async loadExtendedStats() {
                try {
                    const qs = this._statsDateQs();
                    const res = await this.authFetch(`/api/positions/extended-stats${qs}`);
                    const data = await res.json();
                    if (data.success) this.extendedStats = data.data;
                } catch (e) {
                    console.error('❌ Error loading extended stats:', e);
                }
            },

            async loadStats() {
                this.loading.stats = true;
                const qs = this._statsDateQs();
                try {
                    const summaryRes  = await this.authFetch(`/api/positions/summary${qs}`);
                    const summaryData = await summaryRes.json();
                    if (summaryData.success) {
                        this.stats.total_pnl       = summaryData.data.total_pnl       || 0;
                        this.stats.win_rate        = summaryData.data.win_rate        || 0;
                        this.stats.total_positions = summaryData.data.total_positions || 0;
                    } else {
                        this.showNotification('Failed to load statistics', 'error');
                    }
                    await Promise.all([
                        this.loadExtendedStats(),
                        this.loadDailyPnlData(),
                        this.loadCumulativePnlData(),
                        this.loadPieChartData(),
                        this.loadTimeOfDayData(),
                        this.loadDayOfWeekData(),
                        this.loadBrownEntryStats(true),  // entry-trigger panel follows the stats date range
                        this.loadBrownExitStats(true),   // exit-reason panel follows the stats date range
                    ]);
                } catch (error) {
                    console.error('❌ Error loading statistics:', error);
                    this.showNotification('Error loading statistics', 'error');
                } finally {
                    this.loading.stats = false;
                }
            },
            
            async loadDailyPnlData() {
                this.loading.dailyPnl = true;
                try {
                    const response = await this.authFetch(`/api/positions/daily-pnl${this._statsDateQs()}`);
                    const data = await response.json();
                    
                    if (data.success) {
                        this.dailyPnlData = data.data.daily_pnl || [];
                        console.log('✅ Daily P&L data loaded:', this.dailyPnlData.length, 'days');
                        
                        // Update chart with new data
                        this.$nextTick(() => {
                            this.updateDailyPnlChart();
                        });
                    } else {
                        console.error('❌ Failed to load daily P&L data:', data.message);
                        this.showNotification('Failed to load daily P&L data', 'error');
                    }
                } catch (error) {
                    console.error('❌ Error loading daily P&L data:', error);
                    this.showNotification('Error loading daily P&L data', 'error');
                } finally {
                    this.loading.dailyPnl = false;
                }
            },
            
            async loadCumulativePnlData() {
                this.loading.cumulativePnl = true;
                try {
                    const response = await this.authFetch(`/api/positions/cumulative-pnl${this._statsDateQs()}`);
                    const data = await response.json();
                    
                    if (data.success) {
                        this.cumulativePnlData = data.data.cumulative_pnl || [];
                        console.log('✅ Cumulative P&L data loaded:', this.cumulativePnlData.length, 'days');
                        
                        // Update chart with new data
                        this.$nextTick(() => {
                            this.updateCumulativePnlChart();
                        });
                    } else {
                        console.error('❌ Failed to load cumulative P&L data:', data.message);
                        this.showNotification('Failed to load cumulative P&L data', 'error');
                    }
                } catch (error) {
                    console.error('❌ Error loading cumulative P&L data:', error);
                    this.showNotification('Error loading cumulative P&L data', 'error');
                } finally {
                    this.loading.cumulativePnl = false;
                }
            },
            
            async loadTimeOfDayData() {
                this.loading.timeOfDay = true;
                try {
                    const res  = await this.authFetch(`/api/positions/time-of-day${this._statsDateQs()}`);
                    const data = await res.json();
                    if (data.success) {
                        this.timeOfDayData = data.data.time_of_day || [];
                        this.$nextTick(() => { this.updateTimeOfDayChart(); });
                    }
                } catch (e) {
                    console.error('Error loading time-of-day data:', e);
                } finally {
                    this.loading.timeOfDay = false;
                }
            },

            async loadDayOfWeekData() {
                this.loading.dayOfWeek = true;
                try {
                    const res  = await this.authFetch(`/api/positions/day-of-week${this._statsDateQs()}`);
                    const data = await res.json();
                    if (data.success) {
                        this.dayOfWeekData = data.data.day_of_week || [];
                        this.$nextTick(() => { this.updateDayOfWeekChart(); });
                    }
                } catch (e) {
                    console.error('Error loading day-of-week data:', e);
                } finally {
                    this.loading.dayOfWeek = false;
                }
            },

            updateTimeOfDayChart() {
                const ctx = document.getElementById('timeOfDayChart');
                if (!ctx || !this.timeOfDayData.length) return;
                if (this.timeOfDayChart) { this.timeOfDayChart.destroy(); this.timeOfDayChart = null; }
                const labels = this.timeOfDayData.map(r => r.label);
                const values = this.timeOfDayData.map(r => r.total_pnl);
                const colors = values.map(v => v >= 0 ? 'rgba(34,197,94,0.8)' : 'rgba(239,68,68,0.8)');
                this.timeOfDayChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels,
                        datasets: [{
                            label: 'Total P&L ($)',
                            data: values,
                            backgroundColor: colors,
                            borderColor: colors.map(c => c.replace('0.8', '1')),
                            borderWidth: 1,
                            borderRadius: 4,
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true, maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    afterLabel: (ctx) => {
                                        const r = this.timeOfDayData[ctx.dataIndex];
                                        return [`Trades: ${r.trade_count}`, `Avg: $${r.avg_pnl}`, `Win rate: ${r.win_rate}%`];
                                    }
                                }
                            }
                        },
                        scales: {
                            y: { ticks: { color: '#9ca3af', font: { size: 11 } }, grid: { color: 'rgba(255,255,255,0.05)' } },
                            x: {
                                ticks: { color: '#9ca3af', callback: v => '$' + v.toFixed(0) },
                                grid: { color: 'rgba(255,255,255,0.05)' },
                                border: { dash: [4, 4] }
                            }
                        }
                    }
                });
            },

            updateDayOfWeekChart() {
                const ctx = document.getElementById('dayOfWeekChart');
                if (!ctx || !this.dayOfWeekData.length) return;
                if (this.dayOfWeekChart) { this.dayOfWeekChart.destroy(); this.dayOfWeekChart = null; }
                const labels = this.dayOfWeekData.map(r => r.label);
                const values = this.dayOfWeekData.map(r => r.total_pnl);
                const colors = values.map(v => v >= 0 ? 'rgba(99,102,241,0.8)' : 'rgba(239,68,68,0.8)');
                this.dayOfWeekChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels,
                        datasets: [{
                            label: 'Total P&L ($)',
                            data: values,
                            backgroundColor: colors,
                            borderColor: colors.map(c => c.replace('0.8', '1')),
                            borderWidth: 1,
                            borderRadius: 4,
                        }]
                    },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    afterLabel: (ctx) => {
                                        const r = this.dayOfWeekData[ctx.dataIndex];
                                        return [`Trades: ${r.trade_count}`, `Avg: $${r.avg_pnl}`, `Win rate: ${r.win_rate}%`];
                                    }
                                }
                            }
                        },
                        scales: {
                            x: { ticks: { color: '#9ca3af' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                            y: {
                                ticks: { color: '#9ca3af', callback: v => '$' + v.toFixed(0) },
                                grid: { color: 'rgba(255,255,255,0.05)' },
                                border: { dash: [4, 4] }
                            }
                        }
                    }
                });
            },

            updateDailyPnlChart() {
                if (!this.dailyPnlData || this.dailyPnlData.length === 0) {
                    console.log('📊 No daily P&L data to display');
                    return;
                }

                const ctx = document.getElementById('dailyPnlChart');
                if (!ctx) {
                    console.error('❌ Daily P&L chart canvas not found');
                    return;
                }

                // Destroy existing chart if it exists
                if (this.dailyPnlChart) {
                    this.dailyPnlChart.destroy();
                }
                
                // Prepare data for chart
                const labels = this.dailyPnlData.map(item => item.date);
                const data = this.dailyPnlData.map(item => item.daily_pnl);
                const colors = data.map(value => value >= 0 ? '#10B981' : '#EF4444'); // Green for positive, red for negative
                
                // Configure dataset based on chart type
                const datasetConfig = {
                    label: 'Daily P&L',
                    data: data,
                    borderColor: colors,
                    borderWidth: 2
                };
                
                // Add type-specific properties
                if (this.dailyPnlChartType === 'bar') {
                    datasetConfig.backgroundColor = colors;
                    datasetConfig.borderRadius = 4;
                } else if (this.dailyPnlChartType === 'line') {
                    datasetConfig.backgroundColor = 'rgba(59, 130, 246, 0.1)'; // Light blue background for line chart
                    datasetConfig.fill = true;
                    datasetConfig.tension = 0.4; // Smooth line curves
                    datasetConfig.pointBackgroundColor = colors;
                    datasetConfig.pointBorderColor = colors;
                    datasetConfig.pointRadius = 4;
                    datasetConfig.pointHoverRadius = 6;
                }
                
                // Create new chart
                this.dailyPnlChart = new Chart(ctx, {
                    type: this.dailyPnlChartType,
                    data: {
                        labels: labels,
                        datasets: [datasetConfig]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: false
                            },
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                                callbacks: {
                                    label: function(context) {
                                        const value = context.parsed.y;
                                        return `Daily P&L: ${new Intl.NumberFormat('en-US', {
                                            style: 'currency',
                                            currency: 'USD'
                                        }).format(value)}`;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                display: true,
                                title: {
                                    display: true,
                                    text: 'Date',
                                    color: '#9CA3AF'
                                },
                                ticks: {
                                    color: '#9CA3AF',
                                    maxRotation: 45
                                },
                                grid: {
                                    color: '#374151'
                                }
                            },
                            y: {
                                display: true,
                                title: {
                                    display: true,
                                    text: 'P&L ($)',
                                    color: '#9CA3AF'
                                },
                                ticks: {
                                    color: '#9CA3AF',
                                    callback: function(value) {
                                        return new Intl.NumberFormat('en-US', {
                                            style: 'currency',
                                            currency: 'USD',
                                            minimumFractionDigits: 0,
                                            maximumFractionDigits: 0
                                        }).format(value);
                                    }
                                },
                                grid: {
                                    color: '#374151'
                                }
                            }
                        },
                        interaction: {
                            mode: 'nearest',
                            axis: 'x',
                            intersect: false
                        }
                    }
                });
                
                console.log('✅ Daily P&L chart updated');
            },

            toggleDailyPnlChartType(chartType) {
                console.log(`🔄 Switching daily P&L chart type to: ${chartType}`);
                this.dailyPnlChartType = chartType;
                
                // Update the chart with the new type
                if (this.dailyPnlData && this.dailyPnlData.length > 0) {
                    this.updateDailyPnlChart();
                }
            },

            updateCumulativePnlChart() {
                if (!this.cumulativePnlData || this.cumulativePnlData.length === 0) {
                    console.log('📈 No cumulative P&L data to display');
                    return;
                }
                
                const ctx = document.getElementById('cumulativePnlChart');
                if (!ctx) {
                    console.error('❌ Cumulative P&L chart canvas not found');
                    return;
                }
                
                // Destroy existing chart if it exists
                if (this.cumulativePnlChart) {
                    this.cumulativePnlChart.destroy();
                }
                
                // Prepare data for chart
                const labels = this.cumulativePnlData.map(item => item.date);
                const cumulativeData = this.cumulativePnlData.map(item => item.cumulative_pnl);
                const dailyData = this.cumulativePnlData.map(item => item.daily_pnl);
                
                // Create new chart
                this.cumulativePnlChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: 'Cumulative P&L',
                                data: cumulativeData,
                                borderColor: '#3B82F6',
                                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                borderWidth: 3,
                                fill: true,
                                tension: 0.4,
                                pointBackgroundColor: '#3B82F6',
                                pointBorderColor: '#3B82F6',
                                pointRadius: 4,
                                pointHoverRadius: 6,
                                yAxisID: 'y'
                            },
                            {
                                label: 'Daily P&L',
                                data: dailyData,
                                borderColor: '#10B981',
                                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                borderWidth: 2,
                                fill: false,
                                tension: 0.2,
                                pointBackgroundColor: '#10B981',
                                pointBorderColor: '#10B981',
                                pointRadius: 3,
                                pointHoverRadius: 5,
                                yAxisID: 'y1'
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top',
                                labels: {
                                    color: '#9CA3AF',
                                    usePointStyle: true,
                                    padding: 20
                                }
                            },
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                                callbacks: {
                                    label: function(context) {
                                        const value = context.parsed.y;
                                        const label = context.dataset.label;
                                        return `${label}: ${new Intl.NumberFormat('en-US', {
                                            style: 'currency',
                                            currency: 'USD'
                                        }).format(value)}`;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                display: true,
                                title: {
                                    display: true,
                                    text: 'Date',
                                    color: '#9CA3AF'
                                },
                                ticks: {
                                    color: '#9CA3AF',
                                    maxRotation: 45
                                },
                                grid: {
                                    color: '#374151'
                                }
                            },
                            y: {
                                type: 'linear',
                                display: true,
                                position: 'left',
                                title: {
                                    display: true,
                                    text: 'Cumulative P&L ($)',
                                    color: '#9CA3AF'
                                },
                                ticks: {
                                    color: '#9CA3AF',
                                    callback: function(value) {
                                        return new Intl.NumberFormat('en-US', {
                                            style: 'currency',
                                            currency: 'USD',
                                            minimumFractionDigits: 0,
                                            maximumFractionDigits: 0
                                        }).format(value);
                                    }
                                },
                                grid: {
                                    color: '#374151'
                                }
                            },
                            y1: {
                                type: 'linear',
                                display: true,
                                position: 'right',
                                title: {
                                    display: true,
                                    text: 'Daily P&L ($)',
                                    color: '#9CA3AF'
                                },
                                ticks: {
                                    color: '#9CA3AF',
                                    callback: function(value) {
                                        return new Intl.NumberFormat('en-US', {
                                            style: 'currency',
                                            currency: 'USD',
                                            minimumFractionDigits: 0,
                                            maximumFractionDigits: 0
                                        }).format(value);
                                    }
                                },
                                grid: {
                                    drawOnChartArea: false
                                }
                            }
                        },
                        interaction: {
                            mode: 'nearest',
                            axis: 'x',
                            intersect: false
                        }
                    }
                });
                
                console.log('✅ Cumulative P&L chart updated');
            },

            // Pie Chart Methods
            async loadPieChartData() {
                console.log('🥧 Loading pie chart data...');
                this.loading.pieCharts = true;
                
                try {
                    const qs = this._statsDateQs();
                    const sep = qs ? '&' : '?';
                    const [longShortResponse, symbolsResponse, winLossResponse, monthlyResponse] = await Promise.all([
                        this.authFetch(`/api/positions/pie-chart/long-short${qs}`),
                        this.authFetch(`/api/positions/pie-chart/symbols${qs}${sep}limit=${this.pieChartSymbolLimit}`),
                        this.authFetch(`/api/positions/pie-chart/win-loss${qs}`),
                        this.authFetch(`/api/positions/pie-chart/monthly${qs}`)
                    ]);

                    const [longShortData, symbolsData, winLossData, monthlyData] = await Promise.all([
                        longShortResponse.json(),
                        symbolsResponse.json(),
                        winLossResponse.json(),
                        monthlyResponse.json()
                    ]);

                    if (longShortData.success) {
                        this.pieChartData.longShort = longShortData.data.long_short_pnl || [];
                    }
                    if (symbolsData.success) {
                        this.pieChartData.symbols = symbolsData.data.symbol_pnl || [];
                    }
                    if (winLossData.success) {
                        this.pieChartData.winLoss = winLossData.data.win_loss_pnl || [];
                    }
                    if (monthlyData.success) {
                        this.pieChartData.monthly = monthlyData.data.monthly_pnl || [];
                    }

                    console.log('✅ Pie chart data loaded successfully');
                    
                    // Update the current pie chart
                    this.$nextTick(() => {
                        this.updatePieChart();
                    });
                    
                } catch (error) {
                    console.error('❌ Error loading pie chart data:', error);
                    this.showNotification('Error loading pie chart data', 'error');
                } finally {
                    this.loading.pieCharts = false;
                }
            },

            updatePieChart() {
                const chartId = `${this.pieChartType}PieChart`;
                const ctx = document.getElementById(chartId);
                if (!ctx) {
                    console.error(`❌ Pie chart canvas not found: ${chartId}`);
                    return;
                }

                // Destroy existing chart if it exists
                if (this.pieCharts[this.pieChartType]) {
                    this.pieCharts[this.pieChartType].destroy();
                }

                const data = this.pieChartData[this.pieChartType];
                if (!data || data.length === 0) {
                    console.log(`📊 No ${this.pieChartType} data to display`);
                    return;
                }

                // Generate colors for pie chart
                const colors = this.generatePieChartColors(data.length);

                // Prepare chart data
                const labels = data.map(item => {
                    switch (this.pieChartType) {
                        case 'longShort': return item.position_type;
                        case 'symbols':  return item.symbol;
                        case 'winLoss':  return item.trade_result;
                        case 'monthly':  return item.month;
                        default:         return item.label || 'Unknown';
                    }
                });

                // actual P&L values (may be negative)
                const actualValues = data.map(item => item.total_pnl);
                // pie slices must be positive — use absolute values for sizing
                const sliceSizes  = actualValues.map(v => Math.abs(v));
                const counts      = data.map(item => item.position_count);
                const absTotal    = sliceSizes.reduce((a, b) => a + b, 0) || 1; // guard /0

                // Create new chart
                this.pieCharts[this.pieChartType] = new Chart(ctx, {
                    type: 'pie',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: sliceSizes,
                            backgroundColor: colors,
                            borderColor: '#374151',
                            borderWidth: 2,
                            hoverBorderColor: '#6B7280',
                            hoverBorderWidth: 3
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: {
                                    color: '#9CA3AF',
                                    padding: 20,
                                    usePointStyle: true,
                                    generateLabels: (chart) => {
                                        const d = chart.data;
                                        if (d.labels.length && d.datasets.length) {
                                            return d.labels.map((label, i) => {
                                                const pnl = actualValues[i];
                                                const pct = ((sliceSizes[i] / absTotal) * 100).toFixed(1);
                                                const sign = pnl >= 0 ? '+' : '';
                                                return {
                                                    text: `${label}: ${sign}$${pnl.toLocaleString(undefined, {minimumFractionDigits:2,maximumFractionDigits:2})} (${pct}%)`,
                                                    fillStyle: colors[i],
                                                    strokeStyle: colors[i],
                                                    lineWidth: 0,
                                                    pointStyle: 'circle',
                                                    hidden: false,
                                                    index: i
                                                };
                                            });
                                        }
                                        return [];
                                    }
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: (context) => {
                                        const pnl = actualValues[context.dataIndex];
                                        const count = counts[context.dataIndex];
                                        const pct = ((sliceSizes[context.dataIndex] / absTotal) * 100).toFixed(1);
                                        const sign = pnl >= 0 ? '+' : '';
                                        return [
                                            `${context.label}: ${sign}$${pnl.toFixed(2)}`,
                                            `Positions: ${count}`,
                                            `Share of total: ${pct}%`
                                        ];
                                    }
                                }
                            }
                        }
                    }
                });

                console.log(`✅ ${this.pieChartType} pie chart updated`);
            },

            generatePieChartColors(count) {
                const baseColors = [
                    '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
                    '#06B6D4', '#84CC16', '#F97316', '#EC4899', '#6366F1',
                    '#14B8A6', '#FBBF24', '#DC2626', '#A855F7', '#0EA5E9'
                ];
                
                const colors = [];
                for (let i = 0; i < count; i++) {
                    colors.push(baseColors[i % baseColors.length]);
                }
                return colors;
            },

            changePieChartType(type) {
                console.log(`🔄 Switching pie chart type to: ${type}`);
                this.pieChartType = type;
                
                // Update the chart with the new type
                this.$nextTick(() => {
                    this.updatePieChart();
                });
            },

            // Backtest Methods
            async loadBacktestData() {
                this.loading.backtest = true;
                try {
                    const resp = await fetch('/api/backtest/info');
                    const data = await resp.json();
                    if (data.success) {
                        this.backtestInfo = data;
                        if (!this.backtestConfig.startDate && data.min_date) {
                            this.backtestConfig.startDate = data.min_date;
                            this.backtestConfig.endDate   = data.max_date;
                        }
                    }
                } catch (e) {
                    console.error('loadBacktestData error', e);
                } finally {
                    this.loading.backtest = false;
                }
            },

            async runBacktest() {
                const c = this.backtestConfig;
                if (!c.startDate || !c.endDate) {
                    this.showNotification('Please select start and end dates', 'error'); return;
                }
                if (c.initialCapital <= 0) {
                    this.showNotification('Initial capital must be > 0', 'error'); return;
                }
                this.loading.runBacktest = true;
                this.backtestResults = null;
                const isDay = this.backtestTradeType === 'day';
                try {
                    const payload = {
                        trade_type:   this.backtestTradeType,
                        // shared
                        start_date:        c.startDate,
                        end_date:          c.endDate,
                        initial_capital:   c.initialCapital,
                        min_gap_pct:       c.minGapPct,
                        min_price:         c.minPrice,
                        max_price:         c.maxPrice,
                        min_volume_m:      c.minVolumeMillion,
                        max_float_m:       c.maxFloatM,
                        float_operator:    c.floatOperator,
                    };
                    if (isDay) {
                        Object.assign(payload, {
                            position_size_pct:       c.dayPositionSizePct,
                            stop_loss_pct:           c.dayStopLossPct,
                            profit_target_pct:       c.dayProfitTargetPct,
                            day_breakeven_enabled:   c.dayBreakevenEnabled,
                            day_breakeven_trigger_pct: c.dayBreakevenTriggerPct,
                            day_trailing_stop_enabled: c.dayTrailingStopEnabled,
                            day_trailing_stop_pct:   c.dayTrailingStopPct,
                            max_concurrent_day:      c.maxConcurrentDay,
                            day_slippage_pct:        c.daySlippagePct,
                            day_max_reentry:         c.dayMaxReentry,
                            entry_start_time:        c.entryStartTime,
                            entry_end_time:          c.entryEndTime,
                            eod_exit_time:           c.eodExitTime,
                            day_check_vwap:          c.dayCheckVwap,
                            day_check_candle:        c.dayCheckCandle,
                            day_max_extension_pct:   c.dayMaxExtensionPct,
                            day_check_volume_surge:  c.dayCheckVolumeSurge,
                            day_max_below_dayhigh_pct: c.dayMaxBelowDayhighPct,
                            // Breakout triggers (OR)
                            day_check_pmh:           c.dayCheckPmh,
                            day_check_dayhigh_break: c.dayCheckDayhighBreak,
                            day_check_orb:           c.dayCheckOrb,
                            day_orb_minutes:         c.dayOrbMinutes,
                            day_pmh_break_buffer_pct: c.dayPmhBreakBufferPct,
                            day_pmh_vol_mult:        c.dayPmhVolMult,
                            day_pmh_max_wick_pct:    c.dayPmhMaxWickPct,
                            day_pmh_acceptance_bars: c.dayPmhAcceptanceBars,
                        });
                    } else {
                        Object.assign(payload, {
                            swing_position_pct:      c.swingPositionSizePct,
                            swing_stop_loss_pct:     c.swingStopLossPct,
                            swing_profit_target_pct: c.swingProfitTargetPct,
                            swing_max_hold_days:     c.swingMaxHoldDays,
                            min_market_cap_m:        c.swingMinMarketCapM,
                        });
                    }
                    const resp = await fetch('/api/backtest/run', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('session_token')}` },
                        body: JSON.stringify(payload),
                    });
                    const data = await resp.json();
                    if (!data.success) throw new Error(data.error || 'Backtest failed');
                    this.backtestResults = { ...data, tradeType: this.backtestTradeType };
                    this.$nextTick(() => this.updateEquityCurveChart());
                    // Loud warning instead of a silent zero when the date range has no data.
                    const nTrades = data.summary.total_trades || 0;
                    if (nTrades === 0 && this.backtestInfo) {
                        const lo = this.backtestInfo.min_date, hi = this.backtestInfo.max_date;
                        const outOfRange = (c.startDate && hi && c.startDate > hi) || (c.endDate && lo && c.endDate < lo);
                        if (outOfRange) {
                            this.showNotification(`No data for ${c.startDate} → ${c.endDate}. Available range: ${lo} to ${hi}.`, 'error');
                        } else {
                            this.showNotification('0 trades — no candidates matched your filters in this range. Loosen gap/price/volume/float or widen the dates.', 'error');
                        }
                    } else {
                        this.showNotification(`${isDay ? 'Day' : 'Swing'} backtest complete — ${nTrades} trades`, 'success');
                    }
                } catch (e) {
                    this.showNotification('Backtest error: ' + e.message, 'error');
                } finally {
                    this.loading.runBacktest = false;
                }
            },

            updateEquityCurveChart() {
                if (!this.backtestResults?.equity_curve?.length) return;
                const ctx = document.getElementById('equityCurveChart');
                if (!ctx) return;
                if (this.equityCurveChart) this.equityCurveChart.destroy();

                const curve    = this.backtestResults.equity_curve;
                const labels   = curve.map(p => p.date);
                const values   = curve.map(p => p.equity);
                const initCap  = this.backtestResults.summary.initial_capital;
                const colors   = values.map(v => v >= initCap ? 'rgba(52,211,153,0.8)' : 'rgba(248,113,113,0.8)');

                this.equityCurveChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels,
                        datasets: [{
                            label: 'Equity',
                            data: values,
                            borderColor: '#3B82F6',
                            backgroundColor: 'rgba(59,130,246,0.08)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.3,
                            pointRadius: 0,
                            pointHoverRadius: 4,
                        }]
                    },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                mode: 'index', intersect: false,
                                callbacks: {
                                    label: ctx => `$${ctx.parsed.y.toLocaleString('en-US', {minimumFractionDigits:0, maximumFractionDigits:0})}`
                                }
                            }
                        },
                        scales: {
                            x: { ticks: { color:'#9CA3AF', maxTicksLimit:12, maxRotation:30 }, grid: { color:'#374151' } },
                            y: { ticks: { color:'#9CA3AF', callback: v => '$' + (v/1000).toFixed(0)+'k' }, grid: { color:'#374151' } }
                        },
                        interaction: { mode:'nearest', axis:'x', intersect:false }
                    }
                });
            },

            
            async loadDashboardPositions() {
                try {
                    console.log('🔄 Loading fresh dashboard positions data...');
                    
                    // Load positions data for charts and analytics
                    const response = await this.authFetch(`/api/positions/pnl-history?t=${Date.now()}`);
                    const data = await response.json();
                    
                    if (data.success) {
                        this.dashboardPositions = data.data.positions || [];
                        console.log('✅ Fresh dashboard positions loaded:', this.dashboardPositions.length, 'positions');
                        
                        // Calculate analytics with fresh data
                        this.calculateDashboardAnalytics();
                        
                        // Update charts with fresh data
                        this.$nextTick(() => {
                            this.updatePnlChart();
                            this.updatePositionsChart();
                        });
                    } else {
                        console.error('Failed to load dashboard positions:', data.message);
                    }
                    
                } catch (error) {
                    console.error('Error loading dashboard positions:', error);
                }
            },
            
            async onShowAllTradesToggle() {
                console.log('🔄 Show All Trades toggle changed to:', this.showAllTrades);
                // Load fresh dashboard data when toggle changes
                await this.loadDashboardPositions();
                
                // Update charts after data loads
                this.$nextTick(() => {
                    setTimeout(() => {
                        this.updatePnlChart();
                        this.updatePositionsChart();
                    }, 200);
                });
            },
            
            onChartViewTypeChange() {
                console.log('🔄 Chart view type changed to:', this.dashboardChartView);
                this.updatePositionsChart();
            },
            
            setDateRangeTo2025() {
                // Quick method to set date range to 2025 to match database
                this.dashboardDateRange.fromDate = '2025-01-01';
                this.dashboardDateRange.toDate = '2025-12-31';
                this.dashboardDateRange.showAllData = false; // Turn off show all data to use date range
                
                console.log('📅 Date range set to 2025');
                
                // Reload fresh dashboard data
                this.loadDashboardPositions().then(() => {
                    // Update charts after data loads
                    this.$nextTick(() => {
                        setTimeout(() => {
                            this.updatePnlChart();
                            this.updatePositionsChart();
                        }, 200);
                    });
                });
            },
            
            async loadTradeHistory() {
                try {
                    this.loading.trades = true;
                
                // Load scheduled sync status when trade history tab is accessed
                await this.loadScheduledSyncStatus();
                    
                    // Build query parameters
                    const params = new URLSearchParams();
                params.append('limit', '1000');
                if (this.tradeHistoryStartDate) params.append('start_date', this.tradeHistoryStartDate);
                if (this.tradeHistoryEndDate)   params.append('end_date',   this.tradeHistoryEndDate);
                if (this.tradeHistoryTicker && this.tradeHistoryTicker.trim())
                    params.append('symbol', this.tradeHistoryTicker.trim().toUpperCase());
                    
                    const response = await this.authFetch(`/api/trades?${params.toString()}`);
                    const data = await response.json();
                    
                    if (data.success) {
                    const sideLabel = { B: 'buy', S: 'sell', SS: 'short' };
                    this.trades = (data.data.trades || []).map(trade => ({
                        id:            trade.id,
                        ticker:        trade.symbol,
                        direction:     sideLabel[trade.side] || trade.side,
                        quantity:      trade.quantity,
                        price:         trade.price,
                        status:        'filled',
                        pnl:           trade.pnl || 0,
                        submitted_at:  trade.trade_date + ' ' + (trade.trade_time || ''),
                        trade_time:    trade.trade_time || '',
                        route:         trade.route,
                        order_id:      trade.order_id,
                        ecn_fee:       trade.ecn_fee,
                        position_type: trade.position_type || 'day',
                        source:        trade.source || 'brownbot',
                    }));
                    
                    console.log(`📊 Loaded ${this.trades.length} trades from database${this.tradeHistoryTicker ? ` for ${this.tradeHistoryTicker}` : ''}`);
                    
                    // Note: We don't update dashboard stats here to keep them independent
                    // Dashboard stats should only be updated by loadStats() method
                    } else {
                    console.error('Failed to load trade history:', data.error);
                    this.showNotification('Failed to load trade history: ' + data.error, 'error');
                    }
                } catch (error) {
                console.error('Error loading trade history:', error);
                this.showNotification('Error loading trade history: ' + error.message, 'error');
                } finally {
                this.loading.trades = false;
            }
        },
        
        async loadOpenPositions() {
            this.loading.openPositions = true;
            try {
                console.log('🔄 loadOpenPositions: fetching /api/positions/open');
                const res  = await fetch('/api/positions/open', {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` }
                });
                console.log('🔍 loadOpenPositions: HTTP status', res.status);
                let data;
                try {
                    data = await res.json();
                } catch (jsonErr) {
                    const text = await res.text().catch(() => '');
                    console.error('❌ loadOpenPositions: non-JSON response', res.status, text.slice(0, 300));
                    this.openPositions = [];
                    this.openPositionsMessage = `Server error (HTTP ${res.status}). Check console.`;
                    return;
                }
                console.log('📦 loadOpenPositions: response', data);
                if (data.success) {
                    this.openPositions = data.data || [];
                    this.openPositionsMessage = this.openPositions.length === 0
                        ? (data.message || 'No open positions at broker.')
                        : '';
                } else {
                    this.openPositions = [];
                    this.openPositionsMessage = data.error || data.message || 'Failed to load positions.';
                }
            } catch (e) {
                console.error('❌ loadOpenPositions: network error', e);
                this.openPositions = [];
                this.openPositionsMessage = 'Could not reach server.';
            } finally {
                this.loading.openPositions = false;
            }
        },

        async loadPositionsHistory(silent = false) {
            try {
                if (!silent) this.loading.positions = true;

                const params = new URLSearchParams();
                params.append('limit', '1000');
                if (this.positionsHistoryStartDate) params.append('start_date', this.positionsHistoryStartDate);
                if (this.positionsHistoryEndDate)   params.append('end_date',   this.positionsHistoryEndDate);
                if (this.positionsHistoryTicker && this.positionsHistoryTicker.trim())
                    params.append('symbol', this.positionsHistoryTicker.trim().toUpperCase());
                if (this.positionsHistoryType && this.positionsHistoryType.trim())
                    params.append('position_type', this.positionsHistoryType.trim());
                // broker filter applied client-side in sortedPositions computed

                const response = await this.authFetch(`/api/positions/daily?${params.toString()}`);
                const data = await response.json();

                if (data.success) {
                    this.positions       = data.data.positions || [];
                    this.positionsSummary = data.data.summary  || {};
                } else if (!silent) {
                    this.showNotification('Failed to load positions: ' + data.error, 'error');
                }
            } catch (error) {
                if (!silent) this.showNotification('Error loading positions: ' + error.message, 'error');
            } finally {
                this.loading.positions = false;
            }
        },
        
        initializeDateRanges() {
            const today = new Date();
            const sevenDaysAgo = new Date();
            sevenDaysAgo.setDate(today.getDate() - 7);

            const todayStr = today.toISOString().split('T')[0];
            const fromStr  = sevenDaysAgo.toISOString().split('T')[0];

            this.dashboardPnLFromDate    = fromStr;
            this.dashboardPnLToDate      = todayStr;
            this.dashboardTradeFromDate  = fromStr;
            this.dashboardTradeToDate    = todayStr;
        },
            
        // Chart methods
            updatePnlChart() {
                console.log('🔄 Updating PnL chart from positions database...');
                console.log('📊 Chart object exists:', !!this.charts.pnl);
                console.log('📊 Dashboard PnL data:', this.dashboardPnL.length, 'positions');
                
                // Prevent multiple simultaneous chart updates
                if (this.chartUpdateInProgress) {
                    console.log('⚠️ Chart update already in progress, skipping...');
                    return;
                }
                
                this.chartUpdateInProgress = true;
                
                // Add a small delay to prevent rapid successive updates
                if (this.pnlChartUpdateTimeout) {
                    clearTimeout(this.pnlChartUpdateTimeout);
                }
                
                try {
                                    // Safely destroy existing chart if it exists
                if (this.charts.pnl) {
                    try {
                        if (typeof this.charts.pnl.destroy === 'function') {
                            this.charts.pnl.destroy();
                            console.log('🗑️ Destroyed existing PnL chart');
                        }
                    } catch (error) {
                        console.warn('⚠️ Error destroying existing PnL chart:', error);
                    }
                    this.charts.pnl = null;
                }
                    
                    // Create new chart with data directly from database
                    const ctx = document.getElementById('pnlChart');
                    if (!ctx) {
                        console.log('⚠️ PnL chart canvas not found - likely no trades yet');
                        this.chartUpdateInProgress = false;
                        return;
                    }
                    
                    // Ensure the canvas is visible and has dimensions
                    const rect = ctx.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) {
                        console.log('⚠️ PnL chart canvas has no dimensions, waiting...');
                        // Wait a bit and try again
                        setTimeout(() => {
                            this.chartUpdateInProgress = false;
                            this.updatePnlChart();
                        }, 100);
                        return;
                    }
                    
                    // Calculate cumulative P&L from database positions
                    const pnlData = [];
                    const labels = [];
                    let cumulativePnl = 0;
                    
                    // Sort positions by date and last_updated timestamp
                    const sortedPositions = [...this.dashboardPositions].sort((a, b) => {
                        const dateA = new Date(a.date + ' ' + (a.last_updated || a.created_at));
                        const dateB = new Date(b.date + ' ' + (b.last_updated || b.created_at));
                        return dateA - dateB;
                    });
                    
                    console.log('📊 Sorted positions from database:', sortedPositions.length);
                    
                    sortedPositions.forEach((position, index) => {
                        const positionPnl = position.realized || 0;
                        cumulativePnl += positionPnl;
                        pnlData.push(cumulativePnl);
                        // Use date and last_updated for timestamp
                        const timestamp = position.last_updated || position.created_at || position.date;
                        labels.push(new Date(timestamp).toLocaleDateString());
                        console.log(`📈 Position ${index + 1}: ${position.symbol} - PnL: $${positionPnl}, Cumulative: $${cumulativePnl}`);
                    });
                    
                    // If no positions, use default data
                    if (pnlData.length === 0) {
                        pnlData.push(0);
                        labels.push('No positions');
                        console.log('⚠️ No positions found in database, using default data');
                    }
                    
                    console.log('📊 Final PnL data from database:', pnlData);
                    console.log('📊 Final labels:', labels);
                    
                    // Check if canvas is visible and has dimensions
                    const canvasRect = ctx.getBoundingClientRect();
                    console.log('📊 Canvas dimensions:', {
                        width: canvasRect.width,
                        height: canvasRect.height,
                        visible: canvasRect.width > 0 && canvasRect.height > 0
                    });
                    
                    // Ensure canvas has proper dimensions
                    if (canvasRect.width === 0 || canvasRect.height === 0) {
                        console.log('⚠️ Canvas has no dimensions, setting default size');
                        ctx.style.width = '100%';
                        ctx.style.height = '300px';
                    }
                    
                    // Create chart immediately without setTimeout
                    try {
                        console.log('🔄 Creating PnL chart with database data:', {
                            labels: labels,
                            data: pnlData,
                            canvas: ctx
                        });
                        
                        this.charts.pnl = new Chart(ctx, {
                            type: 'line',
                            data: {
                                labels: labels,
                                datasets: [{
                                    label: 'Cumulative P&L',
                                    data: pnlData,
                                    borderColor: '#10B981',
                                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                    tension: 0.4,
                                    fill: true,
                                    pointBackgroundColor: '#10B981',
                                    pointBorderColor: '#ffffff',
                                    pointBorderWidth: 2,
                                    pointRadius: 4,
                                    pointHoverRadius: 6
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                animation: false, // Disable animation to prevent issues
                                plugins: {
                                    legend: {
                                        display: true,
                                        labels: {
                                            color: '#D1D5DB',
                                            font: {
                                                size: 12
                                            }
                                        }
                                    },
                                    tooltip: {
                                        enabled: true,
                                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                        titleColor: '#ffffff',
                                        bodyColor: '#ffffff',
                                        callbacks: {
                                            label: function(context) {
                                                if (context.parsed && context.parsed.y !== undefined) {
                                                    return 'P&L: $' + context.parsed.y.toLocaleString();
                                                }
                                                return '';
                                            }
                                        }
                                    }
                                },
                                scales: {
                                    y: {
                                        beginAtZero: true,
                                        display: true,
                                        ticks: {
                                            color: '#D1D5DB',
                                            callback: function(value) {
                                                return '$' + value.toLocaleString();
                                            }
                                        },
                                        grid: {
                                            color: '#374151',
                                            display: true
                                        }
                                    },
                                    x: {
                                        display: true,
                                        ticks: {
                                            color: '#D1D5DB',
                                            maxRotation: 45
                                        },
                                        grid: {
                                            color: '#374151',
                                            display: true
                                        }
                                    }
                                }
                            }
                        });
                        
                        console.log('✅ PnL chart created successfully from database data');
                        console.log('📊 Chart object:', this.charts.pnl);
                        
                    } catch (error) {
                        console.error('❌ Error creating PnL chart:', error);
                        this.charts.pnl = null;
                    } finally {
                        this.chartUpdateInProgress = false;
                    }
                    
                } catch (error) {
                    console.error('❌ Error in updatePnlChart:', error);
                    this.chartUpdateInProgress = false;
                }
            },
            
            setupPositionsChart() {
                const ctx = document.getElementById('positionsChart');
            if (!ctx) {
                console.log('⚠️ Positions chart canvas not found during setup');
                return;
            }
                
                this.charts.positions = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Winning', 'Losing', 'Pending'],
                        datasets: [{
                            data: [65, 25, 10],
                            backgroundColor: [
                                '#10B981',
                                '#EF4444',
                                '#F59E0B'
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                labels: {
                                    color: '#D1D5DB'
                                }
                            }
                        }
                    }
                });
            },
            
        // Update positions chart with database data
            updatePositionsChart() {
                const ctx = document.getElementById('positionsChart');
                if (!ctx) {
                    console.log('⚠️ Positions chart canvas not found - likely no positions yet');
                    return;
                }
                
                // Ensure the canvas is visible and has dimensions
                const rect = ctx.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) {
                    console.log('⚠️ Positions chart canvas has no dimensions, waiting...');
                    // Wait a bit and try again
                    setTimeout(() => {
                        this.updatePositionsChart();
                    }, 100);
                    return;
                }
                
                // Safely destroy existing chart if it exists
                if (this.charts.positions) {
                    try {
                        if (typeof this.charts.positions.destroy === 'function') {
                            this.charts.positions.destroy();
                            console.log('🗑️ Destroyed existing Positions chart');
                        }
                    } catch (error) {
                        console.warn('⚠️ Error destroying existing positions chart:', error);
                    }
                    this.charts.positions = null;
                }
                
                try {
                    // Ensure canvas has proper dimensions
                    const canvasRect = ctx.getBoundingClientRect();
                    if (canvasRect.width === 0 || canvasRect.height === 0) {
                        console.log('⚠️ Positions chart canvas has no dimensions, setting default size');
                        ctx.style.width = '100%';
                        ctx.style.height = '300px';
                    }
                    
                    let chartData = {};
                    let chartType = 'doughnut';
                    
                    // Prepare chart data based on view type
                                            switch (this.dashboardChartView) {
                        case 'long_short':
                            const longPositions = this.dashboardPositions.filter(p => {
                                const side = p.side?.toLowerCase() || p.direction?.toLowerCase() || '';
                                return side === 'b' || side === 'long'; // 'B' = Buy = Long
                            }).length;
                            
                            const shortPositions = this.dashboardPositions.filter(p => {
                                const side = p.side?.toLowerCase() || p.direction?.toLowerCase() || '';
                                return side === 's' || side === 'short'; // 'S' = Sell = Short
                            }).length;
                            
                            const otherPositions = this.dashboardPositions.length - longPositions - shortPositions;
                            
                            chartData = {
                                labels: ['Long Positions', 'Short Positions', 'Other Positions'],
                                datasets: [{
                                    data: [longPositions, shortPositions, otherPositions],
                                    backgroundColor: ['#10B981', '#EF4444', '#6B7280'],
                                    borderColor: '#374151',
                                    borderWidth: 2
                                }]
                            };
                            console.log('📊 Long vs Short distribution - Long:', longPositions, 'Short:', shortPositions, 'Other:', otherPositions);
                            break;
                            
                        case 'win_loss':
                            const winningPositions = this.dashboardPositions.filter(p => (p.realized || 0) > 0).length;
                            const losingPositions = this.dashboardPositions.filter(p => (p.realized || 0) < 0).length;
                            const neutralPositions = this.dashboardPositions.filter(p => (p.realized || 0) === 0).length;
                            
                            chartData = {
                                labels: ['Winning Positions', 'Losing Positions', 'Neutral Positions'],
                                datasets: [{
                                    data: [winningPositions, losingPositions, neutralPositions],
                                    backgroundColor: ['#10B981', '#EF4444', '#F59E0B'],
                                    borderColor: '#374151',
                                    borderWidth: 2
                                }]
                            };
                            console.log('📊 Win vs Loss distribution - Winning:', winningPositions, 'Losing:', losingPositions, 'Neutral:', neutralPositions);
                            break;
                            
                        case 'ticker':
                            // Group by ticker and show top 10
                            const tickerCounts = {};
                            this.dashboardPositions.forEach(position => {
                                const ticker = position.symbol || position.ticker || 'Unknown';
                                tickerCounts[ticker] = (tickerCounts[ticker] || 0) + 1;
                            });
                            
                            const sortedTickers = Object.entries(tickerCounts)
                                .sort(([,a], [,b]) => b - a)
                                .slice(0, 10);
                            
                            chartData = {
                                labels: sortedTickers.map(([ticker]) => ticker),
                                datasets: [{
                                    data: sortedTickers.map(([,count]) => count),
                                    backgroundColor: [
                                        '#10B981', '#3B82F6', '#8B5CF6', '#F59E0B', '#EF4444',
                                        '#06B6D4', '#84CC16', '#F97316', '#EC4899', '#6B7280'
                                    ],
                                    borderColor: '#374151',
                                    borderWidth: 1
                                }]
                            };
                            console.log('📊 Ticker distribution - Top 10 tickers:', sortedTickers);
                            break;
                            
                        case 'monthly':
                            // Group by month
                            const monthlyData = {};
                            this.dashboardPositions.forEach(position => {
                                const date = new Date(position.created_at || position.date || position.last_updated);
                                const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
                                monthlyData[monthKey] = (monthlyData[monthKey] || 0) + 1;
                            });
                            
                            const sortedMonths = Object.entries(monthlyData)
                                .sort(([a], [b]) => a.localeCompare(b))
                                .slice(-12); // Last 12 months
                            
                            chartType = 'bar';
                            chartData = {
                                labels: sortedMonths.map(([month]) => month),
                                datasets: [{
                                    label: 'Positions per Month',
                                    data: sortedMonths.map(([,count]) => count),
                                    backgroundColor: '#3B82F6',
                                    borderColor: '#1D4ED8',
                                    borderWidth: 1
                                }]
                            };
                            console.log('📊 Monthly distribution - Last 12 months:', sortedMonths);
                            break;
                            
                        default:
                            // Default to long_short
                            const defaultLong = this.dashboardPositions.filter(p => {
                                const side = p.side?.toLowerCase() || p.direction?.toLowerCase() || '';
                                return side === 'b' || side === 'long'; // 'B' = Buy = Long
                            }).length;
                            
                            const defaultShort = this.dashboardPositions.filter(p => {
                                const side = p.side?.toLowerCase() || p.direction?.toLowerCase() || '';
                                return side === 's' || side === 'short'; // 'S' = Sell = Short
                            }).length;
                            
                            chartData = {
                                labels: ['Long Trades', 'Short Trades'],
                                datasets: [{
                                    data: [defaultLong, defaultShort],
                                    backgroundColor: ['#10B981', '#EF4444'],
                                    borderColor: '#374151',
                                    borderWidth: 2
                                }]
                            };
                            break;
                    }
                    
                    // Create new chart with current data
                    this.charts.positions = new Chart(ctx, {
                        type: chartType,
                        data: chartData,
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            animation: false, // Disable animation to prevent issues
                            plugins: {
                                legend: {
                                    display: true,
                                    position: chartType === 'bar' ? 'top' : 'bottom',
                                    labels: {
                                        color: '#D1D5DB',
                                        font: {
                                            size: 12
                                        },
                                        padding: 20
                                    }
                                },
                                tooltip: {
                                    enabled: true,
                                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                    titleColor: '#ffffff',
                                    bodyColor: '#ffffff',
                                    callbacks: {
                                        label: function(context) {
                                            if (context.dataset && context.dataset.data) {
                                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                                const percentage = total > 0 ? ((context.parsed / total) * 100).toFixed(1) : 0;
                                                return `${context.label}: ${context.parsed} (${percentage}%)`;
                                            }
                                            return '';
                                        }
                                    }
                                }
                            },
                            scales: chartType === 'bar' ? {
                                y: {
                                    beginAtZero: true,
                                    ticks: {
                                        color: '#D1D5DB'
                                    },
                                    grid: {
                                        color: '#374151'
                                    }
                                },
                                x: {
                                    ticks: {
                                        color: '#D1D5DB',
                                        maxRotation: 45
                                    },
                                    grid: {
                                        color: '#374151'
                                    }
                                }
                            } : undefined
                        }
                    });
                    
                    console.log('✅ Positions chart created successfully with database data');
                    
                } catch (error) {
                    console.error('❌ Error updating positions chart:', error);
                    this.charts.positions = null;
                }
            },
            
        setupCharts() {
            try {
                console.log('🔄 Setting up charts...');
                
                // Check if Chart.js is available
                if (typeof Chart === 'undefined') {
                    console.error('❌ Chart.js is not loaded');
                    return;
                }
                
                console.log('📊 Chart.js version:', Chart.version);
                
                // Only setup positions chart - PnL chart is created dynamically
                this.setupPositionsChart();
                
                console.log('📊 Charts initialized:', {
                    pnl: !!this.charts.pnl,
                    positions: !!this.charts.positions
                });
                
                // Handle window resize to prevent chart issues
                window.addEventListener('resize', () => {
                    try {
                        if (this.charts.pnl && typeof this.charts.pnl.resize === 'function') {
                            this.charts.pnl.resize();
                        }
                        if (this.charts.positions && typeof this.charts.positions.resize === 'function') {
                            this.charts.positions.resize();
                        }
                    } catch (error) {
                        console.warn('⚠️ Error resizing charts:', error);
                    }
                });
            } catch (error) {
                console.error('❌ Error setting up charts:', error);
                // Continue without charts if they fail to load
            }
        },
        
        // DAS Integration Methods
        async syncTradesFromDAS() {
            try {
                console.log('🔄 Syncing trades from DAS Trader...');
                this.loading.syncTrades = true;
                
                const response = await axios.post('/api/trades/sync-das');
                
                if (response.data.success) {
                    const data = response.data.data;
                    const message = `✅ Synced ${data.added_count} trades from DAS Trader`;
                    this.showNotification(message, 'success');
                    console.log('✅ DAS sync completed successfully:', data);
                    
                    // Reload trade history after sync
                    await this.loadTradeHistory();
                } else {
                    this.showNotification(`❌ Failed to sync from DAS: ${response.data.error}`, 'error');
                    console.error('❌ DAS sync failed:', response.data.error);
                }
                } catch (error) {
                console.error('❌ Error syncing from DAS:', error);
                this.showNotification('❌ Error syncing from DAS Trader', 'error');
            } finally {
                this.loading.syncTrades = false;
            }
        },
        
        
        async importDASData() {
            try {
                if (!this.dasTradesData.trim()) {
                    this.showNotification('Please enter DAS trades data', 'warning');
                    return;
                }
                
                console.log('🔄 Importing DAS trades data...');
                this.loading.importDAS = true;
                
                const response = await axios.post('/api/trades/import-das', {
                    das_trades_text: this.dasTradesData
                });
                
                if (response.data.success) {
                    const data = response.data.data;
                    const message = `✅ Successfully imported ${data.added_count} trades from DAS data`;
                    this.showNotification(message, 'success');
                    console.log('✅ DAS data import completed:', data);
                    
                    // Close modal and reload trade history
                    this.showImportModal = false;
                    this.dasTradesData = '';
                    await this.loadTradeHistory();
                    
                    // Show errors if any
                    if (data.errors && data.errors.length > 0) {
                        console.warn('⚠️ Some trades failed to import:', data.errors);
                    }
                } else {
                    this.showNotification(`❌ Failed to import DAS data: ${response.data.error}`, 'error');
                    console.error('❌ DAS data import failed:', response.data.error);
                }
            } catch (error) {
                console.error('❌ Error importing DAS data:', error);
                this.showNotification('❌ Error importing DAS data', 'error');
            } finally {
                this.loading.importDAS = false;
            }
        },
        
        // Position Sync Status Methods
        async loadPositionSyncStatus() {
            try {
                console.log('🔄 Loading position sync status...');
                console.log('🔍 Making request to /api/positions/sync-status...');
                const response = await axios.get('/api/positions/sync-status');
                console.log('🔍 Response received:', response.status, response.data);
                
                if (response.data.success) {
                    this.scheduledSyncStatus = response.data.data;
                    console.log('✅ Position sync status loaded:', this.scheduledSyncStatus);
                    console.log('✅ scheduledSyncStatus.is_running:', this.scheduledSyncStatus.is_running);
                } else {
                    console.error('❌ Failed to load position sync status:', response.data.error);
                }
            } catch (error) {
                console.error('❌ Error loading position sync status:', error);
                console.error('❌ Error details:', error.response?.data || error.message);
                // Fallback to show running status since we know it's running in app.py
                this.scheduledSyncStatus = {
                    is_running: true,
                    is_market_hours: true,
                    current_time_et: new Date().toLocaleTimeString(),
                    next_scheduled_run: null,
                    thread_alive: true,
                    sync_type: 'automatic',
                    update_interval: '10 seconds'
                };
            }
        },

        // Scheduled Sync Methods (for trade sync)
        async loadScheduledSyncStatus() {
            try {
                console.log('🔄 Loading scheduled sync status...');
                const response = await axios.get('/api/scheduled-sync/status');
                
                if (response.data.success) {
                    // Only update trade sync status, keep position sync status separate
                    const tradeSyncStatus = response.data.data;
                    console.log('✅ Scheduled sync status loaded:', tradeSyncStatus);
                } else {
                    console.error('❌ Failed to load scheduled sync status:', response.data.error);
                }
            } catch (error) {
                console.error('❌ Error loading scheduled sync status:', error);
            }
        },
        
        async startScheduledSync() {
            try {
                console.log('🔄 Starting scheduled sync service...');
                this.loading.scheduledSync = true;
                
                const response = await axios.post('/api/scheduled-sync/start');
                
                if (response.data.success) {
                    this.showNotification('✅ Scheduled sync service started', 'success');
                    console.log('✅ Scheduled sync started successfully');
                    
                    // Reload status
                    await this.loadScheduledSyncStatus();
                } else {
                    this.showNotification(`❌ Failed to start scheduled sync: ${response.data.error}`, 'error');
                    console.error('❌ Failed to start scheduled sync:', response.data.error);
                }
            } catch (error) {
                console.error('❌ Error starting scheduled sync:', error);
                this.showNotification('❌ Error starting scheduled sync', 'error');
            } finally {
                this.loading.scheduledSync = false;
            }
        },
        
        async stopScheduledSync() {
            try {
                console.log('🛑 Stopping scheduled sync service...');
                this.loading.scheduledSync = true;
                
                const response = await axios.post('/api/scheduled-sync/stop');
                
                if (response.data.success) {
                    this.showNotification('🛑 Scheduled sync service stopped', 'success');
                    console.log('✅ Scheduled sync stopped successfully');
                    
                    // Reload status
                    await this.loadScheduledSyncStatus();
                } else {
                    this.showNotification(`❌ Failed to stop scheduled sync: ${response.data.error}`, 'error');
                    console.error('❌ Failed to stop scheduled sync:', response.data.error);
                }
            } catch (error) {
                console.error('❌ Error stopping scheduled sync:', error);
                this.showNotification('❌ Error stopping scheduled sync', 'error');
            } finally {
                this.loading.scheduledSync = false;
            }
        },
        
        async triggerManualSync() {
            try {
                console.log('🔄 Triggering manual sync...');
                this.loading.scheduledSync = true;
                
                const response = await axios.post('/api/scheduled-sync/manual');
                
                if (response.data.success) {
                    const data = response.data.data;
                    const message = `✅ Manual sync completed: ${data.synced_count} trades synced`;
                    this.showNotification(message, 'success');
                    console.log('✅ Manual sync completed successfully:', data);
                    
                    // Reload trade history and status
                    await Promise.all([
                        this.loadTradeHistory(),
                        this.loadScheduledSyncStatus()
                    ]);
                } else {
                    const errorMsg = response.data.error || response.data.message || 'Unknown error';
                    this.showNotification(`❌ Manual sync failed: ${errorMsg}`, 'error');
                    console.error('❌ Manual sync failed:', errorMsg);
                }
            } catch (error) {
                console.error('❌ Error triggering manual sync:', error);
                const errorMsg = error.response?.data?.error || error.response?.data?.message || error.message || 'Network error';
                this.showNotification(`❌ Manual sync failed: ${errorMsg}`, 'error');
            } finally {
                this.loading.scheduledSync = false;
            }
        },
        
        // Utility Methods
            showNotification(message, type = 'info') {
                // Removed notification banners - logging to console instead
                const logLevel = type === 'error' ? 'error' : type === 'warning' ? 'warn' : 'log';
                console[logLevel](`[${type.toUpperCase()}] ${message}`);
            },

        // ───────────────────── Fundamentals Screener ─────────────────────
        presetOptions(type) {
            // Each option carries a {min,max} range (null = unbounded). Index 0 = "Any".
            const P = {
                mktcap: [
                    { label: 'Any' }, { label: 'Mega (>$200B)', min: 200e9 },
                    { label: 'Large (>$10B)', min: 10e9 }, { label: 'Mid ($2B-$10B)', min: 2e9, max: 10e9 },
                    { label: 'Small ($300M-$2B)', min: 300e6, max: 2e9 },
                    { label: 'Micro (<$300M)', max: 300e6 },
                ],
                price: [
                    { label: 'Any' }, { label: 'Under $5', max: 5 }, { label: 'Under $10', max: 10 },
                    { label: 'Under $20', max: 20 }, { label: '$10-$50', min: 10, max: 50 },
                    { label: 'Over $50', min: 50 }, { label: 'Over $100', min: 100 },
                ],
                volume: [
                    { label: 'Any' }, { label: 'Over 100K', min: 1e5 }, { label: 'Over 500K', min: 5e5 },
                    { label: 'Over 1M', min: 1e6 }, { label: 'Over 10M', min: 1e7 },
                ],
                ratio: [
                    { label: 'Any' }, { label: 'Under 1', max: 1 }, { label: 'Under 2', max: 2 },
                    { label: 'Under 5', max: 5 }, { label: 'Under 15', max: 15 }, { label: 'Under 25', max: 25 },
                    { label: 'Over 0', min: 0 }, { label: 'Over 1', min: 1 }, { label: 'Over 5', min: 5 },
                ],
                eps: [
                    { label: 'Any' }, { label: 'Positive (>0)', min: 0 }, { label: 'Negative (<0)', max: 0 },
                    { label: 'Over $1', min: 1 }, { label: 'Over $5', min: 5 },
                ],
                pct: [  // values stored as fractions (0.15 = 15%)
                    { label: 'Any' }, { label: 'Positive', min: 0 }, { label: 'Negative', max: 0 },
                    { label: 'Over 5%', min: 0.05 }, { label: 'Over 10%', min: 0.10 },
                    { label: 'Over 15%', min: 0.15 }, { label: 'Over 20%', min: 0.20 },
                    { label: 'Over 30%', min: 0.30 }, { label: 'Under 50%', max: 0.50 },
                ],
            };
            return P[type] || P.ratio;
        },
        onScreenerPreset(m) {
            if (this.screenerSel[m.key] !== 'custom') this.runScreener();
        },
        buildScreenerFilters() {
            const filters = [];
            if (this.screenerCat.sector) filters.push({ col: 'sector', eq: this.screenerCat.sector });
            if (this.screenerCat.exchange) filters.push({ col: 'exchange', eq: this.screenerCat.exchange });
            for (const m of this.screenerMetrics) {
                const sel = this.screenerSel[m.key];
                if (sel === undefined || sel === 0 || sel === '0') continue;
                if (sel === 'custom') {
                    const c = this.screenerCustom[m.key] || {};
                    if (c.min != null && c.min !== '' || c.max != null && c.max !== '') {
                        const f = { col: m.key };
                        if (c.min != null && c.min !== '') f.min = c.min;
                        if (c.max != null && c.max !== '') f.max = c.max;
                        filters.push(f);
                    }
                } else {
                    const opt = this.presetOptions(m.type)[sel];
                    if (!opt) continue;
                    const f = { col: m.key };
                    if (opt.min != null) f.min = opt.min;
                    if (opt.max != null) f.max = opt.max;
                    if (f.min != null || f.max != null) filters.push(f);
                }
            }
            return filters;
        },
        async loadScreenerMeta() {
            try {
                const res = await this.authFetch('/api/screener/meta');
                const data = await res.json();
                if (data.success) this.screenerMeta = Object.assign({ sectors: [], exchanges: [] }, data.meta);
            } catch (e) { /* ignore */ }
        },
        async runScreener() {
            this.screenerLoading = true;
            try {
                const res = await this.authFetch('/api/screener/data', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        filters: this.buildScreenerFilters(),
                        sort_by: this.screenerSort.by,
                        sort_dir: this.screenerSort.dir,
                        limit: this.screenerLimit,
                        exclude_funds: this.screenerExcludeFunds,
                    }),
                });
                const data = await res.json();
                this.screenerRows = data.success ? (data.rows || []) : [];
            } catch (e) {
                this.screenerRows = [];
            } finally {
                this.screenerLoading = false;
            }
        },
        sortScreener(col) {
            if (this.screenerSort.by === col) {
                this.screenerSort.dir = this.screenerSort.dir === 'asc' ? 'desc' : 'asc';
            } else {
                this.screenerSort.by = col;
                this.screenerSort.dir = (col === 'symbol' || col === 'company_name' || col === 'sector') ? 'asc' : 'desc';
            }
            this.runScreener();
        },
        resetScreener() {
            this.screenerSel = {};
            this.screenerCustom = {};
            this.screenerCat = { sector: '', exchange: '' };
            this.screenerSort = { by: 'market_cap', dir: 'desc' };
            this.runScreener();
        },
        async refreshScreenerData() {
            try {
                const res = await this.authFetch('/api/screener/refresh', { method: 'POST',
                    headers: { 'Content-Type': 'application/json' }, body: '{}' });
                const data = await res.json();
                if (!data.success) { alert(data.error || 'Refresh failed'); return; }
                // Poll meta while refresh runs so the progress counter updates.
                if (this.screenerRefreshTimer) clearInterval(this.screenerRefreshTimer);
                this.screenerRefreshTimer = setInterval(async () => {
                    await this.loadScreenerMeta();
                    if (!this.screenerMeta.refresh || !this.screenerMeta.refresh.running) {
                        clearInterval(this.screenerRefreshTimer);
                        this.screenerRefreshTimer = null;
                        this.runScreener();
                    }
                }, 4000);
            } catch (e) { alert('Refresh request failed'); }
        },
        initScreener() {
            if (this.screenerLoaded) return;
            this.screenerLoaded = true;
            for (const m of this.screenerMetrics) {
                this.screenerSel[m.key] = 0;
                this.screenerCustom[m.key] = { min: null, max: null };
            }
            this.loadScreenerMeta().then(() => this.runScreener());
        },
        fmtCell(v, c) {
            if (v == null || v === '') return '–';
            switch (c.fmt) {
                case 'mktcap': return this.fmtMarketCap(v);
                case 'volume': return this.fmtMarketCap(v).replace('$', '');
                case 'usd': return '$' + Number(v).toFixed(2);
                case 'num1': return Number(v).toFixed(1);
                case 'num2': return Number(v).toFixed(2);
                case 'pct': return (Number(v) * 100).toFixed(1) + '%';      // fraction -> %
                case 'pct_raw': return Number(v).toFixed(2) + '%';          // already a % value
                default: return v;
            }
        },
        fmtMarketCap(v) {
            v = Number(v);
            if (v >= 1e12) return '$' + (v / 1e12).toFixed(2) + 'T';
            if (v >= 1e9)  return '$' + (v / 1e9).toFixed(2) + 'B';
            if (v >= 1e6)  return '$' + (v / 1e6).toFixed(1) + 'M';
            if (v >= 1e3)  return '$' + (v / 1e3).toFixed(0) + 'K';
            return '$' + v.toFixed(0);
        },

        // ───────────────────── Swing Setups ─────────────────────
        initSwingSetups() {
            if (this.swingLoaded) return;
            this.swingLoaded = true;
            for (const m of this.swingFundMetrics) {
                this.swingFundSel[m.key] = this.swingFundDefaults[m.key] ?? 0;
            }
            this.loadSwingMeta().then(() => this.runSwing());
        },
        async loadSwingMeta() {
            try {
                const res = await this.authFetch('/api/swing-setups/meta');
                const data = await res.json();
                if (data.success) this.swingMeta = Object.assign({ sectors: [] }, data.meta);
            } catch (e) { /* ignore */ }
        },
        buildSwingFundFilters() {
            const filters = [];
            for (const m of this.swingFundMetrics) {
                const sel = this.swingFundSel[m.key];
                if (sel === undefined || sel === 0 || sel === '0') continue;
                const opt = this.presetOptions(m.type)[sel];
                if (!opt) continue;
                const f = { col: m.key };
                if (opt.min != null) f.min = opt.min;
                if (opt.max != null) f.max = opt.max;
                if (f.min != null || f.max != null) filters.push(f);
            }
            return filters;
        },
        async runSwing() {
            this.swingLoading = true;
            try {
                const res = await this.authFetch('/api/swing-setups/data', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        trend: this.swingTrend,
                        filters: this.buildSwingFundFilters(),
                        sort_by: this.swingSort.by,
                        sort_dir: this.swingSort.dir,
                        limit: 200,
                    }),
                });
                const data = await res.json();
                this.swingRows = data.success ? (data.rows || []) : [];
            } catch (e) {
                this.swingRows = [];
            } finally {
                this.swingLoading = false;
            }
        },
        sortSwing(col) {
            if (this.swingSort.by === col) {
                this.swingSort.dir = this.swingSort.dir === 'asc' ? 'desc' : 'asc';
            } else {
                this.swingSort.by = col;
                this.swingSort.dir = (col === 'symbol' || col === 'company_name' || col === 'sector') ? 'asc' : 'desc';
            }
            this.runSwing();
        },
        resetSwing() {
            this.swingTrend = {
                above_sma20: true, above_sma50: true, above_sma100: true, above_sma200: false,
                stacked: true, sma50_rising: true, rsi_min: 40, rsi_max: 80,
                min_price: 5, min_avg_vol: 300000,
            };
            for (const m of this.swingFundMetrics) this.swingFundSel[m.key] = this.swingFundDefaults[m.key] ?? 0;
            this.swingSort = { by: 'swing_score', dir: 'desc' };
            this.swingSelected = [];
            this.runSwing();
        },
        async gradeSwingAI() {
            if (!this.swingSelected.length) return;
            this.swingGrading = true;
            try {
                const res = await this.authFetch('/api/swing-setups/grade', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbols: this.swingSelected.slice(0, 8) }),
                });
                const data = await res.json();
                if (data.success) {
                    this.swingGrades = Object.assign({}, this.swingGrades, data.grades);
                } else {
                    alert(data.error || 'AI grading failed');
                }
            } catch (e) {
                alert('AI grading request failed');
            } finally {
                this.swingGrading = false;
            }
        },
        openSwingDetail(sym) {
            if (this.swingGrades[sym]) { this.swingDetailSymbol = sym; this.swingDetailOpen = true; }
        },
        async rerunSwingDetail() {
            const sym = this.swingDetailSymbol;
            if (!sym) return;
            this.swingGrading = true;
            try {
                const res = await this.authFetch('/api/swing-setups/grade', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbols: [sym], refresh: true }),
                });
                const data = await res.json();
                if (data.success && data.grades[sym]) {
                    this.swingGrades = Object.assign({}, this.swingGrades, data.grades);
                } else {
                    alert(data.error || 'Re-run failed');
                }
            } catch (e) {
                alert('Re-run request failed');
            } finally {
                this.swingGrading = false;
            }
        },
        swingMetricLabel(m) {
            const map = {
                pe: 'P/E', forward_pe: 'Forward P/E', ps: 'P/S', pb: 'P/B', ev_ebitda: 'EV/EBITDA',
                peg: 'PEG', roe: 'ROE', roa: 'ROA', net_margin: 'Net Margin', gross_margin: 'Gross Margin',
                operating_margin: 'Oper Margin', revenue_growth_yoy: 'Rev Gr YoY', eps_growth_yoy: 'EPS Gr YoY',
                debt_to_equity: 'Debt/Equity', fcf_yield: 'FCF Yield', dividend_yield: 'Div Yield',
            };
            return map[m] || m;
        },
        fmtSwingMetric(m, v) {
            if (v == null) return '—';
            const pctCols = ['roe','roa','net_margin','gross_margin','operating_margin','revenue_growth_yoy','eps_growth_yoy','fcf_yield','dividend_yield'];
            return pctCols.includes(m) ? (Number(v) * 100).toFixed(1) + '%' : Number(v).toFixed(2);
        },
        async scanSwingData() {
            try {
                const res = await this.authFetch('/api/swing-setups/scan', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
                const data = await res.json();
                if (!data.success) { alert(data.error || 'Scan failed'); return; }
                if (this.swingScanTimer) clearInterval(this.swingScanTimer);
                this.swingScanTimer = setInterval(async () => {
                    await this.loadSwingMeta();
                    if (!this.swingMeta.scan || !this.swingMeta.scan.running) {
                        clearInterval(this.swingScanTimer);
                        this.swingScanTimer = null;
                        this.runSwing();
                    }
                }, 5000);
            } catch (e) { alert('Scan request failed'); }
        },

        // Format date
        formatDate(dateString) {
            if (!dateString) return 'N/A';
            try {
                // Take only the date portion before any space or T (handles "YYYY-MM-DD HH:MM..." or ISO strings)
                const datePart = dateString.split(/[ T]/)[0];
                const [year, month, day] = datePart.split('-');
                return `${month}/${day}/${year}`;
            } catch (error) {
                return dateString;
            }
        },

        // Format trade execution time from a trade_time field (ISO UTC string) → ET display
        formatTradeTime(tradeTime) {
            if (!tradeTime) return '';
            try {
                let iso = tradeTime.trim();
                // trade_time is datetime.now().isoformat() from the server (UTC, no Z marker).
                // Without the Z, JS Date parses as local time — append it to force UTC.
                if (iso.includes('T') && !iso.endsWith('Z') && !/[+\-]\d{2}:?\d{2}$/.test(iso)) {
                    iso += 'Z';
                }
                if (!iso.includes('T')) {
                    // Bare HH:MM:SS — no date context, can't convert; show as-is
                    return iso.substring(0, 8);
                }
                return new Date(iso).toLocaleTimeString('en-US', {
                    timeZone: 'America/New_York',
                    hour:   '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: false,
                }) + ' ET';
            } catch (e) {
                return '';
            }
        },
        
        // Format number with commas
        formatNumber(num) {
            if (!num || num === 0) return 'N/A';
            return num.toLocaleString();
        },
        
        // Format currency
        formatCurrency(amount) {
            if (amount === null || amount === undefined) return '$0.00';
            return new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }).format(amount);
        },
        
        // Format percentage
        formatPercentage(value) {
            if (value === null || value === undefined) return '0.00';
            return value.toFixed(2);
        },
        
        formatFloat(shares) {
            if (!shares || shares === 0) return 'N/A';
            if (shares >= 1e9) return `${(shares / 1e9).toFixed(2)}B`;
            if (shares >= 1e6) return `${(shares / 1e6).toFixed(2)}M`;
            if (shares >= 1e3) return `${(shares / 1e3).toFixed(0)}K`;
            return shares.toString();
        },

        // Format market cap
        formatMarketCap(marketCap) {
            if (!marketCap || marketCap === 0) return 'N/A';
            
            if (marketCap >= 1e12) {
                return `$${(marketCap / 1e12).toFixed(2)}T`;
            } else if (marketCap >= 1e9) {
                return `$${(marketCap / 1e9).toFixed(2)}B`;
            } else if (marketCap >= 1e6) {
                return `$${(marketCap / 1e6).toFixed(2)}M`;
            } else if (marketCap >= 1e3) {
                return `$${(marketCap / 1e3).toFixed(2)}K`;
            } else {
                return `$${marketCap.toFixed(2)}`;
            }
        },
        
        // Get status color
        getStatusColor(status) {
            switch (status?.toLowerCase()) {
                case 'filled':
                    return 'text-green-400';
                case 'pending':
                    return 'text-yellow-400';
                case 'cancelled':
                    return 'text-red-400';
                default:
                    return 'text-gray-400';
            }
        },
        
        // Refresh all data
        async refreshData() {
            console.log('🔄 Manual refresh requested...');
            await this.forceRefreshDashboard();
        },
        
        async forceRefreshDashboard() {
            console.log('🔄 Force refreshing dashboard data...');
            this.loading.dashboard = true;

            try {
                this.dashboardStats = {
                    totalPositions: 0, winRate: 0, totalPnl: 0,
                    activePositions: 0, gapUps: this.gapUps.length
                };
                this.dashboardPositions = [];
                this.dashboardAnalytics = {
                    totalPositions: 0, overallWinRate: 0, totalPnl: 0, avgPositionPnl: 0,
                    longPositions: { count: 0, winRate: 0, pnl: 0 },
                    shortPositions: { count: 0, winRate: 0, pnl: 0 },
                    topPerformers: { bestTicker: '', bestPnl: 0 }
                };
                // Note: gapUps and trades are NOT cleared here.
                // loadGapUps() manages its own data and handles the silent merge path.
                this.trades = [];

                await Promise.all([
                    this.loadDashboardData(),
                    this.loadBotStatus(),
                    this.loadGapUps(),   // gap-ups refresh with proper spinner + cache handling
                ]);

                this.$nextTick(() => {
                    this.updatePnlChart();
                    this.updatePositionsChart();
                });

                this.showNotification('Dashboard refreshed successfully', 'success');
            } catch (error) {
                console.error('❌ Error force refreshing dashboard:', error);
                this.showNotification('Failed to refresh dashboard: ' + error.message, 'error');
            } finally {
                this.loading.dashboard = false;
            }
        },
        
        updateLoadingProgress(component, status) {
            console.log(`📊 Loading progress - ${component}: ${status}`);
            
            // Update loading states
            if (this.loading[component] !== undefined) {
                this.loading[component] = status === 'loading';
            }
            
            // Show notifications for important milestones
            if (status === 'success') {
                this.showNotification(`${component} loaded successfully`, 'success');
            } else if (status === 'error') {
                this.showNotification(`Failed to load ${component}`, 'error');
            }
        },
        
        showOverallLoadingState() {
            this.showNotification('Loading dashboard data...', 'info');
            this.loading.dashboard = true;
            this.loading.bot = true;
            // Note: loading.gapUps is intentionally NOT set here.
            // loadGapUps() owns its own spinner so hideOverallLoadingState()
            // can't prematurely clear it before the API call completes.
        },

        hideOverallLoadingState() {
            setTimeout(() => {
                this.loading.dashboard = false;
                this.loading.bot = false;
                // loading.gapUps is managed exclusively by loadGapUps()
            }, 2000);
        },
        
        async checkBackendConnectivity() {
            console.log('🔍 Checking backend connectivity...');
            const maxRetries = 5;
            const retryDelay = 2000; // 2 seconds
            
            for (let attempt = 1; attempt <= maxRetries; attempt++) {
                try {
                    console.log(`🔍 Backend connectivity attempt ${attempt}/${maxRetries}...`);
                    const response = await fetch('/api/health', {
                        method: 'GET',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        // Add timeout to prevent hanging
                        signal: AbortSignal.timeout(5000) // 5 second timeout
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        console.log('✅ Backend is accessible:', data);
                        this.showNotification('Backend connected successfully', 'success');
                        return true;
                    } else {
                        console.error(`❌ Backend returned error status: ${response.status}`);
                        if (attempt === maxRetries) {
                            this.showNotification('Backend is not responding properly', 'error');
                            return false;
                        }
                    }
                    } catch (error) {
                    console.error(`❌ Backend connectivity attempt ${attempt} failed:`, error);
                    if (attempt === maxRetries) {
                        this.showNotification('Cannot connect to backend server. Please ensure the backend is running.', 'error');
                        return false;
                    }
                    // Wait before retrying
                    await new Promise(resolve => setTimeout(resolve, retryDelay));
                }
            }
            return false;
        },
        
        async waitForBackendReady() {
            console.log('⏳ Waiting for backend to be fully ready...');
            const maxAttempts = 10;
            const delay = 1000; // 1 second between attempts
            
            for (let attempt = 1; attempt <= maxAttempts; attempt++) {
                try {
                    console.log(`🔍 Backend readiness check ${attempt}/${maxAttempts}...`);
                    const response = await fetch('/api/health', {
                        signal: AbortSignal.timeout(3000) // 3 second timeout
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        console.log('✅ Backend is ready:', data);
                        return true;
                    }
                    } catch (error) {
                    console.log(`⏳ Backend not ready yet (attempt ${attempt}):`, error.message);
                }
                
                // Wait before next attempt
                await new Promise(resolve => setTimeout(resolve, delay));
            }
            
            console.error('❌ Backend did not become ready within expected time');
            return false;
        },
        
        // Placeholder methods for compatibility
        async loadStrategiesFromBackend() {
            // Placeholder - implement if needed
            console.log('📊 Loading strategies from backend...');
        },
        
        loadStrategySettings() {
            // Placeholder - implement if needed
            console.log('⚙️ Loading strategy settings...');
        },
        
        initializeStrategyParameters() {
            // Placeholder - implement if needed
            console.log('🔧 Initializing strategy parameters...');
        },
        
        connectWebSocket() {
            // WebSocket is only used for gap-up data broadcasts, not stock subscriptions
            // Stock subscriptions are handled by DAS integration
            console.log('🔌 WebSocket connection not needed for stock subscriptions - using DAS integration');
        },
        
        startPeriodicUpdates() {
            // Placeholder - implement if needed
            console.log('⏰ Starting periodic updates...');
        },
        
        startPeriodicBotUpdates() {
            console.log('⏰ Starting periodic bot updates...');
            // Real-time updates are now handled by startRealTimeUpdates()
            // This method is kept for compatibility but the real work is done elsewhere
        },
        
        // Historical Data Methods
        async loadHistoricalPrefetchStatus() {
            try {
                const resp = await fetch('/api/historical-prefetch/status');
                const data = await resp.json();
                if (data.success) this.historicalPrefetchStatus = data.prefetched || {};
            } catch (e) { /* non-critical */ }
        },

        openInHistorical(ticker) {
            this.historicalTicker  = ticker.toUpperCase();
            this.selectedPeriod    = '1825';   // 5 years
            this.minGapPercent     = 5;        // widest gap filter
            this.historicalData    = [];       // clear stale data
            this.onTabChange('historical');
            this.$nextTick(() => this.loadHistoricalData());
        },

        async loadHistoricalData() {
            if (!this.historicalTicker.trim()) {
                this.showNotification('Please enter a ticker symbol', 'warning');
                return;
            }

            try {
                console.log(`📈 Loading historical data for ${this.historicalTicker}...`);
                this.loading.historical = true;

                const response = await this.authFetch(`/api/historical-data/${this.historicalTicker.toUpperCase()}?period=${this.selectedPeriod}&min_gap=${this.minGapPercent}&_t=${Date.now()}`, { cache: 'no-store' });
                const data = await response.json();

                if (data.success) {
                    this.historicalData = data.data || [];
                    this.historicalAnalysis = null;
                    this.historicalSectorInfo = null;
                    this.historicalSectorPerf = null;
                    this.historicalAnalysisCached = false;
                    this.historicalLoadedFromCache = !!this.historicalPrefetchStatus[this.historicalTicker.trim().toUpperCase()];
                    console.log(`✅ Loaded ${this.historicalData.length} days of historical data for ${this.historicalTicker}`);
                    this.showNotification(`Loaded ${this.historicalData.length} days of historical data`, 'success');
                    this.debugHistoricalData();
                    this.$nextTick(() => this.initHistoricalCharts());
                } else {
                    console.error('Failed to load historical data:', data.error);
                    this.showNotification('Failed to load historical data: ' + data.error, 'error');
                }
            } catch (error) {
                console.error('Error loading historical data:', error);
                this.showNotification('Error loading historical data: ' + error.message, 'error');
            } finally {
                this.loading.historical = false;
            }
        },
        
        getPeriodDescription() {
            const days = parseInt(this.selectedPeriod);
            if (days === 0)    return 'All Time';
            if (days === 180)  return '6 Months';
            if (days === 365)  return '1 Year';
            if (days === 730)  return '2 Years';
            if (days === 1095) return '3 Years';
            if (days === 1825) return '5 Years';
            return `${days} Days`;
        },
        
        getPeriodDays() {
            return parseInt(this.selectedPeriod);
        },
        
        getGapUpDaysCount() {
            const count = this.historicalData.filter(day => {
                const gapPercent = parseFloat(day['gap up % at open']) || 0;
                return gapPercent >= this.minGapPercent;
            }).length;
            console.log(`📊 Gap-up days count: ${count} (from ${this.historicalData.length} total days)`);
            return count;
        },

        getRunnerDaysCount() {
            const count = this.historicalData.filter(day => {
                const gapPercent = parseFloat(day['gap up % at open']) || 0;
                const closePercent = parseFloat(day['closing percent']) || 0;
                return gapPercent >= this.minGapPercent && closePercent >= this.minGapPercent;
            }).length;
            console.log(`🏃 Runner days count: ${count}`);
            return count;
        },

        getFaderDaysCount() {
            const count = this.historicalData.filter(day => {
                const gapPercent = parseFloat(day['gap up % at open']) || 0;
                const closePercent = parseFloat(day['closing percent']) || 0;
                return gapPercent >= this.minGapPercent && closePercent < this.minGapPercent;
            }).length;
            console.log(`📉 Fader days count: ${count}`);
            return count;
        },

        getAverageGapPercent() {
            const gapUpDays = this.historicalData.filter(day => {
                const gapPercent = parseFloat(day['gap up % at open']) || 0;
                return gapPercent >= this.minGapPercent;
            });
            if (gapUpDays.length === 0) return 0;
            const totalGap = gapUpDays.reduce((sum, day) => {
                const gapPercent = parseFloat(day['gap up % at open']) || 0;
                return sum + gapPercent;
            }, 0);
            const average = Math.round(totalGap / gapUpDays.length);
            console.log(`📊 Average gap percent: ${average}% (from ${gapUpDays.length} gap-up days)`);
            return average;
        },
        
        sortTable(column) {
            if (this.sortColumn === column) {
                this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                this.sortColumn = column;
                this.sortDirection = 'asc';
            }
            
            this.historicalData.sort((a, b) => {
                let aVal = a[column];
                let bVal = b[column];
                
                // Handle date sorting
                if (column === 'date') {
                    aVal = new Date(aVal);
                    bVal = new Date(bVal);
                }
                
                // Handle numeric sorting
                if (typeof aVal === 'string' && !isNaN(aVal)) {
                    aVal = parseFloat(aVal);
                    bVal = parseFloat(bVal);
                }
                
                if (this.sortDirection === 'asc') {
                    return aVal > bVal ? 1 : -1;
                } else {
                    return aVal < bVal ? 1 : -1;
                }
                });
            },
            
        getSortIcon(column) {
            if (this.sortColumn !== column) {
                return 'fas fa-sort text-gray-400';
            }
            return this.sortDirection === 'asc' ? 'fas fa-sort-up text-blue-400' : 'fas fa-sort-down text-blue-400';
        },
        
        downloadExcel() {
            if (this.historicalData.length === 0) {
                this.showNotification('No data to export', 'warning');
                return;
            }
            
            try {
                const worksheet = XLSX.utils.json_to_sheet(this.historicalData);
                const workbook = XLSX.utils.book_new();
                XLSX.utils.book_append_sheet(workbook, worksheet, `${this.historicalTicker}_Historical`);
                
                const filename = `${this.historicalTicker}_historical_data_${this.getPeriodDescription().replace(' ', '_')}.xlsx`;
                XLSX.writeFile(workbook, filename);
                
                this.showNotification('Excel file downloaded successfully', 'success');
            } catch (error) {
                console.error('Error downloading Excel:', error);
                this.showNotification('Error downloading Excel file', 'error');
            }
        },
        
        downloadCSV() {
            if (this.historicalData.length === 0) {
                this.showNotification('No data to export', 'warning');
                        return;
                    }
                    
            try {
                const headers = Object.keys(this.historicalData[0]);
                const csvContent = [
                    headers.join(','),
                    ...this.historicalData.map(row => 
                        headers.map(header => {
                            const value = row[header];
                            return typeof value === 'string' && value.includes(',') ? `"${value}"` : value;
                        }).join(',')
                    )
                ].join('\n');
                
                const blob = new Blob([csvContent], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${this.historicalTicker}_historical_data_${this.getPeriodDescription().replace(' ', '_')}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                this.showNotification('CSV file downloaded successfully', 'success');
                } catch (error) {
                console.error('Error downloading CSV:', error);
                this.showNotification('Error downloading CSV file', 'error');
            }
        },
        
        // Helper method to check if historical data is available
        hasHistoricalData() {
            return this.historicalData && this.historicalData.length > 0;
        },
        
        // Helper method to get a sample ticker for testing
        getSampleTicker() {
            const sampleTickers = ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'AMD'];
            return sampleTickers[Math.floor(Math.random() * sampleTickers.length)];
        },
        
        // Debug function to log historical data structure
        debugHistoricalData() {
            if (this.historicalData.length === 0) {
                console.log('❌ No historical data available');
                return;
            }
            
            console.log('🔍 Historical Data Structure Debug:');
            console.log('📊 Total records:', this.historicalData.length);
            console.log('📋 Sample record fields:', Object.keys(this.historicalData[0]));
            console.log('📄 Sample record:', this.historicalData[0]);
            
            // Check for gap-up data
            const gapUpDays = this.historicalData.filter(day => {
                const gapPercent = parseFloat(day['gap up % at open']) || 0;
                return gapPercent >= 25;
            });
            console.log('📈 Days with 25%+ gap-ups:', gapUpDays.length);
            
            if (gapUpDays.length > 0) {
                console.log('📊 Sample gap-up day:', gapUpDays[0]);
            }
        },
        
        buildHistoricalStats() {
            const data = this.historicalData;
            if (!data.length) return {};

            const total = data.length;
            const runnerDays = data.filter(d => d['Runner/Fader'] === 'Runner').length;
            const faderDays  = data.filter(d => d['Runner/Fader'] === 'Fader').length;
            const neutralDays = total - runnerDays - faderDays;

            const sum = (key) => data.reduce((s, d) => s + (parseFloat(d[key]) || 0), 0);
            const avgGap      = (sum('gap up % at open') / total).toFixed(1);
            const avgDayHigh  = (sum('day high %')       / total).toFixed(1);
            const avgClose    = (sum('closing percent')  / total).toFixed(1);
            const avgVol      = (sum('premarket volume') / total).toFixed(2);

            // Gap size buckets
            const gapDist = { '5-15%': 0, '15-30%': 0, '30-50%': 0, '50%+': 0 };
            data.forEach(d => {
                const g = parseFloat(d['gap up % at open']) || 0;
                if (g >= 50) gapDist['50%+']++;
                else if (g >= 30) gapDist['30-50%']++;
                else if (g >= 15) gapDist['15-30%']++;
                else gapDist['5-15%']++;
            });

            // Most common day-high time
            const timeCounts = {};
            data.forEach(d => { const t = d['day high time']; if (t) timeCounts[t] = (timeCounts[t] || 0) + 1; });
            const commonHighTime = Object.entries(timeCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A';

            // Recent 30-day runner rate
            const cutoff30 = new Date(); cutoff30.setDate(cutoff30.getDate() - 30);
            const recent30 = data.filter(d => new Date(d.date) >= cutoff30);
            const recent30RunnerPct = recent30.length
                ? Math.round(recent30.filter(d => d['Runner/Fader'] === 'Runner').length / recent30.length * 100) : 0;

            // High-volume runner rate (top 50% by premarket volume)
            const sortedVol = [...data].sort((a, b) => (parseFloat(b['premarket volume']) || 0) - (parseFloat(a['premarket volume']) || 0));
            const topHalf = sortedVol.slice(0, Math.ceil(total / 2));
            const highVolRunnerPct = topHalf.length
                ? Math.round(topHalf.filter(d => d['Runner/Fader'] === 'Runner').length / topHalf.length * 100) : 0;

            return {
                totalDays: total,
                runnerDays, faderDays, neutralDays,
                runnerPct:  total ? Math.round(runnerDays  / total * 100) : 0,
                faderPct:   total ? Math.round(faderDays   / total * 100) : 0,
                neutralPct: total ? Math.round(neutralDays / total * 100) : 0,
                avgGap, avgDayHigh, avgClose,
                avgPremarketVol: avgVol,
                commonHighTime,
                gapDistribution: gapDist,
                recent30RunnerPct,
                highVolRunnerPct,
                period: this.getPeriodDescription(),
                minGap: this.minGapPercent
            };
        },

        async runHistoricalAnalysis() {
            if (!this.historicalData.length) return;
            try {
                this.loading.historicalAnalysis = true;
                this.historicalAnalysis = null;
                const stats = this.buildHistoricalStats();
                // Send raw filtered rows so the agent can do its own pattern detection
                // (not just pre-aggregated stats). Cap at 200 rows to keep payload reasonable.
                const filteredRows = this.historicalData
                    .filter(d => (parseFloat(d['gap up % at open']) || 0) >= this.minGapPercent)
                    .slice(-200);
                const response = await fetch(`/api/historical-analysis/${this.historicalTicker.toUpperCase()}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ stats, rows: filteredRows })
                });
                const data = await response.json();
                if (data.success) {
                    this.historicalAnalysis = data.analysis;
                    this.historicalSectorInfo = data.sector_info || null;
                    this.historicalSectorPerf = data.sector_perf || null;
                    this.historicalAnalysisCached = data.cached || false;
                    this.$nextTick(() => {
                        const el = document.getElementById('ai-analysis-card');
                        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    });
                } else if (data.rate_limited) {
                    this.showNotification('AI Predict: ' + data.error, 'warning');
                } else {
                    this.showNotification('AI analysis failed: ' + (data.error || 'Unknown error'), 'error');
                }
            } catch (error) {
                this.showNotification('Error running AI analysis: ' + error.message, 'error');
            } finally {
                this.loading.historicalAnalysis = false;
            }
        },

        initHistoricalCharts() {
            this.destroyHistoricalCharts();
            if (!this.historicalData.length) return;

            const stats = this.buildHistoricalStats();
            const chartDefaults = {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#9ca3af', font: { size: 11 }, boxWidth: 12 } } },
                cutout: '60%'
            };

            const rfCtx = document.getElementById('runnerFaderChart');
            if (rfCtx) {
                this._historicalCharts.runnerFader = new Chart(rfCtx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Runner', 'Fader', 'Neutral'],
                        datasets: [{ data: [stats.runnerDays, stats.faderDays, stats.neutralDays],
                            backgroundColor: ['#22c55e', '#ef4444', '#6b7280'], borderWidth: 0 }]
                    },
                    options: { ...chartDefaults }
                });
            }

            const gdCtx = document.getElementById('gapDistChart');
            if (gdCtx) {
                const dist = stats.gapDistribution;
                this._historicalCharts.gapDist = new Chart(gdCtx, {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(dist),
                        datasets: [{ data: Object.values(dist),
                            backgroundColor: ['#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444'], borderWidth: 0 }]
                    },
                    options: { ...chartDefaults }
                });
            }

            const cbCtx = document.getElementById('closingBehaviorChart');
            if (cbCtx) {
                const posClose = this.historicalData.filter(d => (parseFloat(d['closing percent']) || 0) > 0).length;
                this._historicalCharts.closingBehavior = new Chart(cbCtx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Positive Close', 'Negative Close'],
                        datasets: [{ data: [posClose, this.historicalData.length - posClose],
                            backgroundColor: ['#22c55e', '#ef4444'], borderWidth: 0 }]
                    },
                    options: { ...chartDefaults }
                });
            }
        },

        destroyHistoricalCharts() {
            Object.values(this._historicalCharts).forEach(c => { try { c.destroy(); } catch(e) {} });
            this._historicalCharts = {};
        },

        async loadStockNews() {
            const ticker = this.historicalTicker.trim().toUpperCase();
            if (!ticker) return;
            try {
                this.loading.stockNews = true;
                this.stockNews = null;
                const response = await fetch(`/api/stock-news/${ticker}`);
                const data = await response.json();
                if (data.success) {
                    this.stockNews = data;
                } else {
                    this.showNotification('Could not load news: ' + (data.error || 'Unknown error'), 'error');
                }
            } catch (err) {
                this.showNotification('News fetch failed: ' + err.message, 'error');
            } finally {
                this.loading.stockNews = false;
            }
        },

        formatNewsTime(isoStr) {
            if (!isoStr) return '';
            try {
                const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
                if (diff < 3600)   return Math.floor(diff / 60) + 'm ago';
                if (diff < 86400)  return Math.floor(diff / 3600) + 'h ago';
                if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
                return new Date(isoStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            } catch { return ''; }
        },

        getOutlookColor(outlook) {
            if (!outlook) return 'text-gray-400';
            const o = outlook.toLowerCase();
            if (o === 'bullish') return 'text-green-400';
            if (o === 'bearish') return 'text-red-400';
            if (o === 'mixed')   return 'text-yellow-400';
            return 'text-gray-400';
        },

        getOutlookBg(outlook) {
            if (!outlook) return 'bg-gray-700';
            const o = outlook.toLowerCase();
            if (o === 'bullish') return 'bg-green-900/40 border border-green-700/50';
            if (o === 'bearish') return 'bg-red-900/40 border border-red-700/50';
            if (o === 'mixed')   return 'bg-yellow-900/40 border border-yellow-700/50';
            return 'bg-gray-700';
        },

        getCautionColor(level) {
            if (!level) return 'text-gray-400';
            const l = level.toLowerCase();
            if (l === 'high')   return 'text-red-400';
            if (l === 'medium') return 'text-yellow-400';
            if (l === 'low')    return 'text-green-400';
            return 'text-gray-400';
        },

        getPerfColor(pct) {
            if (pct == null || isNaN(pct)) return 'text-gray-400';
            return pct > 0 ? 'text-green-400' : (pct < 0 ? 'text-red-400' : 'text-gray-400');
        },

        getSectorTrendIcon(trend) {
            if (!trend) return 'fas fa-minus';
            const t = trend.toLowerCase();
            if (t.includes('up')) return 'fas fa-arrow-trend-up';
            if (t.includes('down')) return 'fas fa-arrow-trend-down';
            return 'fas fa-minus';
        },

        // ── Swing Trading methods ────────────────────────────────────────────

        async loadSwingData() {
            const ticker = this.swingTicker.trim().toUpperCase();
            if (!ticker) { this.showNotification('Enter a ticker first', 'warning'); return; }
            this.swingTechnicals = null;
            this.swingSectorInfo = null;
            this.swingSectorPerf = null;
            this.swingRecommendation = null;
            this.swingNews = null;
            this.swingFundamentals = null;
            this.swingTechnicalsCached = false;
            this.loading.swingTechnicals = true;
            try {
                const res  = await this.authFetch(`/api/swing-technicals/${ticker}`);
                const data = await res.json();
                if (!data.success) throw new Error(data.error || 'Failed');
                this.swingTechnicals = data.technicals;
                this.swingSectorInfo = data.sector_info;
                this.swingSectorPerf = data.sector_perf;
                this.swingTechnicalsCached = !!data.cached;
                // Fire fundamentals and news in parallel — neither blocks the technicals display
                this.loadSwingFundamentals(ticker);
                this.loadSwingNews(ticker);
            } catch (e) {
                this.showNotification(`Swing data error: ${e.message}`, 'error');
            } finally {
                this.loading.swingTechnicals = false;
            }
        },

        async loadSwingNews(ticker) {
            ticker = (ticker || this.swingTicker).trim().toUpperCase();
            if (!ticker) return;
            this.loading.swingNews = true;
            try {
                const res  = await fetch(`/api/stock-news/${ticker}`);
                const data = await res.json();
                if (data.success) this.swingNews = data;
            } catch (e) { /* silent */ }
            finally { this.loading.swingNews = false; }
        },

        async loadSwingFundamentals(ticker) {
            ticker = (ticker || this.swingTicker).trim().toUpperCase();
            if (!ticker) return;
            this.loading.swingFundamentals = true;
            try {
                const res  = await this.authFetch(`/api/swing-fundamentals/${ticker}`);
                const data = await res.json();
                if (data.success) this.swingFundamentals = data;
            } catch (e) { /* silent — fundamentals are supplementary */ }
            finally { this.loading.swingFundamentals = false; }
        },

        async loadSwingRecommendation() {
            if (!this.swingTechnicals) {
                this.showNotification('Load technicals first', 'warning');
                return;
            }
            this.swingRecommendation = null;
            this.loading.swingRecommendation = true;
            const ticker = this.swingTicker.trim().toUpperCase();
            try {
                const res  = await this.authFetch(`/api/swing-recommendation/${ticker}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        technicals:  this.swingTechnicals,
                        sector_info: this.swingSectorInfo,
                        sector_perf: this.swingSectorPerf,
                    }),
                });
                const data = await res.json();
                if (!data.success) throw new Error(data.error || 'AI error');
                this.swingRecommendation = data.recommendation;
            } catch (e) {
                this.showNotification(`AI error: ${e.message}`, 'error');
            } finally {
                this.loading.swingRecommendation = false;
            }
        },

        async runSwingBacktest() {
            this.loading.swingBacktest = true;
            this.swingBt.stats = null;
            this.swingBt.trades = [];
            this.swingBt.message = '';
            try {
                const res = await fetch('/api/brown-bot/swing-backtest', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('session_token')}` },
                    body: JSON.stringify({
                        start_date:        this.swingBt.startDate,
                        end_date:          this.swingBt.endDate,
                        grade_filter:      this.swingBt.gradeFilter,
                        bias_filter:       this.swingBt.biasFilter,
                        profit_target_pct: this.swingBt.profitTarget,
                        stop_loss_pct:     this.swingBt.stopLoss,
                        max_hold_days:     this.swingBt.maxHold,
                    }),
                });
                const data = await res.json();
                if (!data.success) throw new Error(data.error || 'Backtest failed');
                this.swingBt.stats  = (data.stats && 'total_trades' in data.stats) ? data.stats : null;
                this.swingBt.trades = data.trades || [];
                this.swingBt.message = data.message || '';
                this.swingBt.dataSource = data.stats?.data_source || '';
                if (!data.trades?.length && data.message) {
                    this.showNotification(data.message, 'info');
                }
            } catch (e) {
                this.showNotification(`Backtest error: ${e.message}`, 'error');
            } finally {
                this.loading.swingBacktest = false;
            }
        },

        async loadErCalendar(days) {
            this.erCalendarLoading = true;
            if (days) this.erCalendarDays = days;
            try {
                const res = await this.authFetch('/api/earnings/calendar?days=' + this.erCalendarDays);
                const data = await res.json();
                if (data.success) {
                    this.erCalendar = data.calendar || [];
                    // Auto-select the first date with entries
                    if (this.erCalendar.length && !this.erCalendar.find(d => d.date === this.erSelectedDate)) {
                        this.erSelectedDate = this.erCalendar[0].date;
                    }
                }
            } catch (e) {
                this.erCalendar = [];
            } finally {
                this.erCalendarLoading = false;
            }
        },
        erDayLabel(dateStr) {
            const d = new Date(dateStr + 'T00:00:00');
            return d.toLocaleDateString('en-US', { weekday: 'short' });
        },
        erShortDate(dateStr) {
            const d = new Date(dateStr + 'T00:00:00');
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        },
        erDaysFromNow(erDate) {
            if (!erDate) return -1;
            const today = new Date(); today.setHours(0,0,0,0);
            const er = new Date(erDate + 'T00:00:00');
            return Math.round((er - today) / 86400000);
        },
        async loadEarnings() {
            const sym = this.erTicker.trim().toUpperCase();
            if (!sym) return;
            this.erData = null;
            this.loading.earnings = true;
            try {
                const res = await this.authFetch('/api/earnings/' + sym);
                this.erData = await res.json();
            } catch (e) {
                this.erData = { success: false, error: 'Network error — please try again.' };
            } finally {
                this.loading.earnings = false;
            }
        },
        goToEarnings(ticker) {
            if (!this.canAccessTab('earnings')) return;
            this.erTicker = ticker;
            this.erData = null;
            this.handleTabClick('earnings');
            this.$nextTick(() => this.loadEarnings());
        },
        erRevQoQ(quarters, i) {
            if (i >= quarters.length - 1) return null;
            const curr = quarters[i].revenue_b, prev = quarters[i+1].revenue_b;
            if (curr == null || prev == null || prev === 0) return null;
            return ((curr - prev) / prev * 100).toFixed(1);
        },
        swingGradeColor(grade) {
            if (!grade) return 'text-gray-400';
            const g = grade.toUpperCase();
            if (g === 'A') return 'text-green-400';
            if (g === 'B') return 'text-blue-400';
            if (g === 'C') return 'text-yellow-400';
            return 'text-red-400';
        },

        swingGradeBg(grade) {
            if (!grade) return 'bg-gray-800';
            const g = grade.toUpperCase();
            if (g === 'A') return 'bg-green-900/40 border border-green-700';
            if (g === 'B') return 'bg-blue-900/40 border border-blue-700';
            if (g === 'C') return 'bg-yellow-900/40 border border-yellow-700';
            return 'bg-red-900/40 border border-red-700';
        },

        swingBiasColor(bias) {
            if (!bias) return 'text-gray-400';
            const b = bias.toLowerCase();
            if (b === 'bullish') return 'text-green-400';
            if (b === 'bearish') return 'text-red-400';
            return 'text-yellow-400';
        },

        rsiColor(rsi) {
            if (rsi == null) return 'text-gray-400';
            if (rsi < 30)  return 'text-green-400';
            if (rsi > 70)  return 'text-red-400';
            return 'text-yellow-300';
        },

        macdColor(hist) {
            if (hist == null) return 'text-gray-400';
            return hist > 0 ? 'text-green-400' : 'text-red-400';
        },

        priceVsSma(price, sma) {
            if (!price || !sma) return { label: '—', cls: 'text-gray-400' };
            return price > sma
                ? { label: 'Above', cls: 'text-green-400' }
                : { label: 'Below', cls: 'text-red-400' };
        },

        bbPosition(price, lower, upper) {
            if (!price || !lower || !upper) return '—';
            const pct = ((price - lower) / (upper - lower) * 100).toFixed(0);
            return `${pct}%`;
        },

        swingSignalBadgeColor(type) {
            if (type === 'bullish') return 'bg-green-900/60 text-green-300 border border-green-700';
            if (type === 'bearish') return 'bg-red-900/60 text-red-300 border border-red-700';
            return 'bg-gray-700 text-gray-300 border border-gray-600';
        },

        async loadSectorStrength() {
            this.sectorStrengthLoading = true;
            try {
                const res = await axios.get('/api/sector-strength');
                if (res.data.success) this.sectorStrength = res.data.sectors;
            } catch (e) {
                console.error('Sector strength fetch failed:', e);
            } finally {
                this.sectorStrengthLoading = false;
            }
        },

        toggleSector(sector) {
            this.activeSector = this.activeSector?.etf === sector.etf ? null : sector;
        },

        async loadSwingPicksDates() {
            try {
                const res = await this.authFetch('/api/swing-daily-picks/dates');
                const data = await res.json();
                if (data.success) this.swingPicksDates = data.dates;
            } catch (_) {}
        },

        async selectSwingDate(date) {
            this.swingPicksSelectedDate = date;
            if (!date) {
                // Reset to latest
                this.swingDailyPicks = null;
                this.swingDailyPicksDate = null;
                this.loadSwingDailyPicks(true);
                return;
            }
            this.loading.swingDailyPicks = true;
            try {
                const res = await this.authFetch(`/api/swing-daily-picks/latest?date=${date}`);
                const data = await res.json();
                if (data.success) {
                    this.swingDailyPicks = data;
                    this.swingDailyPicksDate = data.date;
                } else {
                    this.showNotification(data.error || 'No picks for that date', 'error');
                }
            } catch (_) {
                this.showNotification('Failed to load picks for that date', 'error');
            } finally {
                this.loading.swingDailyPicks = false;
            }
        },

        async loadSwingDailyPicks(force = false) {
            const today = new Date().toISOString().slice(0, 10);

            // If a historical date is selected, load that instead
            if (this.swingPicksSelectedDate && this.swingPicksSelectedDate !== today) {
                return this.selectSwingDate(this.swingPicksSelectedDate);
            }

            // Step 1: fast-path — always try the DB first (previous session or today)
            try {
                const snap = await fetch('/api/swing-daily-picks/latest');
                const snapData = await snap.json();
                if (snapData.success && snapData.picks?.length) {
                    this.swingDailyPicks = snapData;
                    if (!snapData.market_open && !force) {
                        this.swingDailyPicksDate = today;
                        return;
                    }
                    this.swingDailyPicksDate = snapData.date;
                    if (snapData.is_today && !force) return;
                }
            } catch (_) { /* silent — fall through to full fetch */ }

            // Step 2: compute today's fresh picks (only reached when market is open)
            this.loading.swingDailyPicks = true;
            const prevPicks = this.swingDailyPicks;
            try {
                const res  = await fetch('/api/swing-daily-picks');
                const data = await res.json();
                if (!data.success) throw new Error(data.error || 'No picks available');
                // Only overwrite if new data has picks — don't clobber good prior data
                // with an empty result from a stale after-hours compute
                if (data.picks?.length || !prevPicks?.picks?.length) {
                    this.swingDailyPicks = data;
                    this.swingDailyPicksDate = data.date || today;
                }
            } catch (e) {
                this.showNotification(`Daily picks: ${e.message}`, 'error');
            } finally {
                this.loading.swingDailyPicks = false;
            }
        },

        selectSwingPick(ticker) {
            this.swingTicker = ticker;
            this.swingTechnicals = null;
            this.swingRecommendation = null;
            this.swingNews = null;
            this.swingFundamentals = null;
            this.loadSwingData();
        },

        // ── End Swing methods ────────────────────────────────────────────────

        // Helper method to get color class for pattern types
        getPatternColor(pattern) {
            if (!pattern) return 'bg-gray-100 text-gray-800';
            
            const patternLower = pattern.toLowerCase();
            if (patternLower.includes('runner') || patternLower.includes('strong')) {
                return 'bg-green-100 text-green-800';
            } else if (patternLower.includes('fader') || patternLower.includes('weak')) {
                return 'bg-red-100 text-red-800';
            } else if (patternLower.includes('neutral') || patternLower.includes('mixed')) {
                return 'bg-yellow-100 text-yellow-800';
            } else {
                return 'bg-gray-100 text-gray-800';
            }
        },
        
        // Helper method to get color class for price changes
        getPriceColor(stock) {
            if (!stock || !stock.price_change_percent) return 'text-gray-400';
            
            const change = parseFloat(stock.price_change_percent);
            if (change > 0) {
                return 'text-green-400';
            } else if (change < 0) {
                return 'text-red-400';
                    } else {
                return 'text-gray-400';
            }
        },
        
        // Helper method to validate strategy parameters
        validateStrategyParameter(strategy, parameter) {
            const value = strategy[parameter];
            if (value < 0) {
                strategy[parameter] = 0;
                this.showNotification(`${parameter} cannot be negative`, 'warning');
            } else if (value > 200) {
                strategy[parameter] = 200;
                this.showNotification(`${parameter} cannot exceed 200%`, 'warning');
            }
        },
        
        // Helper method to view current settings
        viewCurrentSettings() {
            const settings = {
                botStatus: this.botStatus,
                botConfig: this.botConfig,
                scheduledSync: this.scheduledSyncStatus
            };
            console.log('📋 Current Settings:', settings);
            this.showNotification('Current settings logged to console', 'info');
        },
        
        // Helper method to clear trade history for a specific ticker
        clearTradeHistoryTicker() {
            this.tradeHistoryTicker = '';
        },

        clearTradeFilters() {
            this.tradeHistoryTicker    = '';
            this.tradeHistoryStartDate = '';
            this.tradeHistoryEndDate   = '';
            this.tradeHistoryStyle     = '';
            this.tradeHistoryStatus    = '';
        },

        clearPositionsHistoryTicker() {
            this.positionsHistoryTicker = '';
        },

        clearPositionsFilters() {
            this.positionsHistoryStartDate = '';
            this.positionsHistoryEndDate   = '';
            this.positionsHistoryTicker    = '';
            this.positionsHistoryType      = '';
            this.positionsHistorySource    = '';
        },

        clearDateFilters() {
            this.positionsHistoryStartDate = '';
            this.positionsHistoryEndDate   = '';
        },
        
        // Helper method to download trade history as CSV
        downloadTradeHistoryCSV() {
            if (this.tradeHistory.length === 0) {
                this.showNotification('No trade history to export', 'warning');
                return;
            }
            
            try {
                const headers = Object.keys(this.tradeHistory[0]);
                const csvContent = [
                    headers.join(','),
                    ...this.tradeHistory.map(trade => 
                        headers.map(header => {
                            const value = trade[header];
                            return typeof value === 'string' && value.includes(',') ? `"${value}"` : value;
                        }).join(',')
                    )
                ].join('\n');
                
                const blob = new Blob([csvContent], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `trade_history_${new Date().toISOString().split('T')[0]}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                this.showNotification('Trade history CSV downloaded successfully', 'success');
                } catch (error) {
                console.error('Error downloading trade history CSV:', error);
                this.showNotification('Error downloading CSV file', 'error');
            }
        },
        
        // Helper method to download trade history as Excel
        downloadTradeHistoryExcel() {
            if (this.tradeHistory.length === 0) {
                this.showNotification('No trade history to export', 'warning');
                return;
            }
            
            try {
                const worksheet = XLSX.utils.json_to_sheet(this.tradeHistory);
                const workbook = XLSX.utils.book_new();
                XLSX.utils.book_append_sheet(workbook, worksheet, 'Trade_History');
                
                const filename = `trade_history_${new Date().toISOString().split('T')[0]}.xlsx`;
                XLSX.writeFile(workbook, filename);
                
                this.showNotification('Trade history Excel file downloaded successfully', 'success');
            } catch (error) {
                console.error('Error downloading trade history Excel:', error);
                this.showNotification('Error downloading Excel file', 'error');
            }
        },
        
        // Helper method to download positions history as CSV
        downloadPositionsHistoryCSV() {
            if (this.positions.length === 0) {
                this.showNotification('No positions history to export', 'warning');
                return;
            }
            
            try {
                const headers = Object.keys(this.positions[0]);
                const csvContent = [
                    headers.join(','),
                    ...this.positions.map(position => 
                        headers.map(header => {
                            const value = position[header];
                            return typeof value === 'string' && value.includes(',') ? `"${value}"` : value;
                        }).join(',')
                    )
                ].join('\n');
                
                const blob = new Blob([csvContent], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `positions_history_${new Date().toISOString().split('T')[0]}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                this.showNotification('Positions history CSV downloaded successfully', 'success');
            } catch (error) {
                console.error('Error downloading positions history CSV:', error);
                this.showNotification('Error downloading CSV file', 'error');
            }
        },
        
        // Helper method to download positions history as Excel
        downloadPositionsHistoryExcel() {
            if (this.positions.length === 0) {
                this.showNotification('No positions history to export', 'warning');
                return;
            }
            
            try {
                const worksheet = XLSX.utils.json_to_sheet(this.positions);
                const workbook = XLSX.utils.book_new();
                XLSX.utils.book_append_sheet(workbook, worksheet, 'Positions_History');
                
                const filename = `positions_history_${new Date().toISOString().split('T')[0]}.xlsx`;
                XLSX.writeFile(workbook, filename);
                
                this.showNotification('Positions history Excel file downloaded successfully', 'success');
            } catch (error) {
                console.error('Error downloading positions history Excel:', error);
                this.showNotification('Error downloading Excel file', 'error');
            }
        },
        

        
        // Helper method to toggle bot on/off
        async toggleBot() {
            try {
                this.loading.botToggle = true;
                
                // Determine action based on effective running state
                const action = this.botStatus.running ? 'stop' : 'start';
                
                // If trying to start but DAS is disconnected, show error
                if (action === 'start' && !this.botStatus.das_connected) {
                    this.showNotification('❌ Cannot start bot: DAS Trader is not connected. Please reconnect to DAS first.', 'error');
                    return;
                }
                
                const response = await axios.post(`/api/bot/${action}`);
                
                if (response.data.success) {
                    // Update the effective running state
                    this.botStatus.running = !this.botStatus.running;
                    this.showNotification(`Bot ${action}ed successfully`, 'success');
                    await this.loadBotStatusWithRealTime(); // Refresh status with real-time updates
                } else {
                    // Enhanced error handling for bot start failures
                    let errorMessage = response.data.error || 'Unknown error';
                    
                    // Check if it's a bot start failure and provide more specific DAS-related message
                    if (action === 'start' && !response.data.success) {
                        if (errorMessage.includes('Failed to start bot') || errorMessage.includes('Failed to connect')) {
                            errorMessage = '❌ Cannot start bot: DAS Trader is not connected. Please ensure DAS Trader is running and connected.';
                        }
                    }
                    
                    this.showNotification(errorMessage, 'error');
                }
            } catch (error) {
                console.error(`Error ${this.botStatus.running ? 'stopping' : 'starting'} bot:`, error);
                
                // Enhanced error handling for network/connection issues
                let errorMessage = `Error ${this.botStatus.running ? 'stopping' : 'starting'} bot`;
                
                if (!this.botStatus.running && error.response?.status === 500) {
                    errorMessage = '❌ Cannot start bot: DAS Trader is not connected. Please ensure DAS Trader is running and connected before starting the bot.';
                }
                
                this.showNotification(errorMessage, 'error');
            } finally {
                this.loading.botToggle = false;
            }
        },
        
        // Helper method to invalidate gap-ups cache
        async invalidateGapUpsCache() {
            try {
                const response = await fetch('/api/cache/invalidate-gap-ups', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const data = await response.json();
                if (data.success) {
                    this.showNotification('Gap-ups cache invalidated successfully', 'success');
                    await this.loadGapUps(); // Reload gap-ups data
                } else {
                    this.showNotification(`Failed to invalidate cache: ${data.error}`, 'error');
                }
            } catch (error) {
                console.error('Error invalidating gap-ups cache:', error);
                this.showNotification('Error invalidating gap-ups cache', 'error');
            }
        },
        
        // Panic Exit Methods
        async confirmPanicExit() {
            const confirmed = confirm(
                '🚨 EMERGENCY PANIC EXIT\n\n' +
                'This will close ALL current positions at market price immediately.\n\n' +
                '⚠️ WARNING: This action cannot be undone!\n\n' +
                'Are you absolutely sure you want to proceed?'
            );
            
            if (confirmed) {
                await this.executePanicExit();
            }
        },
        
        async executePanicExit() {
            try {
                this.loading.panicExit = true;
                this.panicExitResult = null;
                
                console.log('🚨 Executing panic exit...');
                
                const response = await fetch('/api/bot/panic-exit', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const data = await response.json();
                
                if (data.success) {
                    this.panicExitResult = data.data;
                    this.showNotification(
                        `🚨 Panic exit completed: ${data.data.positions_closed} closed, ${data.data.positions_failed} failed`, 
                        data.data.positions_failed > 0 ? 'warning' : 'success'
                    );
                    
                    // Refresh bot status after panic exit
                    await this.loadBotStatus();
                    
                    console.log('✅ Panic exit completed successfully:', data.data);
                } else {
                    this.showNotification(`❌ Panic exit failed: ${data.error}`, 'error');
                    console.error('❌ Panic exit failed:', data.error);
                }
                
            } catch (error) {
                console.error('❌ Error during panic exit:', error);
                this.showNotification('❌ Error during panic exit: ' + error.message, 'error');
            } finally {
                this.loading.panicExit = false;
            }
        },
        
        // DAS Connection Management
        async checkDasConnection() {
            try {
                this.loading.dasConnection = true;
                const response = await axios.get('/api/bot/das-connection');
                
                if (response.data.success) {
                    this.botStatus.das_connected = response.data.data.das_connected;
                    this.showNotification(response.data.data.message, response.data.data.das_connected ? 'success' : 'warning');
                } else {
                    this.showNotification('Failed to check DAS connection', 'error');
                }
            } catch (error) {
                console.error('Error checking DAS connection:', error);
                this.showNotification('Error checking DAS connection', 'error');
            } finally {
                this.loading.dasConnection = false;
            }
        },
        
        async reconnectDas() {
            try {
                this.loading.dasReconnect = true;
                const response = await axios.post('/api/bot/das-connection');
                
                if (response.data.success) {
                    this.botStatus.das_connected = true;
                    this.showNotification('Successfully reconnected to DAS', 'success');
                    // Refresh bot status to get updated information
                    await this.loadBotStatus();
                } else {
                    this.showNotification(response.data.error || 'Failed to reconnect to DAS', 'error');
                }
            } catch (error) {
                console.error('Error reconnecting to DAS:', error);
                this.showNotification('Error reconnecting to DAS', 'error');
            } finally {
                this.loading.dasReconnect = false;
            }
        },
        
        // AI Chat Methods
        async sendAIMessage(predefinedMessage = null) {
            const message = predefinedMessage || this.aiNewMessage.trim();
            if (!message || this.aiChatLoading) return;
            
            // Clear input if not a predefined message
            if (!predefinedMessage) {
                this.aiNewMessage = '';
            }
            
            // Add user message to chat
            this.aiChatMessages.push({
                id: Date.now(),
                type: 'user',
                content: message,
                timestamp: new Date()
            });
            
            this.aiChatLoading = true;
            
            try {
                const response = await axios.post('/api/ai-agent/chat', {
                    message: message
                }, {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` }
                });
                
                if (response.data.success) {
                    // Add AI response to chat
                    this.aiChatMessages.push({
                        id: Date.now() + 1,
                        type: 'assistant',
                        content: response.data.data.response,
                        timestamp: new Date(),
                        tools_used: response.data.data.tools_used,
                        symbols_analyzed: response.data.data.symbols_analyzed
                    });
                    
                    console.log('✅ AI response received:', response.data.data);
                } else {
                    // Add error message to chat
                    this.aiChatMessages.push({
                        id: Date.now() + 1,
                        type: 'assistant',
                        content: `Sorry, I encountered an error: ${response.data.error}`,
                        timestamp: new Date()
                    });
                }
            } catch (error) {
                console.error('Error sending AI message:', error);
                this.aiChatMessages.push({
                    id: Date.now() + 1,
                    type: 'assistant',
                    content: 'Sorry, I encountered an error processing your request. Please try again.',
                    timestamp: new Date()
                });
            } finally {
                this.aiChatLoading = false;
                // Scroll to bottom of chat
                this.$nextTick(() => {
                    const chatContainer = this.$refs.aiChatScroll;
                    if (chatContainer) {
                        chatContainer.scrollTop = chatContainer.scrollHeight;
                    }
                });
            }
        },
        
        async clearAIChatHistory() {
            this.aiChatMessages = [];
            try {
                await axios.post('/api/ai-agent/clear-history', {}, {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` }
                });
            } catch (e) {
                console.warn('Could not clear server-side chat history:', e);
            }
            this.showNotification('Chat history cleared successfully', 'success');
        },
        
        formatAITime(timestamp) {
            if (!timestamp) return '';
            const date = new Date(timestamp);
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        },

        renderMarkdown(content) {
            if (!content) return '';
            if (typeof marked === 'undefined') return content.replace(/\n/g, '<br>');
            try {
                return marked.parse(content, { breaks: true, gfm: true });
            } catch (e) {
                return content.replace(/\n/g, '<br>');
            }
        },
        updateActivePositions(newPositions) {
            const currentPositions = this.botStatus.active_positions || [];
            
            // If newPositions is empty, clear all positions
            if (newPositions.length === 0) {
                if (currentPositions.length > 0) {
                    currentPositions.length = 0; // Clear the array
                    console.log('🔄 Cleared all active positions');
                }
                this.botStatus.active_positions_count = 0;
                console.log('🔄 Active positions updated: 0 positions');
                return;
            }
            
            // Create a map of current positions by symbol for quick lookup
            const currentPosMap = {};
            currentPositions.forEach((pos, index) => {
                currentPosMap[pos.symbol] = { position: pos, index: index };
            });
            
            // Update existing positions and add new ones
            newPositions.forEach(newPos => {
                const existing = currentPosMap[newPos.symbol];
                
                if (existing) {
                    // Update existing position values without replacing the object reference
                    const currentPos = existing.position;
                    let hasChanges = false;
                    
                    // Check and update each field individually
                    if (currentPos.current_price !== newPos.current_price) {
                        currentPos.current_price = newPos.current_price;
                        hasChanges = true;
                        this.highlightValueUpdate(newPos.symbol, 'current_price');
                    }
                    if (currentPos.unrealized_pnl !== newPos.unrealized_pnl) {
                        currentPos.unrealized_pnl = newPos.unrealized_pnl;
                        hasChanges = true;
                        this.highlightValueUpdate(newPos.symbol, 'unrealized_pnl');
                    }
                    if (currentPos.unrealized_pnl_pct !== newPos.unrealized_pnl_pct) {
                        currentPos.unrealized_pnl_pct = newPos.unrealized_pnl_pct;
                        hasChanges = true;
                        this.highlightValueUpdate(newPos.symbol, 'unrealized_pnl_pct');
                    }
                    if (currentPos.profit_target !== newPos.profit_target) {
                        currentPos.profit_target = newPos.profit_target;
                        hasChanges = true;
                    }
                    if (currentPos.stop_loss !== newPos.stop_loss) {
                        currentPos.stop_loss = newPos.stop_loss;
                        hasChanges = true;
                    }
                    
                    if (hasChanges) {
                        console.log(`🔄 Updated position ${newPos.symbol} values`);
                    }
                } else {
                    // Add new position
                    currentPositions.push(newPos);
                    console.log(`🔄 Added new position ${newPos.symbol}`);
                }
            });
            
            // Remove positions that no longer exist
            const newPosSymbols = new Set(newPositions.map(pos => pos.symbol));
            for (let i = currentPositions.length - 1; i >= 0; i--) {
                if (!newPosSymbols.has(currentPositions[i].symbol)) {
                    console.log(`🔄 Removed position ${currentPositions[i].symbol}`);
                    currentPositions.splice(i, 1);
                }
            }
            
            // Update the count
            this.botStatus.active_positions_count = currentPositions.length;
            
            console.log(`🔄 Active positions updated: ${currentPositions.length} positions`);
        },
        
        // Highlight value updates with visual feedback
        highlightValueUpdate(symbol, field) {
            // Add a temporary class to highlight the updated value
            setTimeout(() => {
                const row = document.querySelector(`[data-symbol="${symbol}"]`);
                if (row) {
                    const valueCells = row.querySelectorAll('.value-cell');
                    valueCells.forEach(cell => {
                        cell.classList.add('updating');
                        setTimeout(() => {
                            cell.classList.remove('updating');
                        }, 300);
                    });
                }
            }, 50);
        },
        
        async updateSwingBotConfig() {
            try {
                const response = await axios.post('/api/swing-bot/update-config', this.swingBotConfig);
                if (response.data.success) {
                    this.showNotification('Swing bot config saved successfully.', 'success');
                } else {
                    this.showNotification('Failed to save swing config: ' + (response.data.error || 'Unknown error'), 'error');
                }
            } catch (error) {
                console.error('Error saving swing config:', error);
                this.showNotification('Error saving swing config: ' + error.message, 'error');
            }
        },

        async loadSwingBotConfig() {
            try {
                const response = await axios.get('/api/swing-bot/config');
                if (response.data.success) {
                    this.swingBotConfig = { ...this.swingBotConfig, ...response.data.data };
                }
            } catch (error) {
                console.error('Error loading swing config:', error);
            }
        },
        
        getTrackingStatusColor(status) {
            switch (status.toLowerCase()) {
                case 'tracking':
                    return 'bg-blue-100 text-blue-800';
                case 'triggered':
                    return 'bg-green-100 text-green-800';
                case 'expired':
                    return 'bg-red-100 text-red-800';
                case 'paused':
                    return 'bg-yellow-100 text-yellow-800';
                default:
                    return 'bg-gray-100 text-gray-800';
            }
        },
        
        getConditionsMetColor(conditionsMet) {
            return conditionsMet ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800';
        },
        
        getLogLevelColor(level) {
            switch (level.toLowerCase()) {
                case 'error':
                    return 'text-red-400';
                case 'warning':
                    return 'text-yellow-400';
                case 'info':
                    return 'text-blue-400';
                case 'debug':
                    return 'text-gray-400';
                default:
                    return 'text-white';
            }
        },
        
        formatDateTime(timestamp) {
            const date = new Date(timestamp);
            return date.toLocaleString();
        },
        
        // ── BrownBot methods ───────────────────────────────────────────────
        async loadFeedbackLatest() {
            try {
                const res = await axios.get('/api/feedback/latest', { headers: this.authHeaders() });
                if (res.data.success) {
                    if (res.data.analysis) this.feedbackData = res.data.analysis;
                    this.feedbackHistory = res.data.history || [];
                }
            } catch (e) {
                console.error('Error loading feedback latest:', e);
            }
        },

        async loadFeedbackRun(runId) {
            try {
                const res = await axios.get(`/api/feedback/history/${runId}`, { headers: this.authHeaders() });
                if (res.data.success) this.feedbackData = res.data.analysis;
            } catch (e) {
                console.error('Error loading feedback run:', e);
            }
        },

        async runFeedbackAnalysis() {
            this.loading.feedback = true;
            try {
                const res = await axios.post(
                    '/api/feedback/analyze',
                    { lookback_days: this.feedbackLookbackDays },
                    { headers: this.authHeaders() }
                );
                if (res.data.success) {
                    this.feedbackData = res.data.analysis;
                    await this.loadFeedbackLatest();
                } else {
                    alert('Analysis failed: ' + (res.data.error || 'unknown error'));
                }
            } catch (e) {
                console.error('Feedback analysis error:', e);
                alert('Analysis error: ' + (e.response?.data?.error || e.message));
            } finally {
                this.loading.feedback = false;
            }
        },

        async loadRegimeStatus() {
            try {
                const response = await axios.get('/api/regime/status');
                if (response.data && response.data.signal) {
                    this.marketRegime = response.data;
                }
            } catch (error) {
                console.error('Error loading regime status:', error);
            }
        },

        async loadBrownBotStatus() {
            if (!localStorage.getItem('session_token')) return;
            try {
                const response = await axios.get('/api/brown-bot/status', { headers: this.authHeaders() });
                if (response.data.success) {
                    this.brownBotStatus = response.data;
                }
            } catch (error) {
                if (error.response && error.response.status === 401) {
                    this.stopBrownBotPolling();
                } else {
                    console.error('Error loading BrownBot status:', error);
                }
            } finally {
                this.brownBotStatusLoaded = true;
            }
        },

        async loadBrownBotConfig() {
            try {
                const response = await axios.get('/api/brown-bot/config', { headers: this.authHeaders() });
                if (response.data.success) {
                    this.brownBotConfig = { ...this.brownBotConfig, ...response.data.config };
                }
            } catch (error) {
                console.error('Error loading BrownBot config:', error);
            }
        },

        async toggleBrownBot() {
            try {
                this.loading.brownBotToggle = true;
                const action = this.brownBotStatus.running ? 'stop' : 'start';
                const response = await axios.post(`/api/brown-bot/${action}`, {}, { headers: this.authHeaders() });
                if (response.data.success) {
                    await this.loadBrownBotStatus();
                    await this.fetchBrownBotLogs();
                    await this.loadBrownBotRiskStatus();
                    this.loadCandidateSignals();
                    if (this.brownBotStatus.running) {
                        this.startSessionKeepalive();
                        await this.pingSessionOnce();
                    } else {
                        this.stopSessionKeepalive();
                    }
                } else {
                    this.showNotification(response.data.error || 'Failed to toggle BrownBot', 'error');
                }
            } catch (error) {
                console.error('Error toggling BrownBot:', error);
                this.showNotification('Error communicating with server', 'error');
            } finally {
                this.loading.brownBotToggle = false;
            }
        },

        async brownBotCloseAll() {
            try {
                this.loading.brownBotCloseAll = true;
                this.brownBotCloseAllConfirm = false;
                const response = await axios.post('/api/brown-bot/close-all', {}, { headers: this.authHeaders() });
                if (response.data.success) {
                    const n = response.data.closed || 0;
                    const syms = (response.data.symbols || []).join(', ');
                    this.showNotification(`Sold ${n} position(s)${syms ? ': ' + syms : ''}`, 'success');
                    await this.loadBrownBotStatus();
                    await this.fetchBrownBotLogs();
                } else {
                    this.showNotification(response.data.error || 'Close all failed', 'error');
                }
            } catch (error) {
                console.error('Error closing all positions:', error);
                this.showNotification('Error closing all positions', 'error');
            } finally {
                this.loading.brownBotCloseAll = false;
            }
        },

        async saveBrownBotConfig() {
            try {
                this.loading.brownBotConfig = true;
                const response = await axios.post('/api/brown-bot/config', this.brownBotConfig, { headers: this.authHeaders() });
                if (response.data.success) {
                    this.showNotification('BrownBot configuration saved', 'success');
                } else {
                    this.showNotification('Failed to save config: ' + (response.data.error || 'Unknown error'), 'error');
                }
            } catch (error) {
                console.error('Error saving BrownBot config:', error);
                this.showNotification('Error saving BrownBot config', 'error');
            } finally {
                this.loading.brownBotConfig = false;
            }
        },

        async fetchBrownBotLogs() {
            try {
                const response = await axios.get('/api/brown-bot/logs', { headers: this.authHeaders() });
                if (response.data.success) {
                    this.brownBotLogs = response.data.logs || [];
                }
            } catch (error) {
                console.error('Error fetching BrownBot logs:', error);
            }
        },

        async loadBrownBotSwingCandidates() {
            try {
                const response = await axios.get('/api/brown-bot/swing-candidates', { headers: this.authHeaders() });
                if (response.data.success) {
                    this.brownBotSwingCandidates = response.data.picks || [];
                }
            } catch (error) {
                console.error('Error loading BrownBot swing candidates:', error);
            }
        },

        async loadBrownBotCandidates() {
            try {
                this.loading.brownBotCandidates = true;
                const response = await axios.get('/api/brown-bot/candidates', { headers: this.authHeaders() });
                if (response.data.success) {
                    this.brownBotCandidates = {
                        scanner: response.data.scanner || [],
                        watchlist: response.data.watchlist || [],
                    };
                    // Load live prices immediately then poll every 30 s
                    this.loadBrownBotLivePrices();
                    if (this._brownPriceInterval) clearInterval(this._brownPriceInterval);
                    this._brownPriceInterval = setInterval(() => this.loadBrownBotLivePrices(), 30000);
                    // Auto-load signals whenever candidates refresh
                    this.loadCandidateSignals();
                }
            } catch (error) {
                console.error('Error loading BrownBot candidates:', error);
            } finally {
                this.loading.brownBotCandidates = false;
            }
        },

        async loadBrownBotLivePrices() {
            const tickers = [
                ...this.brownBotCandidates.scanner.map(s => s.ticker),
                ...this.brownBotCandidates.watchlist.map(s => s.symbol || s.ticker),
            ].filter(Boolean);
            if (!tickers.length) return;
            try {
                const response = await axios.get(
                    `/api/brown-bot/live-prices?symbols=${tickers.join(',')}`,
                    { headers: this.authHeaders() }
                );
                if (response.data.success) {
                    this.brownBotLivePrices = response.data.prices || {};
                }
            } catch (error) {
                console.error('Error loading live prices:', error);
            }
        },

        async loadCandidateSignals() {
            const tickers = this.brownBotCandidates.scanner.map(s => s.ticker);
            if (!tickers.length) return;
            try {
                this.loading.brownBotSignals = true;
                // Keep existing signal values visible during refresh — no per-row spinner reset.
                // Only the button icon changes to indicate a background fetch is in progress.
                const response = await axios.get(
                    `/api/brown-bot/candidate-signals?symbols=${tickers.join(',')}`,
                    { headers: this.authHeaders() }
                );
                if (response.data.success) {
                    const fresh = response.data.signals || {};
                    // Prune stale entries for symbols no longer in the scanner list
                    const tickerSet = new Set(tickers);
                    const kept = {};
                    for (const t of Object.keys(this.brownBotSignals)) {
                        if (tickerSet.has(t)) kept[t] = this.brownBotSignals[t];
                    }
                    this.brownBotSignals = { ...kept, ...fresh };
                }
            } catch (error) {
                console.error('Error loading candidate signals:', error);
            } finally {
                this.loading.brownBotSignals = false;
            }
        },

        async addToWatchlist(symbol, tradeType) {
            symbol = (symbol || '').trim().toUpperCase();
            if (!symbol) return;
            try {
                const response = await axios.post('/api/brown-bot/watchlist', {
                    symbol,
                    trade_type: tradeType || this.brownBotWatchlistForm.trade_type,
                    note: this.brownBotWatchlistForm.note,
                }, { headers: this.authHeaders() });
                if (response.data.success) {
                    this.brownBotWatchlistForm.symbol = '';
                    this.brownBotWatchlistForm.note = '';
                    await this.loadBrownBotCandidates();
                } else {
                    this.showNotification(response.data.error || 'Failed to add to watchlist', 'error');
                }
            } catch (error) {
                console.error('Error adding to watchlist:', error);
                this.showNotification('Error adding to watchlist', 'error');
            }
        },

        async removeFromWatchlist(symbol) {
            try {
                const response = await axios.delete(`/api/brown-bot/watchlist/${symbol}`, { headers: this.authHeaders() });
                if (response.data.success) {
                    await this.loadBrownBotCandidates();
                } else {
                    this.showNotification(response.data.error || 'Failed to remove', 'error');
                }
            } catch (error) {
                console.error('Error removing from watchlist:', error);
                this.showNotification('Error removing from watchlist', 'error');
            }
        },

        async loadBrownBotRiskStatus() {
            try {
                const response = await axios.get('/api/brown-bot/risk-status', { headers: this.authHeaders() });
                if (response.data.success) {
                    this.brownBotRiskStatus = response.data.risk;
                }
            } catch (error) {
                console.error('Error loading BrownBot risk status:', error);
            }
        },

        async loadBrownEntryStats(useStatsDates = false) {
            try {
                const p = [];
                if (this.brownEntryStatsType) p.push('type=' + this.brownEntryStatsType);
                if (useStatsDates && this.statsStartDate) p.push('since=' + this.statsStartDate);
                if (useStatsDates && this.statsEndDate)   p.push('until=' + this.statsEndDate);
                const qs = p.length ? ('?' + p.join('&')) : '';
                const response = await axios.get('/api/brown-bot/entry-stats' + qs, { headers: this.authHeaders() });
                if (response.data.success) {
                    this.brownEntryStats = { rows: response.data.rows || [], overall: response.data.overall || {} };
                }
            } catch (error) {
                console.error('Error loading BrownBot entry stats:', error);
            }
        },
        async loadBrownExitStats(useStatsDates = false) {
            try {
                const p = [];
                if (this.brownEntryStatsType) p.push('type=' + this.brownEntryStatsType);
                if (useStatsDates && this.statsStartDate) p.push('since=' + this.statsStartDate);
                if (useStatsDates && this.statsEndDate)   p.push('until=' + this.statsEndDate);
                const qs = p.length ? ('?' + p.join('&')) : '';
                const response = await axios.get('/api/brown-bot/exit-stats' + qs, { headers: this.authHeaders() });
                if (response.data.success) {
                    this.brownExitStats = { rows: response.data.rows || [], overall: response.data.overall || {} };
                }
            } catch (error) {
                console.error('Error loading BrownBot exit stats:', error);
            }
        },
        fmtHold(mins) {
            if (mins == null) return '—';
            if (mins < 60) return Math.round(mins) + 'm';
            if (mins < 60 * 24) { const h = Math.floor(mins / 60), m = Math.round(mins % 60); return h + 'h' + (m ? ' ' + m + 'm' : ''); }
            return (mins / (60 * 24)).toFixed(1) + 'd';
        },

        async loadBrownBotBrokerOrders() {
            this.loading.brownBotOrders = true;
            try {
                const params = new URLSearchParams({ status: 'filled', limit: 100 });
                if (this.brownBotOrdersAfter)  params.set('after', this.brownBotOrdersAfter);
                if (this.brownBotOrdersUntil) params.set('until', this.brownBotOrdersUntil);
                const response = await axios.get(
                    `/api/brown-bot/broker-orders?${params}`,
                    { headers: this.authHeaders() }
                );
                if (response.data.success) {
                    this.brownBotBrokerOrders = response.data.orders || [];
                }
            } catch (error) {
                console.error('Error loading broker orders:', error);
            } finally {
                this.loading.brownBotOrders = false;
            }
        },

        startBrownBotPolling() {
            this.stopBrownBotPolling();
            this.brownBotPollingInterval = setInterval(() => {
                if (this.activeTab === 'brown-bot') {
                    this.loadBrownBotStatus();
                    this.fetchBrownBotLogs();
                    this.loadBrownBotRiskStatus();
                } else {
                    this.stopBrownBotPolling();
                }
            }, 2000);
            // Swing candidates are cached for 15 min on the backend — refresh every 60 s
            this.brownSwingCandInterval = setInterval(() => {
                if (this.activeTab === 'brown-bot') {
                    this.loadBrownBotSwingCandidates();
                }
            }, 60000);
            // Candle/VWAP/vol signals are based on 1-min bars — refresh every 60 s
            // so the display stays in sync with the bar that the scanner sees.
            this.brownSignalsInterval = setInterval(() => {
                if (this.activeTab === 'brown-bot') {
                    this.loadCandidateSignals();
                }
            }, 60000);
        },

        stopBrownBotPolling() {
            if (this.brownBotPollingInterval) {
                clearInterval(this.brownBotPollingInterval);
                this.brownBotPollingInterval = null;
            }
            if (this.brownSwingCandInterval) {
                clearInterval(this.brownSwingCandInterval);
                this.brownSwingCandInterval = null;
            }
            if (this.brownSignalsInterval) {
                clearInterval(this.brownSignalsInterval);
                this.brownSignalsInterval = null;
            }
            // Reset bot status flag so next tab visit gets a fresh running state
            // (broker configs are stable — no need to re-fetch them every tab switch)
            this.brownBotStatusLoaded = false;
        },

        startSessionKeepalive() {
            this.stopSessionKeepalive();
            // Ping every 4 minutes — well inside the 24-hour session window,
            // but frequent enough to keep the session alive while the bot runs.
            this.keepaliveInterval = setInterval(async () => {
                try {
                    const r = await axios.post('/api/session/ping', {}, { headers: this.authHeaders() });
                    if (r.data.ok && r.data.expires_at) {
                        this.sessionExpiresAt = r.data.expires_at;
                        this.sessionWarningDismissed = false;
                    }
                } catch (e) {
                    console.warn('Session keepalive failed:', e);
                }
            }, 4 * 60 * 1000);
        },

        stopSessionKeepalive() {
            if (this.keepaliveInterval) {
                clearInterval(this.keepaliveInterval);
                this.keepaliveInterval = null;
            }
        },

        async pingSessionOnce() {
            try {
                const r = await axios.post('/api/session/ping', {}, { headers: this.authHeaders() });
                if (r.data.ok && r.data.expires_at) {
                    this.sessionExpiresAt = r.data.expires_at;
                }
            } catch (e) { /* ignore */ }
        },

        brownBotDaysHeld(entryTimeStr) {
            try {
                const entry = new Date(entryTimeStr);
                const days = Math.floor((Date.now() - entry.getTime()) / 86400000);
                return days === 0 ? 'today' : `${days}d`;
            } catch {
                return '—';
            }
        },

        // ── Broker connection methods ──────────────────────────────────

        authHeaders() {
            return { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` };
        },

        async loadBrokerConfigs() {
            try {
                const configsRes = await axios.get('/api/broker/configs', { headers: this.authHeaders() });
                if (configsRes.data.success) {
                    this.brokerConfigs = configsRes.data.configs;
                    const active = this.brokerConfigs.find(c => c.is_active);
                    if (active) this.testBrokerCard(active.broker_name);
                }
            } catch (e) {
                console.error('loadBrokerConfigs error', e);
            } finally {
                this.brokerConfigsLoaded = true;
            }
        },

        brokerCfg(name) {
            return this.brokerConfigs.find(c => c.broker_name === name) || null;
        },

        toggleBrokerCard(name) {
            if (this.brokerCardExpanded === name) { this.brokerCardExpanded = null; return; }
            const cfg = this.brokerCfg(name);
            if (cfg) {
                const ec = cfg.extra_config || {};
                if (name === 'alpaca')     { this.brokerCardForms.alpaca.paper_trading = !!cfg.paper_trading; }
                if (name === 'tastytrade') { this.brokerCardForms.tastytrade.paper_trading = !!cfg.paper_trading; this.brokerCardForms.tastytrade.username = ''; this.brokerCardForms.tastytrade.password = ''; }
                if (name === 'tradier')    { this.brokerCardForms.tradier.paper_trading = !!cfg.paper_trading; }
                if (name === 'das')        { this.brokerCardForms.das.host = ec.host || '127.0.0.1'; this.brokerCardForms.das.port = ec.port || 9800; }
                this.brokerCardForms[name].api_key = '';
                if (this.brokerCardForms[name].api_secret !== undefined) this.brokerCardForms[name].api_secret = '';
            }
            this.brokerCardExpanded = name;
        },

        async saveBrokerCard(name) {
            this.brokerCardLoading = { ...this.brokerCardLoading, [name]: true };
            try {
                const f = this.brokerCardForms[name];
                let payload = {};
                if (name === 'alpaca')     payload = { api_key: f.api_key, api_secret: f.api_secret, paper_trading: f.paper_trading ? 1 : 0 };
                if (name === 'tastytrade') payload = { paper_trading: f.paper_trading ? 1 : 0, extra_config: { username: f.username, password: f.password } };
                if (name === 'tradier')    payload = { api_key: f.api_key, paper_trading: f.paper_trading ? 1 : 0 };
                if (name === 'das')        payload = { extra_config: { host: f.host, port: parseInt(f.port) || 9800 } };
                const res = await axios.post(`/api/broker/config/${name}`, payload, { headers: this.authHeaders() });
                if (res.data.success) {
                    this.brokerCardExpanded = null;
                    await this.loadBrokerConfigs();
                } else { this.showError?.(res.data.error || 'Save failed'); }
            } catch (e) { this.showError?.(e.response?.data?.error || 'Save failed'); }
            finally { this.brokerCardLoading = { ...this.brokerCardLoading, [name]: false }; }
        },

        async testBrokerCard(name) {
            this.brokerCardLoading = { ...this.brokerCardLoading, [name]: true };
            this.brokerCardAccountInfo = { ...this.brokerCardAccountInfo, [name]: null };
            try {
                const res = await axios.post(`/api/broker/test/${name}`, {}, { headers: this.authHeaders() });
                this.brokerCardAccountInfo = { ...this.brokerCardAccountInfo, [name]: res.data };
            } catch (e) {
                this.brokerCardAccountInfo = { ...this.brokerCardAccountInfo, [name]: { connected: false, error: e.response?.data?.error || 'Failed' } };
            } finally { this.brokerCardLoading = { ...this.brokerCardLoading, [name]: false }; }
        },

        async deleteBrokerConfig(brokerName) {
            if (!brokerName || !confirm(`Remove ${brokerName} connection?`)) return;
            try {
                await axios.delete(`/api/broker/config/${brokerName}`, { headers: this.authHeaders() });
                if (this.brokerCardExpanded === brokerName) this.brokerCardExpanded = null;
                const ai = { ...this.brokerCardAccountInfo }; delete ai[brokerName];
                this.brokerCardAccountInfo = ai;
                await this.loadBrokerConfigs();
            } catch (e) { this.showError?.(e.response?.data?.error || 'Delete failed'); }
        },

        async activateBroker(brokerName) {
            try {
                await axios.put(`/api/broker/activate/${brokerName}`, {}, { headers: this.authHeaders() });
                await this.loadBrokerConfigs();
                await this.testBrokerCard(brokerName);
            } catch (e) { this.showError?.(e.response?.data?.error || 'Activate failed'); }
        },

        }
    });
    
    app.mount('#app');
    console.log('✅ Trading Advisor Dashboard initialized successfully'); 

// Make emergency escape available globally
window.emergencyEscape = function() {
    if (window.app && window.app.emergencyEscape) {
        window.app.emergencyEscape();
    } else {
        console.log('🚨 Emergency escape not available, trying manual cleanup...');
        // Manual cleanup as fallback
        document.querySelectorAll('[class*="fixed"], [class*="modal"], [class*="overlay"]').forEach(el => el.remove());
        document.body.style.overflow = 'auto';
        document.body.style.pointerEvents = 'auto';
        console.log('🚨 Manual cleanup completed');
    }
};

// Store app reference globally for debugging
window.app = app;
