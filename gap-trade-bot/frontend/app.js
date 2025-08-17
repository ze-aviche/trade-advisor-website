// Gap Up Trade Bot Dashboard - Vue.js Application
// Rebuilt from scratch to work with DAS trades database

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
                scheduledSync: false,
                unsubscribe: false,
                importDAS: false,
                panicExit: false,
                saveGapUpConfig: false,
                dasConnection: false,
                dasReconnect: false,
                botToggle: false
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
                    monitoring: false,
                    subscribed_stocks: [],
                    positions: [],
                    active_positions: 0,
                    last_update: null,
                    profit_target_pct: 5.0,
                    stop_loss_pct: 2.5,
                    monitor_interval: 5,
                    das_connected: false,
                    internal_running_state: false,
                    internal_monitoring_state: false
                },
                
                // Bot configuration
                botConfig: {
                    profit_target_pct: 5.0,
                    stop_loss_pct: 2.5,
                    monitor_interval: 5
                },
                
                // Gap-up configuration
                gapUpConfig: {
                    min_percentage: 25.0
                },
                
                // Bot positions
                botPositions: [],
                
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
            
            // Dashboard chart data - Direct from database
                dashboardTrades: [],
                dashboardPnL: [],
                
                // Stock selection for unsubscribe
                selectedStocks: []
            }
        },
        
        computed: {
            allStocksSelected() {
                return this.botStatus.subscribed_stocks.length > 0 && 
                       this.selectedStocks.length === this.botStatus.subscribed_stocks.length;
            }
        },
        
        mounted() {
            console.log('🎯 Vue.js app mounted successfully');
        
        // Force close any stuck modals immediately
        this.forceCloseStuckModals();
        
            this.checkAuth();
            
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
            } else if (tabName === 'historical') {
                console.log('📈 Historical Data tab selected - ready for analysis...');
                // Historical tab is ready for user input, no auto-loading needed
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
                        this.loadStats().then(() => console.log('✅ Stats loaded')),
                        this.loadGapUpConfig().then(() => console.log('✅ Gap-up config loaded')),
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
                    
                    if (response.data.success) {
                        this.botStatus = {
                            running: response.data.data.running || false,
                            monitoring: response.data.data.monitoring || false,
                            subscribed_stocks: response.data.data.subscribed_stocks || [],
                            positions: response.data.data.positions || [],
                            active_positions: response.data.data.active_positions || 0,
                            last_update: response.data.data.last_update || null,
                            profit_target_pct: response.data.data.profit_target_pct || 5.0,
                            stop_loss_pct: response.data.data.stop_loss_pct || 2.5,
                            monitor_interval: response.data.data.monitor_interval || 5,
                            das_connected: response.data.data.das_connected || false,
                            internal_running_state: response.data.data.internal_running_state || false,
                            internal_monitoring_state: response.data.data.internal_monitoring_state || false
                        };
                        
                        // Update bot config to match current status
                        this.botConfig = {
                            profit_target_pct: this.botStatus.profit_target_pct,
                            stop_loss_pct: this.botStatus.stop_loss_pct,
                            monitor_interval: this.botStatus.monitor_interval
                        };
                        
                        console.log('✅ Bot status loaded:', this.botStatus);
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
            
            async loadBotPositions() {
                try {
                    console.log('📊 Loading bot positions...');
                    const response = await axios.get('/api/bot/positions');
                    
                    if (response.data.success) {
                        this.botPositions = response.data.data.positions || [];
                        console.log('✅ Bot positions loaded:', this.botPositions.length);
                    } else {
                        console.error('❌ Bot positions error:', response.data.error);
                        this.botPositions = [];
                    }
                } catch (error) {
                    console.error('❌ Error loading bot positions:', error);
                    this.botPositions = [];
                }
            },
            
            async loadBotConfig() {
                try {
                    console.log('⚙️ Loading bot configuration...');
                    const response = await axios.get('/api/bot/config');
                    
                    if (response.data.success) {
                        this.botConfig = {
                            profit_target_pct: response.data.data.profit_target_pct || 5.0,
                            stop_loss_pct: response.data.data.stop_loss_pct || 2.5,
                            monitor_interval: response.data.data.monitor_interval || 5
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
                    const response = await axios.post('/api/bot/config', this.botConfig);
                    
                    if (response.data.success) {
                        console.log('✅ Bot config updated successfully');
                        this.showNotification('Bot configuration updated successfully', 'success');
                        await this.loadBotStatus(); // Refresh bot status
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
                        await this.loadBotPositions(); // Refresh positions
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
                    await this.loadBotPositions();
                    this.showNotification('Bot positions refreshed', 'success');
                } catch (error) {
                    console.error('❌ Error refreshing bot positions:', error);
                    this.showNotification('Failed to refresh bot positions', 'error');
                }
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
            
            async loadStats() {
            console.log('📊 Loading stats from DAS trades database...');
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
                        // Load trades directly from database
                        this.trades = data.data.trades || [];
                        
                        // Update stats from database summary
                        this.stats = {
                            totalTrades: data.data.summary.total_trades || 0,
                            winRate: data.data.summary.win_rate || 0,
                            totalPnl: data.data.summary.total_pnl || 0,
                            pnl: data.data.summary.total_pnl || 0,
                            activePositions: this.trades.filter(t => t.status === 'filled').length,
                            gapUps: this.gapUps.length
                        };
                            
                        console.log('✅ Stats loaded successfully from database:', this.stats);
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
            
            async loadGapUpConfig() {
                try {
                    console.log('⚙️ Loading gap-up configuration...');
                    const response = await fetch('http://localhost:5000/api/gap-ups/config');
                    const data = await response.json();
                    
                    if (data.success) {
                        this.gapUpConfig = data.data;
                        console.log('✅ Gap-up configuration loaded:', this.gapUpConfig);
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
                    const response = await fetch('http://localhost:5000/api/gap-ups/config', {
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
            
            async loadDashboardTrades() {
                try {
                    // Use date range instead of period
                    const fromDate = this.dashboardTradeFromDate || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
                    const toDate = this.dashboardTradeToDate || new Date().toISOString().split('T')[0];
                    
                    console.log('🔄 Loading dashboard trades for date range:', fromDate, 'to', toDate);
                    this.loading.dashboardTrades = true;
                
                const response = await fetch(`http://localhost:5000/api/trades?start_date=${fromDate}&end_date=${toDate}`);
                    const data = await response.json();
                    
                    if (data.success) {
                    // Load trades directly from database
                    this.dashboardTrades = data.data.trades || [];
                    console.log('✅ Dashboard trades loaded from database:', this.dashboardTrades.length, 'trades');
                    
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
                
                const response = await fetch(`http://localhost:5000/api/trades?start_date=${fromDate}&end_date=${toDate}`);
                    const data = await response.json();
                    
                    if (data.success) {
                    // Load PnL data directly from database
                    this.dashboardPnL = data.data.trades || [];
                    console.log('✅ Dashboard P&L loaded from database:', this.dashboardPnL.length, 'trades');
                    
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
                
                // Load scheduled sync status when trade history tab is accessed
                await this.loadScheduledSyncStatus();
                    
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
                    // Transform the data to match the expected format from database
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
                    
                    console.log(`📊 Loaded ${this.trades.length} trades from database${this.tradeHistoryTicker ? ` for ${this.tradeHistoryTicker}` : ''}`);
                    
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
            
        // Chart methods
            updatePnlChart() {
            console.log('🔄 Updating PnL chart from database...');
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
                
            // Create new chart with data directly from database
            const ctx = document.getElementById('pnlChart');
            if (!ctx) {
                console.log('⚠️ PnL chart canvas not found - likely no trades yet');
                return;
            }
            
            // Calculate cumulative P&L from database trades
                const pnlData = [];
                const labels = [];
                let cumulativePnl = 0;
                
                // Sort trades by timestamp
                const sortedTrades = [...this.dashboardPnL].sort((a, b) => 
                new Date(a.trade_date + ' ' + a.trade_time) - new Date(b.trade_date + ' ' + b.trade_time)
                );
                
            console.log('📊 Sorted trades from database:', sortedTrades.length);
                
                sortedTrades.forEach((trade, index) => {
                    const tradePnl = trade.pnl || 0;
                    cumulativePnl += tradePnl;
                    pnlData.push(cumulativePnl);
                labels.push(new Date(trade.trade_date + ' ' + trade.trade_time).toLocaleDateString());
                console.log(`📈 Trade ${index + 1}: ${trade.symbol} - PnL: $${tradePnl}, Cumulative: $${cumulativePnl}`);
                });
                
                // If no trades, use default data
                if (pnlData.length === 0) {
                    pnlData.push(0);
                    labels.push('No trades');
                console.log('⚠️ No trades found in database, using default data');
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
                console.log('✅ PnL chart created successfully from database data');
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
            if (!ctx) {
                console.log('⚠️ Trade chart canvas not found during setup');
                return;
            }
                
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
            
        // Update trade chart with database data
            updateTradeChart() {
            const ctx = document.getElementById('tradeChart');
            if (!ctx) {
                console.log('⚠️ Trade chart canvas not found - likely no trades yet');
                return;
            }
            
                if (!this.charts.trades) {
                    console.warn('⚠️ Trade chart not initialized, attempting to setup...');
                    this.setupTradeChart();
                    if (!this.charts.trades) {
                        console.error('❌ Failed to initialize Trade chart');
                        return;
                    }
                }
                
            // Calculate from database trades
                const winning = this.dashboardTrades.filter(t => (t.pnl || 0) > 0).length;
                const losing = this.dashboardTrades.filter(t => (t.pnl || 0) < 0).length;
                const pending = this.dashboardTrades.filter(t => t.status === 'pending').length;
                
                this.charts.trades.data.datasets[0].data = [winning, losing, pending];
                this.charts.trades.update();
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
        
        // Scheduled Sync Methods
        async loadScheduledSyncStatus() {
            try {
                console.log('🔄 Loading scheduled sync status...');
                const response = await axios.get('/api/scheduled-sync/status');
                
                if (response.data.success) {
                    this.scheduledSyncStatus = response.data.data;
                    console.log('✅ Scheduled sync status loaded:', this.scheduledSyncStatus);
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
        
        // Format number with commas
        formatNumber(num) {
            if (!num || num === 0) return 'N/A';
            return num.toLocaleString();
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
            // Placeholder - implement if needed
            console.log('⏰ Starting periodic bot updates...');
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
                
                // Use the correct endpoint format: /api/historical-data/<ticker>
                const response = await fetch(`http://localhost:5000/api/historical-data/${this.historicalTicker.toUpperCase()}?period=${this.selectedPeriod}`);
                const data = await response.json();
                
                if (data.success) {
                    this.historicalData = data.data || [];
                    console.log(`✅ Loaded ${this.historicalData.length} days of historical data for ${this.historicalTicker}`);
                    this.showNotification(`Loaded ${this.historicalData.length} days of historical data`, 'success');
                    
                    // Debug the data structure
                    this.debugHistoricalData();
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
            if (days === 180) return '6 Months';
            if (days === 365) return '1 Year';
            if (days === 730) return '2 Years';
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
                return gapPercent >= 25;
            }).length;
            console.log(`📊 Gap-up days count: ${count} (from ${this.historicalData.length} total days)`);
            return count;
        },
        
        getRunnerDaysCount() {
            const count = this.historicalData.filter(day => {
                const gapPercent = parseFloat(day['gap up % at open']) || 0;
                const closePercent = parseFloat(day['closing percent']) || 0;
                return gapPercent >= 25 && closePercent >= 25;
            }).length;
            console.log(`🏃 Runner days count: ${count}`);
            return count;
        },
        
        getFaderDaysCount() {
            const count = this.historicalData.filter(day => {
                const gapPercent = parseFloat(day['gap up % at open']) || 0;
                const closePercent = parseFloat(day['closing percent']) || 0;
                return gapPercent >= 25 && closePercent < 25;
            }).length;
            console.log(`📉 Fader days count: ${count}`);
            return count;
        },
        
        getAverageGapPercent() {
            const gapUpDays = this.historicalData.filter(day => {
                const gapPercent = parseFloat(day['gap up % at open']) || 0;
                return gapPercent >= 25;
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
            if (!this.tradeHistoryTicker.trim()) {
                this.showNotification('Please enter a ticker symbol', 'warning');
                return;
            }
            
            // Filter out trades for the specified ticker
            this.tradeHistory = this.tradeHistory.filter(trade => 
                trade.symbol !== this.tradeHistoryTicker.toUpperCase()
            );
            
            this.showNotification(`Cleared trade history for ${this.tradeHistoryTicker.toUpperCase()}`, 'success');
            this.tradeHistoryTicker = '';
        },
        
        // Helper method to handle trade history ticker input changes
        onTradeHistoryTickerChange() {
            // Auto-load trade history when ticker is entered
            if (this.tradeHistoryTicker.trim()) {
                this.loadTradeHistory();
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
        
        // Helper method to refresh all bot components
        async refreshAllBotComponents() {
            try {
                this.loading.bot = true;
                await Promise.all([
                    this.loadBotStatus(),
                    this.loadBotPositions(),
                    this.loadBotConfig(),
                    this.loadScheduledSyncStatus()
                ]);
                this.showNotification('All bot components refreshed successfully', 'success');
            } catch (error) {
                console.error('Error refreshing bot components:', error);
                this.showNotification('Error refreshing bot components', 'error');
            } finally {
                    this.loading.bot = false;
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
                    await this.loadBotStatus(); // Refresh status
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
                const response = await fetch('http://localhost:5000/api/cache/invalidate-gap-ups', {
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
                
                const response = await fetch('http://localhost:5000/api/bot/panic-exit', {
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
                    
                    // Refresh bot status and positions after panic exit
                    await this.loadBotStatus();
                    await this.loadBotPositions();
                    
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
        }
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
