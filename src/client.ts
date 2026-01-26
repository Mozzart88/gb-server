import { db } from './db.js';

const API_KEY = process.env.API_KEY;
const BASE_URL = 'https://api.currencybeacon.com/v1';


export async function fetchRatesForDate(date: string) {
    if (!API_KEY) {
        throw new Error('API_KEY environment variable is not set');
    }

    const url = `${BASE_URL}/historical?date=${date}`;

    try {
        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${API_KEY}`
            }
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (!data.rates) {
            throw new Error('Invalid response format: rates missing');
        }

        db.saveRates(data.rates, date);
        console.log(`[${new Date().toISOString()}] Successfully fetched and saved rates`);
    } catch (error) {
        console.error(`[${new Date().toISOString()}] Error fetching rates:`, error);
    }
}
export async function fetchLatestRates() {
    if (!API_KEY) {
        throw new Error('API_KEY environment variable is not set');
    }

    const url = `${BASE_URL}/latest`;

    try {
        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${API_KEY}`
            }
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (!data.rates) {
            throw new Error('Invalid response format: rates missing');
        }

        db.saveRates(data.rates);
        console.log(`[${new Date().toISOString()}] Successfully fetched and saved rates`);
    } catch (error) {
        console.error(`[${new Date().toISOString()}] Error fetching rates:`, error);
    }
}
