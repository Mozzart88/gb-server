import { describe, test, mock, before, beforeEach } from 'node:test'
import assert from 'node:assert'


describe('scheduler', async () => {
  const mockDB = await import('../src/db.ts').then(exprt => exprt.db)
  const mockFetchLatestRates = mock.fn()
  let startScheduler
  before(async () => {
    mock.module('../src/client.ts', {
      namedExports: {
        fetchLatestRates: mockFetchLatestRates
      }
    })

    mockDB.getLatestRates = () => {
      return [{
        timestamp: '2026-01-10 09:59:59',
        code: 'USD',
        date: '2026-01-10 09:59:59',
        value: 1.0,
      }]
    }
    mock.method(mockDB, 'getLatestRates')

    mock.module('../src/db.ts', {
      namedExports: {
        db: mockDB
      }
    });

    ({ startScheduler } = await import('../src/scheduler.ts'))
  })

  test('', async () => {
    startScheduler()
  })
})
