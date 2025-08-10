# 🚀 Quick Start Guide - Windows with DAS Trader Demo

## ⚡ 5-Minute Setup

### **1. Download & Install**
```cmd
# Download Python 3.8+ from python.org
# Download Git from git-scm.com
# Download DAS Trader Pro Demo from dastrader.com
```

### **2. Clone & Setup**
```cmd
# Open Command Prompt as Administrator
cd C:\
git clone https://github.com/your-username/trade-advisor-website.git
cd trade-advisor-website\gap-trade-bot\backend\bot

# Run automated setup
setup_windows.bat
```

### **3. Configure DAS Trader**
1. Launch DAS Trader Pro Demo
2. Go to Settings → API Configuration
3. Enable CMD API
4. Set port to 8080
5. Save settings

### **4. Test Everything**
```cmd
# Run all tests
test_windows.bat
```

### **5. Start Trading Bot**
```cmd
# Start the bot
start_bot_windows.bat
```

---

## 📋 What You Need

### **Software:**
- ✅ Python 3.8+
- ✅ Git
- ✅ DAS Trader Pro Demo
- ✅ Internet connection

### **APIs:**
- ✅ Polygon API key (for market data)
- ✅ DAS Demo (no real broker needed)

---

## 🔧 Configuration

### **Environment File (.env):**
```env
BROKER_TYPE=das
DAS_API_KEY=demo_key_123
DAS_SECRET_KEY=demo_secret_123
DAS_BASE_URL=localhost:8080
POLYGON_API_KEY=your_polygon_key_here
```

### **DAS Trader Settings:**
- Port: 8080
- API: CMD API
- Mode: Demo
- No real broker connection

---

## 🧪 Testing

### **Quick Tests:**
```cmd
# Test 1: DEMO vs Live comparison
python simple_demo.py

# Test 2: DAS connection
python test_das_demo.py

# Test 3: Full realistic testing
python run_realistic_testing.py
```

### **Expected Results:**
- ✅ All tests pass
- ✅ DAS connection successful
- ✅ Orders simulated in demo mode

---

## 🚨 Troubleshooting

### **Common Issues:**

**Python not found:**
```cmd
# Add to PATH manually
set PATH=%PATH%;C:\Python39;C:\Python39\Scripts
```

**DAS Connection failed:**
- Ensure DAS Trader is running
- Check CMD API is enabled
- Verify port 8080
- Restart DAS Trader

**Module errors:**
```cmd
# Reinstall requirements
pip install -r requirements_windows.txt --force-reinstall
```

---

## 📊 Monitoring

### **Log Files:**
- `trading_bot.log` - Main logs
- `gap_trade_bot_errors.log` - Errors
- `gap_trade_bot_performance.log` - Performance

### **Real-time Monitoring:**
```cmd
# Monitor logs
type trading_bot.log
```

---

## ⚠️ Important Notes

### **DEMO Mode:**
- No real money involved
- Perfect execution (not realistic)
- Use for strategy testing only

### **Risk Management:**
- Start with small orders
- Test thoroughly
- Monitor all trades
- Use stop-losses

---

## 🎯 Next Steps

1. **Test with small orders**
2. **Monitor performance**
3. **Adjust parameters**
4. **Consider live trading**
5. **Scale gradually**

---

## 📞 Support

- Check `WINDOWS_SETUP_GUIDE.md` for detailed instructions
- Review log files for errors
- Ensure all prerequisites installed
- Verify DAS Trader configuration

---

*This is a demo setup. For live trading, additional configuration and risk management required.*
