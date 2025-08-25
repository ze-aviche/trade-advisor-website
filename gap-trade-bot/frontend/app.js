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
                trades: [],
                
                // UI state
                activeTab: localStorage.getItem('activeTab') || 'about',
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
                    // Entry Bot loading states
                    submitEntry: false,
                    refreshTracking: false,
                    refreshPositions: false,
                    refreshLogs: false,
                    toggleEntryBot: false,
                    dailyPnl: false,
                    backtest: false,
                    runBacktest: false,
                    equityChart: false
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
                    monitor_interval: 5
                },
                isEditingBotConfig: false, // Track if user is actively editing bot config
                
                // Gap-up configuration
                gapUpConfig: {
                    min_percentage: 25.0
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
                tradeHistoryPeriod: '365', // Default to 1 year to include more historical trades
                tradeHistoryTicker: '', // Ticker search filter
                
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
            
            // Entry Bot Data
            entryBotStatus: {
                internal_running_state: false,
                positions_entered: 0,
                entry_success_rate: 0,
                active_positions_count: 0
            },
            
            // Entry Form Data
            entryForm: {
                symbol: '',
                totalVolume: '',
                dollarVolume: '',
                entryTime: ''
            },
            
            // Tracking Symbols
            trackingSymbols: [],
            
            // Active Positions
            activePositions: [],
            
            // Debug Logs
            debugLogs: [],
            
                            // Continuous tracking interval
                trackingInterval: null,
            

            
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
                
                // Daily P&L chart data
                dailyPnlData: [],
                dailyPnlChart: null,
                dailyPnlChartType: 'bar', // Default to bar chart

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
        
        beforeDestroy() {
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
            async onTabChange(tabName) {
                console.log(`🔄 Tab changed to: ${tabName}`);
                console.log(`🔍 Current activeTab value: ${this.activeTab}`);
                console.log(`🔍 Previous activeTab value: ${this.activeTab}`);
                
                // Update the activeTab value
                this.activeTab = tabName;
                
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
                } else if (tabName === 'bot') {
                    console.log('🤖 Bot tab selected - loading bot status with real-time updates...');
                    this.stopPositionHistoryUpdates(); // Stop position updates when leaving positions tab
                    this.stopContinuousTracking(); // Stop continuous tracking when leaving entry bot tab
                    this.loadBotStatusWithRealTime();
                } else if (tabName === 'trades') {
                    console.log('📊 Trade History tab selected - loading trade history...');
                    this.stopPositionHistoryUpdates(); // Stop position updates when leaving positions tab
                    this.stopContinuousTracking(); // Stop continuous tracking when leaving entry bot tab
                    this.loadTradeHistory();
                } else if (tabName === 'positions') {
                    console.log('📈 Positions History tab selected - loading positions history...');
                    console.log('🔍 This is the positions tab handler - starting execution...');
                    
                    try {
                        // Stop continuous tracking when leaving entry bot tab
                        this.stopContinuousTracking();
                        
                        // Load position sync status first
                        console.log('🔄 Loading position sync status...');
                        await this.loadPositionSyncStatus();
                        console.log('✅ Position sync status loaded');
                        
                        this.loadPositionsHistory();
                        console.log('✅ Positions history loaded');
                        
                        // Start auto-updates for position history
                        console.log('🚀 Starting position history auto-updates for positions tab...');
                        console.log('🔍 About to call startPositionHistoryUpdates...');
                        
                        // Check if function exists before calling
                        if (typeof this.startPositionHistoryUpdates === 'function') {
                            console.log('✅ Function exists, calling startPositionHistoryUpdates...');
                            try {
                                this.startPositionHistoryUpdates();
                                console.log('✅ startPositionHistoryUpdates() called successfully');
                            } catch (error) {
                                console.error('❌ Error in startPositionHistoryUpdates:', error);
                                console.error('❌ Error stack:', error.stack);
                            }
                        } else {
                            console.error('❌ startPositionHistoryUpdates is not a function!');
                            console.error('❌ Type:', typeof this.startPositionHistoryUpdates);
                            console.error('❌ Value:', this.startPositionHistoryUpdates);
                        }
                        
                        // Stop bot real-time updates when on positions tab to avoid conflicts
                        console.log('🛑 Stopping bot real-time updates to avoid conflicts...');
                        this.stopRealTimeUpdates();
                        
                    } catch (error) {
                        console.error('❌ Error in positions tab initialization:', error);
                        console.error('❌ Error stack:', error.stack);
                    }
                } else if (tabName === 'gap-ups') {
                    console.log('📈 Gap-Ups tab selected - loading gap-up stocks...');
                    this.stopPositionHistoryUpdates(); // Stop position updates when leaving positions tab
                    this.stopContinuousTracking(); // Stop continuous tracking when leaving entry bot tab
                    this.loadGapUps();
                } else if (tabName === 'entry-bot') {
                    console.log('🤖 Entry Bot tab selected - loading entry bot status...');
                    this.stopPositionHistoryUpdates(); // Stop position updates when leaving positions tab
                    this.loadEntryBotStatus();
                    this.updateTrackingStatus();
                    this.updateActivePositions();
                    this.updateDebugLogs();
                    // Start continuous tracking every 1 second
                    this.startContinuousTracking();
                } else if (tabName === 'historical') {
                    console.log('📈 Historical Data tab selected - ready for analysis...');
                    this.stopPositionHistoryUpdates(); // Stop position updates when leaving positions tab
                    this.stopContinuousTracking(); // Stop continuous tracking when leaving entry bot tab
                    // Historical tab is ready for user input, no auto-loading needed
                } else if (tabName === 'stats') {
                    console.log('📊 Stats tab selected - loading statistics...');
                    this.stopPositionHistoryUpdates(); // Stop position updates when leaving positions tab
                    this.stopContinuousTracking(); // Stop continuous tracking when leaving entry bot tab
                    this.loadStats();
                    this.loadDailyPnlData();
                } else if (tabName === 'backtest') {
                    console.log('🧪 Backtest tab selected - loading backtest data...');
                    this.stopPositionHistoryUpdates(); // Stop position updates when leaving positions tab
                    this.stopContinuousTracking(); // Stop continuous tracking when leaving entry bot tab
                    this.loadBacktestData();
                } else if (tabName === 'ai-chat') {
                    console.log('🤖 AI Chat tab selected - ready for chat...');
                    this.stopPositionHistoryUpdates(); // Stop position updates when leaving positions tab
                    this.stopContinuousTracking(); // Stop continuous tracking when leaving entry bot tab
                    // AI chat tab is ready for user interaction
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
                    // Only update if we're on the positions tab
                    if (this.activeTab === 'positions') {
                        console.log('📈 Active tab is positions, loading position history...');
                        await this.loadPositionsHistory();
                        this.positionHistoryUpdates.lastUpdate = new Date();
                        console.log('🔄 Position history auto-update completed:', this.positionHistoryUpdates.lastUpdate);
                    } else {
                        console.log('⏸️ Not on positions tab, skipping update');
                    }
                }, this.positionHistoryUpdates.updateInterval);
                
                console.log('✅ Position history auto-updates started with interval ID:', this.positionHistoryUpdates.interval);
                
                // Add test function to global scope for debugging
                window.testPositionUpdates = () => {
                    console.log('🧪 Testing position updates manually...');
                    console.log('Active tab:', this.activeTab);
                    console.log('Position updates enabled:', this.positionHistoryUpdates.enabled);
                    console.log('Position updates interval:', this.positionHistoryUpdates.interval);
                    console.log('Position updates last update:', this.positionHistoryUpdates.lastUpdate);
                    
                    // Force a manual update
                    this.loadPositionsHistory();
                };
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
                        fetch(`http://localhost:5000/api/positions/total_positions?t=${Date.now()}`),
                        fetch(`http://localhost:5000/api/positions/total_pnl?t=${Date.now()}`),
                        fetch(`http://localhost:5000/api/positions/winrate?t=${Date.now()}`)
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
                    const response = await fetch('http://localhost:5000/api/gap-ups/config');
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
                console.log('📈 Current gap-up config:', this.gapUpConfig);
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
                        console.log('📈 Gap-ups count:', data.count);
                        console.log('📈 Gap-ups data length:', data.data ? data.data.length : 0);
                    
                    if (data.success) {
                        this.gapUps = data.data || [];
                        this.dashboardStats.gapUps = this.gapUps.length;
                            console.log('✅ Gap-ups loaded successfully:', this.gapUps.length, 'stocks');
                            console.log('✅ Gap-ups data:', this.gapUps);
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
            
            async loadStats() {
                console.log('📊 Loading statistics...');
                this.loading.stats = true;
                
                try {
                    // Load total P&L
                    const pnlResponse = await fetch('http://localhost:5000/api/positions/total_pnl');
                    const pnlData = await pnlResponse.json();
                    
                    // Load win rate
                    const winRateResponse = await fetch('http://localhost:5000/api/positions/winrate');
                    const winRateData = await winRateResponse.json();
                    
                    // Load total positions
                    const positionsResponse = await fetch('http://localhost:5000/api/positions/total_positions');
                    const positionsData = await positionsResponse.json();
                    
                    if (pnlData.success && winRateData.success && positionsData.success) {
                        this.stats.total_pnl = pnlData.data.total_pnl || 0;
                        this.stats.win_rate = winRateData.data.win_rate || 0;
                        this.stats.total_positions = positionsData.data.total_positions || 0;
                        
                        console.log('✅ Statistics loaded successfully:');
                        console.log('   Total P&L:', this.stats.total_pnl);
                        console.log('   Win Rate:', this.stats.win_rate);
                        console.log('   Total Positions:', this.stats.total_positions);
                    } else {
                        console.error('❌ Failed to load statistics:', pnlData.message || winRateData.message || positionsData.message);
                        this.showNotification('Failed to load statistics', 'error');
                    }
                } catch (error) {
                    console.error('❌ Error loading statistics:', error);
                    this.showNotification('Error loading statistics', 'error');
                } finally {
                    this.loading.stats = false;
                }
            },
            
            async loadDailyPnlData() {
                console.log('📊 Loading daily P&L data...');
                this.loading.dailyPnl = true;
                
                try {
                    const response = await fetch('http://localhost:5000/api/positions/daily-pnl');
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
                    const response = await fetch(`http://localhost:5000/api/positions/pnl-history?t=${Date.now()}`);
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
                
                // Convert period to date range
                const days = parseInt(this.tradeHistoryPeriod);
                const endDate = new Date().toISOString().split('T')[0];
                
                // Handle "All Time" option (value 0)
                if (days === 0) {
                    // Don't apply date filters for "All Time"
                    params.append('limit', '1000');
                } else {
                    const startDate = new Date(Date.now() - (days * 24 * 60 * 60 * 1000)).toISOString().split('T')[0];
                    params.append('start_date', startDate);
                    params.append('end_date', endDate);
                    params.append('limit', '1000');
                }
                    
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
        
        async loadPositionsHistory() {
            try {
                this.loading.positions = true;
                
                // Always use the daily positions API for historical data
                let apiUrl = 'http://localhost:5000/api/positions/daily';
                const params = new URLSearchParams();
                
                // Check if date filters are set
                const hasDateFilters = this.positionsHistoryStartDate && this.positionsHistoryEndDate;
                
                if (hasDateFilters) {
                    // Use the date range API
                    apiUrl = 'http://localhost:5000/api/positions/daily/range';
                    params.append('start_date', this.positionsHistoryStartDate);
                    params.append('end_date', this.positionsHistoryEndDate);
                } else {
                    // Use the daily positions API with default limit
                    params.append('limit', '1000');
                }
                
                // Add other filters
                if (this.positionsHistoryTicker && this.positionsHistoryTicker.trim()) {
                    params.append('symbol', this.positionsHistoryTicker.trim().toUpperCase());
                }
                
                if (this.positionsHistoryType && this.positionsHistoryType.trim()) {
                    params.append('type', this.positionsHistoryType.trim());
                }
                
                const response = await fetch(`${apiUrl}?${params.toString()}`);
                const data = await response.json();
                
                if (data.success) {
                    this.positions = data.data.positions || [];
                    const dateInfo = hasDateFilters ? 
                        ` for date range ${this.positionsHistoryStartDate} to ${this.positionsHistoryEndDate}` : '';
                    const symbolInfo = this.positionsHistoryTicker ? ` for ${this.positionsHistoryTicker}` : '';
                    console.log(`📈 Loaded ${this.positions.length} positions from database${symbolInfo}${dateInfo}`);
                } else {
                    console.error('Failed to load positions history:', data.error);
                    this.showNotification('Failed to load positions history: ' + data.error, 'error');
                }
            } catch (error) {
                console.error('Error loading positions history:', error);
                this.showNotification('Error loading positions history: ' + error.message, 'error');
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
        
        async syncPositionsFromDAS() {
            try {
                console.log('🔄 Syncing positions from DAS Trader...');
                this.loading.syncPositions = true;
                
                const response = await axios.post('/api/positions/sync-das');
                
                if (response.data.success) {
                    const data = response.data.data;
                    const message = `✅ Synced ${data.synced_count} positions from DAS Trader`;
                    this.showNotification(message, 'success');
                    console.log('✅ DAS positions sync completed successfully:', data);
                    
                    // Reload positions history
                    await this.loadPositionsHistory();
                } else {
                    this.showNotification(`❌ Failed to sync positions from DAS: ${response.data.error}`, 'error');
                    console.error('❌ DAS positions sync failed:', response.data.error);
                }
            } catch (error) {
                console.error('❌ Error syncing positions from DAS:', error);
                this.showNotification('❌ Error syncing positions from DAS Trader', 'error');
            } finally {
                this.loading.syncPositions = false;
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
            // Show a loading overlay or indicator
            this.showNotification('Loading dashboard data...', 'info');
            
            // Update loading states for all components
            this.loading.dashboard = true;
            this.loading.gapUps = true;
            this.loading.bot = true;
        },
        
        hideOverallLoadingState() {
            // Hide loading indicators after a delay
            setTimeout(() => {
                this.loading.dashboard = false;
                this.loading.gapUps = false;
                this.loading.bot = false;
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
                    const chatContainer = document.querySelector('.h-96.overflow-y-auto');
                    if (chatContainer) {
                        chatContainer.scrollTop = chatContainer.scrollHeight;
                    }
                });
            }
        },
        
        clearAIChatHistory() {
            this.aiChatMessages = [];
            this.showNotification('Chat history cleared successfully', 'success');
        },
        
        formatAITime(timestamp) {
            if (!timestamp) return '';
            const date = new Date(timestamp);
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
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
        
        // Entry Bot Methods
        async toggleEntryBot() {
            try {
                this.loading.toggleEntryBot = true;
                const action = this.entryBotStatus.internal_running_state ? 'stop' : 'start';
                
                const response = await axios.post(`/api/entry-bot/${action}`);
                
                if (response.data.success) {
                    this.entryBotStatus.internal_running_state = !this.entryBotStatus.internal_running_state;
                    this.addDebugLog('info', `Entry bot ${action}ed successfully`);
                } else {
                    this.addDebugLog('error', `Failed to ${action} entry bot: ${response.data.message}`);
                }
            } catch (error) {
                console.error('Error toggling entry bot:', error);
                this.addDebugLog('error', `Error toggling entry bot: ${error.message}`);
            } finally {
                this.loading.toggleEntryBot = false;
            }
        },
        
        async submitEntryParameters() {
            try {
                this.loading.submitEntry = true;
                
                const entryData = {
                    symbol: this.entryForm.symbol.toUpperCase(),
                    total_volume: parseInt(this.entryForm.totalVolume),
                    dollar_volume: parseInt(this.entryForm.dollarVolume),
                    entry_time: this.entryForm.entryTime
                };
                
                const response = await axios.post('/api/entry-bot/submit-parameters', entryData);
                
                if (response.data.success) {
                    this.addDebugLog('info', `Entry parameters submitted for ${entryData.symbol}`);
                    this.updateTrackingStatus();
                    
                    // Clear form
                    this.entryForm = {
                        symbol: '',
                        totalVolume: '',
                        dollarVolume: '',
                        entryTime: ''
                    };
                } else {
                    this.addDebugLog('error', `Failed to submit entry parameters: ${response.data.message}`);
                }
            } catch (error) {
                console.error('Error submitting entry parameters:', error);
                this.addDebugLog('error', `Error submitting entry parameters: ${error.message}`);
            } finally {
                this.loading.submitEntry = false;
            }
        },
        
        async refreshTrackingStatus() {
            try {
                this.loading.refreshTracking = true;
                
                const response = await axios.get('/api/entry-bot/tracking-status');
                
                if (response.data.success) {
                    this.trackingSymbols = response.data.tracking_symbols || [];
                    this.addDebugLog('info', `Tracking status refreshed: ${this.trackingSymbols.length} symbols`);
                } else {
                    this.addDebugLog('error', `Failed to refresh tracking status: ${response.data.message}`);
                }
            } catch (error) {
                console.error('Error refreshing tracking status:', error);
                this.addDebugLog('error', `Error refreshing tracking status: ${error.message}`);
            } finally {
                this.loading.refreshTracking = false;
            }
        },

        async refreshActivePositions() {
            try {
                this.loading.refreshPositions = true;
                const response = await axios.get('/api/entry-bot/active-positions');
                
                if (response.data.success) {
                    this.activePositions = response.data.data;
                    this.addDebugLog('info', `Active positions refreshed - ${this.activePositions.length} positions active`);
                } else {
                    this.addDebugLog('error', `Failed to refresh active positions: ${response.data.error}`);
                }
            } catch (error) {
                console.error('Error refreshing active positions:', error);
                this.addDebugLog('error', `Error refreshing active positions: ${error.message}`);
            } finally {
                this.loading.refreshPositions = false;
            }
        },
        
        async stopTrackingSymbol(symbol) {
            try {
                const response = await axios.post('/api/entry-bot/stop-tracking', { symbol });
                
                if (response.data.success) {
                    this.addDebugLog('info', `Stopped tracking ${symbol}`);
                    this.updateTrackingStatus();
                } else {
                    this.addDebugLog('error', `Failed to stop tracking ${symbol}: ${response.data.message}`);
                }
            } catch (error) {
                console.error('Error stopping tracking:', error);
                this.addDebugLog('error', `Error stopping tracking ${symbol}: ${error.message}`);
            }
        },
        
        async refreshDebugLogs() {
            try {
                this.loading.refreshLogs = true;
                
                const response = await axios.get('/api/entry-bot/debug-logs');
                
                if (response.data.success) {
                    this.debugLogs = response.data.logs || [];
                } else {
                    this.addDebugLog('error', `Failed to refresh debug logs: ${response.data.message}`);
                }
            } catch (error) {
                console.error('Error refreshing debug logs:', error);
                this.addDebugLog('error', `Error refreshing debug logs: ${error.message}`);
            } finally {
                this.loading.refreshLogs = false;
            }
        },
        
        clearDebugLogs() {
            this.debugLogs = [];
            this.addDebugLog('info', 'Debug logs cleared');
        },
        
        addDebugLog(level, message) {
            const log = {
                id: Date.now(),
                timestamp: new Date().toISOString(),
                level: level,
                message: message
            };
            
            this.debugLogs.unshift(log);
            
            // Keep only last 100 logs
            if (this.debugLogs.length > 100) {
                this.debugLogs = this.debugLogs.slice(0, 100);
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
        
        async loadEntryBotStatus() {
            try {
                const response = await axios.get('/api/entry-bot/status');
                
                if (response.data.success) {
                    this.entryBotStatus = response.data.data;
                    this.addDebugLog('info', 'Entry bot status loaded successfully');
                } else {
                    this.addDebugLog('error', `Failed to load entry bot status: ${response.data.error}`);
                }
            } catch (error) {
                console.error('Error loading entry bot status:', error);
                this.addDebugLog('error', `Error loading entry bot status: ${error.message}`);
            }
        },
        
        startContinuousTracking() {
            // Stop any existing tracking interval
            this.stopContinuousTracking();
            
            // Start new tracking interval every 1 second
            this.trackingInterval = setInterval(() => {
                // Update tracking status without loading states (smooth updates)
                this.updateTrackingStatus();
                // Update active positions without loading states (smooth updates)
                this.updateActivePositions();
                // Update debug logs without loading states (smooth updates)
                this.updateDebugLogs();
            }, 1000);
            
            this.addDebugLog('info', 'Continuous tracking started (every 1 second)');
        },
        
        stopContinuousTracking() {
            if (this.trackingInterval) {
                clearInterval(this.trackingInterval);
                this.trackingInterval = null;
                this.addDebugLog('info', 'Continuous tracking stopped');
            }
        },
        
        // Smooth update methods without loading states
        async updateTrackingStatus() {
            try {
                const response = await axios.get('/api/entry-bot/tracking-status');
                
                if (response.data.success) {
                    this.trackingSymbols = response.data.tracking_symbols || [];
                }
            } catch (error) {
                console.error('Error updating tracking status:', error);
            }
        },
        
        async updateActivePositions() {
            try {
                const response = await axios.get('/api/entry-bot/active-positions');
                
                if (response.data.success) {
                    this.activePositions = response.data.data;
                }
            } catch (error) {
                console.error('Error updating active positions:', error);
            }
        },
        
        async updateDebugLogs() {
            try {
                const response = await axios.get('/api/entry-bot/debug-logs');
                
                if (response.data.success) {
                    this.debugLogs = response.data.logs || [];
                }
            } catch (error) {
                console.error('Error updating debug logs:', error);
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
