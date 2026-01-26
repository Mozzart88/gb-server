import { fetchRatesForDate } from './client.js';
import { db } from './db.js';

async function wait(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export async function fillMissingRates() {
  const latest = db.getLatestRates()[0]?.date || '2025'
  const startDate = new Date(latest);
  const endDate = new Date();
  const currentDate = new Date(startDate);
  console.log(startDate)

  while (currentDate <= endDate) {
    const dateStr = currentDate.toISOString().split('T')[0];
    await fetchRatesForDate(dateStr);
    currentDate.setDate(currentDate.getDate() + 1);

    await wait(5 * 1000);
  }
}

await fillMissingRates()
