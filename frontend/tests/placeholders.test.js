import { describe, expect, it } from 'vitest';
import { PLACEHOLDER_PHRASES, pickPlaceholder } from '../src/placeholders.js';

describe('PLACEHOLDER_PHRASES', () => {
  it('is non-empty and frozen', () => {
    expect(PLACEHOLDER_PHRASES.length).toBeGreaterThan(0);
    expect(Object.isFrozen(PLACEHOLDER_PHRASES)).toBe(true);
  });

  it('weights the tagline higher than the flavour phrases', () => {
    const tagline = 'A minimalistic thesaurus for phrases';
    const taglineCount = PLACEHOLDER_PHRASES.filter((p) => p === tagline).length;
    const flavourCount = PLACEHOLDER_PHRASES.length - taglineCount;
    expect(taglineCount).toBeGreaterThan(flavourCount);
  });
});

describe('pickPlaceholder', () => {
  it('returns the first element when random() returns 0', () => {
    const result = pickPlaceholder(() => 0, ['first', 'second', 'third']);
    expect(result).toBe('first');
  });

  it('returns the last element for a random value just below 1', () => {
    const result = pickPlaceholder(() => 0.9999, ['a', 'b', 'c']);
    expect(result).toBe('c');
  });

  it('uses the default source when none is provided', () => {
    const result = pickPlaceholder(() => 0);
    expect(PLACEHOLDER_PHRASES).toContain(result);
  });
});
