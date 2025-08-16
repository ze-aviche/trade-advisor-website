// Gap Up Trade Bot Dashboard - Vue.js Application

console.log('🚀 Loading Trading Advisor Dashboard...');

const { createApp } = Vue;

console.log('✅ Vue.js loaded successfully');

// Configure axios base URL
axios.defaults.baseURL = 'http://localhost:5000';

const app = createApp({
        data() {
            return {
                // Dashboard data
                stats: {
                    totalTrades: 0,
                    winRate: 0,
                    totalPnl: 0,
                    pnl: 0,
                    activePositions: 0,
                    gapUps: 0
                },
                recentActivity: [],
                gapUps: [],
                trades: [],
                
                // UI state
                activeTab: 'dashboard',
                loading: {
                    stats: false,
                    gapUps: false,
                    trades: false,
                    historical: false,
                    bot: false,
                    dashboardTrades: false,
                    dashboardPnL: false,
                    syncTrades: false,
                    unsubscribe: false,
                    importDAS: false
                },
                
                // Charts
                charts: {
                    pnl: null,
                    trades: null
                },
                
                // WebSocket connection
                socket: null,
                socketConnected: false,
                subscribedStocks: new Set(),
                livePrices: {},
                
                // AI Chat
                chatSession: null,
                chatMessages: [],
                newMessage: '',
                chatLoading: false,
                
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
                    subscribedStocks: [],
                    analysisResults: [],
                    positions: [],
                    activePositions: 0
                },
                
                // User data
                user: null,
                
                // Historical data
                historicalTicker: '',
                historicalData: [],
                selectedPeriod: '365', // Default to 1 year
                sortColumn: '',
                sortDirection: 'asc',
                
                // Trade History
                tradeHistoryPeriod: '7', // Default to 1 week
                tradeHistoryTicker: '', // Ticker search filter
                
                // Dashboard Trade Period
                dashboardTradePeriod: '365', // Default to 1 year
                
                // Dashboard P&L Date Range
                dashboardPnLFromDate: '',
                dashboardPnLToDate: '',
                
                // Dashboard Trade Date Range
                dashboardTradeFromDate: '',
                dashboardTradeToDate: '',
                
                // Import DAS Data Modal
                showImportModal: false,
                dasTradesData: '',
                
                // Dashboard chart data
                dashboardTrades: [],
                dashboardPnL: [],
                
                // Stock selection for unsubscribe
                selectedStocks: [],
                
                // Strategy configuration
                strategiesLoaded: null

            }
        },
        
        computed: {
            availableStrategies() {
                // Try to load from backend first, then fallback to local config
                if (this.strategiesLoaded) {
                    return this.strategiesLoaded;
                }
                
                // Use external configuration if available
                if (window.STRATEGY_CONFIG) {
                    return window.STRATEGY_CONFIG.strategies;
                }
                
                // Fallback configuration
                return [
                    {
                        key: 'breakOut',
                        name: 'Break Out',
                        direction: 'LONG',
                        directionColor: 'text-green-400',
                        color: 'text-blue-400',
                        badgeClass: 'bg-blue-100 text-blue-800',
                        minGap: 25,
                        target: 25, // Default to min gap value
                        stopLoss: 15,
                        availability: 'Always',
                        availabilityColor: 'text-green-400',
                        conditions: [
                            'Gap up above 25%',
                            'Price breaks above day high',
                            'Above VWAP',
                            'Sufficient volume'
                        ]
                    },
                    {
                        key: 'gapUpShort',
                        name: 'Gap Up Short',
                        direction: 'SHORT',
                        directionColor: 'text-red-400',
                        color: 'text-purple-400',
                        badgeClass: 'bg-purple-100 text-purple-800',
                        minGap: 40,
                        target: 15, // Default to 15% for short
                        stopLoss: 15,
                        availability: 'After 10 AM',
                        availabilityColor: 'text-yellow-400',
                        conditions: [
                            'Gap up above 40%',
                            'After 10 AM',
                            'Below premarket high',
                            'Volume in range'
                        ]
                    }
                ];
            },
            
            allStocksSelected() {
                return this.botStatus.subscribedStocks.length > 0 && 
                       this.selectedStocks.length === this.botStatus.subscribedStocks.length;
            }
        },
        

        
        mounted() {
            console.log('🎯 Vue.js app mounted successfully');
            this.checkAuth();
            
            // Add page load event listener for automatic refresh
            window.addEventListener('load', () => {
                console.log('📄 Page loaded, ensuring dashboard data is fresh...');
                // Small delay to ensure Vue is fully initialized
                setTimeout(() => {
                    if (this.user) {
                        console.log('🔄 Page load refresh triggered...');
                        this.forceRefreshDashboard();
                    }
                }, 1000);
            });
        },
        
        methods: {
            checkAuth() {
                const sessionToken = localStorage.getItem('session_token');
                const user = localStorage.getItem('user');
                
                if (!sessionToken || !user) {
                    // For testing, create a mock session
                    console.log('No session found, creating mock session for testing...');
                    localStorage.setItem('session_token', 'mock-session-token');
                    localStorage.setItem('user', JSON.stringify({
                        username: 'testuser',
                        email: 'test@example.com'
                    }));
                    
                    // Initialize app directly for testing
                    this.user = { username: 'testuser', email: 'test@example.com' };
                    this.initializeApp();
                    return;
                }
                
                // Validate session with backend
                this.validateSession();
            },
            
            // Handle tab changes
            onTabChange(tabName) {
                console.log(`🔄 Tab changed to: ${tabName}`);
                if (tabName === 'bot') {
                    console.log('🤖 Bot tab selected - loading bot status...');
                    this.loadBotStatus();
                } else if (tabName === 'trades') {
                    console.log('📊 Trade History tab selected - loading trade history...');
                    this.loadTradeHistory();
                }
            },
            
            async validateSession() {
                try {
                    const response = await fetch('http://localhost:5000/api/auth/profile', {
                        headers: {
                            'Authorization': `Bearer ${localStorage.getItem('session_token')}`
                        }
                    });
                    
                    if (response.ok) {
                        const userData = await response.json();
                        this.user = userData;
                        return true;
                    } else {
                        // Session invalid, redirect to login
                        localStorage.removeItem('session_token');
                        localStorage.removeItem('user');
                        window.location.href = '/login.html';
                        return false;
                    }
                } catch (error) {
                    console.error('Session validation error:', error);
                    return false;
                }
            },
            
            logout() {
                localStorage.removeItem('session_token');
                localStorage.removeItem('user');
                window.location.href = '/login.html';
            },
            
            async initializeApp() {
                console.log('🚀 Initializing Trading Advisor Dashboard...');
                
                try {
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
                    this.loadDashboardData().catch(error => {
                        console.error('❌ Failed to load dashboard data:', error);
                    });
                    
                    // Load bot status in parallel
                    console.log('🤖 Loading bot status...');
                    this.loadBotStatus().catch(error => {
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
            
            async checkSystemStatus() {
                try {
                    console.log('🔍 Checking system status...');
                    const response = await fetch('http://localhost:5000/api/health');
                    const data = await response.json();
                    console.log('📊 System status response:', data);
                    
                    // Get bot status from the new API
                    const botResponse = await fetch('http://localhost:5000/api/bot/status');
                    const botData = await botResponse.json();
                    console.log('🤖 Bot status response:', botData);
                    
                    // Update individual properties to ensure Vue reactivity
                    this.systemStatus.connected = data.status === 'healthy';
                    this.systemStatus.realDataAvailable = data.real_data_available;
                    this.systemStatus.websocketConnected = data.websocket_connected;
                    this.systemStatus.botRunning = botData.is_running;
                    
                    console.log('✅ System status updated:', this.systemStatus);
                    console.log('🔍 Current systemStatus object:', JSON.stringify(this.systemStatus, null, 2));
                } catch (error) {
                    console.error('❌ Error checking system status:', error);
                    this.systemStatus.connected = false;
                    console.log('❌ System status set to disconnected due to error');
                }
            },
            
            async loadDashboardData() {
                console.log('📊 Starting dashboard data load...');
                try {
                    const promises = [
                        this.loadStats().then(() => console.log('✅ Stats loaded')),
                        this.loadGapUps().then(() => console.log('✅ Gap-ups loaded')),
                        this.loadDashboardTrades().then(() => console.log('✅ Dashboard trades loaded')),
                        this.loadDashboardPnL().then(() => console.log('✅ Dashboard PnL loaded'))
                    ];
                    
                    await Promise.allSettled(promises);
                    console.log('✅ Dashboard data load completed');
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
                    this.botStatus = {
                        running: response.data.is_running || false,
                        subscribedStocks: response.data.subscribed_stocks || [],
                        analysisResults: response.data.analysis_results || [],
                        positions: response.data.positions || [],
                        activePositions: response.data.positions ? response.data.positions.length : 0
                    };
                    console.log('✅ Bot status loaded:', this.botStatus);
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
            
            async toggleBot() {
                try {
                    if (this.botStatus.running) {
                        // Stop bot
                        await axios.post('/api/bot/stop');
                        this.showNotification('Bot stopped successfully', 'success');
                    } else {
                        // Start bot
                        await axios.post('/api/bot/start');
                        this.showNotification('Bot started successfully', 'success');
                    }
                    
                    // Refresh bot status
                    await this.loadBotStatus();
                } catch (error) {
                    console.error('Error toggling bot:', error);
                    this.showNotification('Failed to toggle bot', 'error');
                }
            },
            
            async refreshBotData() {
                try {
                    console.log('🔄 Refreshing bot data...');
                    this.loading.bot = true;
                    await this.loadBotStatus();
                    this.showNotification('Bot data refreshed successfully', 'success');
                } catch (error) {
                    console.error('❌ Error refreshing bot data:', error);
                    this.showNotification('Failed to refresh bot data', 'error');
                } finally {
                    this.loading.bot = false;
                }
            },
            
            async refreshAllBotComponents() {
                try {
                    console.log('🔄 Refreshing all bot components...');
                    this.loading.bot = true;
                    
                    // Show loading notification
                    this.showNotification('Refreshing all bot components...', 'info');
                    
                    // Refresh all bot-related data in parallel
                    const refreshTasks = [
                        this.loadBotStatus(),
                        this.loadStrategiesFromBackend()
                    ];
                    
                    await Promise.all(refreshTasks);
                    
                    console.log('✅ All bot components refreshed successfully');
                    this.showNotification('All bot components refreshed successfully', 'success');
                } catch (error) {
                    console.error('❌ Error refreshing all bot components:', error);
                    this.showNotification('Failed to refresh all bot components', 'error');
                } finally {
                    this.loading.bot = false;
                }
            },
            
            startPeriodicBotUpdates() {
                // Update bot data every 5 seconds when bot tab is active
                setInterval(() => {
                    if (this.activeTab === 'bot') {
                        this.refreshBotData();
                    }
                }, 5000);
                
                // Auto-sync functionality removed - no longer using Alpaca
            },
            

            
            async loadStats() {
                console.log('📊 Loading stats...');
                this.updateLoadingProgress('stats', 'loading');
                
                const maxRetries = 3;
                const retryDelay = 1000; // 1 second
                
                for (let attempt = 1; attempt <= maxRetries; attempt++) {
                    try {
                        console.log(`📊 Stats loading attempt ${attempt}/${maxRetries}...`);
                    const sessionToken = localStorage.getItem('session_token');
                        console.log('🔑 Using session token:', sessionToken ? 'Present' : 'Missing');
                        
                    const response = await fetch('http://localhost:5000/api/trades', {
                        headers: {
                            'Authorization': `Bearer ${sessionToken}`
                            },
                            signal: AbortSignal.timeout(10000) // 10 second timeout
                        });
                        
                        console.log('📡 Stats API response status:', response.status);
                        
                        if (!response.ok) {
                            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                        }
                        
                    const data = await response.json();
                        console.log('📊 Stats API response data:', data);
                    
                    if (data.success) {
                        this.trades = data.trades;
                        this.stats = {
                            totalTrades: data.summary.total_trades,
                            winRate: data.summary.win_rate,
                            totalPnl: data.summary.total_pnl,
                            pnl: data.summary.total_pnl,
                            activePositions: this.trades.filter(t => t.status === 'filled').length,
                            gapUps: this.gapUps.length
                        };
                            
                            console.log('✅ Stats loaded successfully:', this.stats);
                            this.updateLoadingProgress('stats', 'success');
                        
                        // Update charts after data is loaded
                        setTimeout(() => {
                            this.updatePnlChart();
                        }, 100);
                            
                            return; // Success, exit retry loop
                        } else {
                            console.error('❌ Stats API returned error:', data.message);
                            throw new Error(data.message || 'Failed to load stats');
                    }
                } catch (error) {
                        console.error(`❌ Error loading stats (attempt ${attempt}):`, error);
                        if (attempt === maxRetries) {
                            this.updateLoadingProgress('stats', 'error');
                        } else {
                            console.log(`⏳ Retrying stats load in ${retryDelay}ms...`);
                            await new Promise(resolve => setTimeout(resolve, retryDelay));
                        }
                    }
                }
                
                this.updateLoadingProgress('stats', 'error');
            },
            
            async loadGapUps() {
                console.log('📈 Loading gap-ups...');
                this.updateLoadingProgress('gapUps', 'loading');
                
                const maxRetries = 3;
                const retryDelay = 1000; // 1 second
                
                for (let attempt = 1; attempt <= maxRetries; attempt++) {
                    try {
                        console.log(`📈 Gap-ups loading attempt ${attempt}/${maxRetries}...`);
                        const response = await fetch('http://localhost:5000/api/gap-ups', {
                            signal: AbortSignal.timeout(10000) // 10 second timeout
                        });
                        
                        console.log('📡 Gap-ups API response status:', response.status);
                        
                        if (!response.ok) {
                            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                        }
                        
                    const data = await response.json();
                        console.log('📈 Gap-ups API response data:', data);
                    
                    if (data.success) {
                        this.gapUps = data.data || [];
                        this.stats.gapUps = this.gapUps.length;
                            console.log('✅ Gap-ups loaded successfully:', this.gapUps.length, 'stocks');
                            this.updateLoadingProgress('gapUps', 'success');
                            return; // Success, exit retry loop
                    } else {
                            console.error('❌ Gap-ups API returned error:', data.message);
                            throw new Error(data.message || 'Failed to load gap-ups');
                    }
                } catch (error) {
                        console.error(`❌ Error loading gap-ups (attempt ${attempt}):`, error);
                        if (attempt === maxRetries) {
                            this.updateLoadingProgress('gapUps', 'error');
                        } else {
                            console.log(`⏳ Retrying gap-ups load in ${retryDelay}ms...`);
                            await new Promise(resolve => setTimeout(resolve, retryDelay));
                        }
                    }
                }
                
                this.updateLoadingProgress('gapUps', 'error');
            },
            
            async invalidateGapUpsCache() {
                try {
                    console.log('🗑️ Invalidating gap-ups cache...');
                    const response = await fetch('http://localhost:5000/api/cache/invalidate-gap-ups', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        console.log('✅ Gap-ups cache invalidated successfully');
                        this.showNotification('Gap-ups cache cleared successfully', 'success');
                        
                        // Reload gap-ups data immediately after cache invalidation
                        await this.loadGapUps();
                    } else {
                        console.error('❌ Failed to invalidate gap-ups cache:', data.error);
                        this.showNotification('Failed to clear cache: ' + data.error, 'error');
                    }
                } catch (error) {
                    console.error('❌ Error invalidating gap-ups cache:', error);
                    this.showNotification('Error clearing cache: ' + error.message, 'error');
                }
            },
            
            async loadGapUpsBackground() {
                try {
                    console.log('🔄 Background gap-ups refresh triggered at:', new Date().toLocaleTimeString());
                    const response = await fetch('http://localhost:5000/api/gap-ups');
                    const data = await response.json();
                    
                    if (data.success) {
                        const oldCount = this.gapUps.length;
                        this.gapUps = data.data || [];
                        this.stats.gapUps = this.gapUps.length;
                        
                        console.log(`✅ Background gap-ups updated: ${oldCount} → ${this.gapUps.length} stocks at ${new Date().toLocaleTimeString()}`);
                        
                        // Subscribe to real-time updates for gap-up stocks
                        if (this.socketConnected && this.gapUps.length > 0) {
                            const tickers = this.gapUps.map(stock => stock.ticker);
                            this.subscribeToStocks(tickers);
                        }
                    } else {
                        console.warn('⚠️ Background gap-ups API returned error:', data.message);
                    }
                } catch (error) {
                    console.error('❌ Error loading gap-ups in background:', error);
                }
            },
            
            async loadTrades() {
                try {
                    this.loading.trades = true;
                    const response = await fetch('http://localhost:5000/api/trades');
                    const data = await response.json();
                    
                    if (data.success) {
                        this.trades = data.trades || [];
                    } else {
                        console.error('Failed to load trades:', data.message);
                    }
                } catch (error) {
                    console.error('Error loading trades:', error);
                } finally {
                    this.loading.trades = false;
                }
            },
            
            initializeDateRanges() {
                // Set default date ranges (last 7 days to include recent activity)
                const today = new Date();
                const sevenDaysAgo = new Date();
                sevenDaysAgo.setDate(today.getDate() - 7);
                
                // Format dates for input fields (YYYY-MM-DD)
                this.dashboardPnLFromDate = sevenDaysAgo.toISOString().split('T')[0];
                this.dashboardPnLToDate = today.toISOString().split('T')[0];
                this.dashboardTradeFromDate = sevenDaysAgo.toISOString().split('T')[0];
                this.dashboardTradeToDate = today.toISOString().split('T')[0];
                
                console.log('📅 Date ranges initialized:', {
                    pnl: `${this.dashboardPnLFromDate} to ${this.dashboardPnLToDate}`,
                    trades: `${this.dashboardTradeFromDate} to ${this.dashboardTradeToDate}`
                });
            },
            
            async loadDashboardTrades() {
                try {
                    // Use date range instead of period
                    const fromDate = this.dashboardTradeFromDate || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
                    const toDate = this.dashboardTradeToDate || new Date().toISOString().split('T')[0];
                    
                    console.log('🔄 Loading dashboard trades for date range:', fromDate, 'to', toDate);
                    this.loading.dashboardTrades = true;
                    const response = await fetch(`http://localhost:5000/api/trades?from=${fromDate}&to=${toDate}`);
                    const data = await response.json();
                    
                    if (data.success) {
                        this.dashboardTrades = data.trades || [];
                        console.log('✅ Dashboard trades loaded:', this.dashboardTrades.length, 'trades');
                        // Update the trade chart with new data
                        setTimeout(() => {
                            this.updateTradeChart();
                        }, 100);
                    } else {
                        console.error('Failed to load dashboard trades:', data.message);
                    }
                } catch (error) {
                    console.error('Error loading dashboard trades:', error);
                } finally {
                    this.loading.dashboardTrades = false;
                    console.log('🏁 Dashboard trades loading finished');
                }
            },
            
            async loadDashboardPnL() {
                try {
                    // Use date range instead of period
                    const fromDate = this.dashboardPnLFromDate || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
                    const toDate = this.dashboardPnLToDate || new Date().toISOString().split('T')[0];
                    
                    console.log('🔄 Loading dashboard P&L for date range:', fromDate, 'to', toDate);
                    this.loading.dashboardPnL = true;
                    const response = await fetch(`http://localhost:5000/api/trades?from=${fromDate}&to=${toDate}`);
                    const data = await response.json();
                    
                    if (data.success) {
                        this.dashboardPnL = data.trades || [];
                        console.log('✅ Dashboard P&L loaded:', this.dashboardPnL.length, 'trades');
                        // Update the P&L chart with new data
                        setTimeout(() => {
                            this.updatePnlChart();
                        }, 100);
                    } else {
                        console.error('Failed to load dashboard P&L data:', data.message);
                    }
                } catch (error) {
                    console.error('Error loading dashboard P&L data:', error);
                } finally {
                    this.loading.dashboardPnL = false;
                    console.log('🏁 Dashboard P&L loading finished');
                }
            },
            
            async loadTradeHistory() {
                try {
                    this.loading.trades = true;
                    
                    // Build query parameters
                    const params = new URLSearchParams();
                    
                    // Convert period to date range
                    const days = parseInt(this.tradeHistoryPeriod);
                    const endDate = new Date().toISOString().split('T')[0];
                    const startDate = new Date(Date.now() - (days * 24 * 60 * 60 * 1000)).toISOString().split('T')[0];
                    
                    params.append('start_date', startDate);
                    params.append('end_date', endDate);
                    params.append('limit', '1000');
                    
                    if (this.tradeHistoryTicker && this.tradeHistoryTicker.trim()) {
                        params.append('symbol', this.tradeHistoryTicker.trim().toUpperCase());
                    }
                    
                    const response = await fetch(`http://localhost:5000/api/trades?${params.toString()}`);
                    const data = await response.json();
                    
                    if (data.success) {
                        // Transform the data to match the expected format
                        this.trades = (data.data.trades || []).map(trade => ({
                            id: trade.id,
                            ticker: trade.symbol,
                            direction: trade.side === 'B' ? 'long' : (trade.side === 'S' ? 'short' : 'short'),
                            quantity: trade.quantity,
                            price: trade.price,
                            status: 'filled',
                            pnl: trade.pnl || 0,
                            submitted_at: trade.trade_date + ' ' + trade.trade_time,
                            route: trade.route,
                            order_id: trade.order_id,
                            ecn_fee: trade.ecn_fee
                        }));
                        
                        console.log(`📊 Loaded ${this.trades.length} trades${this.tradeHistoryTicker ? ` for ${this.tradeHistoryTicker}` : ''}`);
                        
                        // Update stats if summary is available
                        if (data.data.summary) {
                            this.stats.totalTrades = data.data.summary.total_trades || 0;
                            this.stats.pnl = data.data.summary.total_pnl || 0;
                        }
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
            
            downloadTradeHistoryCSV() {
                if (this.trades.length === 0) {
                    this.showNotification('No trades to download', 'warning');
                    return;
                }
                
                const headers = ['Ticker', 'Type', 'Quantity', 'Price', 'Status', 'P&L', 'Date'];
                const csvContent = [
                    headers.join(','),
                    ...this.trades.map(trade => [
                        trade.ticker,
                        trade.direction?.toUpperCase() || '',
                        trade.quantity || '',
                        trade.price || '',
                        trade.status || '',
                        trade.pnl || '0.00',
                        trade.submitted_at || ''
                    ].join(','))
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
                
                this.showNotification('Trade history downloaded as CSV', 'success');
            },
            
            downloadTradeHistoryExcel() {
                if (this.trades.length === 0) {
                    this.showNotification('No trades to download', 'warning');
                    return;
                }
                
                // Create workbook and worksheet
                const wb = XLSX.utils.book_new();
                const wsData = this.trades.map(trade => ({
                    'Ticker': trade.ticker,
                    'Type': trade.direction?.toUpperCase() || '',
                    'Quantity': trade.quantity || '',
                    'Price': trade.price || '',
                    'Status': trade.status || '',
                    'P&L': trade.pnl || '0.00',
                    'Date': trade.submitted_at || ''
                }));
                
                const ws = XLSX.utils.json_to_sheet(wsData);
                XLSX.utils.book_append_sheet(wb, ws, 'Trade History');
                
                // Download the file
                XLSX.writeFile(wb, `trade_history_${new Date().toISOString().split('T')[0]}.xlsx`);
                
                this.showNotification('Trade history downloaded as Excel', 'success');
            },
            
            loadRecentActivity() {
                // Mock recent activity data
                this.recentActivity = [
                    {
                        id: 1,
                        type: 'trade',
                        message: 'Bought 100 shares of AAPL at $150.25',
                        timestamp: new Date(Date.now() - 300000).toISOString(),
                        status: 'completed'
                    },
                    {
                        id: 2,
                        type: 'alert',
                        message: 'NVDA gap-up detected: +5.8%',
                        timestamp: new Date(Date.now() - 600000).toISOString(),
                        status: 'new'
                    },
                    {
                        id: 3,
                        type: 'analysis',
                        message: 'Technical analysis completed for TSLA',
                        timestamp: new Date(Date.now() - 900000).toISOString(),
                        status: 'completed'
                    }
                ];
            },
            
            async analyzeStock(ticker) {
                try {
                    console.log(`🔍 Analyzing stock: ${ticker}`);
                    
                    // Find the stock data
                    const stock = this.gapUps.find(s => s.ticker === ticker);
                    if (!stock) {
                        console.error(`❌ Stock ${ticker} not found in gap-ups`);
                        return;
                    }
                    
                    console.log(`✅ Found stock:`, stock);
                    this.showNotification(`Stock analysis for ${ticker} - Modal feature removed`, 'info');
                    
                } catch (error) {
                    console.error(`❌ Error analyzing ${ticker}:`, error);
                    this.showNotification(`Error analyzing ${ticker}`, 'error');
                }
            },
            
            async loadHistoricalData() {
                if (!this.historicalTicker) {
                    this.showNotification('Please enter a ticker symbol', 'warning');
                    return;
                }
                
                try {
                    this.loading.historical = true;
                    this.historicalData = [];
                    
                    const response = await fetch(`http://localhost:5000/api/historical-data/${this.historicalTicker.toUpperCase()}?days=${this.selectedPeriod}&cache=true&_t=${Date.now()}`);
                    const data = await response.json();
                    
                    if (data.success) {
                        this.historicalData = data.data || [];
                        console.log(`📊 Loaded ${this.historicalData.length} historical data points for ${this.historicalTicker.toUpperCase()}`);
                    } else {
                        this.showNotification(data.message || 'Failed to load historical data', 'error');
                    }
                } catch (error) {
                    console.error('Error loading historical data:', error);
                    this.showNotification('Error loading historical data', 'error');
                } finally {
                    this.loading.historical = false;
                }
            },
            
            clearHistoricalData() {
                this.historicalData = [];
                this.historicalTicker = '';
                this.loading.historical = false;
            },
            

            
            downloadExcel() {
                if (this.historicalData.length === 0) {
                    this.showNotification('No data to export', 'warning');
                    return;
                }
                
                try {
                    console.log('📊 Preparing Excel export...');
                    
                    // Prepare worksheet data
                    const worksheetData = this.historicalData.map(day => ({
                        'Date': day.date,
                        'Previous Close': day['pd close'] ? `$${day['pd close']}` : 'N/A',
                        'Premarket Open': day['premarket open'] ? `$${day['premarket open']}` : 'N/A',
                        'Premarket High': day['premarket high'] ? `$${day['premarket high']}` : 'N/A',
                        'Premarket High Time': day['premarket high time'] || 'N/A',
                        'Premarket Volume': day['premarket volume'] ? `${(day['premarket volume'] / 1000000).toFixed(2)}M` : 'N/A',
                        'Open': `$${day.open}`,
                        'Gap % at Open': day['gap up % at open'] ? `${day['gap up % at open']}%` : 'N/A',
                        'Day High': `$${day['day high']}`,
                        'Day High Time': day['day high time'] || 'N/A',
                        'Day High %': day['day high %'] ? `${day['day high %']}%` : 'N/A',
                        'Close': `$${day['close price']}`,
                        'Closing %': day['closing percent'] ? `${day['closing percent']}%` : 'N/A',
                        'After Hours Close': day['afterhours close'] ? `$${day['afterhours close']}` : 'N/A',
                        'Total Volume': day['total volume'] ? `${(day['total volume'] / 1000000).toFixed(2)}M` : 'N/A',
                        'VWAP Crosses': day['VWAP Crosses'] || 0,
                        'Pattern': day['Runner/Fader'] || 'N/A',
                        'Volume (Millions)': day.volume_millions ? `${day.volume_millions}M` : 'N/A',
                        'Dollar Volume (Millions)': day.dollar_volume_millions ? `$${day.dollar_volume_millions}M` : 'N/A'
                    }));
                    
                    // Create workbook and worksheet
                    const workbook = XLSX.utils.book_new();
                    const worksheet = XLSX.utils.json_to_sheet(worksheetData);
                    
                    // Set column widths for better readability
                    const columnWidths = [
                        { wch: 12 }, // Date
                        { wch: 15 }, // Previous Close
                        { wch: 15 }, // Premarket Open
                        { wch: 15 }, // Premarket High
                        { wch: 18 }, // Premarket High Time
                        { wch: 18 }, // Premarket Volume
                        { wch: 12 }, // Open
                        { wch: 15 }, // Gap % at Open
                        { wch: 15 }, // Day High
                        { wch: 18 }, // Day High Time
                        { wch: 15 }, // Day High %
                        { wch: 12 }, // Close
                        { wch: 15 }, // Closing %
                        { wch: 18 }, // After Hours Close
                        { wch: 15 }, // Total Volume
                        { wch: 15 }, // VWAP Crosses
                        { wch: 12 }, // Pattern
                        { wch: 18 }, // Volume (Millions)
                        { wch: 22 }  // Dollar Volume (Millions)
                    ];
                    worksheet['!cols'] = columnWidths;
                    
                    // Add worksheet to workbook
                    XLSX.utils.book_append_sheet(workbook, worksheet, 'Historical Data');
                    
                    // Generate filename with timestamp
                                    const timestamp = new Date().toISOString().slice(0, 10);
                const filename = `${this.historicalTicker.toUpperCase()}_3Year_Historical_Data_${timestamp}.xlsx`;
                    
                    // Download the file
                    XLSX.writeFile(workbook, filename);
                    
                    console.log('✅ Excel file downloaded successfully');
                    this.showNotification(`Excel file "${filename}" downloaded successfully`, 'success');
                    
                } catch (error) {
                    console.error('❌ Error downloading Excel file:', error);
                    this.showNotification('Error downloading Excel file', 'error');
                }
            },
            
            downloadCSV() {
                if (this.historicalData.length === 0) {
                    this.showNotification('No data to export', 'warning');
                    return;
                }
                
                try {
                    console.log('📊 Preparing CSV export...');
                    
                    // Define CSV headers
                    const headers = [
                        'Date',
                        'Previous Close',
                        'Premarket Open',
                        'Premarket High',
                        'Premarket High Time',
                        'Premarket Volume',
                        'Open',
                        'Gap % at Open',
                        'Day High',
                        'Day High Time',
                        'Day High %',
                        'Close',
                        'Closing %',
                        'After Hours Close',
                        'Total Volume',
                        'VWAP Crosses',
                        'Pattern',
                        'Volume (Millions)',
                        'Dollar Volume (Millions)'
                    ];
                    
                    // Prepare CSV data
                    const csvData = this.historicalData.map(day => [
                        day.date,
                        day['pd close'] ? `$${day['pd close']}` : 'N/A',
                        day['premarket open'] ? `$${day['premarket open']}` : 'N/A',
                        day['premarket high'] ? `$${day['premarket high']}` : 'N/A',
                        day['premarket high time'] || 'N/A',
                        day['premarket volume'] ? `${(day['premarket volume'] / 1000000).toFixed(2)}M` : 'N/A',
                        `$${day.open}`,
                        day['gap up % at open'] ? `${day['gap up % at open']}%` : 'N/A',
                        `$${day['day high']}`,
                        day['day high time'] || 'N/A',
                        day['day high %'] ? `${day['day high %']}%` : 'N/A',
                        `$${day['close price']}`,
                        day['closing percent'] ? `${day['closing percent']}%` : 'N/A',
                        day['afterhours close'] ? `$${day['afterhours close']}` : 'N/A',
                        day['total volume'] ? `${(day['total volume'] / 1000000).toFixed(2)}M` : 'N/A',
                        day['VWAP Crosses'] || 0,
                        day['Runner/Fader'] || 'N/A',
                        day.volume_millions ? `${day.volume_millions}M` : 'N/A',
                        day.dollar_volume_millions ? `$${day.dollar_volume_millions}M` : 'N/A'
                    ]);
                    
                    // Combine headers and data
                    const csvContent = [headers, ...csvData]
                        .map(row => row.map(cell => `"${cell}"`).join(','))
                        .join('\n');
                    
                    // Create and download CSV file
                                    const timestamp = new Date().toISOString().slice(0, 10);
                const filename = `${this.historicalTicker.toUpperCase()}_3Year_Historical_Data_${timestamp}.csv`;
                    
                    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                    const link = document.createElement('a');
                    const url = URL.createObjectURL(blob);
                    link.setAttribute('href', url);
                    link.setAttribute('download', filename);
                    link.style.visibility = 'hidden';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    
                    console.log('✅ CSV file downloaded successfully');
                    this.showNotification(`CSV file "${filename}" downloaded successfully`, 'success');
                    
                } catch (error) {
                    console.error('❌ Error downloading CSV file:', error);
                    this.showNotification('Error downloading CSV file', 'error');
                }
            },
            
            // Helper methods for historical data statistics
            getGapUpDaysCount() {
                if (!this.historicalData.length) return 0;
                return this.historicalData.filter(day => 
                    day['gap up % at open'] && day['gap up % at open'] >= 25
                ).length;
            },
            
            getRunnerDaysCount() {
                if (!this.historicalData.length) return 0;
                return this.historicalData.filter(day => 
                    day['Runner/Fader'] === 'Runner'
                ).length;
            },
            
            getFaderDaysCount() {
                if (!this.historicalData.length) return 0;
                return this.historicalData.filter(day => 
                    day['Runner/Fader'] === 'Fader'
                ).length;
            },
            
            getAverageGapPercent() {
                if (!this.historicalData.length) return 0;
                const gapUpDays = this.historicalData.filter(day => 
                    day['gap up % at open'] && day['gap up % at open'] >= 25
                );
                if (gapUpDays.length === 0) return 0;
                
                const totalGap = gapUpDays.reduce((sum, day) => 
                    sum + day['gap up % at open'], 0
                );
                return (totalGap / gapUpDays.length).toFixed(2);
            },
            
            // Sorting methods
            sortTable(column) {
                if (this.sortColumn === column) {
                    // Toggle direction if same column
                    this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
                } else {
                    // New column, start with ascending
                    this.sortColumn = column;
                    this.sortDirection = 'asc';
                }
                
                this.historicalData.sort((a, b) => {
                    let aVal = a[column];
                    let bVal = b[column];
                    
                    // Handle numeric values
                    if (typeof aVal === 'number' && typeof bVal === 'number') {
                        return this.sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
                    }
                    
                    // Handle string values
                    if (typeof aVal === 'string' && typeof bVal === 'string') {
                        return this.sortDirection === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
                    }
                    
                    // Handle null/undefined values
                    if (aVal == null && bVal == null) return 0;
                    if (aVal == null) return this.sortDirection === 'asc' ? -1 : 1;
                    if (bVal == null) return this.sortDirection === 'asc' ? 1 : -1;
                    
                    return 0;
                });
            },
            
            getSortIcon(column) {
                if (this.sortColumn !== column) {
                    return 'fas fa-sort text-gray-400';
                }
                return this.sortDirection === 'asc' ? 'fas fa-sort-up text-blue-400' : 'fas fa-sort-down text-blue-400';
            },
            

            

            

            
            async startChatSession() {
                try {
                    const response = await fetch('http://localhost:5000/api/ai-agent/start-session', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        this.chatSession = data.data.session_id;
                        this.chatMessages = [];
                        this.showNotification('AI Agent session started', 'success');
                        
                        // Add welcome message
                        this.chatMessages.push({
                            id: Date.now(),
                            type: 'assistant',
                            content: 'Hello! I\'m your AI Trading Assistant. I can help you with gap-up trading strategies, market analysis, and trade planning. What would you like to know?',
                            timestamp: new Date().toISOString()
                        });
                    } else {
                        this.showNotification(data.error || 'Failed to start AI Agent session', 'error');
                    }
                } catch (error) {
                    console.error('Error starting AI Agent session:', error);
                    this.showNotification('Error starting AI Agent session', 'error');
                }
            },
            
            async sendChatMessage() {
                if (!this.newMessage.trim()) return;
                
                const userMessage = {
                    id: Date.now(),
                    type: 'user',
                    content: this.newMessage,
                    timestamp: new Date().toISOString()
                };
                
                this.chatMessages.push(userMessage);
                const messageToSend = this.newMessage;
                this.newMessage = '';
                
                this.chatLoading = true;
                
                try {
                    const response = await fetch('http://localhost:5000/api/ai-agent/chat', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            message: messageToSend
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        this.chatMessages.push({
                            id: Date.now() + 1,
                            type: 'assistant',
                            content: data.data.response,
                            timestamp: new Date().toISOString()
                        });
                    } else {
                        this.chatMessages.push({
                            id: Date.now() + 1,
                            type: 'assistant',
                            content: `Error: ${data.error || 'Failed to get response from AI Agent'}`,
                            timestamp: new Date().toISOString()
                        });
                    }
                } catch (error) {
                    console.error('Error sending message to AI Agent:', error);
                    
                    this.chatMessages.push({
                        id: Date.now() + 1,
                        type: 'assistant',
                        content: 'Sorry, I encountered an error. Please try again.',
                        timestamp: new Date().toISOString()
                    });
                } finally {
                    this.chatLoading = false;
                }
            },
            
            // WebSocket methods
            connectWebSocket() {
                console.log('🔌 Attempting to connect WebSocket...');
                try {
                    // Socket.IO is now loaded in HTML head
                    this.initializeSocket();
                } catch (error) {
                    console.error('Error initializing WebSocket:', error);
                    // Don't let WebSocket errors crash the entire app
                    this.systemStatus.websocketConnected = false;
                }
            },
            
            initializeSocket() {
                if (typeof io === 'undefined') {
                    console.error('Socket.IO not loaded');
                    this.systemStatus.websocketConnected = false;
                    return;
                }
                
                console.log('🔌 Initializing Socket.IO connection...');
                try {
                    this.socket = io('http://localhost:5000');
                } catch (error) {
                    console.error('Failed to create Socket.IO connection:', error);
                    this.systemStatus.websocketConnected = false;
                    return;
                }
                
                this.socket.on('connect', () => {
                    console.log('✅ Connected to WebSocket server');
                    this.socketConnected = true;
                    this.systemStatus.websocketConnected = true;
                    
                    // Subscribe to gap-up stocks if available
                    if (this.gapUps.length > 0) {
                        const tickers = this.gapUps.map(stock => stock.ticker);
                        this.subscribeToStocks(tickers);
                    }
                });
                
                this.socket.on('disconnect', () => {
                    console.log('❌ Disconnected from WebSocket server');
                    this.socketConnected = false;
                    this.systemStatus.websocketConnected = false;
                });
                
                this.socket.on('price_update', (data) => {
                    console.log('📊 Received price update:', data);
                    this.handlePriceUpdate(data);
                });
                
                this.socket.on('real_time_gap_up', (data) => {
                    console.log('🚨 Real-time gap-up detected:', data);
                    this.handleRealTimeGapUp(data);
                });
                
                this.socket.on('subscribed', (data) => {
                    console.log('✅ Subscribed to stocks:', data.stocks);
                    data.stocks.forEach(ticker => this.subscribedStocks.add(ticker));
                });
                
                this.socket.on('unsubscribed', (data) => {
                    console.log('❌ Unsubscribed from stocks:', data.stocks);
                    data.stocks.forEach(ticker => this.subscribedStocks.delete(ticker));
                });
                
                this.socket.on('connect_error', (error) => {
                    console.error('❌ WebSocket connection error:', error);
                    this.socketConnected = false;
                    this.systemStatus.websocketConnected = false;
                });
            },
            
            subscribeToStocks(tickers) {
                if (this.socket && this.socketConnected) {
                    this.socket.emit('subscribe_stocks', { stocks: tickers });
                }
            },
            
            unsubscribeFromStocks(tickers) {
                if (this.socket && this.socketConnected) {
                    this.socket.emit('unsubscribe_stocks', { stocks: tickers });
                }
            },
            
            handlePriceUpdate(data) {
                const { ticker, data: priceData } = data;
                
                // Update live prices
                this.livePrices[ticker] = priceData;
                
                // Update gap-up stocks if this ticker is in the list
                const stockIndex = this.gapUps.findIndex(stock => stock.ticker === ticker);
                if (stockIndex !== -1) {
                    this.gapUps[stockIndex] = {
                        ...this.gapUps[stockIndex],
                        price: priceData.price,
                        change: priceData.change,
                        change_percent: priceData.change_percent
                    };
                }
                
                // Emit custom event for price updates
                this.$emit('price-updated', { ticker, data: priceData });
            },
            
            handleRealTimeGapUp(data) {
                const gapUpData = data.data;
                
                // Filter out stocks less than $1
                if (!gapUpData.price || gapUpData.price < 1.0) {
                    console.log(`🚫 Filtered out low-priced stock: ${gapUpData.ticker} ($${gapUpData.price})`);
                    return;
                }
                
                // Check if stock already exists
                const existingIndex = this.gapUps.findIndex(
                    stock => stock.ticker === gapUpData.ticker
                );
                
                if (existingIndex === -1) {
                    // New stock - add to beginning
                    this.gapUps.unshift(gapUpData);
                    this.stats.gapUps = this.gapUps.length;
                    
                    // Show special real-time gap-up notification
                    this.showRealTimeGapUpNotification(gapUpData);
                    
                    // Subscribe to real-time updates for this stock
                    if (this.socketConnected) {
                        this.subscribeToStocks([gapUpData.ticker]);
                    }
                    
                    console.log('🚨 Real-time gap-up added:', gapUpData);
                } else {
                    // Update existing stock data
                    this.gapUps[existingIndex] = {
                        ...this.gapUps[existingIndex],
                        ...gapUpData
                    };
                    console.log('🔄 Updated existing gap-up stock:', gapUpData.ticker);
                }
            },
            
            showRealTimeGapUpNotification(gapUpData) {
                const notification = document.createElement('div');
                notification.className = `fixed top-0 left-0 right-0 z-50 transform -translate-y-full transition-transform duration-700 ease-out bg-gradient-to-r from-red-600 via-orange-500 to-yellow-500 text-white shadow-2xl`;
                
                notification.innerHTML = `
                    <div class="flex items-center justify-between px-8 py-6">
                        <div class="flex items-center space-x-4">
                            <div class="flex-shrink-0">
                                <div class="w-12 h-12 bg-white bg-opacity-20 rounded-full flex items-center justify-center">
                                    <i class="fas fa-rocket text-2xl"></i>
                                </div>
                            </div>
                            <div>
                                <div class="flex items-center space-x-2">
                                    <h3 class="text-xl font-bold">🚨 REAL-TIME GAP-UP DETECTED!</h3>
                                    <span class="bg-white bg-opacity-20 px-2 py-1 rounded-full text-sm font-semibold">LIVE</span>
                                </div>
                                <p class="text-lg font-semibold">${gapUpData.ticker} - ${gapUpData.company_name}</p>
                                <p class="text-2xl font-bold">+${gapUpData.gap_percent}% GAP</p>
                                <p class="text-sm opacity-90">Price: $${gapUpData.price} | Previous: $${gapUpData.previous_close}</p>
                            </div>
                        </div>
                        <div class="flex items-center space-x-4">
                            <div class="text-right">
                                <p class="text-sm opacity-90">${new Date().toLocaleTimeString()}</p>
                                <p class="text-xs opacity-75">Auto-detected</p>
                            </div>
                            <button onclick="this.parentElement.parentElement.parentElement.remove()" class="text-white hover:text-gray-200 p-2">
                                <i class="fas fa-times text-xl"></i>
                            </button>
                        </div>
                    </div>
                `;
                
                document.body.appendChild(notification);
                
                // Slide in with bounce effect
                setTimeout(() => {
                    notification.classList.remove('-translate-y-full');
                }, 100);
                
                // Auto remove after 8 seconds
                setTimeout(() => {
                    notification.classList.add('-translate-y-full');
                    setTimeout(() => {
                        if (notification.parentElement) {
                            notification.remove();
                        }
                    }, 700);
                }, 8000);
            },
            
            setupCharts() {
                try {
                    console.log('🔄 Setting up charts...');
                    // Only setup trade chart - PnL chart is created dynamically
                    this.setupTradeChart();
                    
                    console.log('📊 Charts initialized:', {
                        pnl: !!this.charts.pnl,
                        trades: !!this.charts.trades
                    });
                    
                    // Handle window resize to prevent chart issues
                    window.addEventListener('resize', () => {
                        if (this.charts.pnl) {
                            this.charts.pnl.resize();
                        }
                        if (this.charts.trades) {
                            this.charts.trades.resize();
                        }
                    });
                } catch (error) {
                    console.error('❌ Error setting up charts:', error);
                    // Continue without charts if they fail to load
                }
            },
            
            setupPnlChart() {
                // This function is now deprecated - charts are created directly in updatePnlChart
                console.log('🔄 setupPnlChart called - this function is deprecated');
            },
            
            updatePnlChart() {
                console.log('🔄 Updating PnL chart...');
                console.log('📊 Chart object exists:', !!this.charts.pnl);
                console.log('📊 Dashboard PnL data:', this.dashboardPnL.length, 'trades');
                
                // Safely destroy existing chart if it exists
                if (this.charts.pnl) {
                    try {
                        this.charts.pnl.destroy();
                        console.log('🗑️ Destroyed existing PnL chart');
                    } catch (error) {
                        console.warn('⚠️ Error destroying existing chart:', error);
                    }
                    this.charts.pnl = null;
                }
                
                // Create chart directly - no need to call setupPnlChart since it's deprecated
                
                // Calculate cumulative P&L from trades
                const pnlData = [];
                const labels = [];
                let cumulativePnl = 0;
                
                // Sort trades by timestamp
                const sortedTrades = [...this.dashboardPnL].sort((a, b) => 
                    new Date(a.submitted_at) - new Date(b.submitted_at)
                );
                
                console.log('📊 Sorted trades:', sortedTrades.length);
                
                sortedTrades.forEach((trade, index) => {
                    const tradePnl = trade.pnl || 0;
                    cumulativePnl += tradePnl;
                    pnlData.push(cumulativePnl);
                    labels.push(new Date(trade.submitted_at).toLocaleDateString());
                    console.log(`📈 Trade ${index + 1}: ${trade.ticker} - PnL: $${tradePnl}, Cumulative: $${cumulativePnl}`);
                });
                
                // If no trades, use default data
                if (pnlData.length === 0) {
                    pnlData.push(0);
                    labels.push('No trades');
                    console.log('⚠️ No trades found, using default data');
                }
                
                console.log('📊 Final PnL data:', pnlData);
                console.log('📊 Final labels:', labels);
                
                // Create new chart with data directly
                const ctx = document.getElementById('pnlChart');
                if (!ctx) {
                    console.error('❌ PnL chart canvas not found');
                    return;
                }
                
                // Check if canvas is visible and has dimensions
                const canvasRect = ctx.getBoundingClientRect();
                console.log('📊 Canvas dimensions:', {
                    width: canvasRect.width,
                    height: canvasRect.height,
                    visible: canvasRect.width > 0 && canvasRect.height > 0
                });
                
                try {
                    console.log('🔄 Creating PnL chart with data:', {
                        labels: labels,
                        data: pnlData,
                        canvas: ctx
                    });
                
                this.charts.pnl = new Chart(ctx, {
                    type: 'line',
                    data: {
                            labels: labels,
                        datasets: [{
                            label: 'P&L',
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
                        plugins: {
                            legend: {
                                labels: {
                                        color: '#D1D5DB'
                                }
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: '#ffffff',
                                    bodyColor: '#ffffff'
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    color: '#D1D5DB',
                                    callback: function(value) {
                                        return '$' + value.toLocaleString();
                                    }
                                },
                                grid: {
                                    color: '#374151'
                                }
                            },
                            x: {
                                ticks: {
                                    color: '#D1D5DB'
                                },
                                grid: {
                                    color: '#374151'
                                }
                            }
                        }
                    }
                });
                    console.log('✅ PnL chart created successfully');
                    console.log('📊 Chart object:', this.charts.pnl);
                    console.log('📊 Chart data:', this.charts.pnl.data);
                    console.log('📊 Chart options:', this.charts.pnl.options);
                    
                    // Force a resize to ensure the chart renders properly
                    setTimeout(() => {
                        if (this.charts.pnl && this.charts.pnl.resize) {
                            this.charts.pnl.resize();
                            console.log('📊 Chart resized');
                        }
                    }, 100);
                } catch (error) {
                    console.error('❌ Error creating PnL chart:', error);
                    this.charts.pnl = null;
                }
            },
            
            setupTradeChart() {
                const ctx = document.getElementById('tradeChart');
                if (!ctx) return;
                
                this.charts.trades = new Chart(ctx, {
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
            
            // Update trade chart
            updateTradeChart() {
                if (!this.charts.trades) {
                    console.warn('⚠️ Trade chart not initialized, attempting to setup...');
                    this.setupTradeChart();
                    if (!this.charts.trades) {
                        console.error('❌ Failed to initialize Trade chart');
                        return;
                    }
                }
                
                const winning = this.dashboardTrades.filter(t => (t.pnl || 0) > 0).length;
                const losing = this.dashboardTrades.filter(t => (t.pnl || 0) < 0).length;
                const pending = this.dashboardTrades.filter(t => t.status === 'pending').length;
                
                this.charts.trades.data.datasets[0].data = [winning, losing, pending];
                this.charts.trades.update();
            },
            
            // Refresh all data
            async refreshData() {
                console.log('🔄 Manual refresh requested...');
                await this.forceRefreshDashboard();
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
            
            // Format date
            formatDate(dateString) {
                if (!dateString) return 'N/A';
                try {
                    // Parse the ISO string and format to MM/DD/YYYY HH:MM
                    const date = new Date(dateString);
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const day = String(date.getDate()).padStart(2, '0');
                    const year = date.getFullYear();
                    const hours = String(date.getHours()).padStart(2, '0');
                    const minutes = String(date.getMinutes()).padStart(2, '0');
                    
                    return `${month}/${day}/${year} ${hours}:${minutes}`;
                } catch (error) {
                    // Fallback to original string if parsing fails
                return dateString;
                }
            },
            
            // Format time
            formatTime(date) {
                return new Date(date).toLocaleTimeString();
            },
            
            // Format number with commas
            formatNumber(num) {
                if (!num || num === 0) return 'N/A';
                return num.toLocaleString();
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
                    return `$${marketCap.toLocaleString()}`;
                }
            },
            
            // Get price color based on stock data
            getPriceColor(stock) {
                if (stock.gap_percent > 5) return 'text-green-400';
                if (stock.gap_percent > 2) return 'text-yellow-400';
                return 'text-white';
            },
            
            // Get price change color
            getPriceChangeColor(changePercent) {
                if (changePercent > 0) return 'text-green-400';
                if (changePercent < 0) return 'text-red-400';
                return 'text-gray-400';
            },
            
            // Show sliding notification
            getPatternColor(patternType) {
                if (!patternType) return 'bg-gray-600 text-gray-300';
                
                switch (patternType.toLowerCase()) {
                    case 'runner':
                        return 'bg-green-600 text-white';
                    case 'fader':
                        return 'bg-red-600 text-white';
                    case 'neutral':
                        return 'bg-yellow-600 text-white';
                    default:
                        return 'bg-gray-600 text-gray-300';
                }
            },
            
            getPeriodDescription() {
                switch (this.selectedPeriod) {
                    case '180':
                        return '6 Months';
                    case '365':
                        return '1 Year';
                    case '730':
                        return '2 Years';
                    case '1095':
                        return '3 Years';
                    default:
                        return '3 Years';
                }
            },
            
            getPeriodDays() {
                return parseInt(this.selectedPeriod);
            },
            
            // Strategy-related functions
            getAvailableStrategies() {
                // Return the computed property for backward compatibility
                return this.availableStrategies;
            },
            
            getStrategyColor(strategyName) {
                const strategies = this.getAvailableStrategies();
                const strategy = strategies.find(s => s.name === strategyName);
                return strategy ? strategy.badgeClass : 'bg-gray-100 text-gray-800';
            },
            
            getDateRange() {
                if (!this.historicalData || this.historicalData.length === 0) {
                    return 'No data available';
                }
                
                // Sort the data by date to ensure correct order
                const sortedData = [...this.historicalData].sort((a, b) => {
                    const dateA = new Date(a.date);
                    const dateB = new Date(b.date);
                    return dateA - dateB;
                });
                
                const startDate = this.formatDate(sortedData[0].date);
                const endDate = this.formatDate(sortedData[sortedData.length - 1].date);
                
                return `${startDate} - ${endDate}`;
            },
            
            showNotification(message, type = 'info') {
                const notification = document.createElement('div');
                notification.className = `fixed top-0 left-0 right-0 z-50 transform -translate-y-full transition-transform duration-500 ease-in-out ${
                    type === 'warning' ? 'bg-gradient-to-r from-yellow-500 to-orange-500 text-white' :
                    type === 'error' ? 'bg-gradient-to-r from-red-500 to-pink-500 text-white' :
                    type === 'success' ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white' :
                    'bg-gradient-to-r from-blue-500 to-indigo-500 text-white'
                }`;
                
                notification.innerHTML = `
                    <div class="flex items-center justify-between px-6 py-4 shadow-lg">
                        <div class="flex items-center space-x-3">
                            <div class="flex-shrink-0">
                                ${type === 'warning' ? '<i class="fas fa-exclamation-triangle text-xl"></i>' :
                                  type === 'error' ? '<i class="fas fa-times-circle text-xl"></i>' :
                                  type === 'success' ? '<i class="fas fa-check-circle text-xl"></i>' :
                                  '<i class="fas fa-info-circle text-xl"></i>'}
                            </div>
                            <div>
                                <p class="font-semibold">${message}</p>
                                <p class="text-sm opacity-90">${new Date().toLocaleTimeString()}</p>
                            </div>
                        </div>
                        <button onclick="this.parentElement.parentElement.remove()" class="text-white hover:text-gray-200">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                `;
                
                document.body.appendChild(notification);
                
                // Slide in
                setTimeout(() => {
                    notification.classList.remove('-translate-y-full');
                }, 100);
                
                // Auto remove after 6 seconds
                setTimeout(() => {
                    notification.classList.add('-translate-y-full');
                    setTimeout(() => {
                        if (notification.parentElement) {
                            notification.remove();
                        }
                    }, 500);
                }, 6000);
            },
            
            // Start periodic updates
            startPeriodicUpdates() {
                console.log('⏰ Starting periodic updates at:', new Date().toLocaleTimeString());
                
                // Update gap-ups every 30 seconds
                setInterval(() => {
                    console.log('⏰ 30-second interval triggered at:', new Date().toLocaleTimeString());
                    this.loadGapUpsBackground();
                }, 30000);
                
                // Update bot status every 5 seconds when bot tab is active
                setInterval(() => {
                    if (this.activeTab === 'bot') {
                        this.loadBotStatus();
                    }
                }, 5000);
                
                // Auto-refresh dashboard data every 2 minutes
                setInterval(() => {
                    console.log('⏰ Periodic dashboard refresh...');
                    this.loadDashboardData();
                }, 120000); // 2 minutes
                
                // Auto-sync functionality removed - no longer using Alpaca
            },
            
            // Strategy settings management
            async saveStrategySettings() {
                try {
                    console.log('💾 Saving strategy settings...');
                    
                    // Validate all strategy parameters before saving
                    const validationErrors = [];
                    
                    this.availableStrategies.forEach((strategy, index) => {
                        const strategyName = strategy.name;
                        
                        // Check for empty or invalid values
                        if (!strategy.minGap || strategy.minGap === '' || isNaN(strategy.minGap)) {
                            validationErrors.push(`${strategyName}: Min Gap % is required and must be a number`);
                        }
                        
                        if (!strategy.target || strategy.target === '' || isNaN(strategy.target)) {
                            validationErrors.push(`${strategyName}: Target is required and must be a number`);
                        }
                        
                        if (!strategy.stopLoss || strategy.stopLoss === '' || isNaN(strategy.stopLoss)) {
                            validationErrors.push(`${strategyName}: Stop Loss is required and must be a number`);
                        }
                        
                        // Check for reasonable value ranges
                        if (strategy.minGap < 0 || strategy.minGap > 200) {
                            validationErrors.push(`${strategyName}: Min Gap % must be between 0-200%`);
                        }
                        
                        if (strategy.target < 0 || strategy.target > 200) {
                            validationErrors.push(`${strategyName}: Target must be between 0-200%`);
                        }
                        
                        if (strategy.stopLoss < 0 || strategy.stopLoss > 100) {
                            validationErrors.push(`${strategyName}: Stop Loss must be between 0-100%`);
                        }
                    });
                    
                    // If there are validation errors, show them and stop saving
                    if (validationErrors.length > 0) {
                        const errorMessage = 'Please fix the following errors:\n' + validationErrors.join('\n');
                        this.showNotification(errorMessage, 'error');
                        console.error('❌ Strategy validation failed:', validationErrors);
                        return;
                    }
                    
                    // Save to localStorage for persistence
                    localStorage.setItem('strategySettings', JSON.stringify(this.availableStrategies));
                    
                    // Send to backend API to update bot configuration
                    const response = await axios.post('/api/bot/update-strategies', {
                        strategies: this.availableStrategies
                    });
                    
                    if (response.data.success) {
                        this.showNotification('Strategy settings saved successfully!', 'success');
                        console.log('✅ Strategy settings saved');
                    } else {
                        this.showNotification('Failed to save strategy settings', 'error');
                    }
                    } catch (error) {
                    console.error('❌ Error saving strategy settings:', error);
                    this.showNotification('Error saving strategy settings', 'error');
                }
            },
            
            loadStrategySettings() {
                try {
                    // Load saved settings from localStorage
                    const savedSettings = localStorage.getItem('strategySettings');
                    if (savedSettings) {
                        const parsedSettings = JSON.parse(savedSettings);
                        console.log('📋 Loading saved strategy settings:', parsedSettings);
                        
                        // Check if the saved settings contain old string values
                        const hasOldStringValues = parsedSettings.some(strategy => 
                            typeof strategy.target === 'string' || 
                            typeof strategy.stopLoss === 'string' ||
                            strategy.target?.includes('%') ||
                            strategy.stopLoss?.includes('%')
                        );
                        
                        if (hasOldStringValues) {
                            console.warn('⚠️ Found old string values in saved settings, clearing...');
                            localStorage.removeItem('strategySettings');
                            this.showNotification('Old settings format detected and cleared. Using default values.', 'warning');
                            return;
                        }
                        
                        // Update the computed property with saved settings
                        // Note: We need to update the window.STRATEGY_CONFIG for this to work
                        if (window.STRATEGY_CONFIG) {
                            window.STRATEGY_CONFIG.strategies = parsedSettings;
                        }
                    }
                    } catch (error) {
                    console.error('❌ Error loading strategy settings:', error);
                }
            },
            

            
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
            
            // Unsubscribe functionality
            async unsubscribeSelectedStocks() {
                if (this.selectedStocks.length === 0) {
                    this.showNotification('Please select stocks to unsubscribe', 'warning');
                    return;
                }
                
                try {
                    console.log('🔄 Unsubscribing from stocks:', this.selectedStocks);
                    this.loading.unsubscribe = true;
                    
                    const response = await axios.post('/api/bot/unsubscribe-stocks', {
                        stocks: this.selectedStocks
                    });
                    
                    if (response.data.success) {
                        this.showNotification(`✅ ${response.data.message}`, 'success');
                        console.log('✅ Unsubscribed successfully:', response.data.data);
                        
                        // Clear selection and reload bot status
                        this.selectedStocks = [];
                        await this.loadBotStatus();
                    } else {
                        // Handle position check error
                        if (response.data.error === 'Cannot unsubscribe from stocks with active positions') {
                            const stocksWithPositions = response.data.data?.stocks_with_positions || [];
                            const stockList = stocksWithPositions.map(s => `${s.ticker} (${s.quantity} ${s.side})`).join(', ');
                            this.showNotification(`⚠️ Cannot unsubscribe: ${stockList} have active positions. Please close positions first.`, 'warning');
                            console.warn('⚠️ Stocks with active positions:', stocksWithPositions);
                        } else {
                            this.showNotification(`❌ Failed to unsubscribe: ${response.data.error}`, 'error');
                            console.error('❌ Unsubscribe failed:', response.data.error);
                        }
                    }
                } catch (error) {
                    console.error('❌ Error unsubscribing from stocks:', error);
                    this.showNotification('❌ Error unsubscribing from stocks', 'error');
                } finally {
                    this.loading.unsubscribe = false;
                }
            },
            
            async unsubscribeSingleStock(ticker) {
                try {
                    console.log('🔄 Unsubscribing from single stock:', ticker);
                    this.loading.unsubscribe = true;
                    
                    const response = await axios.post('/api/bot/unsubscribe-stocks', {
                        stocks: [ticker]
                    });
                    
                    if (response.data.success) {
                        this.showNotification(`✅ Unsubscribed from ${ticker}`, 'success');
                        console.log('✅ Single stock unsubscribed successfully:', response.data.data);
                        
                        // Reload bot status
                        await this.loadBotStatus();
                    } else {
                        // Handle position check error
                        if (response.data.error === 'Cannot unsubscribe from stocks with active positions') {
                            const stocksWithPositions = response.data.data?.stocks_with_positions || [];
                            const stockList = stocksWithPositions.map(s => `${s.ticker} (${s.quantity} ${s.side})`).join(', ');
                            this.showNotification(`⚠️ Cannot unsubscribe from ${ticker}: Has active position. Please close position first.`, 'warning');
                            console.warn('⚠️ Stock with active position:', stocksWithPositions);
                        } else {
                            this.showNotification(`❌ Failed to unsubscribe from ${ticker}: ${response.data.error}`, 'error');
                            console.error('❌ Single stock unsubscribe failed:', response.data.error);
                        }
                    }
                } catch (error) {
                    console.error('❌ Error unsubscribing from single stock:', error);
                    this.showNotification('❌ Error unsubscribing from stock', 'error');
                } finally {
                    this.loading.unsubscribe = false;
                }
            },
            
            selectAllStocks() {
                this.selectedStocks = this.botStatus.subscribedStocks.map(stock => stock.ticker);
                console.log('✅ All stocks selected:', this.selectedStocks);
            },
            
            clearStockSelection() {
                this.selectedStocks = [];
                console.log('✅ Stock selection cleared');
            },
            
            toggleAllStocks() {
                if (this.allStocksSelected) {
                    this.clearStockSelection();
                } else {
                    this.selectAllStocks();
                }
            },
            
            hasActivePosition(ticker) {
                // Check if the stock has an active position in the bot status
                return this.botStatus.positions.some(position => position.ticker === ticker);
            },
            
            // Trade History Ticker Search Methods
            onTradeHistoryTickerChange() {
                // Debounce the search to avoid too many API calls
                clearTimeout(this.tickerSearchTimeout);
                this.tickerSearchTimeout = setTimeout(() => {
                    this.loadTradeHistory();
                }, 500);
            },
            
            clearTradeHistoryTicker() {
                this.tradeHistoryTicker = '';
                this.loadTradeHistory();
            },
            
            // Strategy Parameter Validation
            validateStrategyParameter(strategy, parameter) {
                const value = strategy[parameter];
                
                // Ensure value is a number and not null/undefined
                if (isNaN(value) || value === null || value === undefined || value === '') {
                    // Set default values based on parameter
                    if (parameter === 'minGap') {
                        strategy[parameter] = 25; // Default min gap
                    } else if (parameter === 'target') {
                        strategy[parameter] = strategy.minGap || 25; // Default to min gap
                    } else if (parameter === 'stopLoss') {
                        strategy[parameter] = 15; // Default stop loss
                    }
                    this.showNotification(`Invalid ${parameter} value. Set to default.`, 'warning');
                    return;
                }
                
                // Validate ranges
                if (parameter === 'minGap') {
                    if (value < 0 || value > 200) {
                        strategy[parameter] = Math.max(0, Math.min(200, value));
                        this.showNotification(`Min Gap % must be between 0-200%. Set to ${strategy[parameter]}.`, 'warning');
                    }
                    // Auto-update target to match min gap if target is empty or 0
                    if (!strategy.target || strategy.target === 0) {
                        strategy.target = value;
                    }
                } else if (parameter === 'target') {
                    if (value < 0 || value > 200) {
                        strategy[parameter] = Math.max(0, Math.min(200, value));
                        this.showNotification(`Target must be between 0-200%. Set to ${strategy[parameter]}.`, 'warning');
                    }
                } else if (parameter === 'stopLoss') {
                    if (value < 0 || value > 100) {
                        strategy[parameter] = Math.max(0, Math.min(100, value));
                        this.showNotification(`Stop Loss must be between 0-100%. Set to ${strategy[parameter]}.`, 'warning');
                    }
                }
            },
            
            // Initialize strategy parameters with proper defaults
            initializeStrategyParameters() {
                this.availableStrategies.forEach(strategy => {
                    // Ensure all parameters are numbers with proper defaults
                    strategy.minGap = Number(strategy.minGap) || 25;
                    strategy.target = Number(strategy.target) || strategy.minGap; // Default to min gap
                    strategy.stopLoss = Number(strategy.stopLoss) || 15;
                    
                    // Validate initial values
                    this.validateStrategyParameter(strategy, 'minGap');
                    this.validateStrategyParameter(strategy, 'target');
                    this.validateStrategyParameter(strategy, 'stopLoss');
                });
            },
            
            // Save individual strategy
            async saveIndividualStrategy(strategy) {
                try {
                    console.log(`💾 Saving individual strategy: ${strategy.name}`);
                    
                    // Validate the specific strategy
                    const validationErrors = [];
                    const strategyName = strategy.name;
                    
                    // Check for empty or invalid values
                    if (!strategy.minGap || strategy.minGap === '' || isNaN(strategy.minGap)) {
                        validationErrors.push(`Min Gap % is required and must be a number`);
                    }
                    
                    if (!strategy.target || strategy.target === '' || isNaN(strategy.target)) {
                        validationErrors.push(`Target is required and must be a number`);
                    }
                    
                    if (!strategy.stopLoss || strategy.stopLoss === '' || isNaN(strategy.stopLoss)) {
                        validationErrors.push(`Stop Loss is required and must be a number`);
                    }
                    
                    // Check for reasonable value ranges
                    if (strategy.minGap < 0 || strategy.minGap > 200) {
                        validationErrors.push(`Min Gap % must be between 0-200%`);
                    }
                    
                    if (strategy.target < 0 || strategy.target > 200) {
                        validationErrors.push(`Target must be between 0-200%`);
                    }
                    
                    if (strategy.stopLoss < 0 || strategy.stopLoss > 100) {
                        validationErrors.push(`Stop Loss must be between 0-100%`);
                    }
                    
                    // If there are validation errors, show them and stop saving
                    if (validationErrors.length > 0) {
                        const errorMessage = `${strategyName} - Please fix the following errors:\n` + validationErrors.join('\n');
                        this.showNotification(errorMessage, 'error');
                        console.error(`❌ ${strategyName} validation failed:`, validationErrors);
                        return;
                    }
                    
                    // Save to localStorage for persistence
                    localStorage.setItem('strategySettings', JSON.stringify(this.availableStrategies));
                    
                    // Send to backend API to update bot configuration
                    const response = await axios.post('/api/bot/update-strategies', {
                        strategies: this.availableStrategies
                    });
                    
                    if (response.data.success) {
                        this.showNotification(`${strategyName} settings saved successfully!`, 'success');
                        console.log(`✅ ${strategyName} settings saved`);
                    } else {
                        this.showNotification(`Failed to save ${strategyName} settings`, 'error');
                    }
                } catch (error) {
                    console.error(`❌ Error saving ${strategy.name} settings:`, error);
                    this.showNotification(`Error saving ${strategy.name} settings`, 'error');
                }
            },
            
            // View current settings
            viewCurrentSettings() {
                console.log('📋 Current strategy settings:');
                
                // Ensure all values are properly formatted as numbers
                const settingsSummary = this.availableStrategies.map(strategy => {
                    // Ensure values are numbers and format them properly
                    const minGap = Number(strategy.minGap) || 0;
                    const target = Number(strategy.target) || 0;
                    const stopLoss = Number(strategy.stopLoss) || 0;
                    
                    return `${strategy.name} Strategy:
  • Min Gap %: ${minGap}%
  • Target: ${target}%
  • Stop Loss: ${stopLoss}%
  • Direction: ${strategy.direction}
  • Availability: ${strategy.availability}`;
                }).join('\n\n');
                
                // Create a modal or alert to show the settings
                const message = `Current Strategy Settings:\n\n${settingsSummary}`;
                
                // Use browser alert for now (can be enhanced with a modal later)
                alert(message);
                
                // Also log to console for debugging
                console.log('📊 Strategy Settings Summary:', this.availableStrategies);
            },
            
            // Clear old strategy settings to fix the display issue
            clearOldStrategySettings() {
                try {
                    localStorage.removeItem('strategySettings');
                    console.log('🗑️ Cleared old strategy settings from localStorage');
                    this.showNotification('Old settings cleared. Please refresh the page.', 'info');
                } catch (error) {
                    console.error('❌ Error clearing old settings:', error);
                }
            },
            
            async loadStrategiesFromBackend() {
                try {
                    console.log('🔄 Loading strategies from backend...');
                    this.loading.strategies = true;
                    
                    const response = await axios.get('/api/strategies/get');
                    
                    if (response.data.success) {
                        this.strategiesLoaded = response.data.strategies;
                        console.log('✅ Strategies loaded from backend:', this.strategiesLoaded);
                    } else {
                        console.warn('⚠️ Failed to load strategies from backend, using fallback');
                        this.strategiesLoaded = null;
                    }
                } catch (error) {
                    console.warn('⚠️ Error loading strategies from backend, using fallback:', error);
                    this.strategiesLoaded = null;
                } finally {
                    this.loading.strategies = false;
                }
            },
            
            async checkBackendConnectivity() {
                console.log('🔍 Checking backend connectivity...');
                const maxRetries = 5;
                const retryDelay = 2000; // 2 seconds
                
                for (let attempt = 1; attempt <= maxRetries; attempt++) {
                    try {
                        console.log(`🔍 Backend connectivity attempt ${attempt}/${maxRetries}...`);
                        const response = await fetch('http://localhost:5000/api/health', {
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
            
            async forceRefreshDashboard() {
                console.log('🔄 Force refreshing dashboard data...');
                this.loading.stats = true;
                this.loading.gapUps = true;
                this.loading.dashboardTrades = true;
                this.loading.dashboardPnL = true;
                
                try {
                    // Clear existing data
                    this.stats = {
                        totalTrades: 0,
                        winRate: 0,
                        totalPnl: 0,
                        pnl: 0,
                        activePositions: 0,
                        gapUps: 0
                    };
                    this.gapUps = [];
                    this.trades = [];
                    
                    // Reload all data
                    await this.loadDashboardData();
                    await this.loadBotStatus();
                    
                    // Update charts
                    this.$nextTick(() => {
                        this.updatePnlChart();
                        this.updateTradeChart();
                    });
                    
                    this.showNotification('Dashboard refreshed successfully', 'success');
                } catch (error) {
                    console.error('❌ Error force refreshing dashboard:', error);
                    this.showNotification('Failed to refresh dashboard: ' + error.message, 'error');
                } finally {
                    this.loading.stats = false;
                    this.loading.gapUps = false;
                    this.loading.dashboardTrades = false;
                    this.loading.dashboardPnL = false;
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
                // Show a loading overlay or indicator
                this.showNotification('Loading dashboard data...', 'info');
                
                // Update loading states for all components
                this.loading.stats = true;
                this.loading.gapUps = true;
                this.loading.bot = true;
                this.loading.dashboardTrades = true;
                this.loading.dashboardPnL = true;
            },
            
            hideOverallLoadingState() {
                // Hide loading indicators after a delay
                setTimeout(() => {
                    this.loading.stats = false;
                    this.loading.gapUps = false;
                    this.loading.bot = false;
                    this.loading.dashboardTrades = false;
                    this.loading.dashboardPnL = false;
                }, 2000);
            },
            
            async waitForBackendReady() {
                console.log('⏳ Waiting for backend to be fully ready...');
                const maxAttempts = 10;
                const delay = 1000; // 1 second between attempts
                
                for (let attempt = 1; attempt <= maxAttempts; attempt++) {
                    try {
                        console.log(`🔍 Backend readiness check ${attempt}/${maxAttempts}...`);
                        const response = await fetch('http://localhost:5000/api/health', {
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
            }
        }
    });
    
    app.mount('#app');
    console.log('✅ Trading Advisor Dashboard initialized successfully'); 