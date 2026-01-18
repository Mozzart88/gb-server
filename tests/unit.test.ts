import { test, describe, before, after } from 'node:test';
import assert from 'node:assert';
import { DB } from '../src/db.js';
import { unlinkSync, existsSync } from 'node:fs';

describe('Database Tests', () => {
    const testDbPath = 'test.db';
    let db: DB;

    before(() => {
        if (existsSync(testDbPath)) {
            unlinkSync(testDbPath);
        }
        db = new DB(testDbPath);
    });

    after(() => {
        if (existsSync(testDbPath)) {
            unlinkSync(testDbPath);
        }
    });

    test('should insert and retrieve rates', () => {
        const rates = { 'USD': 1.0, 'EUR': 0.9 };
        db.saveRates(rates);

        const latest = db.getLatestRates();
        assert.strictEqual(latest.length >= 2, true);

        const usd = latest.find(r => r.currency === 'USD');
        assert.strictEqual(usd?.value, 1.0);
    });

    test('should filter by currency', () => {
        const rates = { 'USD': 1.0, 'EUR': 0.9, 'GBP': 0.8 };
        db.saveRates(rates);

        const filtered = db.getLatestRates(['usd', 'eur']);
        assert.strictEqual(filtered.length, 2);
        assert.ok(filtered.find(r => r.currency === 'USD'));
        assert.ok(filtered.find(r => r.currency === 'EUR'));
        assert.ok(!filtered.find(r => r.currency === 'GBP'));
    });
});
