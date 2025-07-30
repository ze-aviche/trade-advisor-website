// Gap Up Trade Bot Dashboard - Vue.js Application

console.log('🚀 Loading Trading Advisor Dashboard...');

const { createApp } = Vue;

console.log('✅ Vue.js loaded successfully');

try {
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
                    historical: false
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
                
                // System status
                systemStatus: {
                    connected: false,
                    realDataAvailable: false,
                    websocketConnected: false
                },
                
                // User data
                user: null,
                
                // Historical data
                historicalTicker: '',
                historicalData: [],
                selectedPeriod: '1095', // Default to 3 years
                sortColumn: '',
                sortDirection: 'asc'
            }
        },
        
        mounted() {
            console.log('🎯 Vue.js app mounted successfully');
            this.checkAuth();
        },
        
        methods: {
            checkAuth() {
                const sessionToken = localStorage.getItem('session_token');
                const user = localStorage.getItem('user');
                
                if (!sessionToken || !user) {
                    // Redirect to login
                    window.location.href = '/login.html';
                    return;
                }
                
                // Validate session with backend
                this.validateSession();
            },
            
            async validateSession() {
                try {
                    const sessionToken = localStorage.getItem('session_token');
                    const response = await fetch('http://localhost:5000/api/auth/profile', {
                        headers: {
                            'Authorization': `Bearer ${sessionToken}`
                        }
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        if (data.success) {
                            this.user = data.data;
                            this.initializeApp();
                        } else {
                            this.logout();
                        }
                    } else {
                        this.logout();
                    }
                } catch (error) {
                    console.error('Session validation error:', error);
                    this.logout();
                }
            },
            
            logout() {
                localStorage.removeItem('session_token');
                localStorage.removeItem('user');
                window.location.href = '/login.html';
            },
            
            async initializeApp() {
                try {
                    await this.checkSystemStatus();
                    await this.loadDashboardData();
                    this.setupCharts();
                    this.startPeriodicUpdates();
                    this.connectWebSocket();
                } catch (error) {
                    console.error('Error in initializeApp:', error);
                    // Don't let initialization errors crash the app
                    this.systemStatus.connected = false;
                }
            },
            
            async checkSystemStatus() {
                try {
                    const sessionToken = localStorage.getItem('session_token');
                    const response = await fetch('http://localhost:5000/api/health', {
                        headers: {
                            'Authorization': `Bearer ${sessionToken}`
                        }
                    });
                    const data = await response.json();
                    this.systemStatus = {
                        connected: true,
                        realDataAvailable: data.real_data_available,
                        websocketConnected: data.websocket_connected
                    };
                } catch (error) {
                    console.error('Error checking system status:', error);
                    this.systemStatus.connected = false;
                }
            },
            
            async loadDashboardData() {
                try {
                    await Promise.all([
                        this.loadStats(),
                        this.loadGapUps(),
                        this.loadTrades()
                    ]);
                } catch (error) {
                    console.error('Error loading dashboard data:', error);
                    // Continue with the app even if some data fails to load
                }
            },
            
            async loadStats() {
                this.loading.stats = true;
                try {
                    const sessionToken = localStorage.getItem('session_token');
                    const response = await fetch('http://localhost:5000/api/trades', {
                        headers: {
                            'Authorization': `Bearer ${sessionToken}`
                        }
                    });
                    const data = await response.json();
                    
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
                        
                        // Update charts after data is loaded
                        setTimeout(() => {
                            this.updatePnlChart();
                        }, 100);
                    }
                } catch (error) {
                    console.error('Error loading stats:', error);
                } finally {
                    this.loading.stats = false;
                }
            },
            
            async loadGapUps() {
                this.loading.gapUps = true;
                try {
                    const sessionToken = localStorage.getItem('session_token');
                    const response = await fetch('http://localhost:5000/api/gap-ups', {
                        headers: {
                            'Authorization': `Bearer ${sessionToken}`
                        }
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        // Filter out stocks less than $1
                        const filteredGapUps = data.data.filter(stock => 
                            stock.price && stock.price >= 1.0
                        );
                        
                        this.gapUps = filteredGapUps;
                        this.stats.gapUps = filteredGapUps.length;
                        
                        console.log(`📊 Filtered gap-ups: ${data.data.length} total, ${filteredGapUps.length} above $1`);
                        
                        // Subscribe to real-time updates for gap-up stocks
                        if (this.socketConnected && filteredGapUps.length > 0) {
                            const tickers = filteredGapUps.map(stock => stock.ticker);
                            this.subscribeToStocks(tickers);
                        }
                    }
                } catch (error) {
                    console.error('Error loading gap-ups:', error);
                } finally {
                    this.loading.gapUps = false;
                }
            },
            
            async loadGapUpsBackground() {
                // Background update - no UI impact
                try {
                    const sessionToken = localStorage.getItem('session_token');
                    const response = await fetch('http://localhost:5000/api/gap-ups', {
                        headers: {
                            'Authorization': `Bearer ${sessionToken}`
                        }
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        // Filter out stocks less than $1
                        const filteredData = data.data.filter(stock => 
                            stock.price && stock.price >= 1.0
                        );
                        
                        // Only update if there are new stocks or significant changes
                        const newStocks = filteredData.filter(newStock => 
                            !this.gapUps.some(existingStock => 
                                existingStock.ticker === newStock.ticker
                            )
                        );
                        
                        if (newStocks.length > 0) {
                            console.log(`🔄 Background update: Found ${newStocks.length} new gap-up stocks (filtered from ${data.data.length} total)`);
                            // Add new stocks to the beginning
                            this.gapUps.unshift(...newStocks);
                            this.stats.gapUps = this.gapUps.length;
                            
                            // Show subtle notification for new stocks
                            this.showNotification(`📈 ${newStocks.length} new gap-up stock(s) detected (≥$1)`, 'success');
                            
                            // Subscribe to new stocks
                            if (this.socketConnected && newStocks.length > 0) {
                                const tickers = newStocks.map(stock => stock.ticker);
                                this.subscribeToStocks(tickers);
                            }
                        }
                        
                        // Update existing stocks with new data (price changes, etc.)
                        data.data.forEach(newStock => {
                            const existingIndex = this.gapUps.findIndex(
                                existing => existing.ticker === newStock.ticker
                            );
                            if (existingIndex !== -1) {
                                // Update with new data but preserve position
                                this.gapUps[existingIndex] = {
                                    ...this.gapUps[existingIndex],
                                    ...newStock
                                };
                            }
                        });
                    }
                } catch (error) {
                    console.error('Error in background gap-ups update:', error);
                }
            },
            
            async loadTrades() {
                this.loading.trades = true;
                try {
                    const sessionToken = localStorage.getItem('session_token');
                    const response = await fetch('http://localhost:5000/api/trades', {
                        headers: {
                            'Authorization': `Bearer ${sessionToken}`
                        }
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        this.trades = data.trades;
                        this.updateTradeChart();
                    }
                } catch (error) {
                    console.error('Error loading trades:', error);
                } finally {
                    this.loading.trades = false;
                }
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
                if (!this.historicalTicker.trim()) {
                    this.showNotification('Please enter a ticker symbol', 'warning');
                    return;
                }
                
                try {
                    this.loading.historical = true;
                    console.log(`📊 Loading historical data for ${this.historicalTicker} (${this.getPeriodDescription()})...`);
                    
                    const sessionToken = localStorage.getItem('session_token');
                    const response = await fetch(`http://localhost:5000/api/historical-data/${this.historicalTicker.toUpperCase()}?days=${this.selectedPeriod}`, {
                        headers: {
                            'Authorization': `Bearer ${sessionToken}`
                        }
                    });
                    
                    const data = await response.json();
                    if (data.success) {
                        // Filter for gap-ups >= 25%
                        const filteredData = data.data.filter(day => 
                            day['gap up % at open'] && day['gap up % at open'] >= 25
                        );
                        
                        this.historicalData = filteredData;
                        console.log(`✅ Loaded ${filteredData.length} days of 25%+ gap-up data for ${this.historicalTicker} (filtered from ${data.data.length} total days over ${this.getPeriodDescription()})`);
                        this.showNotification(`Loaded ${filteredData.length} days of 25%+ gap-up data for ${this.historicalTicker.toUpperCase()} (${this.getPeriodDescription()} analysis)`, 'success');
                    } else {
                        console.error(`❌ Failed to load historical data for ${this.historicalTicker}:`, data.error);
                        this.showNotification(`Failed to load historical data for ${this.historicalTicker.toUpperCase()}`, 'error');
                    }
                } catch (error) {
                    console.error(`❌ Error loading historical data for ${this.historicalTicker}:`, error);
                    this.showNotification(`Error loading historical data for ${this.historicalTicker.toUpperCase()}`, 'error');
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
                    const response = await fetch('http://localhost:5000/api/start-session', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            user_id: 'web_user'
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        this.chatSession = data.session_id;
                        this.chatMessages = [{
                            id: 1,
                            type: 'system',
                            message: 'Trading session started. How can I help you today?',
                            timestamp: new Date().toISOString()
                        }];
                        this.showNotification('Chat session started', 'success');
                    }
                } catch (error) {
                    console.error('Error starting chat session:', error);
                    this.showNotification('Error starting chat session', 'error');
                }
            },
            
            async sendChatMessage() {
                if (!this.newMessage.trim() || !this.chatSession) return;
                
                const userMessage = {
                    id: Date.now(),
                    type: 'user',
                    message: this.newMessage,
                    timestamp: new Date().toISOString()
                };
                
                this.chatMessages.push(userMessage);
                const messageToSend = this.newMessage;
                this.newMessage = '';
                
                try {
                    const response = await fetch('http://localhost:5000/api/send-message', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            session_id: this.chatSession,
                            message: messageToSend
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        this.chatMessages.push({
                            id: Date.now() + 1,
                            type: 'assistant',
                            message: data.response,
                            timestamp: new Date().toISOString()
                        });
                    }
                } catch (error) {
                    console.error('Error sending message:', error);
                    this.showNotification('Error sending message', 'error');
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
                    this.setupPnlChart();
                    this.setupTradeChart();
                    
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
                    console.error('Error setting up charts:', error);
                    // Continue without charts if they fail to load
                }
            },
            
            setupPnlChart() {
                const ctx = document.getElementById('pnlChart');
                if (!ctx) return;
                
                this.charts.pnl = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                        datasets: [{
                            label: 'P&L',
                            data: [1200, 1900, 3000, 5000, 2000, 3000],
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
                        interaction: {
                            intersect: false,
                            mode: 'index'
                        },
                        plugins: {
                            legend: {
                                labels: {
                                    color: '#D1D5DB',
                                    usePointStyle: true
                                }
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: '#ffffff',
                                bodyColor: '#ffffff',
                                borderColor: '#10B981',
                                borderWidth: 1
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
                                    color: '#374151',
                                    drawBorder: false
                                },
                                border: {
                                    color: '#374151'
                                }
                            },
                            x: {
                                ticks: {
                                    color: '#D1D5DB'
                                },
                                grid: {
                                    color: '#374151',
                                    drawBorder: false
                                },
                                border: {
                                    color: '#374151'
                                }
                            }
                        },
                        animation: {
                            duration: 750,
                            easing: 'easeInOutQuart'
                        }
                    }
                });
            },
            
            updatePnlChart() {
                if (!this.charts.pnl) return;
                
                // Calculate cumulative P&L from trades
                const pnlData = [];
                const labels = [];
                let cumulativePnl = 0;
                
                // Sort trades by timestamp
                const sortedTrades = [...this.trades].sort((a, b) => 
                    new Date(a.timestamp) - new Date(b.timestamp)
                );
                
                sortedTrades.forEach((trade, index) => {
                    cumulativePnl += (trade.pnl || 0);
                    pnlData.push(cumulativePnl);
                    labels.push(new Date(trade.timestamp).toLocaleDateString());
                });
                
                // If no trades, use default data
                if (pnlData.length === 0) {
                    pnlData.push(0);
                    labels.push('No trades');
                }
                
                this.charts.pnl.data.labels = labels;
                this.charts.pnl.data.datasets[0].data = pnlData;
                
                // Update y-axis range based on data
                const minPnl = Math.min(...pnlData);
                const maxPnl = Math.max(...pnlData);
                const range = maxPnl - minPnl;
                
                this.charts.pnl.options.scales.y.min = minPnl - (range * 0.1);
                this.charts.pnl.options.scales.y.max = maxPnl + (range * 0.1);
                
                this.charts.pnl.update('none'); // Update without animation to prevent weird behavior
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
                if (!this.charts.trades) return;
                
                const winning = this.trades.filter(t => (t.pnl || 0) > 0).length;
                const losing = this.trades.filter(t => (t.pnl || 0) < 0).length;
                const pending = this.trades.filter(t => t.status === 'pending').length;
                
                this.charts.trades.data.datasets[0].data = [winning, losing, pending];
                this.charts.trades.update();
            },
            
            // Refresh all data
            async refreshData() {
                this.showNotification('Refreshing data...', 'warning');
                await this.loadDashboardData();
                this.showNotification('Data refreshed', 'success');
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
                return new Date(dateString).toLocaleDateString();
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
                return parseInt(this.selectedPeriod) || 1095;
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
                console.log('⏰ Starting periodic updates...');
                // Update system status every 30 seconds
                setInterval(() => {
                    try {
                        this.checkSystemStatus();
                    } catch (error) {
                        console.error('Error in periodic system status check:', error);
                    }
                }, 30000);
                
                // Update dashboard data every 5 minutes
                setInterval(() => {
                    try {
                        this.loadDashboardData();
                    } catch (error) {
                        console.error('Error in periodic dashboard update:', error);
                    }
                }, 300000);
                
                // Enhanced polling for gap-ups every 30 seconds (background only)
                setInterval(() => {
                    try {
                        this.loadGapUpsBackground();
                    } catch (error) {
                        console.error('Error in periodic gap-ups update:', error);
                    }
                }, 30000);
            }
        }
    });
    
    app.mount('#app');
    console.log('✅ Trading Advisor Dashboard initialized successfully');
} catch (error) {
    console.error('❌ Error initializing Vue.js app:', error);
    document.querySelector('#app').innerHTML = `
        <div class="min-h-screen bg-gray-900 text-white flex items-center justify-center">
            <div class="text-center">
                <h1 class="text-2xl font-bold mb-4 text-red-400">Error Loading Dashboard</h1>
                <p class="text-gray-400 mb-4">There was an error initializing the application.</p>
                <p class="text-sm text-gray-500">Check browser console for details.</p>
                <button onclick="location.reload()" class="mt-4 bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded">
                    Reload Page
                </button>
            </div>
        </div>
    `;
} 