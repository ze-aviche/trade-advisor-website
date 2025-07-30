# Trading Advisor Web Application

A modern web-based trading dashboard built with Flask backend and Vue.js frontend with **real-time gap-up stock detection** using Polygon API and **WebSocket-powered live price updates**.

## Features

- 📊 Real-time trading dashboard
- 📈 **Real gap-up stock detection** using Polygon API
- ⚡ **WebSocket-powered live price updates** every second
- 🔄 **Hybrid real-time system**: WebSocket + Enhanced Polling
- 💹 Trade history and performance tracking
- 🤖 AI-powered trading advisor chat
- 📱 Responsive design with modern UI
- 🔄 Real-time data updates with fallback to mock data
- 🎯 **Live price indicators** and real-time status monitoring

## Real-Time Architecture

The application implements a **hybrid real-time system** with three complementary approaches:

### 1. WebSocket-based Real-time Updates ⚡
- **Backend**: Flask-SocketIO server with real-time price broadcasting
- **Frontend**: Socket.IO client for live updates
- **Frequency**: Every 1 second for subscribed stocks
- **Features**: Live price changes, real-time indicators, automatic stock subscriptions

### 2. Enhanced Polling System 🔄
- **System Status**: Every 30 seconds
- **Dashboard Data**: Every 5 minutes
- **Gap-ups Data**: Every 30 seconds (enhanced from 5 minutes)
- **Real-time Status**: Live connection indicators

### 3. Hybrid Approach 🎯
- **WebSocket for Real-time**: Price updates every second
- **HTTP Polling for Gap-ups**: Detection and analysis
- **Smart Subscriptions**: Automatically subscribe to gap-up stocks
- **Fallback Support**: Graceful degradation to polling if WebSocket fails

## Project Structure

```
gap-trade-bot/
├── backend/
│   ├── app.py              # Flask API server with WebSocket support
│   ├── config.py           # Configuration settings
│   ├── gap_up_detector.py  # Real gap-up detection functions
│   ├── requirements.txt     # Python dependencies
│   └── env_example.txt     # Environment variables template
├── frontend/
│   ├── index.html          # Main HTML file with real-time UI
│   ├── app.js              # Vue.js application with WebSocket client
│   └── styles.css          # Custom styles
├── start.py                # Easy startup script
└── README.md              # This file
```

## Quick Start

### Option 1: Using the Startup Script (Recommended)

1. **Install Python dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

2. **Set up API keys (Optional):**
   ```bash
   # Copy the example environment file
   cp backend/env_example.txt backend/.env
   
   # Edit the .env file and add your Polygon API key
   # Get your free API key from: https://polygon.io/
   ```

3. **Run the startup script:**
   ```bash
   python start.py
   ```

4. **Choose option 3** to start both backend and frontend servers.

5. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:5000
   - WebSocket: ws://localhost:5000 (automatic)

### Option 2: Manual Setup

#### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up API keys (Optional):**
   ```bash
   cp env_example.txt .env
   # Edit .env and add your Polygon API key
   ```

4. **Start the Flask server with WebSocket support:**
   ```bash
   python app.py
   ```

The backend will be available at http://localhost:5000 with WebSocket support

#### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Start a simple HTTP server:**
   ```bash
   python -m http.server 3000
   ```

The frontend will be available at http://localhost:3000

## Real-Time Features

### WebSocket Implementation

#### Backend WebSocket Events:
- `connect` - Client connection established
- `disconnect` - Client disconnection
- `subscribe_stocks` - Subscribe to real-time updates for specific stocks
- `unsubscribe_stocks` - Unsubscribe from stock updates
- `price_update` - Broadcast real-time price updates

#### Frontend WebSocket Features:
- **Automatic Connection**: Connects to backend WebSocket on page load
- **Smart Subscriptions**: Automatically subscribes to gap-up stocks
- **Live Price Updates**: Receives price updates every second
- **Real-time Indicators**: Visual indicators for live data
- **Connection Status**: Shows WebSocket connection status

#### Real-time Price Updates:
```javascript
// Frontend WebSocket event handling
socket.on('price_update', (data) => {
    const { ticker, data: priceData } = data;
    // Update live prices and UI
    this.livePrices[ticker] = priceData;
    // Update gap-up stocks display
    this.updateStockPrice(ticker, priceData);
});
```

### Live Data Display

The gap-ups page now displays comprehensive real-time information:

#### Data Fields:
- **Ticker**: Stock symbol
- **Company Name**: Full company name
- **Price**: Current live price with real-time updates
- **Change%**: Live price change percentage
- **Gap%**: Gap-up percentage from previous close
- **Volume**: Trading volume with formatting
- **Market Cap**: Formatted market capitalization (B/M/K/T)
- **Sector**: Company sector information
- **List Date**: Stock listing date

#### Real-time Features:
- **Live Price Indicators**: Color-coded price changes
- **Real-time Updates**: Prices update every second
- **Visual Indicators**: Animated live data indicators
- **Connection Status**: Shows WebSocket connection status
- **Automatic Subscriptions**: Subscribes to gap-up stocks automatically

### Enhanced Gap-ups Display

The gap-ups section now shows detailed stock information with real-time updates:

```html
<!-- Real-time price display -->
<div class="text-2xl font-bold" :class="getPriceColor(stock)">
    ${{ stock.price }}
    <span v-if="livePrices[stock.ticker]" class="text-sm ml-1" 
          :class="getPriceChangeColor(livePrices[stock.ticker].change_percent)">
        {{ livePrices[stock.ticker].change_percent >= 0 ? '+' : '' }}{{ livePrices[stock.ticker].change_percent.toFixed(2) }}%
    </span>
</div>

<!-- Live price indicator -->
<div v-if="livePrices[stock.ticker]" class="mt-3 p-2 bg-blue-900 bg-opacity-20 rounded border border-blue-500">
    <div class="flex items-center justify-between text-xs">
        <span class="text-blue-300">Live Price:</span>
        <span class="font-bold" :class="getPriceChangeColor(livePrices[stock.ticker].change_percent)">
            ${{ livePrices[stock.ticker].price }}
            <span class="ml-1">
                {{ livePrices[stock.ticker].change_percent >= 0 ? '+' : '' }}{{ livePrices[stock.ticker].change_percent.toFixed(2) }}%
            </span>
        </span>
    </div>
</div>
```

## Real Gap-Up Detection

The application includes **real-time gap-up stock detection** using the Polygon API:

### Features:
- **Real-time gap-up detection** from live market data
- **Automatic filtering** for common stocks (CS type)
- **Price validation** (stocks must be $1+)
- **Gap percentage calculation** (2%+ gaps)
- **Fallback to mock data** when API key is not available
- **Real-time price updates** for detected gap-up stocks

### How it works:
1. Fetches current gainers from Polygon API
2. Filters for common stocks with $1+ previous close
3. Calculates gap percentage: `(current_price - previous_close) / previous_close * 100`
4. Returns stocks with 2%+ gaps
5. Includes company details, market cap, sector info
6. **Automatically subscribes to real-time updates** for gap-up stocks

### API Key Setup:
1. Get a free API key from [Polygon.io](https://polygon.io/)
2. Create `.env` file in the `backend` directory
3. Add: `POLYGON_API_KEY=your-api-key-here`
4. Restart the application

## API Endpoints

- `GET /api/health` - Health check with real data and WebSocket status
- `GET /api/gap-ups` - Get real gap-up stocks (or mock data)
- `GET /api/trades` - Get trade history
- `POST /api/analyze` - Analyze specific stocks
- `POST /api/start-session` - Start AI chat session
- `POST /api/send-message` - Send message to AI advisor
- `GET /api/system-status` - Get system status and API key status
- `GET /api/market-data/<ticker>` - Get real-time market data for ticker

### WebSocket Events:
- `connect` - Client connected
- `disconnect` - Client disconnected
- `subscribe_stocks` - Subscribe to stock updates
- `unsubscribe_stocks` - Unsubscribe from stock updates
- `price_update` - Real-time price update
- `subscribed` - Confirmation of stock subscription
- `unsubscribed` - Confirmation of stock unsubscription

## Features

### Dashboard
- Overview of trading statistics
- Real-time gap-up stocks with live price updates
- Performance charts
- System status monitoring with WebSocket connection status
- Real data availability indicator
- Live connection indicators

### Gap-Ups Analysis
- **Real gap-up stocks** from live market data
- **Live price updates** every second
- Price and volume information with real-time changes
- Gap percentage calculations
- Company details and sector info
- Automatic refresh functionality
- **Real-time price indicators** and visual updates

### Trade History
- Complete trade history
- Performance summary
- P&L tracking
- Win/loss statistics

### AI Chat
- Interactive trading advisor
- Market analysis
- Trading recommendations
- Risk management advice

### Real-time Status Monitoring
- **WebSocket Connection Status**: Shows live connection status
- **Real Data Availability**: Indicates if real data is available
- **Active Stock Subscriptions**: Shows number of stocks being tracked
- **Live Data Indicators**: Animated indicators for real-time data

## Configuration

The application uses environment variables for configuration. Create a `.env` file in the backend directory:

```env
FLASK_DEBUG=True
SECRET_KEY=your-secret-key
POLYGON_API_KEY=your-polygon-api-key  # For real gap-up detection
GOOGLE_API_KEY=your-google-api-key
ALPACA_API_KEY=your-alpaca-api-key
ALPACA_SECRET_KEY=your-alpaca-secret-key
```

### API Key Sources:
- **Polygon API**: [polygon.io](https://polygon.io/) (Free tier available)
- **Google API**: [Google Cloud Console](https://console.cloud.google.com/)
- **Alpaca API**: [alpaca.markets](https://alpaca.markets/)

## Development

### Backend Development
- Flask-based REST API with WebSocket support
- Flask-SocketIO for real-time communication
- CORS enabled for frontend communication
- **Real Polygon API integration**
- **Background price update threads**
- Fallback to mock data when APIs unavailable

### Frontend Development
- Vue.js 3 for reactive UI
- Socket.IO client for WebSocket communication
- Tailwind CSS for styling
- Chart.js for data visualization
- **Real-time price update handling**
- **Live data indicators and animations**

### WebSocket Architecture

#### Backend WebSocket Flow:
1. **Client Connection**: Frontend connects to WebSocket server
2. **Stock Subscription**: Frontend subscribes to gap-up stocks
3. **Price Updates**: Backend fetches real-time prices every second
4. **Broadcasting**: Backend broadcasts price updates to all clients
5. **UI Updates**: Frontend updates UI with live price data

#### Frontend WebSocket Flow:
1. **Connection**: Automatically connects to WebSocket server
2. **Event Listeners**: Listens for price updates and connection events
3. **Stock Management**: Manages stock subscriptions and unsubscriptions
4. **UI Updates**: Updates gap-up display with live prices
5. **Status Monitoring**: Shows connection and data status

## Troubleshooting

### Common Issues

1. **Port already in use:**
   - Change the port in the respective server configuration
   - Kill processes using the ports: `lsof -ti:5000 | xargs kill -9`

2. **CORS errors:**
   - Ensure the backend CORS configuration includes your frontend URL
   - Check that both servers are running

3. **WebSocket connection issues:**
   - Check if Socket.IO client is loaded properly
   - Verify WebSocket server is running on correct port
   - Check browser console for WebSocket errors

4. **Module not found errors:**
   - Install dependencies: `pip install -r backend/requirements.txt`
   - Check Python version compatibility

5. **Polygon API errors:**
   - Verify your API key is correct
   - Check API key permissions and rate limits
   - Application will fallback to mock data if API fails

6. **Real-time updates not working:**
   - Check WebSocket connection status in browser console
   - Verify backend is running with WebSocket support
   - Check if stocks are being subscribed to properly

7. **Real data not showing:**
   - Check if `POLYGON_API_KEY` is set in `.env` file
   - Verify API key is valid
   - Check backend logs for API errors

### Logs

- Backend logs are displayed in the terminal where you started the Flask server
- WebSocket connection logs show client connections and disconnections
- Frontend errors can be viewed in the browser's developer console
- API status is shown in the system status endpoint

### WebSocket Debugging

To debug WebSocket issues:

1. **Check Browser Console:**
   ```javascript
   // Check WebSocket connection status
   console.log('Socket connected:', this.socketConnected);
   console.log('Subscribed stocks:', this.subscribedStocks);
   ```

2. **Check Backend Logs:**
   - Look for WebSocket connection messages
   - Check for price update thread status
   - Verify stock subscription logs

3. **Test WebSocket Connection:**
   ```bash
   # Test WebSocket endpoint
   curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==" http://localhost:5000/socket.io/
   ```

## Performance

### Real-time Update Performance:
- **Price Updates**: Every 1 second for subscribed stocks
- **System Status**: Every 30 seconds
- **Gap-up Detection**: Every 30 seconds
- **Dashboard Data**: Every 5 minutes

### WebSocket Performance:
- **Connection Management**: Automatic reconnection on disconnection
- **Stock Subscriptions**: Smart subscription management
- **Memory Management**: Efficient price caching and updates
- **Error Handling**: Graceful fallback to polling on WebSocket failure

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly, especially WebSocket functionality
5. Submit a pull request

## License

This project is for educational and demonstration purposes.

## Support

For issues and questions, please check the troubleshooting section above or create an issue in the repository. 