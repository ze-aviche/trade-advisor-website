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
                activeTab: localStorage.getItem('activeTab') || 'dashboard',
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
                
                // Chart update control
                chartUpdateInProgress: false,
                pnlChartUpdateTimeout: null,
                tradeChartUpdateTimeout: null,
                
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
            
            // Clean up timeouts and charts
            if (this.pnlChartUpdateTimeout) {
                clearTimeout(this.pnlChartUpdateTimeout);
            }
            if (this.tradeChartUpdateTimeout) {
                clearTimeout(this.tradeChartUpdateTimeout);
            }
            
            // Destroy charts
            if (this.charts.pnl && typeof this.charts.pnl.destroy === 'function') {
                this.charts.pnl.destroy();
            }
            if (this.charts.trades && typeof this.charts.trades.destroy === 'function') {
                this.charts.trades.destroy();
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
            onTabChange(tabName) {
                console.log(`🔄 Tab changed to: ${tabName}`);
                console.log(`🔍 Current activeTab value: ${this.activeTab}`);
                
                // Save the active tab to localStorage for persistence across page refreshes
                localStorage.setItem('activeTab', tabName);
                
                if (tabName === 'dashboard') {
                    console.log('📊 Dashboard tab selected - ensuring charts are updated...');
                    // Ensure charts are updated when dashboard tab is accessed
                    this.$nextTick(() => {
                        setTimeout(() => {
                            this.updatePnlChart();
                            this.updateTradeChart();
                        }, 100);
                    });
                } else if (tabName === 'bot') {
                    console.log('🤖 Bot tab selected - loading bot status with real-time updates...');
                    this.loadBotStatusWithRealTime();
                } else if (tabName === 'trades') {
                    console.log('📊 Trade History tab selected - loading trade history...');
                    this.loadTradeHistory();
                } else if (tabName === 'gap-ups') {
                    console.log('📈 Gap-Ups tab selected - loading gap-up stocks...');
                    this.loadGapUps();
                } else if (tabName === 'historical') {
                    console.log('📈 Historical Data tab selected - ready for analysis...');
                    // Historical tab is ready for user input, no auto-loading needed
                } else if (tabName === 'ai-chat') {
                    console.log('🤖 AI Chat tab selected - ready for chat...');
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
                            this.updateTradeChart();
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
                        this.loadStats().then(() => console.log('✅ Stats loaded')),
                        this.loadGapUpConfig().then(() => console.log('✅ Gap-up config loaded')),
                        this.loadGapUps().then(() => console.log('✅ Gap-ups loaded')),
                        this.loadDashboardTrades().then(() => console.log('✅ Dashboard trades loaded')),
                        this.loadDashboardPnL().then(() => console.log('✅ Dashboard PnL loaded'))
                    ];
                    
                    await Promise.allSettled(promises);
                    console.log('✅ Dashboard data load completed');
                    
                    // Update charts after all data is loaded
                    setTimeout(() => {
                        console.log('🔄 Updating charts after data load...');
                        this.$nextTick(() => {
                            this.updatePnlChart();
                            this.updateTradeChart();
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
                                if (positionsChanged) {
                                    this.botStatus[key] = newBotStatus[key];
                                    hasChanges = true;
                                    console.log('🔄 Active positions updated');
                                }
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
            
            async loadStats() {
            console.log('📊 Loading DASHBOARD stats from DAS trades database (all trades, no filtering)...');
                this.updateLoadingProgress('stats', 'loading');
                
                const maxRetries = 3;
                const retryDelay = 1000; // 1 second
                
                for (let attempt = 1; attempt <= maxRetries; attempt++) {
                    try {
                        console.log(`📊 Stats loading attempt ${attempt}/${maxRetries}...`);
                        
                    // Load ALL trades for dashboard stats (no filtering)
                    const response = await fetch('http://localhost:5000/api/trades?limit=1000', {
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
                        
                        // Calculate DASHBOARD stats from ALL database trades (no filtering)
                        const totalTrades = this.trades.length;
                        const winningTrades = this.trades.filter(t => (t.pnl || 0) > 0).length;
                        const totalPnl = this.trades.reduce((sum, t) => sum + (t.pnl || 0), 0);
                        const winRate = totalTrades > 0 ? (winningTrades / totalTrades) * 100 : 0;
                        
                        // Update DASHBOARD stats (these should remain constant regardless of trade history filters)
                        this.stats = {
                            totalTrades: totalTrades,
                            winRate: winRate,
                            totalPnl: totalPnl,
                            pnl: totalPnl,
                            activePositions: this.trades.filter(t => t.status === 'filled').length,
                            gapUps: this.gapUps.length
                        };
                            
                        console.log('✅ DASHBOARD stats loaded successfully from database:', this.stats);
                        console.log('📊 DASHBOARD stats - Total:', totalTrades, 'Winning:', winningTrades, 'Win Rate:', winRate.toFixed(2) + '%', 'Total P&L:', totalPnl);
                            this.updateLoadingProgress('stats', 'success');
                            
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
            
            calculateTradeAnalytics() {
                try {
                    console.log('📊 Calculating trade analytics...');
                    
                    const trades = this.dashboardTrades;
                    if (!trades || trades.length === 0) {
                        console.log('⚠️ No trades available for analytics calculation');
                        return;
                    }
                    
                    // Overall stats
                    const totalTrades = trades.length;
                    const winningTrades = trades.filter(t => (t.pnl || 0) > 0).length;
                    const totalPnl = trades.reduce((sum, t) => sum + (t.pnl || 0), 0);
                    const overallWinRate = totalTrades > 0 ? (winningTrades / totalTrades) * 100 : 0;
                    const avgTradePnl = totalTrades > 0 ? totalPnl / totalTrades : 0;
                    
                    // Long trades analysis
                    const longTrades = trades.filter(t => {
                        const side = t.side?.toLowerCase() || t.direction?.toLowerCase() || '';
                        return side === 'b'; // 'B' = Buy = Long
                    });
                    const longWinningTrades = longTrades.filter(t => (t.pnl || 0) > 0).length;
                    const longPnl = longTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);
                    const longWinRate = longTrades.length > 0 ? (longWinningTrades / longTrades.length) * 100 : 0;
                    
                    // Short trades analysis
                    const shortTrades = trades.filter(t => {
                        const side = t.side?.toLowerCase() || t.direction?.toLowerCase() || '';
                        return side === 's'; // 'S' = Sell = Short
                    });
                    const shortWinningTrades = shortTrades.filter(t => (t.pnl || 0) > 0).length;
                    const shortPnl = shortTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);
                    const shortWinRate = shortTrades.length > 0 ? (shortWinningTrades / shortTrades.length) * 100 : 0;
                    
                    // Top performers analysis
                    const tickerPerformance = {};
                    trades.forEach(trade => {
                        const ticker = trade.symbol || trade.ticker || 'Unknown';
                        if (!tickerPerformance[ticker]) {
                            tickerPerformance[ticker] = { pnl: 0, count: 0 };
                        }
                        tickerPerformance[ticker].pnl += (trade.pnl || 0);
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
                    this.tradeAnalytics = {
                        totalTrades: totalTrades,
                        overallWinRate: overallWinRate,
                        totalPnl: totalPnl,
                        avgTradePnl: avgTradePnl,
                        longTrades: {
                            count: longTrades.length,
                            winRate: longWinRate,
                            pnl: longPnl
                        },
                        shortTrades: {
                            count: shortTrades.length,
                            winRate: shortWinRate,
                            pnl: shortPnl
                        },
                        topPerformers: {
                            bestTicker: bestTicker,
                            bestPnl: bestPnl
                        }
                    };
                    
                    console.log('✅ Trade analytics calculated:', this.tradeAnalytics);
                    console.log(`📊 Long trades: ${longTrades.length} trades, ${longWinRate.toFixed(2)}% win rate, $${longPnl.toFixed(2)} P&L`);
                    console.log(`📊 Short trades: ${shortTrades.length} trades, ${shortWinRate.toFixed(2)}% win rate, $${shortPnl.toFixed(2)} P&L`);
                    
                } catch (error) {
                    console.error('❌ Error calculating trade analytics:', error);
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
                        this.stats.gapUps = this.gapUps.length;
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
            
            async loadDashboardTrades() {
                try {
                    this.loading.dashboardTrades = true;
                    
                    if (this.showAllTrades) {
                        // Load all trades without date restrictions
                        console.log('🔄 Loading all dashboard trades (no date filter)...');
                        const response = await fetch(`http://localhost:5000/api/trades?limit=100`);
                        const data = await response.json();
                        
                        if (data.success) {
                            this.dashboardTrades = data.data.trades || [];
                            console.log('✅ All dashboard trades loaded from database:', this.dashboardTrades.length, 'trades');
                        } else {
                            console.error('Failed to load dashboard trades:', data.message);
                        }
                    } else {
                        // Use date range instead of period
                        const fromDate = this.dashboardTradeFromDate || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
                        const toDate = this.dashboardTradeToDate || new Date().toISOString().split('T')[0];
                        
                        console.log('🔄 Loading dashboard trades for date range:', fromDate, 'to', toDate);
                    
                        // First try with the specified date range
                        let response = await fetch(`http://localhost:5000/api/trades?start_date=${fromDate}&end_date=${toDate}`);
                        let data = await response.json();
                        
                        if (data.success && data.data.trades && data.data.trades.length > 0) {
                            // Load trades directly from database
                            this.dashboardTrades = data.data.trades || [];
                            console.log('✅ Dashboard trades loaded from database with date filter:', this.dashboardTrades.length, 'trades');
                        } else {
                            console.log('⚠️ No trades found with date filter, trying without date restrictions...');
                            // If no trades found with date filter, try without date restrictions
                            response = await fetch(`http://localhost:5000/api/trades?limit=100`);
                            data = await response.json();
                            
                            if (data.success) {
                                this.dashboardTrades = data.data.trades || [];
                                console.log('✅ Dashboard trades loaded from database without date filter:', this.dashboardTrades.length, 'trades');
                            } else {
                                console.error('Failed to load dashboard trades:', data.message);
                            }
                        }
                    }
                    
                    // Apply trade type filter
                    if (this.tradeTypeFilter !== 'all') {
                        const originalCount = this.dashboardTrades.length;
                        this.dashboardTrades = this.dashboardTrades.filter(trade => {
                            // Map database fields to expected frontend fields
                            const tradeDirection = trade.side?.toLowerCase() || trade.direction?.toLowerCase() || '';
                            // Map 'B' to 'long', 'S' to 'short'
                            const mappedDirection = tradeDirection === 'b' ? 'long' : tradeDirection === 's' ? 'short' : tradeDirection;
                            return mappedDirection === this.tradeTypeFilter;
                        });
                        console.log(`🔍 Applied trade type filter '${this.tradeTypeFilter}': ${originalCount} → ${this.dashboardTrades.length} trades`);
                    }
                    
                    // Calculate trade analytics
                    this.calculateTradeAnalytics();
                    
                    // Update trade chart after data loads with debouncing
                    if (this.tradeChartUpdateTimeout) {
                        clearTimeout(this.tradeChartUpdateTimeout);
                    }
                    this.tradeChartUpdateTimeout = setTimeout(() => {
                        this.updateTradeChart();
                    }, 200);
                    
                } catch (error) {
                    console.error('Error loading dashboard trades:', error);
                } finally {
                    this.loading.dashboardTrades = false;
                    console.log('🏁 Dashboard trades loading finished');
                }
            },
            
            async loadDashboardPnL() {
                try {
                    this.loading.dashboardPnL = true;
                    
                    if (this.showAllTrades) {
                        // Load all trades without date restrictions
                        console.log('🔄 Loading all dashboard P&L (no date filter)...');
                        const response = await fetch(`http://localhost:5000/api/trades?limit=100`);
                        const data = await response.json();
                        
                        if (data.success) {
                            this.dashboardPnL = data.data.trades || [];
                            console.log('✅ All dashboard P&L loaded from database:', this.dashboardPnL.length, 'trades');
                        } else {
                            console.error('Failed to load dashboard P&L data:', data.message);
                        }
                    } else {
                        // Use date range instead of period
                        const fromDate = this.dashboardPnLFromDate || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
                        const toDate = this.dashboardPnLToDate || new Date().toISOString().split('T')[0];
                        
                        console.log('🔄 Loading dashboard P&L for date range:', fromDate, 'to', toDate);
                    
                        // First try with the specified date range
                        let response = await fetch(`http://localhost:5000/api/trades?start_date=${fromDate}&end_date=${toDate}`);
                        let data = await response.json();
                        
                        if (data.success && data.data.trades && data.data.trades.length > 0) {
                            // Load PnL data directly from database
                            this.dashboardPnL = data.data.trades || [];
                            console.log('✅ Dashboard P&L loaded from database with date filter:', this.dashboardPnL.length, 'trades');
                        } else {
                            console.log('⚠️ No trades found with date filter, trying without date restrictions...');
                            // If no trades found with date filter, try without date restrictions
                            response = await fetch(`http://localhost:5000/api/trades?limit=100`);
                            data = await response.json();
                            
                            if (data.success) {
                                this.dashboardPnL = data.data.trades || [];
                                console.log('✅ Dashboard P&L loaded from database without date filter:', this.dashboardPnL.length, 'trades');
                            } else {
                                console.error('Failed to load dashboard P&L data:', data.message);
                            }
                        }
                    }
                    
                    // Update PnL chart after data loads with debouncing
                    if (this.pnlChartUpdateTimeout) {
                        clearTimeout(this.pnlChartUpdateTimeout);
                    }
                    this.pnlChartUpdateTimeout = setTimeout(() => {
                        this.updatePnlChart();
                    }, 200);
                    
                } catch (error) {
                    console.error('Error loading dashboard P&L data:', error);
                } finally {
                    this.loading.dashboardPnL = false;
                    console.log('🏁 Dashboard P&L loading finished');
                }
            },
            
            async onShowAllTradesToggle() {
                console.log('🔄 Show All Trades toggle changed to:', this.showAllTrades);
                // Load both dashboard components when toggle changes
                await Promise.all([
                    this.loadDashboardTrades(),
                    this.loadDashboardPnL()
                ]);
                
                // Update charts after data loads
                this.$nextTick(() => {
                    setTimeout(() => {
                        this.updatePnlChart();
                        this.updateTradeChart();
                    }, 200);
                });
            },
            
            onChartViewTypeChange() {
                console.log('🔄 Chart view type changed to:', this.chartViewType);
                this.updateTradeChart();
            },
            
            setDateRangeTo2025() {
                // Quick method to set date range to 2025 to match database
                this.dashboardPnLFromDate = '2025-01-01';
                this.dashboardPnLToDate = '2025-12-31';
                this.dashboardTradeFromDate = '2025-01-01';
                this.dashboardTradeToDate = '2025-12-31';
                this.showAllTrades = false; // Turn off show all trades to use date range
                
                console.log('📅 Date range set to 2025');
                
                // Reload both components
                Promise.all([
                    this.loadDashboardTrades(),
                    this.loadDashboardPnL()
                ]).then(() => {
                    // Update charts after data loads
                    this.$nextTick(() => {
                        setTimeout(() => {
                            this.updatePnlChart();
                            this.updateTradeChart();
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
                console.log('🔄 Updating PnL chart from database...');
                console.log('📊 Chart object exists:', !!this.charts.pnl);
                console.log('📊 Dashboard PnL data:', this.dashboardPnL.length, 'trades');
                
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
                
                // Ensure the canvas is visible and has dimensions
                const rect = ctx.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) {
                    console.log('⚠️ Trade chart canvas has no dimensions, waiting...');
                    // Wait a bit and try again
                    setTimeout(() => {
                        this.updateTradeChart();
                    }, 100);
                    return;
                }
                
                // Safely destroy existing chart if it exists
                if (this.charts.trades) {
                    try {
                        if (typeof this.charts.trades.destroy === 'function') {
                            this.charts.trades.destroy();
                            console.log('🗑️ Destroyed existing Trade chart');
                        }
                    } catch (error) {
                        console.warn('⚠️ Error destroying existing trade chart:', error);
                    }
                    this.charts.trades = null;
                }
                
                try {
                    // Ensure canvas has proper dimensions
                    const canvasRect = ctx.getBoundingClientRect();
                    if (canvasRect.width === 0 || canvasRect.height === 0) {
                        console.log('⚠️ Trade chart canvas has no dimensions, setting default size');
                        ctx.style.width = '100%';
                        ctx.style.height = '300px';
                    }
                    
                    let chartData = {};
                    let chartType = 'doughnut';
                    
                    // Prepare chart data based on view type
                    switch (this.chartViewType) {
                        case 'long_short':
                            const longTrades = this.dashboardTrades.filter(t => {
                                const side = t.side?.toLowerCase() || t.direction?.toLowerCase() || '';
                                return side === 'b'; // 'B' = Buy = Long
                            }).length;
                            
                            const shortTrades = this.dashboardTrades.filter(t => {
                                const side = t.side?.toLowerCase() || t.direction?.toLowerCase() || '';
                                return side === 's'; // 'S' = Sell = Short
                            }).length;
                            
                            const otherTrades = this.dashboardTrades.length - longTrades - shortTrades;
                            
                            chartData = {
                                labels: ['Long Trades', 'Short Trades', 'Other Trades'],
                                datasets: [{
                                    data: [longTrades, shortTrades, otherTrades],
                                    backgroundColor: ['#10B981', '#EF4444', '#6B7280'],
                                    borderColor: '#374151',
                                    borderWidth: 2
                                }]
                            };
                            console.log('📊 Long vs Short distribution - Long:', longTrades, 'Short:', shortTrades, 'Other:', otherTrades);
                            break;
                            
                        case 'win_loss':
                            const winningTrades = this.dashboardTrades.filter(t => (t.pnl || 0) > 0).length;
                            const losingTrades = this.dashboardTrades.filter(t => (t.pnl || 0) < 0).length;
                            const neutralTrades = this.dashboardTrades.filter(t => (t.pnl || 0) === 0).length;
                            
                            chartData = {
                                labels: ['Winning Trades', 'Losing Trades', 'Neutral Trades'],
                                datasets: [{
                                    data: [winningTrades, losingTrades, neutralTrades],
                                    backgroundColor: ['#10B981', '#EF4444', '#F59E0B'],
                                    borderColor: '#374151',
                                    borderWidth: 2
                                }]
                            };
                            console.log('📊 Win vs Loss distribution - Winning:', winningTrades, 'Losing:', losingTrades, 'Neutral:', neutralTrades);
                            break;
                            
                        case 'ticker':
                            // Group by ticker and show top 10
                            const tickerCounts = {};
                            this.dashboardTrades.forEach(trade => {
                                const ticker = trade.symbol || trade.ticker || 'Unknown';
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
                            this.dashboardTrades.forEach(trade => {
                                const date = new Date(trade.created_at || trade.trade_date || trade.submitted_at);
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
                                    label: 'Trades per Month',
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
                            const defaultLong = this.dashboardTrades.filter(t => {
                                const side = t.side?.toLowerCase() || t.direction?.toLowerCase() || '';
                                return side === 'b'; // 'B' = Buy = Long
                            }).length;
                            
                            const defaultShort = this.dashboardTrades.filter(t => {
                                const side = t.side?.toLowerCase() || t.direction?.toLowerCase() || '';
                                return side === 's'; // 'S' = Sell = Short
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
                    this.charts.trades = new Chart(ctx, {
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
                    
                    console.log('✅ Trade chart created successfully with database data');
                    
                } catch (error) {
                    console.error('❌ Error updating trade chart:', error);
                    this.charts.trades = null;
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
                
                // Only setup trade chart - PnL chart is created dynamically
                this.setupTradeChart();
                
                console.log('📊 Charts initialized:', {
                    pnl: !!this.charts.pnl,
                    trades: !!this.charts.trades
                });
                
                // Handle window resize to prevent chart issues
                window.addEventListener('resize', () => {
                    try {
                        if (this.charts.pnl && typeof this.charts.pnl.resize === 'function') {
                            this.charts.pnl.resize();
                        }
                        if (this.charts.trades && typeof this.charts.trades.resize === 'function') {
                            this.charts.trades.resize();
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
