import { describe, expect, it, vi } from 'vitest';
import { ApiError, fetchSynonym } from '../src/api.js';

/**
 * Minimal fetch-shaped stub.
 * @param {{ ok?: boolean, status?: number, jsonBody?: unknown, jsonThrows?: boolean }} spec
 */
function makeFetchStub(spec) {
  return vi.fn(async () => ({
    ok: spec.ok ?? true,
    status: spec.status ?? 200,
    json: async () => {
      if (spec.jsonThrows) throw new Error('bad json');
      return spec.jsonBody;
    },
  }));
}

describe('fetchSynonym', () => {
  it('returns the synonym on a 200 response', async () => {
    const fetchFn = makeFetchStub({ jsonBody: { synonym: 'ephemeral' } });

    const result = await fetchSynonym('fleeting', {
      apiUrl: 'https://x.example/api',
      timeoutMs: 1000,
      fetchFn,
    });

    expect(result).toBe('ephemeral');
    expect(fetchFn).toHaveBeenCalledOnce();
    const [url, init] = fetchFn.mock.calls[0];
    expect(url).toBe('https://x.example/api');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ phrase: 'fleeting' });
    expect(init.headers['Content-Type']).toBe('application/json');
  });

  it('throws ApiError on non-2xx', async () => {
    const fetchFn = makeFetchStub({ ok: false, status: 500, jsonBody: {} });

    await expect(
      fetchSynonym('x', { apiUrl: 'u', timeoutMs: 1000, fetchFn })
    ).rejects.toMatchObject({ name: 'ApiError', status: 500 });
  });

  it('throws ApiError when response is not JSON', async () => {
    const fetchFn = makeFetchStub({ jsonThrows: true });

    await expect(
      fetchSynonym('x', { apiUrl: 'u', timeoutMs: 1000, fetchFn })
    ).rejects.toMatchObject({ name: 'ApiError', message: /valid JSON/ });
  });

  it('throws ApiError when payload has no synonym', async () => {
    const fetchFn = makeFetchStub({ jsonBody: { other: 'thing' } });

    await expect(
      fetchSynonym('x', { apiUrl: 'u', timeoutMs: 1000, fetchFn })
    ).rejects.toMatchObject({ name: 'ApiError' });
  });

  it('throws a timeout ApiError when the request is aborted', async () => {
    const fetchFn = vi.fn(async (_url, init) => {
      return await new Promise((_resolve, reject) => {
        init.signal.addEventListener('abort', () => {
          const err = new Error('aborted');
          err.name = 'AbortError';
          reject(err);
        });
      });
    });

    await expect(fetchSynonym('x', { apiUrl: 'u', timeoutMs: 5, fetchFn })).rejects.toMatchObject({
      name: 'ApiError',
      message: /timed out/,
    });
  });

  it('throws a network ApiError on unexpected fetch failure', async () => {
    const fetchFn = vi.fn(async () => {
      throw new Error('DNS explosion');
    });

    await expect(
      fetchSynonym('x', { apiUrl: 'u', timeoutMs: 1000, fetchFn })
    ).rejects.toMatchObject({ name: 'ApiError', message: /Network/ });
  });
});

describe('ApiError', () => {
  it('carries status and cause', () => {
    const cause = new Error('underlying');
    const err = new ApiError('boom', { status: 418, cause });
    expect(err.name).toBe('ApiError');
    expect(err.status).toBe(418);
    expect(err.cause).toBe(cause);
  });
});
