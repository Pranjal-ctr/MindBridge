import '@testing-library/jest-dom/vitest';

/**
 * jsdom implements no media queries at all, and `window.matchMedia` is simply
 * absent rather than returning a default. Anything that renders KioMascot —
 * which asks for `prefers-reduced-motion` at runtime, because its blink is a
 * JS timer no CSS variant could stop — therefore throws on mount.
 *
 * Reporting "no preference" matches the default a browser gives, so components
 * under test take their normal path. A test that cares about reduced motion
 * should stub this itself rather than rely on the default here.
 */
if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

/**
 * jsdom has no layout engine, so `Element.scrollIntoView` does not exist. The
 * chat transcript calls it on every message change to keep the newest reply in
 * view. A no-op is the honest stub: there is nothing to scroll.
 */
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
