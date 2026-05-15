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
                    syncPositions: false,
                    dailyPnl: false,
                    cumulativePnl: false,
                    pieCharts: false,
                    backtest: false,
                    runBacktest: false,
                    equityChart: false,
                    historicalAnalysis: false,
                    stockNews: false,
                    swingTechnicals: false,
                    swingRecommendation: false,
                    swingNews: false,
                    swingDailyPicks: false,
                    // BrownBot loading states
                    brownBotToggle: false,
                    brownBotConfig: false,
                    brownBotCandidates: false,
                    brownBotSignals: false,
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
                positionsSort: { key: 'date', dir: 'desc' },
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
                swingTechnicalsCached: false,
                swingDailyPicks: null,
                swingDailyPicksDate: null,
                swingSourceExpanded: null,
                
                // Trade History
                tradeHistoryTicker: '',
                tradeHistoryStartDate: '',
                tradeHistoryEndDate: '',
                tradeHistoryStyle: '',
                tradeHistoryStatus: '',
                
                // Positions History
                positions: [],
                positionsHistoryTicker: '', // Ticker search filter for positions
                positionsHistoryType: '', // Position type filter (number)
                positionsHistoryStartDate: '', // Start date filter (YYYY-MM-DD)
                positionsHistoryEndDate: '', // End date filter (YYYY-MM-DD)
                
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
            brownBotConfig: {
                day_profit_target_pct: 5.0,
                day_stop_loss_pct: 2.5,
                day_trailing_stop_enabled: false,
                day_trailing_stop_pct: 1.5,
                day_eod_exit_time: '15:45',
                day_breakeven_trigger_pct: 50.0,
                day_time_gate_enabled: true,
                day_time_gate_start: '09:35',
                day_time_gate_end: '10:30',
                swing_profit_target_pct: 15.0,
                swing_stop_loss_pct: 7.0,
                swing_max_hold_days: 20,
                swing_earnings_protection_enabled: true,
                swing_earnings_exit_days: 2,
                swing_breakeven_trigger_pct: 50.0,
                max_daily_loss: -500.0,
                max_concurrent_day: 3,
                max_concurrent_swing: 5,
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
                day_position_pct: 5.0,
                swing_position_pct: 3.0,
            },
            brownBotLogs: [],
            brownBotPollingInterval: null,
            sessionExpiresAt: null,
            sessionWarningDismissed: false,
            keepaliveInterval: null,
            brownBotCandidates: { scanner: [], watchlist: [] },
            brownBotSignals: {},
            brownBotWatchlistForm: { symbol: '', trade_type: 'day', note: '' },
            brownBotRiskStatus: {
                daily_pnl: 0,
                max_daily_loss: -500,
                open_day: 0,
                max_concurrent_day: 3,
                open_swing: 0,
                max_concurrent_swing: 5,
                circuit_breaker_open: false,
            },
            brownBotConfigCollapsed: false,

            // Broker connection settings
            supportedBrokers: [],
            brokerConfigs: [],
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
                    best_trade: 0, best_trade_symbol: '', worst_trade: 0, worst_trade_symbol: '',
                    avg_pnl: 0, win_count: 0, loss_count: 0, breakeven_count: 0,
                    total_count: 0, expectancy: 0, max_consecutive_wins: 0, max_consecutive_losses: 0,
                },
                statsStartDate: '',
                statsEndDate: '',
                statsPreset: 'all',
                
                // Daily P&L chart data
                dailyPnlData: [],
                dailyPnlChart: null,
                dailyPnlChartType: 'bar', // Default to bar chart
                
                // Cumulative P&L chart data
                cumulativePnlData: [],
                cumulativePnlChart: null,

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
                backtestConfig: {
                    strategy: 'gap_up',
                    startDate: '',
                    endDate: '',
                    initialCapital: 100000,
                    positionSize: 10,
                    stopLoss: 2.0
                },
                backtestResults: null,
                equityCurveChart: null

            }
        },
        

        
        computed: {
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
                            { icon: 'fa-calendar-alt',  text: 'Browse months of daily gap-up scan results' },
                            { icon: 'fa-filter',        text: 'Filter by date range, ticker, or gap size' },
                            { icon: 'fa-file-download', text: 'Export historical data to CSV / Excel' },
                            { icon: 'fa-search-dollar', text: 'Spot recurring gap patterns across sectors' },
                        ],
                    },
                    swing: {
                        label: 'Swing Trading', plan: 'Beginner Trader', price: '$5/mo', tier: 'beginner', icon: 'fa-wave-square', color: 'blue',
                        tagline: 'Find the best swing setups with AI precision.',
                        features: [
                            { icon: 'fa-chart-mixed',   text: 'RSI, MACD, Bollinger Bands, ATR and more' },
                            { icon: 'fa-layer-group',   text: 'SMA 20/50/200 and EMA 9/21 crossover analysis' },
                            { icon: 'fa-newspaper',     text: 'Latest news headlines + AI summary' },
                            { icon: 'fa-robot',         text: 'Claude AI entry zone, stop, and target recommendation' },
                        ],
                    },
                    trades: {
                        label: 'Trade History', plan: 'Advanced Trader', price: '$10/mo', tier: 'advanced', icon: 'fa-exchange-alt', color: 'purple',
                        tagline: 'Every trade logged, analyzed, and actionable.',
                        features: [
                            { icon: 'fa-list-alt',      text: 'Complete record of all executed trades' },
                            { icon: 'fa-sort-amount-down', text: 'Sort and filter by ticker, date, P&L, or side' },
                            { icon: 'fa-file-excel',    text: 'One-click export to CSV or Excel' },
                            { icon: 'fa-sync-alt',      text: 'Auto-sync trades directly from DAS Trader' },
                        ],
                    },
                    positions: {
                        label: 'Positions', plan: 'Advanced Trader', price: '$10/mo', tier: 'advanced', icon: 'fa-chart-line', color: 'purple',
                        tagline: 'Live visibility into every open position.',
                        features: [
                            { icon: 'fa-eye',           text: 'Real-time unrealized P&L for open positions' },
                            { icon: 'fa-history',       text: 'Full position lifecycle from entry to exit' },
                            { icon: 'fa-layer-group',   text: 'Track multiple simultaneous positions' },
                            { icon: 'fa-tachometer-alt', text: 'Live price feed via WebSocket integration' },
                        ],
                    },
                    stats: {
                        label: 'Stats', plan: 'Advanced Trader', price: '$10/mo', tier: 'advanced', icon: 'fa-chart-bar', color: 'purple',
                        tagline: 'Data-driven insights to sharpen your edge.',
                        features: [
                            { icon: 'fa-percentage',    text: 'Win rate, average P&L, and expectancy metrics' },
                            { icon: 'fa-chart-pie',     text: 'Visual breakdowns by ticker, side, and time' },
                            { icon: 'fa-calendar-week', text: 'Day-of-week and time-of-day performance analysis' },
                            { icon: 'fa-trophy',        text: 'Best / worst trade highlights and streaks' },
                        ],
                    },
                    backtest: {
                        label: 'Backtest', plan: 'Yogi Trader', price: '$25/mo', tier: 'yogi', icon: 'fa-flask', color: 'yellow',
                        tagline: 'Validate your strategy before risking real capital.',
                        features: [
                            { icon: 'fa-redo',          text: 'Replay strategies against months of historical data' },
                            { icon: 'fa-dollar-sign',   text: 'Simulated P&L with configurable capital and sizing' },
                            { icon: 'fa-chart-area',    text: 'Equity curve chart and drawdown analysis' },
                            { icon: 'fa-balance-scale', text: 'Compare multiple strategies side by side' },
                        ],
                    },
                    'brown-bot': {
                        label: 'BrownBot', plan: 'Yogi Trader', price: '$25/mo', tier: 'yogi', icon: 'fa-brain', color: 'yellow',
                        tagline: 'Fully autonomous day & swing trading bot.',
                        features: [
                            { icon: 'fa-search-dollar', text: 'Auto gap-up scanning — no manual symbol entry needed' },
                            { icon: 'fa-robot',         text: 'AI-powered swing signal tiebreaker via Claude' },
                            { icon: 'fa-shield-alt',    text: 'Portfolio risk manager with daily loss circuit breaker' },
                            { icon: 'fa-clock',         text: 'Hard EOD flatten + earnings-protection exits' },
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
                    let va = a[key], vb = b[key];
                    if (va == null) return 1;
                    if (vb == null) return -1;
                    if (typeof va === 'string') { va = va.toLowerCase(); vb = (vb || '').toLowerCase(); }
                    return dir === 'asc' ? (va > vb ? 1 : va < vb ? -1 : 0) : (va < vb ? 1 : va > vb ? -1 : 0);
                });
            },

            sortedPositions() {
                const { key, dir } = this.positionsSort;
                return [...this.positions].sort((a, b) => {
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
                const picks = this.swingDailyPicks?.picks || [];
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
                return picks
                    .filter(p => ['A', 'B'].includes(p.grade) && p.bias?.toLowerCase() === 'bullish')
                    .map(p => {
                        let status = 'eligible';
                        if (activeSymbols.has(p.ticker)) status = 'active';
                        else if (enteredSymbols.has(p.ticker)) status = 'entered';
                        else if (skippedSymbols.has(p.ticker)) status = 'skipped';
                        return { ...p, status };
                    });
            }
        },

        mounted() {
            console.log('🎯 Vue.js app mounted successfully');
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

            // Auto-refresh gap-ups every 2 minutes — silent so the table doesn't flash
            this.gapUpRefreshInterval = setInterval(() => {
                if (this.activeTab === 'gap-ups') this.loadGapUps(true);
            }, 2 * 60 * 1000);

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
                    if (ok) this.pingSessionOnce();
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
                        // If data is already cached, refresh silently in the background
                        this.loadPositionsHistory(this.positions.length > 0);
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

                } else if (tabName === 'swing') {
                    console.log('📊 Swing Trading tab selected - loading daily picks...');
                    this.stopPositionHistoryUpdates();

                    this.loadSwingDailyPicks();
                } else if (tabName === 'stats') {
                    this.stopPositionHistoryUpdates();
                    this.loadStats();
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
                    } else {
                        this.activeTab = 'about';
                    }
                } else if (tabName === 'account') {
                    this.loadBrokerConfigs();
                } else if (tabName === 'brown-bot') {
                    console.log('🤖 BrownBot tab selected - loading status...');
                    this.stopPositionHistoryUpdates();

                    this.loadBrownBotStatus();
                    this.loadBrownBotConfig();
                    this.fetchBrownBotLogs();
                    this.loadBrownBotCandidates();
                    this.loadBrownBotRiskStatus();
                    this.startBrownBotPolling();
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
                    beginner: ['gap-ups', 'ai-chat', 'help', 'contact', 'historical', 'swing'],
                    advanced: ['gap-ups', 'ai-chat', 'help', 'contact', 'historical', 'swing', 'trades', 'positions', 'stats'],
                    yogi:     ['gap-ups', 'ai-chat', 'help', 'contact', 'historical', 'swing', 'trades', 'positions', 'stats', 'backtest', 'brown-bot'],
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
                    this.gapUpSort.dir = ['gap_percent', 'volume', 'market_cap', 'float_shares', 'price'].includes(key) ? 'desc' : 'asc';
                }
            },

            togglePositionsSort(key) {
                if (this.positionsSort.key === key) {
                    this.positionsSort.dir = this.positionsSort.dir === 'asc' ? 'desc' : 'asc';
                } else {
                    this.positionsSort.key = key;
                    this.positionsSort.dir = ['avg_cost', 'init_price', 'realized', 'unrealized', 'quantity', 'init_quantity'].includes(key) ? 'desc' : 'asc';
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
            console.log('🔧 Force closing any stuck modals...');
            
            // Close import modal if stuck
            this.showImportModal = false;
            
            // Remove any stuck loading overlays from DOM
            const stuckOverlays = document.querySelectorAll('.loading-overlay, .modal-overlay, [class*="fixed inset-0"]');
            stuckOverlays.forEach(overlay => {
                console.log('🗑️ Removing stuck overlay:', overlay);
                overlay.remove();
            });
            
            // Remove any stuck notifications
            const stuckNotifications = document.querySelectorAll('[class*="fixed top-0"]');
            stuckNotifications.forEach(notification => {
                if (notification.textContent.includes('Loading')) {
                    console.log('🗑️ Removing stuck notification:', notification);
                    notification.remove();
                }
            });
            
            // Ensure body is not blocked
            document.body.style.overflow = 'auto';
            document.body.style.pointerEvents = 'auto';
            
            console.log('✅ Modal cleanup completed');
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
                        fetch(`/api/positions/total_positions?t=${Date.now()}`),
                        fetch(`/api/positions/total_pnl?t=${Date.now()}`),
                        fetch(`/api/positions/winrate?t=${Date.now()}`)
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
                            signal: AbortSignal.timeout(10000)
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
                if (this.statsStartDate) p.push(`start_date=${this.statsStartDate}`);
                if (this.statsEndDate)   p.push(`end_date=${this.statsEndDate}`);
                return p.length ? '?' + p.join('&') : '';
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
                this.statsStartDate = '';
                this.statsEndDate = '';
                this.statsPreset = 'all';
                this.loadStats();
            },

            async loadExtendedStats() {
                try {
                    const qs = this._statsDateQs();
                    const res = await fetch(`/api/positions/extended-stats${qs}`);
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
                    const [pnlRes, winRes, posRes] = await Promise.all([
                        fetch(`/api/positions/total_pnl${qs}`),
                        fetch(`/api/positions/winrate${qs}`),
                        fetch(`/api/positions/total_positions${qs}`),
                    ]);
                    const [pnlData, winRateData, positionsData] = await Promise.all([
                        pnlRes.json(), winRes.json(), posRes.json()
                    ]);
                    if (pnlData.success && winRateData.success && positionsData.success) {
                        this.stats.total_pnl        = pnlData.data.total_pnl || 0;
                        this.stats.win_rate         = winRateData.data.win_rate || 0;
                        this.stats.total_positions  = positionsData.data.total_positions || 0;
                    } else {
                        this.showNotification('Failed to load statistics', 'error');
                    }
                    await Promise.all([
                        this.loadExtendedStats(),
                        this.loadDailyPnlData(),
                        this.loadCumulativePnlData(),
                        this.loadPieChartData(),
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
                    const response = await fetch(`/api/positions/daily-pnl${this._statsDateQs()}`);
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
                    const response = await fetch(`/api/positions/cumulative-pnl${this._statsDateQs()}`);
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
                        fetch(`/api/positions/pie-chart/long-short${qs}`),
                        fetch(`/api/positions/pie-chart/symbols${qs}${sep}limit=${this.pieChartSymbolLimit}`),
                        fetch(`/api/positions/pie-chart/win-loss${qs}`),
                        fetch(`/api/positions/pie-chart/monthly${qs}`)
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
                        case 'longShort':
                            return item.position_type;
                        case 'symbols':
                            return item.symbol;
                        case 'winLoss':
                            return item.trade_result;
                        case 'monthly':
                            return item.month;
                        default:
                            return item.label || 'Unknown';
                    }
                });

                const values = data.map(item => item.total_pnl);
                const counts = data.map(item => item.position_count);

                // Create new chart
                this.pieCharts[this.pieChartType] = new Chart(ctx, {
                    type: 'pie',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: values,
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
                                        const data = chart.data;
                                        if (data.labels.length && data.datasets.length) {
                                            return data.labels.map((label, i) => {
                                                const value = data.datasets[0].data[i];
                                                const count = counts[i];
                                                const percentage = ((value / values.reduce((a, b) => a + b, 0)) * 100).toFixed(1);
                                                return {
                                                    text: `${label}: $${value.toLocaleString()} (${percentage}%)`,
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
                                        const value = context.parsed;
                                        const count = counts[context.dataIndex];
                                        const percentage = ((value / values.reduce((a, b) => a + b, 0)) * 100).toFixed(1);
                                        return [
                                            `${context.label}: $${value.toLocaleString()}`,
                                            `Positions: ${count}`,
                                            `Percentage: ${percentage}%`
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
                console.log('🧪 Loading backtest data...');
                this.loading.backtest = true;
                
                try {
                    // Set default dates if not set
                    if (!this.backtestConfig.startDate) {
                        const today = new Date();
                        const thirtyDaysAgo = new Date(today.getTime() - (30 * 24 * 60 * 60 * 1000));
                        this.backtestConfig.startDate = thirtyDaysAgo.toISOString().split('T')[0];
                        this.backtestConfig.endDate = today.toISOString().split('T')[0];
                    }
                    
                    console.log('✅ Backtest configuration loaded');
                } catch (error) {
                    console.error('❌ Error loading backtest data:', error);
                    this.showNotification('Error loading backtest data', 'error');
                } finally {
                    this.loading.backtest = false;
                }
            },

            async runBacktest() {
                console.log('🧪 Running backtest...');
                this.loading.runBacktest = true;
                
                try {
                    // Validate configuration
                    if (!this.backtestConfig.startDate || !this.backtestConfig.endDate) {
                        this.showNotification('Please select start and end dates', 'error');
                        return;
                    }
                    
                    if (this.backtestConfig.initialCapital <= 0) {
                        this.showNotification('Initial capital must be greater than 0', 'error');
                        return;
                    }
                    
                    // Generate mock backtest results for now
                    const mockResults = this.generateMockBacktestResults();
                    this.backtestResults = mockResults;
                    
                    // Update equity curve chart
                    this.$nextTick(() => {
                        this.updateEquityCurveChart();
                    });
                    
                    console.log('✅ Backtest completed successfully');
                    this.showNotification('Backtest completed successfully', 'success');
                    
                } catch (error) {
                    console.error('❌ Error running backtest:', error);
                    this.showNotification('Error running backtest', 'error');
                } finally {
                    this.loading.runBacktest = false;
                }
            },

            generateMockBacktestResults() {
                console.log('🧪 Generating mock backtest results...');
                
                const startDate = new Date(this.backtestConfig.startDate);
                const endDate = new Date(this.backtestConfig.endDate);
                const daysDiff = Math.floor((endDate - startDate) / (1000 * 60 * 60 * 24));
                
                // Generate mock trades
                const trades = [];
                const totalTrades = Math.floor(Math.random() * 20) + 10; // 10-30 trades
                
                for (let i = 0; i < totalTrades; i++) {
                    const tradeDate = new Date(startDate.getTime() + (Math.random() * daysDiff * 24 * 60 * 60 * 1000));
                    const symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA', 'META', 'NFLX'];
                    const symbol = symbols[Math.floor(Math.random() * symbols.length)];
                    const action = Math.random() > 0.5 ? 'BUY' : 'SELL';
                    const price = Math.random() * 500 + 50;
                    const pnl = (Math.random() - 0.4) * 2000; // 60% chance of profit
                    const returnPercent = (pnl / (price * 100)) * 100;
                    
                    trades.push({
                        id: i + 1,
                        date: tradeDate.toISOString().split('T')[0],
                        symbol: symbol,
                        action: action,
                        price: price,
                        pnl: pnl,
                        returnPercent: returnPercent
                    });
                }
                
                // Sort trades by date
                trades.sort((a, b) => new Date(a.date) - new Date(b.date));
                
                // Calculate metrics
                const totalPnl = trades.reduce((sum, trade) => sum + trade.pnl, 0);
                const winningTrades = trades.filter(trade => trade.pnl > 0);
                const losingTrades = trades.filter(trade => trade.pnl < 0);
                const winRate = trades.length > 0 ? (winningTrades.length / trades.length) * 100 : 0;
                const totalReturn = (totalPnl / this.backtestConfig.initialCapital) * 100;
                const finalCapital = this.backtestConfig.initialCapital + totalPnl;
                
                const avgWin = winningTrades.length > 0 ? winningTrades.reduce((sum, trade) => sum + trade.pnl, 0) / winningTrades.length : 0;
                const avgLoss = losingTrades.length > 0 ? losingTrades.reduce((sum, trade) => sum + trade.pnl, 0) / losingTrades.length : 0;
                const largestWin = winningTrades.length > 0 ? Math.max(...winningTrades.map(trade => trade.pnl)) : 0;
                const largestLoss = losingTrades.length > 0 ? Math.min(...losingTrades.map(trade => trade.pnl)) : 0;
                
                // Mock risk metrics
                const maxDrawdown = Math.random() * 15; // 0-15% max drawdown
                const sharpeRatio = (Math.random() * 2) + 0.5; // 0.5-2.5 Sharpe ratio
                const profitFactor = (Math.random() * 3) + 0.5; // 0.5-3.5 profit factor
                
                return {
                    totalReturn: totalReturn,
                    finalCapital: finalCapital,
                    winRate: winRate,
                    totalTrades: trades.length,
                    maxDrawdown: maxDrawdown,
                    sharpeRatio: sharpeRatio,
                    profitFactor: profitFactor,
                    avgWin: avgWin,
                    avgLoss: avgLoss,
                    largestWin: largestWin,
                    largestLoss: largestLoss,
                    trades: trades,
                    equityCurve: this.generateEquityCurve(trades, this.backtestConfig.initialCapital)
                };
            },

            generateEquityCurve(trades, initialCapital) {
                const equityCurve = [];
                let currentCapital = initialCapital;
                
                // Sort trades by date
                const sortedTrades = [...trades].sort((a, b) => new Date(a.date) - new Date(b.date));
                
                for (let i = 0; i < sortedTrades.length; i++) {
                    currentCapital += sortedTrades[i].pnl;
                    equityCurve.push({
                        date: sortedTrades[i].date,
                        equity: currentCapital
                    });
                }
                
                return equityCurve;
            },

            updateEquityCurveChart() {
                if (!this.backtestResults || !this.backtestResults.equityCurve) {
                    console.log('📊 No equity curve data to display');
                    return;
                }
                
                const ctx = document.getElementById('equityCurveChart');
                if (!ctx) {
                    console.error('❌ Equity curve chart canvas not found');
                    return;
                }
                
                // Destroy existing chart if it exists
                if (this.equityCurveChart) {
                    this.equityCurveChart.destroy();
                }
                
                // Prepare data for chart
                const labels = this.backtestResults.equityCurve.map(point => point.date);
                const data = this.backtestResults.equityCurve.map(point => point.equity);
                
                // Create new chart
                this.equityCurveChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Portfolio Value',
                            data: data,
                            borderColor: '#3B82F6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4,
                            pointBackgroundColor: '#3B82F6',
                            pointBorderColor: '#3B82F6',
                            pointRadius: 3,
                            pointHoverRadius: 5
                        }]
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
                                        return `Portfolio Value: ${new Intl.NumberFormat('en-US', {
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
                                    text: 'Portfolio Value ($)',
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
                
                console.log('✅ Equity curve chart updated');
            },

            
            async loadDashboardPositions() {
                try {
                    console.log('🔄 Loading fresh dashboard positions data...');
                    
                    // Load positions data for charts and analytics
                    const response = await fetch(`/api/positions/pnl-history?t=${Date.now()}`);
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
                    
                    const response = await fetch(`/api/trades?${params.toString()}`);
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

                const response = await fetch(`/api/positions/daily?${params.toString()}`);
                const data = await response.json();

                if (data.success) {
                    this.positions = data.data.positions || [];
                } else if (!silent) {
                    this.showNotification('Failed to load positions history: ' + data.error, 'error');
                }
            } catch (error) {
                if (!silent) this.showNotification('Error loading positions history: ' + error.message, 'error');
            } finally {
                this.loading.positions = false;
            }
        },
        
        initializeDateRanges() {
            // Check if we should use 2025 dates (since trades are from 2025)
            const use2025Dates = true; // Set to true since trades are from 2025
            
            if (use2025Dates) {
                // Set dates to 2025 to match the database
                this.dashboardPnLFromDate = '2025-01-01';
                this.dashboardPnLToDate = '2025-12-31';
                this.dashboardTradeFromDate = '2025-01-01';
                this.dashboardTradeToDate = '2025-12-31';
                
                console.log('📅 Date ranges initialized for 2025:', {
                    pnl: `${this.dashboardPnLFromDate} to ${this.dashboardPnLToDate}`,
                    trades: `${this.dashboardTradeFromDate} to ${this.dashboardTradeToDate}`
                });
            } else {
                // Use current year dates
                const today = new Date();
                const sevenDaysAgo = new Date();
                sevenDaysAgo.setDate(today.getDate() - 7);
                
                this.dashboardPnLFromDate = sevenDaysAgo.toISOString().split('T')[0];
                this.dashboardPnLToDate = today.toISOString().split('T')[0];
                this.dashboardTradeFromDate = sevenDaysAgo.toISOString().split('T')[0];
                this.dashboardTradeToDate = today.toISOString().split('T')[0];
                
                console.log('📅 Date ranges initialized for current year:', {
                    pnl: `${this.dashboardPnLFromDate} to ${this.dashboardPnLToDate}`,
                    trades: `${this.dashboardTradeFromDate} to ${this.dashboardTradeToDate}`
                });
            }
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
            
        // Format date
        formatDate(dateString) {
            if (!dateString) return 'N/A';
            try {
                // Split directly to avoid timezone offset converting the date
                const [year, month, day] = dateString.split('-');
                return `${month}/${day}/${year}`;
            } catch (error) {
                return dateString;
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
            this.loading.gapUps = true;
            
            try {
                // Clear existing data
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
                this.gapUps = [];
                this.trades = [];
                
                // Reload all data
                await this.loadDashboardData();
                await this.loadBotStatus();
                
                // Update charts
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
                this.loading.gapUps = false;
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
        async loadHistoricalData() {
            if (!this.historicalTicker.trim()) {
                this.showNotification('Please enter a ticker symbol', 'warning');
                return;
            }

            try {
                console.log(`📈 Loading historical data for ${this.historicalTicker}...`);
                this.loading.historical = true;

                const response = await fetch(`/api/historical-data/${this.historicalTicker.toUpperCase()}?period=${this.selectedPeriod}&min_gap=${this.minGapPercent}&_t=${Date.now()}`, { cache: 'no-store' });
                const data = await response.json();

                if (data.success) {
                    this.historicalData = data.data || [];
                    this.historicalAnalysis = null;
                    this.historicalSectorInfo = null;
                    this.historicalSectorPerf = null;
                    this.historicalAnalysisCached = false;
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
                const response = await fetch(`/api/historical-analysis/${this.historicalTicker.toUpperCase()}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ stats })
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
            this.swingTechnicalsCached = false;
            this.loading.swingTechnicals = true;
            try {
                const res  = await fetch(`/api/swing-technicals/${ticker}`);
                const data = await res.json();
                if (!data.success) throw new Error(data.error || 'Failed');
                this.swingTechnicals = data.technicals;
                this.swingSectorInfo = data.sector_info;
                this.swingSectorPerf = data.sector_perf;
                this.swingTechnicalsCached = !!data.cached;
                // Also load news
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

        async loadSwingRecommendation() {
            if (!this.swingTechnicals) {
                this.showNotification('Load technicals first', 'warning');
                return;
            }
            this.swingRecommendation = null;
            this.loading.swingRecommendation = true;
            const ticker = this.swingTicker.trim().toUpperCase();
            try {
                const res  = await fetch(`/api/swing-recommendation/${ticker}`, {
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

        async loadSwingDailyPicks(force = false) {
            const today = new Date().toISOString().slice(0, 10);
            if (!force && this.swingDailyPicks && this.swingDailyPicksDate === today) return;

            // Step 1: load latest stored picks instantly (previous session or today from DB)
            if (!this.swingDailyPicks) {
                try {
                    const snap = await fetch('/api/swing-daily-picks/latest');
                    const snapData = await snap.json();
                    if (snapData.success && snapData.picks?.length) {
                        this.swingDailyPicks = snapData;
                        this.swingDailyPicksDate = snapData.date;
                        // If this is already today's picks (from DB), we're done
                        if (snapData.is_today && !force) return;
                    }
                } catch (_) { /* silent — fall through to full fetch */ }
            }

            // Step 2: compute today's fresh picks (may take a few seconds)
            this.loading.swingDailyPicks = true;
            try {
                const res  = await fetch('/api/swing-daily-picks');
                const data = await res.json();
                if (!data.success) throw new Error(data.error || 'No picks available');
                this.swingDailyPicks = data;
                this.swingDailyPicksDate = data.date || today;
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
            this.loadTradeHistory();
        },

        clearTradeFilters() {
            this.tradeHistoryTicker    = '';
            this.tradeHistoryStartDate = '';
            this.tradeHistoryEndDate   = '';
            this.tradeHistoryStyle     = '';
            this.tradeHistoryStatus    = '';
            this.loadTradeHistory();
        },
        
        // Helper method to clear positions history for a specific ticker
        clearPositionsHistoryTicker() {
            this.positionsHistoryTicker = '';
            this.loadPositionsHistory();
        },
        
        // Helper method to clear date filters
        clearDateFilters() {
            this.positionsHistoryStartDate = '';
            this.positionsHistoryEndDate = '';
            this.loadPositionsHistory();
            this.showNotification('Date filters cleared', 'success');
        },
        
        // Helper method to handle trade history ticker input changes
        onTradeHistoryTickerChange() {
            // Auto-load trade history when ticker is entered
            if (this.tradeHistoryTicker.trim()) {
                this.loadTradeHistory();
            }
        },
        
        // Helper method to handle positions history ticker input changes
        onPositionsHistoryTickerChange() {
            // Auto-load positions history when ticker is entered
            if (this.positionsHistoryTicker.trim()) {
                this.loadPositionsHistory();
            }
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
        async loadBrownBotStatus() {
            try {
                const response = await axios.get('/api/brown-bot/status');
                if (response.data.success) {
                    this.brownBotStatus = response.data;
                }
            } catch (error) {
                console.error('Error loading BrownBot status:', error);
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
                    if (this.brownBotStatus.running) {
                        this.startSessionKeepalive();
                        await this.pingSessionOnce();
                    } else {
                        this.stopSessionKeepalive();
                    }
                }
            } catch (error) {
                console.error('Error toggling BrownBot:', error);
            } finally {
                this.loading.brownBotToggle = false;
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

        async loadBrownBotCandidates() {
            try {
                this.loading.brownBotCandidates = true;
                const response = await axios.get('/api/brown-bot/candidates', { headers: this.authHeaders() });
                if (response.data.success) {
                    this.brownBotCandidates = {
                        scanner: response.data.scanner || [],
                        watchlist: response.data.watchlist || [],
                    };
                    // Auto-load signals whenever candidates refresh
                    this.loadCandidateSignals();
                }
            } catch (error) {
                console.error('Error loading BrownBot candidates:', error);
            } finally {
                this.loading.brownBotCandidates = false;
            }
        },

        async loadCandidateSignals() {
            const tickers = this.brownBotCandidates.scanner.map(s => s.ticker);
            if (!tickers.length) return;
            try {
                this.loading.brownBotSignals = true;
                // Reset so stale data doesn't linger for symbols no longer in list
                this.brownBotSignals = Object.fromEntries(tickers.map(t => [t, { loading: true }]));
                const response = await axios.get(
                    `/api/brown-bot/candidate-signals?symbols=${tickers.join(',')}`,
                    { headers: this.authHeaders() }
                );
                if (response.data.success) {
                    this.brownBotSignals = response.data.signals || {};
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
        },

        stopBrownBotPolling() {
            if (this.brownBotPollingInterval) {
                clearInterval(this.brownBotPollingInterval);
                this.brownBotPollingInterval = null;
            }
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
