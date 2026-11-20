# Visual workflow

1. **Baseline.** Use the documented development command and installed Playwright setup. Open approved local routes with synthetic fixtures. Save screenshots to the repository's ignored output location. Record route, fixture, browser, viewport, theme, locale, and state. Wait for specific page readiness and font loading before capture.
2. **Implement.** Reuse existing components and tokens. Keep route behavior, form semantics, and permission conditions intact. Keep the diff inside delegated ownership.
3. **Verify.** Capture the same states after editing at about 390, 768, and 1440 CSS pixels. Exercise supported light and dark themes and representative locales, including longer translations. Inspect headings, alignment, overflow, wrapping, density, action order, and default, loading, empty, error, disabled, and validation states.
4. **Correct.** Compare the images at matching conditions with the baseline and brief. Fix unintended changes within two correction passes, then report residual defects. Update an approved screenshot baseline only after reviewing and explaining the differences.
5. **Check behavior.** Run the repository checks and existing Playwright routes. Verify navigation, critical form submissions and errors, and permission-dependent visibility and actions using authorized local fixtures. Report exact commands, exit codes, counts, and gaps.

## Responsive and accessibility checks

- Test narrow layouts, zoom, longer strings, and any supported right-to-left locale. Check that essential actions remain reachable without horizontal scrolling or clipping.
- Traverse navigation and controls by keyboard. Check visible focus, logical order, and focus entry and return for dialogs. Exercise Escape and dismissal where specified.
- Check semantic headings, landmarks, control names, form labels, error associations, and status announcements. Verify semantic colors have a text or equivalent cue and check contrast for essential text and controls.
- Use the repository's accessibility automation where available and inspect affected interactions manually. Record any assistive-technology coverage gaps against the WCAG 2.2 AA target.

Report findings with severity, route and conditions, observed evidence, impact, and proposed fix. In IMPLEMENT also report the changed files, screenshot pairs, verification results, and any unmet acceptance criteria. If browser tooling is absent, record the exact gap and mark visual checks pending.
