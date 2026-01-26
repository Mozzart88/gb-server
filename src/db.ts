import { DatabaseSync } from 'node:sqlite';
import { resolve } from 'node:path';

const DB_PATH = process.env.DB_PATH || resolve(process.cwd(), 'data/data.db');

export interface Rate {
  code: string;
  value: number;
  timestamp: string;
  date: string
}

export interface Currency {
  id: number
  code: string
  name: string
  symbol: string
  crypto: boolean
}

export class DB {
  private db: DatabaseSync;

  constructor(path: string = DB_PATH) {
    this.db = new DatabaseSync(path);
    this.init()
  }

  setPath(path: string) {
    if (this.db.isOpen)
      this.db.close()
    this.db = new DatabaseSync(path);
    this.init()
  }

  private init() {
    this.db.exec(`pragma foreign_keys=ON`)
  }


  saveRates(rates: Record<string, number>, date?: string) {
    const targetDate = date || new Date().toISOString().split('T')[0];
    const sql = `
      INSERT OR REPLACE INTO rate (currency_id, value, date) VALUES
        ((SELECT id  FROM currency WHERE code = upper(?)), ?, ?)`
    const insert = this.db.prepare(sql);
    for (const [currency, value] of Object.entries(rates)) {
      insert.run(currency, value, targetDate);
    }
  }

  hasDataForDate(date: string): boolean {
    const stmt = this.db.prepare('SELECT 1 FROM rates WHERE date = ? LIMIT 1');
    const result = stmt.get(date);
    return !!result;
  }

  getCurrenies(crypto?: boolean): Currency[] {
    const where = crypto !== undefined ? `WHERE crypto = ?` : ''
    const sql = `SELECT * FROM currency ${where}`
    const stmt = this.db.prepare(sql)
    if (crypto === undefined)
      return stmt.all() as unknown as Currency[]
    return stmt.all(crypto ? 1 : 0) as unknown as Currency[]
  }

  getRatesForDate(date: string, currencies?: string[]): Rate[] {
    let query = `
      SELECT code, value, timestamp, date
      FROM rates 
      WHERE date = ?
    `;

    if (currencies && currencies.length > 0) {
      const upperCurrencies = currencies.map(c => c.toUpperCase());
      const placeholders = upperCurrencies.map(() => '?').join(',');
      query += ` AND code IN (${placeholders})`;
      const stmt = this.db.prepare(query);
      return stmt.all(date, ...upperCurrencies) as unknown as Rate[];
    }

    const stmt = this.db.prepare(query);
    return stmt.all(date) as unknown as Rate[];

  }

  getLatestRates(currencies?: string[]): Rate[] {
    let query = `
      SELECT code, value, timestamp, date
      FROM rates 
      WHERE date = (select date from rate order by date desc limit 1)
    `;

    if (currencies && currencies.length > 0) {
      const upperCurrencies = currencies.map(c => c.toUpperCase());
      const placeholders = upperCurrencies.map(() => '?').join(',');
      query += ` AND code IN (${placeholders})`;
      const stmt = this.db.prepare(query);
      return stmt.all(...upperCurrencies) as unknown as Rate[];
    }

    const stmt = this.db.prepare(query);
    return stmt.all() as unknown as Rate[];
  }
}

export const db = new DB();
