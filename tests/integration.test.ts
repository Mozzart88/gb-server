import { test, describe, before, after } from 'node:test';
import assert from 'node:assert';
import { startServer } from '../src/server.js';
import { db } from '../src/db.js';
import { Server } from 'node:http';

describe('Integration Tests', () => {
  let server: Server;
  const PORT = 3001;
  const BASE_URL = `http://127.0.0.1:${PORT}`;

  const fetchData = async (uri: string, expectedStatusCode: number): Promise<any> => {
    const res = await fetch(`${BASE_URL}${uri}`)
    assert.strictEqual(res.status, expectedStatusCode)
    return await res.json()
  }

  before(async () => {
    const TEST_DB = 'tests/data/integration.db';
    db.setPath(TEST_DB);
    server = await startServer(PORT);
  });

  after(() => {
    server.close();
  });

  test('GET /latest should return all rates', async () => {
    const data = await fetchData('/latest', 200)
    assert.ok(data.rates.length >= 3);
  });

  test('GET /latest?currencies=usd,eur should filter rates', async () => {
    const data = await fetchData(`/latest?currencies=usd,eur`, 200);
    assert.strictEqual(data.rates.length, 2);
    assert.ok(data.rates.find((r: any) => r.code === 'USD'));
    assert.ok(data.rates.find((r: any) => r.code === 'EUR'));
  });

  test('GET /historical should return 400', async () => {
    const res = await fetch(`${BASE_URL}/historical`)
    assert.strictEqual(res.status, 400)
  })

  test('GET /historical?date=2026-01-10 should return all rates for date', async () => {
    const data = await fetchData(`/historical?date=2026-01-10`, 200)
    assert.strictEqual(data.rates.length, 229)
    assert.ok(data.rates.every((r: any) => r.date === '2026-01-10'))
  })

  test('GET /historical?date=2026-01-10&currencies=usd,EUR should return filter rates for date', async () => {
    const data = await fetchData(`/historical?date=2026-01-10&currencies=usd,EUR`, 200)
    assert.strictEqual(data.rates.length, 2)
    assert.ok(data.rates.every((r: any) => r.date === '2026-01-10'))
    assert.ok(data.rates.find((r: any) => r.code = 'USD'))
    assert.ok(data.rates.find((r: any) => r.code = 'EUR'))
  })

  test('GET /currencies should return list of all suppored currencies', async () => {
    const data = await fetchData('/currencies', 200)
    assert.strictEqual(data.list.length, 311)
  })

  test.todo('GET /currencies?crypto=1 should return list of all cryptocurrencies', { skip: true }, async () => {
    const data = await fetchData('/currencies?crypto=1', 200)
    assert.ok(data.list.every((c: any) => c.crypto = true))
  })

  test.todo('GET /currencies?crypto=0 should return list of all fiat currencies', { skip: true }, async () => {
    const data = await fetchData('/currencies?crypto=0', 200)
    assert.ok(data.list.every((c: any) => c.crypto = false))
  })

  test('GET /unknown should return 404', async () => {
    const res = await fetch(`${BASE_URL}/unknown`);
    assert.strictEqual(res.status, 404);
  });
});
