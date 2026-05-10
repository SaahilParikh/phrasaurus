import { describe, expect, it } from 'vitest';
import { CONFIG_DEFAULTS, resolveConfig } from '../src/config.js';

describe('resolveConfig', () => {
  it('returns defaults when no overrides are provided', () => {
    const cfg = resolveConfig();
    expect(cfg.apiUrl).toBe(CONFIG_DEFAULTS.apiUrl);
    expect(cfg.typewriterDelayMs).toBe(CONFIG_DEFAULTS.typewriterDelayMs);
    expect(cfg.requestTimeoutMs).toBe(CONFIG_DEFAULTS.requestTimeoutMs);
  });

  it('merges valid overrides over defaults', () => {
    const cfg = resolveConfig({
      apiUrl: 'http://localhost:3000',
      typewriterDelayMs: 5,
      requestTimeoutMs: 2000,
    });
    expect(cfg.apiUrl).toBe('http://localhost:3000');
    expect(cfg.typewriterDelayMs).toBe(5);
    expect(cfg.requestTimeoutMs).toBe(2000);
  });

  it('ignores invalid override types', () => {
    const cfg = resolveConfig({
      apiUrl: 42,
      typewriterDelayMs: 'fast',
      requestTimeoutMs: -10,
    });
    expect(cfg.apiUrl).toBe(CONFIG_DEFAULTS.apiUrl);
    expect(cfg.typewriterDelayMs).toBe(CONFIG_DEFAULTS.typewriterDelayMs);
    expect(cfg.requestTimeoutMs).toBe(CONFIG_DEFAULTS.requestTimeoutMs);
  });

  it('ignores empty-string apiUrl override', () => {
    const cfg = resolveConfig({ apiUrl: '' });
    expect(cfg.apiUrl).toBe(CONFIG_DEFAULTS.apiUrl);
  });

  it('returns a frozen object', () => {
    const cfg = resolveConfig();
    expect(Object.isFrozen(cfg)).toBe(true);
  });
});
