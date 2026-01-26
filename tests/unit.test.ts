import { test, describe, before, after } from 'node:test';
import assert from 'node:assert';
import { DB } from '../src/db.js';
import { unlinkSync, existsSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';

describe('Database Tests', () => {
  const testDbPath = 'tests/data/unit.db';
  let db: DB;

  before(() => {
    if (existsSync(testDbPath)) {
      unlinkSync(testDbPath);
    }
    const sqlite = new DatabaseSync(testDbPath)
    const queries = [
      `pragma foreign_keys=ON`,
      `CREATE TABLE currency (id integer not null primary key autoincrement, code text not null, name text, symbol text, crypto bool not null default true)`,
      `CREATE VIEW rates as select date, currency.id, currency.code, value, timestamp from rate left join currency on rate.currency_id = currency.id`,
      `CREATE TABLE rate (date DATE not null, currency_id references currency(id), value real not null, timestamp DATETIME default CURRENT_TIMESTAMP, UNIQUE(date, currency_id))`,
      `CREATE INDEX idx_rate_date_currency_id on rate(date, currency_id)`,
      `CREATE INDEX idx_rate_date on rate(date)`,
      `insert into currency (code, name, symbol, crypto) VALUES
      ('USD', 'US Dollar', '$', false),
      ('GBP', 'GB Pound', 'gbp', false),
      ('EUR', 'Euro', 'e', false),
      ('BTC', 'BitCount', 'B', true)`
    ]
    for (const sql of queries) {
      sqlite.exec(sql)
    }
    sqlite.close()
    db = new DB(testDbPath);
  });

  after(() => {
    if (existsSync(testDbPath)) {
      unlinkSync(testDbPath);
    }
  });

  test('should insert and retrieve rates', () => {
    db.saveRates(
      { 'USD': 1.0, 'EUR': 0.9 }
    )

    const latest = db.getLatestRates();
    assert.strictEqual(latest.length == 2, true);

    const usd = latest.find(r => r.code === 'USD');
    assert.strictEqual(usd?.value, 1.0);
  });

  test('should insert and retrieve historical rates', () => {
    const yesterdayDate = new Date()
    yesterdayDate.setDate(new Date().getDate() - 1)
    const yesterday = yesterdayDate.toISOString().split('T')[0]
    db.saveRates(
      { 'USD': 1.0, 'EUR': 0.98 },
      yesterday
    )
    db.saveRates(
      { 'USD': 1.0, 'EUR': 0.9 }
    )


    assert.strictEqual(db.hasDataForDate(yesterday), true)

    const historical = db.getRatesForDate(yesterday)
    const usd = historical.find(r => r.code === 'EUR');
    assert.strictEqual(usd?.value, 0.98);
  });

  test('should filter by currency and date', () => {
    const yesterdayDate = new Date()
    yesterdayDate.setDate(new Date().getDate() - 1)
    const yesterday = yesterdayDate.toISOString().split('T')[0]
    db.saveRates(
      { 'USD': 1.0, 'EUR': 0.98, 'GBP': 0.89 },
      yesterday
    )
    db.saveRates(
      { 'USD': 1.0, 'EUR': 0.9, 'GBP': 0.8 }
    )


    assert.strictEqual(db.hasDataForDate(yesterday), true)

    const historical = db.getRatesForDate(yesterday, ['usd', 'eur'])
    assert.strictEqual(historical.length, 2);
    assert.ok(historical.find(r => r.code === 'EUR'))
    assert.ok(historical.find(r => r.code === 'EUR'))
    assert.ok(historical.find(r => r.code === 'EUR'))
  });

  test('should filter by currency', () => {
    const rates = { 'USD': 1.0, 'EUR': 0.9, 'GBP': 0.8 };
    db.saveRates(rates);

    const filtered = db.getLatestRates(['usd', 'eur']);
    assert.strictEqual(filtered.length, 2);
    assert.ok(filtered.find(r => r.code === 'USD'));
    assert.ok(filtered.find(r => r.code === 'EUR'));
    assert.ok(!filtered.find(r => r.code === 'GBP'));
  });

  test('should list all currencies', () => {
    const list = db.getCurrenies()
    assert.strictEqual(list.length, 4)
    assert.ok(list.find(c => c.code === 'USD'))
    assert.ok(list.find(c => c.code === 'EUR'))
    assert.ok(list.find(c => c.code === 'GBP'))
    assert.ok(list.find(c => c.code === 'BTC'))
  })

  test('should list fiat currencies', () => {
    const list = db.getCurrenies(false)
    assert.strictEqual(list.length, 3)
    assert.ok(list.find(c => c.code === 'USD'))
    assert.ok(list.find(c => c.code === 'EUR'))
    assert.ok(list.find(c => c.code === 'GBP'))
  })

  test('should list crypto currencies', () => {
    const list = db.getCurrenies(true)
    assert.strictEqual(list.length, 1)
    assert.ok(list.find(c => c.code === 'BTC'))
    assert.ok(!list.find(c => c.code === 'USD'))
  })
});
