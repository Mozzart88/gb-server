import { fetchLatestRates } from './client.js';

export function startScheduler() {
    console.log('[Scheduler] Started');

    // Rule: 10am and 6pm UTC
    // We check every minute if we should trigger
    setInterval(() => {
        const now = new Date();
        const hoursUTC = now.getUTCHours();
        const minutesUTC = now.getUTCMinutes();
        const secondsUTC = now.getUTCSeconds();

        // Trigger at 10:00:00 UTC and 18:00:00 UTC
        if (minutesUTC === 0 && secondsUTC === 0) {
            if (hoursUTC === 10 || hoursUTC === 18) {
                console.log(`[Scheduler] Triggering fetch at ${now.toISOString()}`);
                fetchLatestRates().catch(console.error);
            }
        }
    }, 1000); // Check every second to be precise on the "00" minute/second mark
}
