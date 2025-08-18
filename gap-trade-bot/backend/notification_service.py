#!/usr/bin/env python3
"""
Notification Service for Trading Events
Sends SMS and Email notifications for gap-ups, bot entries/exits, and other trading events
"""

import os
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from logging_config import get_logger

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

class NotificationService:
    """Service for sending SMS and Email notifications"""
    
    def __init__(self):
        # Email configuration
        self.email_enabled = self._check_email_config()
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.email_username = os.getenv('EMAIL_USERNAME')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        
        # SMS configuration (using Twilio)
        self.sms_enabled = self._check_sms_config()
        self.twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')
        self.recipient_phone = os.getenv('RECIPIENT_PHONE')
        
        # Notification settings
        self.notify_gap_ups = os.getenv('NOTIFY_GAP_UPS', 'true').lower() == 'true'
        self.notify_bot_entries = os.getenv('NOTIFY_BOT_ENTRIES', 'true').lower() == 'true'
        self.notify_bot_exits = os.getenv('NOTIFY_BOT_EXITS', 'true').lower() == 'true'
        self.min_gap_percent = float(os.getenv('MIN_GAP_PERCENT', '25.0'))
        
        logger.info("✅ Notification service initialized")
        logger.info(f"📧 Email notifications: {'Enabled' if self.email_enabled else 'Disabled'}")
        logger.info(f"📱 SMS notifications: {'Enabled' if self.sms_enabled else 'Disabled'}")
        logger.info(f"🎯 Minimum gap for notifications: {self.min_gap_percent}%")
    
    def _check_email_config(self):
        """Check if email configuration is complete"""
        required_vars = ['EMAIL_USERNAME', 'EMAIL_PASSWORD', 'RECIPIENT_EMAIL']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.warning(f"⚠️ Email notifications disabled - missing: {', '.join(missing_vars)}")
            return False
        
        return True
    
    def _check_sms_config(self):
        """Check if SMS configuration is complete"""
        required_vars = ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_NUMBER', 'RECIPIENT_PHONE']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.warning(f"⚠️ SMS notifications disabled - missing: {', '.join(missing_vars)}")
            return False
        
        return True
    
    def send_email(self, subject, message, html_message=None):
        """Send email notification"""
        if not self.email_enabled:
            logger.debug("📧 Email notifications disabled")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_username
            msg['To'] = self.recipient_email
            msg['Subject'] = subject
            
            # Add text and HTML parts
            text_part = MIMEText(message, 'plain')
            msg.attach(text_part)
            
            if html_message:
                html_part = MIMEText(html_message, 'html')
                msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_username, self.email_password)
                server.send_message(msg)
            
            logger.info(f"📧 Email sent: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending email: {e}")
            return False
    
    def send_sms(self, message):
        """Send SMS notification using Twilio"""
        if not self.sms_enabled:
            logger.debug("📱 SMS notifications disabled")
            return False
        
        try:
            # Twilio API endpoint
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_account_sid}/Messages.json"
            
            # Request data
            data = {
                'From': self.twilio_phone_number,
                'To': self.recipient_phone,
                'Body': message
            }
            
            # Send SMS
            response = requests.post(
                url,
                data=data,
                auth=(self.twilio_account_sid, self.twilio_auth_token),
                timeout=10
            )
            
            if response.status_code == 201:
                logger.info(f"📱 SMS sent: {message[:50]}...")
                return True
            else:
                logger.error(f"❌ SMS failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending SMS: {e}")
            return False
    
    def notify_gap_up_detection(self, gap_up_data):
        """Send notification for gap-up detection"""
        if not self.notify_gap_ups:
            return
        
        ticker = gap_up_data['ticker']
        gap_percent = gap_up_data['gap_percent']
        
        # Only notify for significant gaps
        if gap_percent < self.min_gap_percent:
            return
        
        # Create notification message
        subject = f"🚨 GAP-UP ALERT: {ticker} +{gap_percent:.1f}%"
        
        message = f"""
🚨 REAL-TIME GAP-UP DETECTED!

Ticker: {ticker}
Gap: +{gap_percent:.1f}%
Price: ${gap_up_data['price']:.2f}
Previous Close: ${gap_up_data['previous_close']:.2f}
Change: +${gap_up_data['change']:.2f}

Company: {gap_up_data['company_name']}
Sector: {gap_up_data['sector']}
Market Cap: ${gap_up_data['market_cap']:,}

Detected: {gap_up_data['detected_at']}

🎯 This is a trading opportunity!
"""
        
        html_message = f"""
<html>
<body>
<h2 style="color: #ff6b6b;">🚨 REAL-TIME GAP-UP ALERT</h2>
<table style="border-collapse: collapse; width: 100%;">
<tr><td><strong>Ticker:</strong></td><td>{ticker}</td></tr>
<tr><td><strong>Gap:</strong></td><td style="color: #2ecc71;">+{gap_percent:.1f}%</td></tr>
<tr><td><strong>Price:</strong></td><td>${gap_up_data['price']:.2f}</td></tr>
<tr><td><strong>Previous Close:</strong></td><td>${gap_up_data['previous_close']:.2f}</td></tr>
<tr><td><strong>Change:</strong></td><td style="color: #2ecc71;">+${gap_up_data['change']:.2f}</td></tr>
<tr><td><strong>Company:</strong></td><td>{gap_up_data['company_name']}</td></tr>
<tr><td><strong>Sector:</strong></td><td>{gap_up_data['sector']}</td></tr>
<tr><td><strong>Market Cap:</strong></td><td>${gap_up_data['market_cap']:,}</td></tr>
</table>
<p><strong>Detected:</strong> {gap_up_data['detected_at']}</p>
<p style="color: #e74c3c; font-weight: bold;">🎯 This is a trading opportunity!</p>
</body>
</html>
"""
        
        # Send notifications
        self.send_email(subject, message, html_message)
        self.send_sms(f"🚨 GAP-UP: {ticker} +{gap_percent:.1f}% - ${gap_up_data['price']:.2f}")
    
    def notify_bot_entry(self, entry_data):
        """Send notification for bot position entry"""
        if not self.notify_bot_entries:
            return
        
        ticker = entry_data['ticker']
        quantity = entry_data['quantity']
        entry_price = entry_data['entry_price']
        strategy = entry_data.get('strategy', 'Unknown')
        
        subject = f"✅ BOT ENTRY: {ticker} - {strategy}"
        
        message = f"""
✅ BOT POSITION ENTERED

Ticker: {ticker}
Strategy: {strategy}
Quantity: {quantity}
Entry Price: ${entry_price:.2f}
Total Value: ${quantity * entry_price:.2f}

Entry Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🤖 Bot has entered a position!
"""
        
        html_message = f"""
<html>
<body>
<h2 style="color: #2ecc71;">✅ BOT POSITION ENTERED</h2>
<table style="border-collapse: collapse; width: 100%;">
<tr><td><strong>Ticker:</strong></td><td>{ticker}</td></tr>
<tr><td><strong>Strategy:</strong></td><td>{strategy}</td></tr>
<tr><td><strong>Quantity:</strong></td><td>{quantity}</td></tr>
<tr><td><strong>Entry Price:</strong></td><td>${entry_price:.2f}</td></tr>
<tr><td><strong>Total Value:</strong></td><td>${quantity * entry_price:.2f}</td></tr>
</table>
<p><strong>Entry Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<p style="color: #2ecc71; font-weight: bold;">🤖 Bot has entered a position!</p>
</body>
</html>
"""
        
        # Send notifications
        self.send_email(subject, message, html_message)
        self.send_sms(f"✅ BOT ENTRY: {ticker} {quantity}@${entry_price:.2f} - {strategy}")
    
    def notify_bot_exit(self, exit_data):
        """Send notification for bot position exit"""
        if not self.notify_bot_exits:
            return
        
        ticker = exit_data['ticker']
        quantity = exit_data['quantity']
        exit_price = exit_data['exit_price']
        entry_price = exit_data.get('entry_price', 0)
        pnl = exit_data.get('pnl', 0)
        pnl_percent = exit_data.get('pnl_percent', 0)
        exit_reason = exit_data.get('exit_reason', 'Unknown')
        
        # Determine emoji based on P&L
        pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
        
        subject = f"{pnl_emoji} BOT EXIT: {ticker} - {exit_reason}"
        
        message = f"""
{pnl_emoji} BOT POSITION EXITED

Ticker: {ticker}
Exit Reason: {exit_reason}
Quantity: {quantity}
Entry Price: ${entry_price:.2f}
Exit Price: ${exit_price:.2f}
P&L: ${pnl:.2f} ({pnl_percent:+.2f}%)

Exit Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🤖 Bot has exited the position!
"""
        
        html_message = f"""
<html>
<body>
<h2 style="color: {'#2ecc71' if pnl > 0 else '#e74c3c' if pnl < 0 else '#95a5a6'};">
{pnl_emoji} BOT POSITION EXITED
</h2>
<table style="border-collapse: collapse; width: 100%;">
<tr><td><strong>Ticker:</strong></td><td>{ticker}</td></tr>
<tr><td><strong>Exit Reason:</strong></td><td>{exit_reason}</td></tr>
<tr><td><strong>Quantity:</strong></td><td>{quantity}</td></tr>
<tr><td><strong>Entry Price:</strong></td><td>${entry_price:.2f}</td></tr>
<tr><td><strong>Exit Price:</strong></td><td>${exit_price:.2f}</td></tr>
<tr><td><strong>P&L:</strong></td><td style="color: {'#2ecc71' if pnl > 0 else '#e74c3c' if pnl < 0 else '#95a5a6'};">${pnl:.2f} ({pnl_percent:+.2f}%)</td></tr>
</table>
<p><strong>Exit Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<p style="color: #3498db; font-weight: bold;">🤖 Bot has exited the position!</p>
</body>
</html>
"""
        
        # Send notifications
        self.send_email(subject, message, html_message)
        self.send_sms(f"{pnl_emoji} BOT EXIT: {ticker} ${pnl:.2f} ({pnl_percent:+.1f}%) - {exit_reason}")
    
    def test_notifications(self):
        """Test notification functionality"""
        logger.info("🧪 Testing notification service...")
        
        # Test email
        if self.email_enabled:
            test_subject = "🧪 Test Email - Trading Advisor"
            test_message = "This is a test email from the Trading Advisor notification service."
            self.send_email(test_subject, test_message)
        
        # Test SMS
        if self.sms_enabled:
            test_sms = "🧪 Test SMS - Trading Advisor notification service is working!"
            self.send_sms(test_sms)
        
        logger.info("✅ Notification test completed")

# Global notification service instance
notification_service = NotificationService() 