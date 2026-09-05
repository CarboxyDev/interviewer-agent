"""V2-008 synthetic journey and recovery acceptance checks in real Chromium."""

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


def click(page: Page, name: str) -> None:
    page.get_by_role("button", name=name, exact=True).click()


def ready(page: Page, mode: str = "focused", retain: bool = False) -> None:
    click(page, "Start a practice session")
    if mode == "mock":
        page.get_by_role("radio", name="Mock interview").check()
    click(page, "Continue to ready check")
    if retain:
        page.get_by_role("checkbox", name="Also keep audio").check()


def begin(page: Page, mode: str = "focused", retain: bool = False) -> None:
    ready(page, mode, retain)
    click(page, "Simulate microphone check")
    page.get_by_role("checkbox", name="I agree to transcription").check()
    click(page, "Start practice")
    expect(page.get_by_role("heading", name="Your turn", exact=True)).to_be_visible()


def answer(page: Page) -> None:
    click(page, "Use sample answer")
    expect(page.get_by_role("heading", name="Thinking", exact=True)).to_be_visible()
    expect(page.get_by_role("heading", name="Your turn", exact=True)).to_be_visible()


def review(page: Page, retain: bool = False) -> None:
    begin(page, retain=retain)
    answer(page)
    click(page, "Finish sample segment")
    click(page, "View sample feedback")


def fault(page: Page, name: str) -> None:
    page.locator("#lab > summary").click()
    click(page, f"{name} failure")


def test_start_needs_no_account_upload_or_permission(page: Page) -> None:
    expect(page.get_by_role("button")).to_have_count(1)
    ready(page)
    expect(page.get_by_label("Focus preview")).to_contain_text("Focused practice · 5 minutes")
    expect(page.locator('input[type="file"]')).to_have_count(0)
    expect(page.locator("main")).to_contain_text("24 hours")


def test_consent_and_device_are_separate_start_gates(page: Page) -> None:
    ready(page)
    start = page.get_by_role("button", name="Start practice", exact=True)
    expect(start).to_be_disabled()
    page.get_by_role("checkbox", name="I agree to transcription").check()
    expect(start).to_be_disabled()
    click(page, "Simulate microphone check")
    expect(start).to_be_enabled()
    page.get_by_role("checkbox", name="I agree to transcription").uncheck()
    expect(start).to_be_disabled()
    expect(page.get_by_role("checkbox", name="Also keep audio")).not_to_be_checked()


def test_configuration_preview_and_synthetic_personal_paths(page: Page) -> None:
    click(page, "Start a practice session")
    page.get_by_label("Practice goal").select_option("Clarity")
    page.get_by_role("radio", name="Mock interview").check()
    page.get_by_label("Duration", exact=True).select_option("10")
    for source in ("paste", "document"):
        page.get_by_label("Role context").select_option(source)
        expect(page.locator("main")).to_contain_text("fixed fictional text")
    page.get_by_role("checkbox", name="Include a sample resume").check()
    click(page, "Continue to ready check")
    expect(page.get_by_label("Focus preview")).to_contain_text("Clarity")
    expect(page.get_by_label("Focus preview")).to_contain_text("Mock interview · 10 minutes")
    expect(page.get_by_label("Focus preview")).to_contain_text("No coaching between questions")
    click(page, "Back to setup")
    expect(page.get_by_label("Role context")).to_have_value("document")
    expect(page.get_by_role("checkbox", name="Include a sample resume")).to_be_checked()


def test_live_states_captions_mute_pause_and_repeat(page: Page) -> None:
    begin(page)
    expect(page.locator("#captions")).not_to_have_attribute("open", "")
    page.locator("#captions > summary").click()
    expect(page.locator("#captions")).to_contain_text("inventory update")
    click(page, "Mute")
    expect(page.get_by_role("button", name="Use sample answer", exact=True)).to_be_disabled()
    expect(page.locator("main")).to_contain_text("Transcription paused")
    click(page, "Unmute")
    click(page, "Pause for a moment")
    expect(page.get_by_role("heading", name="Take your time")).to_be_visible()
    click(page, "Resume")
    click(page, "Repeat question")
    expect(page.get_by_role("heading", name="Interviewer speaking")).to_be_visible()
    expect(page.locator("#captions")).to_have_attribute("open", "")
    expect(page.get_by_role("heading", name="Your turn", exact=True)).to_be_visible()
    expect(page.locator("main")).not_to_contain_text("latency")


def test_mock_has_no_coaching_between_answers(page: Page) -> None:
    begin(page, mode="mock")
    answer(page)
    expect(page.locator("main")).not_to_contain_text("Improve first")
    expect(page.locator("main")).not_to_contain_text("Strength:")
    click(page, "End interview")
    expect(page.get_by_role("dialog")).to_contain_text("keep consented work")
    click(page, "End and review")
    click(page, "View sample feedback")
    expect(page.get_by_role("heading", name="Improve first", exact=False)).to_be_visible()


@pytest.mark.parametrize("retain", [False, True])
def test_observation_evidence_and_optional_playback(page: Page, retain: bool) -> None:
    review(page, retain)
    click(page, "Open improvement evidence")
    expect(page.locator("#evidence")).to_be_focused()
    expect(page.locator("#evidence")).to_contain_text("I built the inventory update endpoint.")
    click(page, "Open strength evidence")
    expect(page.locator("#evidence")).to_contain_text("one hundred requests")
    if retain:
        expect(page.get_by_label("Original answer evidence audio")).to_have_attribute(
            "src", "/sample-answer.wav#t=12,19"
        )
        page.wait_for_function("document.querySelector('audio').readyState >= 1")
        assert page.locator("audio").evaluate("el => el.duration") > 19
    else:
        expect(page.locator("main audio")).to_have_count(0)
        expect(page.locator("#evidence")).to_contain_text("Audio was not retained")


def test_retry_comparison_export_and_next_focus(page: Page) -> None:
    review(page)
    click(page, "Retry this answer")
    click(page, "Use sample retry answer")
    click(page, "Finish retry")
    expect(page.get_by_role("heading", name="What changed")).to_be_visible()
    expect(page.locator("main")).to_contain_text("My goal was to prevent duplicate inventory")
    with page.expect_download() as downloaded:
        click(page, "Export sample report")
    report = json.loads(Path(downloaded.value.path()).read_text())
    assert report["synthetic"] is True
    assert report["retry"].startswith("My goal was")
    assert len(report["observations"]) == 2
    click(page, "Practice explaining tradeoffs")
    expect(page.get_by_label("Practice goal")).to_have_value("Clarity")
    expect(page.get_by_role("radio", name="Focused practice")).to_be_checked()


def test_ending_without_an_answer_does_not_invent_feedback(page: Page) -> None:
    begin(page)
    click(page, "End interview")
    click(page, "End and review")
    click(page, "View sample feedback")
    expect(page.get_by_role("heading", name="No answer to review yet.")).to_be_visible()


@pytest.mark.parametrize("from_review", [False, True])
def test_delete_clears_answers_and_consent(page: Page, from_review: bool) -> None:
    if from_review:
        review(page, retain=True)
        click(page, "Delete session")
    else:
        begin(page, retain=True)
        click(page, "Withdraw consent and delete")
    expect(page.get_by_role("dialog")).to_contain_text("cannot be undone")
    click(page, "Delete session now")
    expect(page.get_by_role("heading", name="Session cleared.")).to_be_visible()
    click(page, "Start a new practice")
    click(page, "Continue to ready check")
    expect(page.get_by_role("checkbox", name="I agree to transcription")).not_to_be_checked()
    expect(page.get_by_role("checkbox", name="Also keep audio")).not_to_be_checked()
    expect(page.get_by_role("button", name="Start practice", exact=True)).to_be_disabled()


def test_cancel_end_dialog_keeps_practice_paused(page: Page) -> None:
    begin(page)
    click(page, "End interview")
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).not_to_be_visible()
    expect(page.get_by_role("heading", name="Take your time")).to_be_visible()
    click(page, "Resume")
    expect(page.get_by_role("heading", name="Your turn", exact=True)).to_be_visible()


@pytest.mark.parametrize("failure", ["Permission", "Device"])
def test_ready_failures_require_a_new_check(page: Page, failure: str) -> None:
    ready(page)
    fault(page, failure)
    click(page, "Try microphone again" if failure == "Permission" else "Check microphone again")
    expect(page.get_by_role("button", name="Start practice", exact=True)).to_be_disabled()
    click(page, "Simulate microphone check")
    page.get_by_role("checkbox", name="I agree to transcription").check()
    expect(page.get_by_role("button", name="Start practice", exact=True)).to_be_enabled()


@pytest.mark.parametrize(
    ("failure", "recovery"),
    [
        ("Silence", "Continue when ready"),
        ("Network", "Try reconnecting"),
        ("Provider", "Try interviewer again"),
    ],
)
def test_live_recovery_has_resume_and_exit(page: Page, failure: str, recovery: str) -> None:
    begin(page)
    fault(page, failure)
    expect(page.get_by_role("button", name="End interview", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Withdraw consent and delete")).to_be_visible()
    click(page, recovery)
    expect(page.get_by_role("heading", name="Your turn", exact=True)).to_be_visible()


def test_device_loss_requires_readiness_before_resuming(page: Page) -> None:
    begin(page)
    fault(page, "Device")
    click(page, "Check microphone again")
    expect(page.get_by_role("button", name="Start practice", exact=True)).to_be_disabled()
    expect(page.get_by_role("checkbox", name="I agree to transcription")).not_to_be_checked()


def test_report_failure_preserves_transcript_and_delete_path(page: Page) -> None:
    begin(page)
    answer(page)
    click(page, "Finish sample segment")
    expect(page.get_by_role("heading", name="Preparing your feedback")).to_be_visible()
    fault(page, "Report")
    page.get_by_text("Available transcript", exact=True).click()
    expect(page.locator("main blockquote")).to_contain_text("inventory update endpoint")
    expect(page.get_by_role("button", name="Delete session", exact=True)).to_be_visible()
    click(page, "Retry feedback")
    expect(page.get_by_role("heading", name="Lead with the problem you solved.")).to_be_visible()


def test_refresh_clears_demo_without_persistence(page: Page) -> None:
    review(page)
    assert (
        page.evaluate("Object.keys(localStorage).length + Object.keys(sessionStorage).length") == 0
    )
    page.reload()
    expect(page.get_by_role("button", name="Start a practice session")).to_be_visible()


def test_keyboard_focus_and_mobile_reduced_motion(page: Page) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.emulate_media(reduced_motion="reduce")
    page.keyboard.press("Tab")
    expect(page.get_by_role("link", name="Skip to practice")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("main")).to_be_focused()
    for name in ("Start a practice session", "Continue to ready check"):
        click(page, name)
        expect(page.locator("main")).to_be_focused()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert (
        page.locator("button").first.evaluate("el => getComputedStyle(el).transitionDuration")
        == "0s"
    )


def test_ending_from_recovery_keeps_available_answer(page: Page) -> None:
    begin(page)
    answer(page)
    fault(page, "Network")
    click(page, "End interview")
    click(page, "End and review")
    click(page, "View sample feedback")
    expect(page.get_by_role("heading", name="Improve first", exact=False)).to_be_visible()


def test_abandoned_retry_preserves_original_evidence(page: Page) -> None:
    review(page)
    click(page, "Retry this answer")
    click(page, "End interview")
    click(page, "End and review")
    click(page, "Open improvement evidence")
    expect(page.locator("#evidence")).to_contain_text("I built the inventory update endpoint.")
    expect(page.get_by_role("button", name="Compare attempts", exact=True)).to_have_count(0)


def test_live_controls_preserve_keyboard_focus(page: Page) -> None:
    begin(page)
    click(page, "Mute")
    expect(page.get_by_role("button", name="Unmute", exact=True)).to_be_focused()
    click(page, "Unmute")
    click(page, "Pause for a moment")
    expect(page.get_by_role("button", name="Resume", exact=True)).to_be_focused()


@pytest.mark.parametrize("path", ["/.env", "/data/", "/src/voice_interviewer/config.py"])
def test_preview_server_does_not_serve_repository_files(page: Page, path: str) -> None:
    response = page.request.get(f"{page.url.rstrip('/')}{path}")
    assert response.status == 404
