# Exchange API Server

A minimal server that fetches currency rates from Currency Beacon twice a day and exposes them via a local API.

## Features
- Fetches data from Currency Beacon API at 10am and 6pm UTC.
- Stores historical data in a local SQLite database using `node:sqlite`.
- Exposes a `/latest` endpoint for fetching the most recent rates.
- Minimal third-party dependencies (uses Node.js v24 native features).

## Installation
```bash
npm install
```

## Running the Server
```bash
# Development (with tsx)
npm run dev

# Build and Start
npm run build
npm start
```

## API Usage
- `GET /latest`: Fetches all latest rates.
- `GET /latest?currencies=usd,eur`: Fetches latest rates for specific currencies (comma-separated).

## Running Tests
```bash
npm test
```
