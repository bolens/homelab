/** @type {import('stylelint').Config} */
export default {
  // Ignore generated artifacts.
  ignoreFiles: ['dist/**', 'coverage/**'],
  rules: {
    // Enforce project convention: BEM tokens under ui-* and asking-*.
    'selector-class-pattern': [
      /^(?:ui|asking|leaflet)(?:-[a-z0-9]+)*(?:__(?:[a-z0-9]+(?:-[a-z0-9]+)*))?(?:--[a-z0-9]+(?:-[a-z0-9]+)*)*$/,
      {
        message:
          'Expected class selector to follow ui-/asking- BEM naming (leaflet-* allowed for third-party overrides).',
        resolveNestedSelectors: true,
      },
    ],
    // Limit nested rule depth for readable, maintainable CSS.
    'max-nesting-depth': 3,
    // Cap chained selector parts to avoid overly contextual selectors.
    'selector-max-compound-selectors': 3,
    // Keep default specificity class-first and predictable.
    'selector-max-specificity': '0,3,0',
    // Avoid type-qualified classes like button.foo; prefer class-only selectors.
    'selector-no-qualifying-type': [true, { ignore: ['attribute'] }],
    // Normalize zero values to `0` instead of `0px`/`0rem`.
    'length-zero-no-unit': true,
    // Prefer minimal shorthand syntax to reduce declaration churn.
    'shorthand-property-no-redundant-values': true,
    // Catch accidental duplicate selectors that mask earlier declarations.
    'no-duplicate-selectors': true,
    // Catch duplicate declarations in a block unless values intentionally vary by fallback order.
    'declaration-block-no-duplicate-properties': [true, { ignore: ['consecutive-duplicates-with-different-values'] }],
    // Ensure keyframe steps are unique inside each animation definition.
    'keyframe-block-no-duplicate-selectors': true,
    // Ensure pseudo-elements use modern :: notation for consistency.
    'selector-pseudo-element-colon-notation': 'double',
    // Prevent repeated @import blocks in the same stylesheet.
    'no-duplicate-at-import-rules': true,
    // Avoid unknown animations due to typos in `animation-name`.
    'no-unknown-animations': true,
    // Require explicit notation for alpha values for readability.
    'alpha-value-notation': 'number',
    // Catch empty comments created during refactors.
    'comment-no-empty': true,
    // Disallow accidentally committed empty CSS sources.
    'no-empty-source': true,
    // Disallow JS-style // comments in CSS sources.
    'no-invalid-double-slash-comments': true,
    // Prevent typos in @media feature names.
    'media-feature-name-no-unknown': true,
    // Prevent unknown CSS properties from silently being ignored.
    'property-no-unknown': true,
    // Catch typos in CSS units.
    'unit-no-unknown': true,
    // Catch typos in CSS functions.
    'function-no-unknown': true,
    // Prevent accidentally committed empty declaration blocks.
    'block-no-empty': true,
    // Catch impossible nth-child/an+b selectors.
    'selector-anb-no-unmatchable': true,
    // Catch invalid media query syntax and ranges.
    'media-query-no-invalid': true,
    // Ensure custom properties are consumed via var(--token).
    'custom-property-no-missing-var-function': true,
    // Prevent accidental multiline strings in declarations.
    'string-no-newline': true,
    // Disallow shorthand declarations that accidentally override longhands.
    'declaration-block-no-shorthand-property-overrides': true,
    // Prevent duplicate family names in font stacks.
    'font-family-no-duplicate-names': true,
    // Enforce token naming for CSS custom properties.
    'custom-property-pattern': '^(?:color|accent|ui|asking|space|layout|font|radius|shadow|z)-[a-z0-9-]+$',
    // Require namespaced keyframes for collision-safe animations.
    'keyframes-name-pattern': '^(?:asking|ui)-[a-z0-9-]+$',
    // Prevent ordering/specificity regressions as styles grow.
    'no-descending-specificity': true,
    // Disallow raw hex values on rendered color properties; use tokens/functions.
    'declaration-property-value-disallowed-list': {
      '/^(?:color|background(?:-color)?|border(?:-[a-z]+)?-color|outline-color|text-decoration-color)$/i':
        [/#(?:[0-9a-fA-F]{3,8})\b/],
    },
  },
  overrides: [
    {
      // UI primitives should stay token-driven and avoid literal colors.
      files: ['src/ui/**/*.css'],
      rules: {
        // Disallow literal hex colors in UI primitives; use tokens/functions.
        'color-no-hex': true,
      },
    },
    {
      // Theme/palette files intentionally define raw custom properties and broad selector contexts.
      files: ['src/theme/**/*.css', 'src/index.css'],
      rules: {
        // Allow broader specificity in legacy/global style layers.
        'selector-max-specificity': null,
        // Allow longer selector compounds in legacy/global style layers.
        'selector-max-compound-selectors': null,
      },
    },
  ],
};
