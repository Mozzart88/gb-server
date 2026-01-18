import { test, describe, before, after } from 'node:test';
import assert from 'node:assert';
import { startServer } from '../src/server.js';
import { db } from '../src/db.js';
import { unlinkSync, existsSync } from 'node:fs';
import { Server } from 'node:http';

describe('Integration Tests', () => {
    let server: Server;
    const PORT = 3001;
    const BASE_URL = `http://127.0.0.1:${PORT}`;

    before(async () => {
        const TEST_DB = 'test.db';
        if (existsSync(TEST_DB)) {
            unlinkSync(TEST_DB);
        }
        db.setPath(TEST_DB);
        server = await startServer(PORT);
        // Insert some mock data
        db.saveRates({ 'USD': 1.0, 'EUR': 0.9, 'BTC': 50000 });
    });

    after(() => {
        server.close();
        if (existsSync('test.db')) {
            unlinkSync('test.db');
        }
    });

    test('GET /latest should return all rates', async () => {
        const res = await fetch(`${BASE_URL}/latest`);
        assert.strictEqual(res.status, 200);
        const data = await res.json();
        assert.ok(data.rates.length >= 3);
    });

    test('GET /latest?currencies=usd,eur should filter rates', async () => {
        const res = await fetch(`${BASE_URL}/latest?currencies=usd,eur`);
        assert.strictEqual(res.status, 200);
        const data = await res.json();
        assert.strictEqual(data.rates.length, 2);
        assert.ok(data.rates.find((r: any) => r.currency === 'USD'));
        assert.ok(data.rates.find((r: any) => r.currency === 'EUR'));
    });

    test('GET /unknown should return 404', async () => {
        const res = await fetch(`${BASE_URL}/unknown`);
        assert.strictEqual(res.status, 404);
    });
});
