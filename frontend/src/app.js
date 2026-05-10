/**
 * phrasaurus frontend entry point.
 *
 * Wires DOM events to the API client and animation helpers. No
 * side-effectful logic lives at module scope — everything starts from
 * `init()` which is called on DOMContentLoaded.
 */

import { resolveConfig } from './config.js';
import { pickPlaceholder } from './placeholders.js';
import { ApiError, fetchSynonym } from './api.js';

const INPUT_ELEMENT_PHRASE = 'Phrasaurus';

/**
 * Incrementally type a string into either the textContent of an element
 * or the placeholder of a textarea.
 *
 * Returns a cancel function so callers can preempt long animations
 * (e.g. when the user presses Enter mid-animation).
 *
 * @param {HTMLElement} element
 * @param {string} text
 * @param {number} delayMs
 * @returns {() => void} cancel
 */
function typeText(element, text, delayMs) {
  const isTextarea = element.tagName === 'TEXTAREA';
  if (isTextarea) {
    /** @type {HTMLTextAreaElement} */ (element).placeholder = '';
  } else {
    element.textContent = '';
  }

  let index = 0;
  let timerId = 0;

  const tick = () => {
    if (index >= text.length) return;
    const ch = text.charAt(index);
    if (isTextarea) {
      /** @type {HTMLTextAreaElement} */ (element).placeholder += ch;
    } else {
      element.textContent += ch;
    }
    index += 1;
    timerId = window.setTimeout(tick, delayMs);
  };

  tick();
  return () => window.clearTimeout(timerId);
}

/**
 * Resize a textarea so its height matches its content.
 *
 * @param {HTMLTextAreaElement} textarea
 */
function autogrow(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = `${textarea.scrollHeight}px`;
}

/**
 * Copy the output phrase text to the clipboard using the modern async
 * Clipboard API. Falls back silently if unavailable (e.g. insecure
 * contexts) — we prefer silent failure to a confusing legacy path.
 *
 * @param {string} text
 * @returns {Promise<boolean>} true if the copy succeeded.
 */
async function copyToClipboard(text) {
  if (!navigator.clipboard || typeof navigator.clipboard.writeText !== 'function') {
    return false;
  }
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/**
 * Hook up the UI on DOMContentLoaded.
 */
function init() {
  const config = resolveConfig(window.PHRASAURUS_CONFIG);

  /** @type {HTMLFormElement}     */ const form = document.getElementById('query-form');
  /** @type {HTMLTextAreaElement} */ const input = document.getElementById('phrase-input');
  /** @type {HTMLButtonElement}   */ const submitButton = document.getElementById('submit-button');
  /** @type {HTMLElement}         */ const buttonText = document.getElementById('button-text');
  /** @type {HTMLElement}         */ const loadingSpinner =
    document.getElementById('loading-spinner');
  /** @type {HTMLElement}         */ const outputPhrase = document.getElementById('output-phrase');

  /** Cancel handle for any in-flight typewriter animation. */
  let cancelTypewriter = () => {};

  /** Play the placeholder/landing animations. */
  const showLandingAnimations = () => {
    cancelTypewriter();
    cancelTypewriter = typeText(input, INPUT_ELEMENT_PHRASE, config.typewriterDelayMs);
    outputPhrase.classList.remove('hidden');
    typeText(outputPhrase, pickPlaceholder(), config.typewriterDelayMs);
  };

  /** Put the UI into the "waiting for OpenAI" state. */
  const setLoading = (isLoading) => {
    submitButton.disabled = isLoading;
    buttonText.classList.toggle('hidden', isLoading);
    loadingSpinner.classList.toggle('hidden', !isLoading);
  };

  /** Show an error in the output area. */
  const showError = (message) => {
    cancelTypewriter();
    outputPhrase.classList.remove('hidden');
    outputPhrase.textContent = message;
  };

  /** Handle a submit: validate, call the API, animate the result. */
  const handleSubmit = async (event) => {
    event.preventDefault();
    const phrase = input.value.trim();

    cancelTypewriter();
    outputPhrase.textContent = '';
    outputPhrase.classList.add('hidden');

    if (!phrase) {
      showLandingAnimations();
      return;
    }

    setLoading(true);
    try {
      const synonym = await fetchSynonym(phrase, {
        apiUrl: config.apiUrl,
        timeoutMs: config.requestTimeoutMs,
      });
      outputPhrase.classList.remove('hidden');
      cancelTypewriter = typeText(outputPhrase, synonym, config.typewriterDelayMs);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        showError('Invalid phrase — try something shorter.');
      } else {
        showError('Could not fetch a synonym. Please try again.');
      }
      console.error('fetchSynonym failed:', err);
    } finally {
      setLoading(false);
    }
  };

  // -- event wiring -----------------------------------------------------

  form.addEventListener('submit', handleSubmit);

  input.addEventListener('input', () => autogrow(input));

  // Submit on Enter without inserting a newline; allow Shift+Enter to be
  // a regular newline for users who want to edit multi-line phrases.
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  // Dim the placeholder after the first focus (replaces the legacy
  // `arguments.callee` pattern which is banned in strict mode).
  input.addEventListener(
    'focus',
    () => {
      input.classList.add('placeholder-dimmed');
    },
    { once: true }
  );

  const copyHandler = async () => {
    const text = outputPhrase.textContent ?? '';
    if (!text) return;
    const ok = await copyToClipboard(text);
    if (ok) {
      // Brief visual confirmation using a CSS flash.
      outputPhrase.animate([{ opacity: 1 }, { opacity: 0.6 }, { opacity: 1 }], { duration: 250 });
    }
  };
  outputPhrase.addEventListener('click', copyHandler);
  outputPhrase.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      copyHandler();
    }
  });

  // Kick off landing animation.
  showLandingAnimations();
}

// Export pure helpers so tests can import them without running init().
export { autogrow, copyToClipboard, typeText };

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
