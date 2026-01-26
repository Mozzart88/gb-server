import { readFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import { resolve } from 'node:path';

const DB_PATH = resolve(process.cwd(), 'data/data.db');
const db = new DatabaseSync(DB_PATH);

function populate() {
    console.log('Reading HTML files...');
    const fiatHtml = readFileSync('fiat.html', 'utf-8');
    const cryptoHtml = readFileSync('crypto.html', 'utf-8');

    console.log('Parsing fiat.html...');
    // Regex for fiat.html: Extracts code, name, and symbol
    const fiatRegex = /<tr>\s*<td><a href="\/rates\/USD\/([A-Z0-9]+)">\1<\/a>\s*<\/td>\s*<td class="text-muted">\s*<a href="\/rates\/USD\/\1">([\s\S]*?)<\/a>\s*<\/td>\s*<td class="text-muted">([\s\S]*?)<\/td>/gs;

    let fiatCount = 0;
    let match;
    while ((match = fiatRegex.exec(fiatHtml)) !== null) {
        const [, code, name, symbol] = match;
        const trimmedName = name.trim();
        const trimmedSymbol = symbol.trim();

        const existing = db.prepare('SELECT id FROM currency WHERE code = ?').get(code);
        if (existing) {
            db.prepare('UPDATE currency SET name = ?, symbol = ?, crypto = 0 WHERE code = ?').run(trimmedName, trimmedSymbol, code);
        } else {
            db.prepare('INSERT INTO currency (code, name, symbol, crypto) VALUES (?, ?, ?, 0)').run(code, trimmedName, trimmedSymbol);
        }
        fiatCount++;
    }
    console.log(`Updated/Inserted ${fiatCount} fiat currencies.`);

    console.log('Parsing crypto.html...');
    // Regex for crypto.html: Extracts name and code
    const cryptoRegex = /<div class="font-weight-medium">\s*([\s\S]*?)\s*<\/div>\s*<div class="text-muted">\s*([A-Z0-9_-]+)\s*<\/div>/gs;

    let cryptoCount = 0;
    while ((match = cryptoRegex.exec(cryptoHtml)) !== null) {
        const [, name, code] = match;
        const trimmedName = name.trim();
        const trimmedCode = code.trim();

        const existing = db.prepare('SELECT id FROM currency WHERE code = ?').get(trimmedCode);
        if (existing) {
            db.prepare('UPDATE currency SET name = ?, symbol = NULL, crypto = 1 WHERE code = ?').run(trimmedName, trimmedCode);
        } else {
            db.prepare('INSERT INTO currency (code, name, symbol, crypto) VALUES (?, ?, NULL, 1)').run(trimmedCode, trimmedName);
        }
        cryptoCount++;
    }
    console.log(`Updated/Inserted ${cryptoCount} crypto currencies.`);
}

try {
    populate();
    console.log('Population completed successfully.');
} catch (error) {
    console.error('An error occurred during population:', error);
    process.exit(1);
}
