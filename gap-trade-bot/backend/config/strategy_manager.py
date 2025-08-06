import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class StrategyConfigManager:
    """Manages unified strategy configuration for both frontend and backend"""
    
    def __init__(self, config_file: str = "config/strategy_settings.json"):
        self.config_file = config_file
        self.config_dir = Path(config_file).parent
        self.config_dir.mkdir(exist_ok=True)
        self._config = None
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self._config = json.load(f)
                logger.info(f"✅ Loaded strategy config from {self.config_file}")
            else:
                logger.warning(f"⚠️ Config file {self.config_file} not found, using defaults")
                self._config = self._get_default_config()
                self._save_config()
        except Exception as e:
            logger.error(f"❌ Error loading strategy config: {e}")
            self._config = self._get_default_config()
    
    def _save_config(self) -> None:
        """Save configuration to file"""
        try:
            self._config['last_updated'] = datetime.now().isoformat()
            with open(self.config_file, 'w') as f:
                json.dump(self._config, f, indent=4)
            logger.info(f"✅ Saved strategy config to {self.config_file}")
        except Exception as e:
            logger.error(f"❌ Error saving strategy config: {e}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "strategies": [
                {
                    "key": "breakOut",
                    "name": "Break Out",
                    "direction": "LONG",
                    "directionColor": "text-green-400",
                    "color": "text-blue-400",
                    "badgeClass": "bg-blue-100 text-blue-800",
                    "minGap": 25,
                    "target": 25,
                    "stopLoss": 15,
                    "availability": "Always",
                    "availabilityColor": "text-green-400",
                    "description": "Buy when price breaks above day high with volume confirmation",
                    "conditions": [
                        "Gap up above 25%",
                        "Price breaks above day high",
                        "Above VWAP",
                        "Sufficient volume"
                    ],
                    "backend_config": {
                        "target_multiplier": 1.25,
                        "stop_loss_multiplier": 0.85,
                        "min_gap_percentage": 25,
                        "volume_threshold": 4000000,
                        "confidence_threshold": 60
                    }
                },
                {
                    "key": "gapUpShort",
                    "name": "Gap Up Short",
                    "direction": "SHORT",
                    "directionColor": "text-red-400",
                    "color": "text-purple-400",
                    "badgeClass": "bg-purple-100 text-purple-800",
                    "minGap": 40,
                    "target": 15,
                    "stopLoss": 15,
                    "availability": "After 10 AM",
                    "availabilityColor": "text-yellow-400",
                    "description": "Short high gap-up stocks after 10 AM when they show reversal signs",
                    "conditions": [
                        "Gap up above 40%",
                        "After 10 AM",
                        "Below premarket high",
                        "Volume in range"
                    ],
                    "backend_config": {
                        "target_multiplier": 0.85,
                        "stop_loss_multiplier": 1.15,
                        "min_gap_percentage": 40,
                        "volume_min_multiplier": 2.0,
                        "volume_max_multiplier": 10.0,
                        "min_time": "10:00",
                        "max_distance_from_day_high": 10.0,
                        "confidence_threshold": 70
                    }
                }
            ],
            "last_updated": datetime.now().isoformat(),
            "version": "1.0"
        }
    
    def get_all_strategies(self) -> List[Dict[str, Any]]:
        """Get all strategies for frontend"""
        return self._config.get('strategies', [])
    
    def get_strategy_by_key(self, strategy_key: str) -> Optional[Dict[str, Any]]:
        """Get specific strategy by key"""
        for strategy in self._config.get('strategies', []):
            if strategy.get('key') == strategy_key:
                return strategy
        return None
    
    def get_backend_config(self, strategy_key: str) -> Optional[Dict[str, Any]]:
        """Get backend configuration for a strategy"""
        strategy = self.get_strategy_by_key(strategy_key)
        if strategy:
            return strategy.get('backend_config', {})
        return None
    
    def update_strategy(self, strategy_key: str, updates: Dict[str, Any]) -> bool:
        """Update strategy configuration"""
        try:
            strategy = self.get_strategy_by_key(strategy_key)
            if not strategy:
                logger.error(f"❌ Strategy {strategy_key} not found")
                return False
            
            # Update frontend parameters
            for key, value in updates.items():
                if key in ['minGap', 'target', 'stopLoss']:
                    strategy[key] = int(value)
                elif key in strategy:
                    strategy[key] = value
            
            # Update backend configuration based on frontend changes
            if 'target' in updates:
                target_percent = int(updates['target'])
                if strategy['direction'] == 'LONG':
                    strategy['backend_config']['target_multiplier'] = 1 + (target_percent / 100)
                else:  # SHORT
                    strategy['backend_config']['target_multiplier'] = 1 - (target_percent / 100)
            
            if 'stopLoss' in updates:
                stop_loss_percent = int(updates['stopLoss'])
                if strategy['direction'] == 'LONG':
                    strategy['backend_config']['stop_loss_multiplier'] = 1 - (stop_loss_percent / 100)
                else:  # SHORT
                    strategy['backend_config']['stop_loss_multiplier'] = 1 + (stop_loss_percent / 100)
            
            if 'minGap' in updates:
                strategy['backend_config']['min_gap_percentage'] = int(updates['minGap'])
            
            self._save_config()
            logger.info(f"✅ Updated strategy {strategy_key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating strategy {strategy_key}: {e}")
            return False
    
    def update_all_strategies(self, strategies: List[Dict[str, Any]]) -> bool:
        """Update all strategies at once"""
        try:
            self._config['strategies'] = strategies
            self._save_config()
            logger.info("✅ Updated all strategies")
            return True
        except Exception as e:
            logger.error(f"❌ Error updating all strategies: {e}")
            return False
    
    def reload_config(self) -> None:
        """Reload configuration from file"""
        self._load_config()

# Global instance
strategy_manager = StrategyConfigManager() 