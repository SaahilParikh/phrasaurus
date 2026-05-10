/**
 * Placeholder phrases shown when the user hasn't typed anything.
 *
 * The list is weighted toward the tagline ("A minimalistic thesaurus
 * for phrases") — it appears 5x more often than the flavour entries.
 * That's intentional: repeated exposures reinforce the product
 * positioning, and the flavour entries are there to be a fun
 * occasional surprise.
 */

const TAGLINE = 'A minimalistic thesaurus for phrases';

/** @type {readonly string[]} */
export const PLACEHOLDER_PHRASES = Object.freeze([
  TAGLINE,
  TAGLINE,
  TAGLINE,
  TAGLINE,
  TAGLINE,
  'A phrase synonym repository',
  'Phrase equivalent compendium',
  'A dinosaur that eats phrases',
]);

/**
 * Pick a random placeholder phrase.
 *
 * Accepts an injectable randomiser so tests can seed results deterministically.
 *
 * @param {() => number} [random=Math.random]
 * @param {readonly string[]} [source=PLACEHOLDER_PHRASES]
 * @returns {string}
 */
export function pickPlaceholder(random = Math.random, source = PLACEHOLDER_PHRASES) {
  const index = Math.floor(random() * source.length);
  return source[index];
}
