CREATE TABLE IF NOT EXISTS currency (id integer not null primary key autoincrement, code text not null, name text, symbol text, crypto bool not null default true);
CREATE VIEW IF NOT EXISTS rates as select date, currency.id, currency.code, value, timestamp from rate left join currency on rate.currency_id = currency.id
/* rates(date,id,code,value,timestamp) */;
CREATE TABLE IF NOT EXISTS rate (date DATE not null, currency_id references currency(id), value real not null, timestamp DATETIME default CURRENT_TIMESTAMP, UNIQUE(date, currency_id));
CREATE INDEX IF NOT EXISTS idx_rate_date_currency_id on rate(date, currency_id);
CREATE INDEX IF NOT EXISTS idx_rate_date on rate(date);
CREATE TABLE IF NOT EXISTS packages (
    id TEXT NOT NULL PRIMARY KEY,
    sender_id TEXT NOT NULL,
    iv TEXT NOT NULL,
    ciphertext TEXT NOT NULL,
    recipient_keys TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS package_recipients (
    package_id TEXT NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
    installation_id TEXT NOT NULL,
    encrypted_key TEXT NOT NULL,
    PRIMARY KEY (package_id, installation_id)
);
CREATE INDEX IF NOT EXISTS idx_package_recipients_installation ON package_recipients(installation_id);
CREATE INDEX IF NOT EXISTS idx_packages_updated_at ON packages(updated_at);
CREATE TABLE IF NOT EXISTS installations (timestamp DATETIME not null default CURRENT_TIMESTAMP, uuid text not null primary key, jwt text not null, installations integer not null default 1);
CREATE TABLE IF NOT EXISTS handshake (
  id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  uuid TEXT REFERENCES installations(uuid) NOT NULL,
  msg TEXT NOT NULL,
  created_at INTEGER NOT NULL DEFAULT (unixepoch(CURRENT_TIMESTAMP))
);
