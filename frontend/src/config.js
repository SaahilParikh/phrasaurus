/**
 * Runtime configuration for the phrasaurus frontend.
 *
 * Defaults are production, but the HTML page can inject overrides by
 * defining `window.PHRASAURUS_CONFIG` BEFORE loading app.js, e.g.:
 *
 *     <script>window.PHRASAURUS_CONFIG = { apiUrl: 'http://localhost:3000' };</script>
 *     <script type="module" src="./app.js"></script>
 *
 * This is deliberately a plain data module with no I/O so it's easy to
 * unit-test and to swap under test fixtures.
 */

const DEFAULTS = Object.freeze({
  apiUrl: 'https://phrasaurus.com/api/v1',
  typewriterDelayMs: 10,
  requestTimeoutMs: 15000,
});

/**
 * Merge window overrides over defaults. Overrides are shallow-merged and
 * validated minimally (non-empty string / positive integer).
 *
 * @param {Record<string, unknown> | undefined} overrides
 * @returns {Readonly<typeof DEFAULTS>}
 */
export function resolveConfig(overrides) {
  const merged = { ...DEFAULTS };

  if (overrides && typeof overrides === 'object') {
    if (typeof overrides.apiUrl === 'string' && overrides.apiUrl.length > 0) {
      merged.apiUrl = overrides.apiUrl;
    }
    if (Number.isInteger(overrides.typewriterDelayMs) && overrides.typewriterDelayMs >= 0) {
      merged.typewriterDelayMs = overrides.typewriterDelayMs;
    }
    if (Number.isInteger(overrides.requestTimeoutMs) && overrides.requestTimeoutMs > 0) {
      merged.requestTimeoutMs = overrides.requestTimeoutMs;
    }
  }

  return Object.freeze(merged);
}

export const CONFIG_DEFAULTS = DEFAULTS;
