import { createServer, IncomingMessage, ServerResponse } from 'node:http';
import { parse, UrlWithParsedQuery } from 'node:url';
import { db } from './db.js';
import { ParsedUrlQuery } from 'node:querystring';

const PORT = process.env.PORT || 3000;

function writeResponse(res: ServerResponse, status: number, data: { [key: string | symbol | number]: any }) {
  res.writeHead(status, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify(data))
}

function handleLatest(req: IncomingMessage, res: ServerResponse) {
  const parsedUrl = parse(req.url || '', true);
  const currenciesParam = parsedUrl.query.currencies as string | undefined;

  const currencies = currenciesParam ? currenciesParam.split(',').map(c => c.trim().toUpperCase()) : undefined;

  try {
    const rates = db.getLatestRates(currencies);
    writeResponse(res, 200, { rates })
  } catch (error) {
    console.error('Error handling /latest:', error);
    writeResponse(res, 500, { error: 'Internal Server Error' })
  }
}

function handleHistorical(query: ParsedUrlQuery, res: ServerResponse) {
  const date = query.date as string | undefined
  const currencies = query.currencies !== undefined ? (query.currencies as string).split(',').map(c => c.trim().toUpperCase()) : undefined

  if (date === undefined || date.length === 0) {
    writeResponse(res, 400, { error: 'Bad request' })
    return
  }

  try {
    const rates = db.getRatesForDate(date!, currencies)
    writeResponse(res, 200, { rates })
  } catch (error) {
    console.error('Error handling /historical', { error })
    writeResponse(res, 500, { error: 'Internal Server Error' })
  }

}

function handleCurrencies(res: ServerResponse) {
  try {
    const list = db.getCurrenies()
    writeResponse(res, 200, { list })
  } catch (error) {
    console.error('Error handling /currencies', { error })
    writeResponse(res, 500, { error: 'Internal Server Error' })
  }
}

export async function startServer(port?: number) {
  const listenPort = port || Number(PORT);
  const server = createServer((req, res) => {
    const parsedUrl = parse(req.url || '', true);

    if (req.method === 'GET') {
      switch (parsedUrl.pathname) {
        case '/latest': handleLatest(req, res);
          break
        case '/historical':
          handleHistorical(parsedUrl.query, res)
          break
        case '/currencies': handleCurrencies(res)
          break
        default:
          writeResponse(res, 404, { error: 'Not Found' })
      }
    } else {
      writeResponse(res, 404, { error: 'Not Found' })
    }
  });

  await new Promise<void>((resolve) => {
    const HOST = '127.0.0.1';
    server.listen(listenPort, HOST, () => {
      const addr = server.address();
      console.log(`[Server] Listening on http://${HOST}:${listenPort}`, addr);
      resolve();
    });
  });

  return server;
}
