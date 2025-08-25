// Strategy Configuration
// This file contains all available trading strategies
// Add new strategies here to automatically display them in the frontend

const STRATEGY_CONFIG = {
    strategies: [
        {
            key: 'breakOut',
            name: 'Break Out',
            direction: 'LONG',
            directionColor: 'text-green-400',
            color: 'text-blue-400',
            badgeClass: 'bg-blue-100 text-blue-800',
            minGap: 25,
            target: 25,
            stopLoss: 15,
            availability: 'Always',
            availabilityColor: 'text-green-400',
            description: 'Buy when price breaks above day high with volume confirmation',
            conditions: [
                'Gap up above 0%',
                'Price breaks above day high',
                'Above VWAP',
                'Sufficient volume'
            ]
        },
        {
            key: 'gapUpShort',
            name: 'Gap Up Short',
            direction: 'SHORT',
            directionColor: 'text-red-400',
            color: 'text-purple-400',
            badgeClass: 'bg-purple-100 text-purple-800',
            minGap: 40,
            target: 15,
            stopLoss: 15,
            availability: 'After 10 AM',
            availabilityColor: 'text-yellow-400',
            description: 'Short high gap-up stocks after 10 AM when they show reversal signs',
            conditions: [
                'Gap up above 40%',
                'After 10 AM',
                'Below premarket high',
                'Volume in range'
            ]
        }
        // Add new strategies here:
        // {
        //     key: 'newStrategy',
        //     name: 'New Strategy',
        //     direction: 'LONG/SHORT',
        //     directionColor: 'text-green-400/text-red-400',
        //     color: 'text-color-400',
        //     badgeClass: 'bg-color-100 text-color-800',
        //     minGap: 30,
        //     target: 25,
        //     stopLoss: 10,
        //     availability: 'Market Hours',
        //     availabilityColor: 'text-blue-400',
        //     description: 'Description of the new strategy',
        //     conditions: [
        //         'Condition 1',
        //         'Condition 2',
        //         'Condition 3'
        //     ]
        // }
    ]
};

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = STRATEGY_CONFIG;
} else {
    window.STRATEGY_CONFIG = STRATEGY_CONFIG;
} 