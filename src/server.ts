import { createServer, IncomingMessage, ServerResponse } from 'node:http';
import { parse } from 'node:url';
import { db } from './db.js';

const PORT = process.env.PORT || 3000;

function handleLatest(req: IncomingMessage, res: ServerResponse) {
    const parsedUrl = parse(req.url || '', true);
    const currenciesParam = parsedUrl.query.currencies as string | undefined;

    const currencies = currenciesParam ? currenciesParam.split(',').map(c => c.trim().toLowerCase()) : undefined;

    try {
        const rates = db.getLatestRates(currencies);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ rates }));
    } catch (error) {
        console.error('Error handling /latest:', error);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Internal Server Error' }));
    }
}

export async function startServer(port?: number) {
    const listenPort = port || Number(PORT);
    const server = createServer((req, res) => {
        const parsedUrl = parse(req.url || '', true);

        if (req.method === 'GET' && parsedUrl.pathname === '/latest') {
            handleLatest(req, res);
        } else {
            res.writeHead(404, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Not Found' }));
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
