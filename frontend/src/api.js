/**
 * Thin client for the phrasaurus Lambda endpoint.
 *
 * Responsibilities:
 *   - POST { phrase } to the configured URL.
 *   - Abort after `timeoutMs` to avoid a spinner that spins forever.
 *   - Translate non-2xx responses and network errors into typed Errors
 *     so the UI layer can react without parsing response shapes.
 */

/** Error thrown for any non-success outcome from the API. */
export class ApiError extends Error {
  /**
   * @param {string} message
   * @param {{ status?: number, cause?: unknown }} [options]
   */
  constructor(message, { status, cause } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    if (cause !== undefined) {
      this.cause = cause;
    }
  }
}

/**
 * Request a synonym for a user phrase.
 *
 * @param {string} phrase
 * @param {object} deps
 * @param {string} deps.apiUrl           Endpoint to POST to.
 * @param {number} deps.timeoutMs        Abort threshold.
 * @param {typeof fetch} [deps.fetchFn]  Injectable for tests.
 * @returns {Promise<string>}            The synonym text.
 * @throws {ApiError}
 */
export async function fetchSynonym(phrase, { apiUrl, timeoutMs, fetchFn = fetch }) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    response = await fetchFn(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phrase }),
      signal: controller.signal,
    });
  } catch (err) {
    if (err && err.name === 'AbortError') {
      throw new ApiError('Request timed out', { cause: err });
    }
    throw new ApiError('Network error', { cause: err });
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    throw new ApiError(`Request failed with status ${response.status}`, {
      status: response.status,
    });
  }

  /** @type {{ synonym?: unknown }} */
  let payload;
  try {
    payload = await response.json();
  } catch (err) {
    throw new ApiError('Response was not valid JSON', { cause: err });
  }

  if (typeof payload.synonym !== 'string' || payload.synonym.length === 0) {
    throw new ApiError('Response did not contain a synonym');
  }

  return payload.synonym;
}
