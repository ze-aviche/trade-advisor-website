# 🖥️ Windows Setup Guide for Trading Bot with DAS Trader Demo

## 📋 Prerequisites

### **Required Software:**
- **Python 3.8+** (Download from python.org)
- **Git** (Download from git-scm.com)
- **DAS Trader Pro** (Demo version)
- **Visual Studio Code** (Optional, for editing)

### **System Requirements:**
- Windows 10/11 (64-bit)
- 8GB RAM minimum
- 10GB free disk space
- Internet connection

---

## 🚀 Step-by-Step Installation

### **Step 1: Install Python**
1. Go to [python.org](https://www.python.org/downloads/)
2. Download Python 3.8+ for Windows
3. **IMPORTANT**: Check "Add Python to PATH" during installation
4. Verify installation:
   ```cmd
   python --version
   pip --version
   ```

### **Step 2: Install Git**
1. Go to [git-scm.com](https://git-scm.com/download/win)
2. Download Git for Windows
3. Install with default settings
4. Verify installation:
   ```cmd
   git --version
   ```

### **Step 3: Clone the Repository**
```cmd
# Open Command Prompt as Administrator
cd C:\
git clone https://github.com/your-username/trade-advisor-website.git
cd trade-advisor-website
```

### **Step 4: Set Up Python Environment**
```cmd
# Navigate to the bot directory
cd gap-trade-bot\backend\bot

# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### **Step 5: Install DAS Trader Pro Demo**
1. Go to [DAS Trader website](https://www.dastrader.com/)
2. Download DAS Trader Pro Demo
3. Install with default settings
4. Launch DAS Trader Pro
5. **Enable CMD API**:
   - Go to Settings → API Configuration
   - Enable CMD API
   - Set port to 8080 (default)
   - Save settings

### **Step 6: Configure Environment Variables**
Create a `.env` file in `gap-trade-bot\backend\bot\`:

```env
# Broker Configuration
BROKER_TYPE=das

# DAS Demo Configuration
DAS_API_KEY=demo_key_123
DAS_SECRET_KEY=demo_secret_123
DAS_BASE_URL=localhost:8080

# Polygon API (for market data)
POLYGON_API_KEY=your_polygon_api_key_here

# Leave FIX settings empty for DEMO
DAS_FIX_HOST=
DAS_FIX_PORT=
DAS_USERNAME=
DAS_PASSWORD=

# Trading Parameters
DEFAULT_VOLUME=100
STOP_LOSS_PERCENTAGE=15.0
MAX_POSITIONS=5

# Logging
LOG_LEVEL=INFO
```

### **Step 7: Test DAS Connection**
```cmd
# Make sure DAS Trader is running
python test_das_demo.py
```

### **Step 8: Run Realistic Testing**
```cmd
# Test bot behavior with realistic conditions
python simple_demo.py
```

---

## 🔧 Configuration Details

### **DAS Trader Demo Settings:**
- **Port**: 8080 (default)
- **API Type**: CMD API
- **Demo Mode**: Enabled
- **No Real Broker**: Connected to demo only

### **Bot Configuration:**
- **Trading Mode**: DEMO
- **Risk Management**: Conservative
- **Position Sizing**: Small for testing
- **Logging**: Detailed

---

## 🧪 Testing Your Setup

### **Test 1: Basic Connection**
```cmd
python test_das_demo.py
```
Expected output: Connection successful, orders simulated

### **Test 2: Realistic Conditions**
```cmd
python simple_demo.py
```
Expected output: DEMO vs Live comparison

### **Test 3: Full Bot Test**
```cmd
python run_realistic_testing.py
```
Expected output: Comprehensive testing results

---

## 🚨 Troubleshooting

### **Common Issues:**

**1. Python not found:**
```cmd
# Add Python to PATH manually
set PATH=%PATH%;C:\Python39;C:\Python39\Scripts
```

**2. DAS Connection failed:**
- Ensure DAS Trader is running
- Check CMD API is enabled
- Verify port 8080 is not blocked
- Restart DAS Trader

**3. Module not found:**
```cmd
# Reinstall requirements
pip install -r requirements.txt --force-reinstall
```

**4. Permission errors:**
- Run Command Prompt as Administrator
- Check Windows Defender settings
- Allow Python through firewall

---

## 📊 Monitoring and Logs

### **Log Files:**
- `trading_bot.log` - Main bot logs
- `gap_trade_bot_errors.log` - Error logs
- `gap_trade_bot_performance.log` - Performance metrics

### **Real-time Monitoring:**
```cmd
# Monitor logs in real-time
tail -f trading_bot.log
```

---

## 🔄 Daily Operations

### **Starting the Bot:**
```cmd
# Activate environment
venv\Scripts\activate

# Start bot
python run_agent.py
```

### **Stopping the Bot:**
```cmd
# Press Ctrl+C to stop
# Or use task manager to kill Python processes
```

### **Updating the Bot:**
```cmd
# Pull latest changes
git pull origin main

# Reinstall requirements if needed
pip install -r requirements.txt
```

---

## ⚠️ Important Notes

### **DEMO Mode Limitations:**
- No real money involved
- Perfect execution (not realistic)
- No slippage or rejections
- Use for strategy testing only

### **Risk Management:**
- Start with small position sizes
- Test thoroughly before live trading
- Monitor all trades carefully
- Use stop-losses always

### **Performance:**
- Monitor CPU and memory usage
- Keep DAS Trader running
- Ensure stable internet connection
- Regular log rotation

---

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section
2. Review log files for errors
3. Ensure all prerequisites are installed
4. Verify DAS Trader configuration

---

## 🎯 Next Steps

After successful setup:
1. Test with small orders
2. Monitor bot performance
3. Adjust risk parameters
4. Consider live trading setup
5. Implement additional strategies

---

*This guide assumes you have basic Windows and Python knowledge. For advanced configuration, refer to the main documentation.*
