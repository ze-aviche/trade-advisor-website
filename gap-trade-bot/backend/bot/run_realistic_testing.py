#!/usr/bin/env python3
"""
Run Realistic Testing
Demonstrates the differences between DEMO and live trading
"""

import os
import sys
import asyncio
import signal

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from logging_config import get_logger
from realistic_testing import realistic_tester

logger = get_logger(__name__)

def signal_handler(signum, frame):
    """Handle interrupt signal"""
    logger.info("\n⚠️ Interrupt received, shutting down...")
    sys.exit(0)

async def main():
    """Main function"""
    try:
        logger.info("🧪 REALISTIC TRADING TESTING")
        logger.info("=" * 50)
        logger.info("This will demonstrate the differences between:")
        logger.info("• DEMO Mode: Perfect, instant execution")
        logger.info("• Live Trading: Realistic market conditions")
        logger.info("=" * 50)
        
        # Run comprehensive testing
        results = await realistic_tester.run_all_scenarios()
        
        # Run stress test
        await realistic_tester.stress_test(duration_minutes=1)
        
        logger.info("\n🎯 KEY INSIGHTS:")
        logger.info("1. DEMO mode gives false confidence")
        logger.info("2. Live trading has real risks and delays")
        logger.info("3. Always test with realistic conditions")
        logger.info("4. Start small and scale gradually")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run the testing
    asyncio.run(main())
