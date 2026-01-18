import { DatabaseSync } from 'node:sqlite';
import { resolve } from 'node:path';

const DB_PATH = process.env.DB_PATH || resolve(process.cwd(), 'data.db');

export interface Rate {
    currency: string;
    value: number;
    timestamp: string;
}

export class DB {
    private db: DatabaseSync;

    constructor(path: string = DB_PATH) {
        this.db = new DatabaseSync(path);
        this.init();
    }

    setPath(path: string) {
        // node:sqlite DatabaseSync doesn't have a close() in current experimental version easily?
        // Wait, it does have close() but it's not documented well or might be missing in some versions.
        // Actually, let's just create a new instance and delegate.
        this.db = new DatabaseSync(path);
        this.init();
    }

    private init() {
        this.db.exec(`
      CREATE TABLE IF NOT EXISTS rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        currency TEXT NOT NULL,
        value REAL NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
        this.db.exec(`CREATE INDEX IF NOT EXISTS idx_currency ON rates(currency)`);
        this.db.exec(`CREATE INDEX IF NOT EXISTS idx_timestamp ON rates(timestamp)`);
    }

    saveRates(rates: Record<string, number>) {
        const insert = this.db.prepare('INSERT INTO rates (currency, value) VALUES (?, ?)');
        for (const [currency, value] of Object.entries(rates)) {
            insert.run(currency, value);
        }
    }

    getLatestRates(currencies?: string[]): Rate[] {
        let query = `
      SELECT currency, value, timestamp 
      FROM rates 
      WHERE id IN (SELECT MAX(id) FROM rates GROUP BY currency)
    `;

        if (currencies && currencies.length > 0) {
            const upperCurrencies = currencies.map(c => c.toUpperCase());
            const placeholders = upperCurrencies.map(() => '?').join(',');
            query += ` AND UPPER(currency) IN (${placeholders})`;
            const stmt = this.db.prepare(query);
            return stmt.all(...upperCurrencies) as unknown as Rate[];
        }

        const stmt = this.db.prepare(query);
        return stmt.all() as unknown as Rate[];
    }
}

export const db = new DB();
