"""Exercise the visual workflow with synthetic data and an existing Playwright installation."""
from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.sync_api import expect, sync_playwright


FIXTURE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Room bookings</title>
<style>
    :root { color-scheme: light dark; font: 16px system-ui; }
    body { margin: 0; padding: 24px; color: CanvasText; background: Canvas; }
    main { margin: auto; max-width: 960px; }
    form { display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: end; }
    label { display: grid; gap: 6px; min-width: 0; }
    button, input { font: inherit; padding: 8px 12px; }
    :focus-visible { outline: 2px solid Highlight; outline-offset: 2px; }
</style>
<main>
  <nav aria-label="Main"><a href="#bookings">View bookings</a></nav>
  <h1>Room bookings</h1>
  <p>Reserve a meeting room for your team.</p>
  <form>
    <label>Booking title <input name="title" required></label>
    <button type="submit">Save booking</button>
  </form>
  <h2 id="bookings">Upcoming bookings</h2>
  <p role="status">No bookings yet.</p>
</main>
<script>
  const form = document.querySelector('form');
  form.addEventListener('submit', event => {
    event.preventDefault();
    document.querySelector('[role=status]').textContent = form.elements.title.value;
  });
  if (location.search === '?role=manager') {
    const button = document.createElement('button');
    button.textContent = 'Manage bookings';
    document.querySelector('main').append(button);
  }
</script>
</html>
"""
REFINEMENT = """<style>
    form { max-width: 42rem; }
    @media (max-width: 40rem) {
        form { grid-template-columns: minmax(0, 1fr); }
    }
</style>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as temp, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for version, markup in (("baseline", FIXTURE), ("refined", FIXTURE.replace("</style>", "</style>" + REFINEMENT))):
            fixture = Path(temp) / f"{version}.html"
            fixture.write_text(markup, encoding="utf-8")
            for width in (390, 768, 1440):
                for theme in ("light", "dark"):
                    page = browser.new_page(viewport={"width": width, "height": 800}, color_scheme=theme)
                    page.goto(fixture.as_uri())
                    page.evaluate("document.fonts.ready")
                    page.screenshot(path=output / f"{version}-{width}-{theme}.png")
                    navigation = page.get_by_role("link", name="View bookings")
                    page.keyboard.press("Tab")
                    expect(navigation).to_be_focused()
                    page.keyboard.press("Enter")
                    assert page.url.endswith("#bookings")
                    title = page.get_by_role("textbox", name="Booking title")
                    save = page.get_by_role("button", name="Save booking")
                    save.click()
                    assert title.evaluate("(input) => input.validity.valueMissing")
                    title.fill("Design review")
                    save.click()
                    expect(page.get_by_role("status")).to_have_text("Design review")
                    if version == "refined":
                        assert page.evaluate("document.documentElement.scrollWidth === innerWidth")
                        if width == 390:
                            assert save.bounding_box()["y"] > title.bounding_box()["y"]
                    manager = page.get_by_role("button", name="Manage bookings")
                    expect(manager).to_have_count(0)
                    page.goto(fixture.as_uri() + "?role=manager")
                    expect(manager).to_be_visible()
                    page.close()
                    print(f"{version} · {width}px · {theme} · passed", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
