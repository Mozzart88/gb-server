import { startServer } from './server.js';
import { startScheduler } from './scheduler.js';
import { fetchLatestRates } from './client.js';

// Load .env manually if needed, or rely on node --env-file
// Given the environment, API_KEY is already in .env
// Node 20.6.0+ supports --env-file .env

import { fileURLToPath } from 'node:url';

async function bootstrap() {
  console.log('[App] Initializing...');

  // Start the scheduler
  startScheduler();

  // Start the server
  startServer();
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  bootstrap().catch(console.error);
}
