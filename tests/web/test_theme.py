"""V2-010: theme behavior, contrast, motion and session isolation in the built web app."""

import re

import pytest
from playwright.sync_api import Page, expect
from test_practice_flow import answer, begin, click, fault, review


def appearance(page: Page, theme: str) -> None:
    page.get_by_label("Appearance", exact=True).select_option(theme)


def dark(page: Page, enabled: bool = True) -> None:
    if enabled:
        expect(page.locator("html")).to_have_class(re.compile(r"\bdark\b"))
    else:
        expect(page.locator("html")).not_to_have_class(re.compile(r"\bdark\b"))


def test_system_theme_follows_device_until_explicitly_overridden(page: Page) -> None:
    expect(page.get_by_label("Appearance")).to_have_value("system")
    page.emulate_media(color_scheme="dark")
    dark(page)
    page.emulate_media(color_scheme="light")
    dark(page, False)
    appearance(page, "light")
    page.emulate_media(color_scheme="dark")
    dark(page, False)
    page.reload()
    dark(page, False)
    expect(page.get_by_label("Appearance")).to_have_value("light")
    appearance(page, "system")
    dark(page)


def test_dark_preference_survives_refresh_but_answers_and_consent_do_not(page: Page) -> None:
    appearance(page, "dark")
    review(page)
    page.reload()
    dark(page)
    expect(page.get_by_label("Appearance")).to_have_value("dark")
    expect(page.get_by_role("button", name="Set up practice")).to_be_visible()
    assert page.evaluate("Object.keys(localStorage)") == ["practice-room-theme"]
    assert page.evaluate("Object.keys(sessionStorage)") == []
    click(page, "Set up practice")
    click(page, "Continue")
    expect(page.get_by_role("checkbox", name="Allow a transcript")).not_to_be_checked()
    expect(page.get_by_role("button", name="Start practice", exact=True)).to_be_disabled()


def test_unavailable_storage_does_not_break_theme_or_practice(page: Page) -> None:
    page.add_init_script(
        "Object.defineProperty(window, 'localStorage', "
        "{ get() { throw new Error('Storage unavailable'); } });"
    )
    page.reload()
    appearance(page, "dark")
    dark(page)
    begin(page)
    expect(page.get_by_role("heading", name="Your turn", exact=True)).to_be_visible()


def test_invalid_saved_preference_falls_back_to_system(page: Page) -> None:
    page.evaluate("localStorage.setItem('practice-room-theme', 'invalid')")
    page.emulate_media(color_scheme="dark")
    page.reload()
    dark(page)
    expect(page.get_by_label("Appearance")).to_have_value("system")


def test_theme_changes_sync_between_tabs(page: Page) -> None:
    other = page.context.new_page()
    try:
        other.goto(page.url)
        appearance(page, "dark")
        dark(other)
        expect(other.get_by_label("Appearance")).to_have_value("dark")
        appearance(other, "light")
        dark(page, False)
        expect(page.get_by_label("Appearance")).to_have_value("light")
    finally:
        other.close()


def test_dark_dialog_evidence_retry_and_theme_changes_preserve_session(page: Page) -> None:
    appearance(page, "dark")
    begin(page, retain=True)
    click(page, "Pause for a moment")
    appearance(page, "light")
    expect(page.get_by_role("heading", name="Take your time")).to_be_visible()
    appearance(page, "dark")
    expect(page.locator("main")).to_contain_text("Review audio included")
    click(page, "Resume")
    answer(page)
    click(page, "Review answer")
    click(page, "View feedback")
    click(page, "See result in transcript")
    expect(page.locator("#evidence")).to_be_focused()
    assert page.locator("audio").evaluate("el => getComputedStyle(el).colorScheme") == "dark"
    click(page, "Retry this answer")
    expect(page.get_by_role("heading", name="Your turn", exact=True)).to_be_visible()
    click(page, "Continue with revised answer")
    click(page, "Finish retry")
    expect(page.get_by_role("heading", name="Compare your answers")).to_be_visible()
    click(page, "Delete session")
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    assert dialog.evaluate("el => getComputedStyle(el).colorScheme") == "dark"
    page.keyboard.press("Escape")
    expect(page.get_by_role("button", name="Delete session", exact=True)).to_be_focused()
    click(page, "Delete session")
    click(page, "Delete session now")
    expect(page.get_by_role("heading", name="Session cleared.")).to_be_visible()
    dark(page)


def test_dark_recovery_keeps_work_and_has_a_keyboard_exit(page: Page) -> None:
    page.goto(page.url + "?qa=1")
    appearance(page, "dark")
    begin(page)
    answer(page)
    fault(page, "Network")
    expect(page.get_by_role("heading", name="Connection interrupted")).to_be_visible()
    dark(page)
    click(page, "Try reconnecting")
    expect(page.get_by_role("heading", name="Your turn", exact=True)).to_be_visible()
    click(page, "End interview")
    page.keyboard.press("Escape")
    expect(page.get_by_role("button", name="End interview", exact=True)).to_be_focused()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_text_theme_tokens_meet_normal_text_contrast(page: Page, theme: str) -> None:
    appearance(page, theme)
    pairs = page.evaluate("""() => {
      const css = getComputedStyle(document.documentElement);
      return [['foreground','background'], ['muted-foreground','background'],
              ['primary-foreground','primary'], ['card-foreground','card'],
              ['popover-foreground','popover']].map(pair => pair.map(
                name => css.getPropertyValue('--' + name).trim()));
    }""")

    def luminance(value: str) -> float:
        if len(value) == 4:
            value = "#" + "".join(character * 2 for character in value[1:])
        channels = [int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        ]
        return sum(
            channel * weight
            for channel, weight in zip(linear, [0.2126, 0.7152, 0.0722], strict=True)
        )

    for foreground, background in pairs:
        low, high = sorted([luminance(foreground), luminance(background)])
        assert (high + 0.05) / (low + 0.05) >= 4.5, (theme, foreground, background)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_motion_is_intentional_and_respects_reduced_motion(page: Page, theme: str) -> None:
    appearance(page, theme)
    page.emulate_media(reduced_motion="no-preference")
    begin(page)
    assert (
        page.locator(".voice i").first.evaluate("el => getComputedStyle(el).animationName")
        == "speak"
    )
    page.emulate_media(reduced_motion="reduce")
    assert page.locator("main").evaluate("el => getComputedStyle(el).animationName") == "none"
    assert (
        page.locator(".voice i").first.evaluate("el => getComputedStyle(el).animationName")
        == "none"
    )
    click(page, "End interview")
    assert page.get_by_role("dialog").evaluate("el => getComputedStyle(el).animationName") == "none"


@pytest.mark.parametrize("width", [390, 820, 1440])
def test_dark_setup_controls_remain_readable_without_overflow(page: Page, width: int) -> None:
    page.set_viewport_size({"width": width, "height": 900})
    appearance(page, "dark")
    click(page, "Set up practice")
    page.get_by_label("Practice role", exact=True).select_option("finance")
    expect(page.get_by_label("Focus preview")).to_contain_text("Finance analyst")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    expect(page.get_by_label("Appearance")).to_be_visible()
    expect(page.get_by_role("button", name="Continue", exact=True)).to_be_visible()


def test_setup_selects_fill_their_column_while_appearance_stays_compact(page: Page) -> None:
    click(page, "Set up practice")
    role_wrapper = page.get_by_label("Practice role", exact=True).locator("..")
    setup_width = role_wrapper.evaluate("el => el.getBoundingClientRect().width")
    column_width = role_wrapper.locator("..").evaluate("el => el.getBoundingClientRect().width")
    appearance_wrapper = page.get_by_label("Appearance", exact=True).locator("..")
    appearance_width = appearance_wrapper.evaluate("el => el.getBoundingClientRect().width")
    assert abs(setup_width - column_width) < 1
    assert appearance_width < 140


def test_saved_dark_theme_applies_before_the_react_bundle(page: Page) -> None:
    appearance(page, "dark")
    page.route("**/assets/*.js", lambda route: route.abort())
    page.reload()
    dark(page)
    expect(page.locator("#root")).to_be_empty()
    assert page.locator("html").get_attribute("data-theme") == "dark"
