"""Property-based tests for platform selection locking (Property 1).

Uses Hypothesis to validate that once a platform is selected in
PlatformSelectWidget, the selection is locked and all subsequent
selection attempts are rejected.
"""
# Feature: automatic-commenter, Property 1: Platform selection is locked after first choice

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from PySide6.QtWidgets import QApplication


# ─── QApplication fixture (required for widget instantiation) ────────────────

@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ─── Strategies ──────────────────────────────────────────────────────────────

SUPPORTED_PLATFORMS = ["facebook", "twitter", "instagram", "tiktok"]

# Strategy for a single platform choice
platform_strategy = st.sampled_from(SUPPORTED_PLATFORMS)

# Strategy for a non-empty sequence of platform selections (min 2 to test locking)
platform_sequence_strategy = st.lists(
    platform_strategy,
    min_size=2,
    max_size=20,
)


# ─── Property 1: Platform selection is locked after first choice ─────────────
# Feature: automatic-commenter, Property 1: Platform selection is locked after first choice

class TestProperty1PlatformSelectionLocking:
    """
    For any sequence of platform selection attempts within a session, only the
    first selection shall be active, and all subsequent selection attempts shall
    be rejected, regardless of which platforms are attempted.

    **Validates: Requirements 3.3, 3.4**
    """

    @given(platform_selections=platform_sequence_strategy)
    @settings(max_examples=100, deadline=None)
    def test_only_first_selection_is_accepted(self, platform_selections):
        """For any sequence of platform selection attempts, only the first
        selection shall be active and all subsequent attempts are rejected."""
        from gui_ac import PlatformSelectWidget

        widget = PlatformSelectWidget()

        first_platform = platform_selections[0]

        # Simulate the first selection by clicking the corresponding radio button
        first_radio = None
        for radio in widget._radio_buttons:
            if radio.property("platform_key") == first_platform:
                first_radio = radio
                break

        assert first_radio is not None, f"Radio button for {first_platform} not found"

        # Perform the first selection
        first_radio.setChecked(True)

        # Verify first selection was accepted
        assert widget.selected_platform == first_platform, (
            f"Expected selected_platform={first_platform!r}, "
            f"got {widget.selected_platform!r}"
        )
        assert widget._locked is True, (
            "Expected widget to be locked after first selection"
        )

        # Attempt all subsequent selections — they should all be rejected
        for subsequent_platform in platform_selections[1:]:
            subsequent_radio = None
            for radio in widget._radio_buttons:
                if radio.property("platform_key") == subsequent_platform:
                    subsequent_radio = radio
                    break

            assert subsequent_radio is not None

            # Attempt to change selection (simulating programmatic toggle)
            # Since radio buttons are disabled, we call _on_radio_toggled directly
            # to test the locking logic even if someone bypasses the disabled state
            widget._on_radio_toggled(True)

            # The selected platform must still be the first one
            assert widget.selected_platform == first_platform, (
                f"Platform selection changed from {first_platform!r} to "
                f"{widget.selected_platform!r} after lock — "
                f"attempted platform: {subsequent_platform!r}"
            )

        # Verify all radio buttons are disabled after locking
        for radio in widget._radio_buttons:
            assert not radio.isEnabled(), (
                f"Radio button for {radio.property('platform_key')} "
                f"should be disabled after lock"
            )

    @given(first_platform=platform_strategy, second_platform=platform_strategy)
    @settings(max_examples=100, deadline=None)
    def test_locked_flag_prevents_second_selection(self, first_platform, second_platform):
        """After _locked is set True and _selected_platform is set,
        _on_radio_toggled rejects any subsequent toggled=True event."""
        from gui_ac import PlatformSelectWidget

        widget = PlatformSelectWidget()

        # Simulate locking: set _locked and _selected_platform directly
        # (testing the guard logic in _on_radio_toggled)
        widget._selected_platform = first_platform
        widget._locked = True

        # Now attempt to trigger _on_radio_toggled with checked=True
        # This simulates what would happen if a radio toggle event fired
        # The method should early-return because _locked is True
        original_platform = widget._selected_platform
        widget._on_radio_toggled(True)

        assert widget._selected_platform == original_platform, (
            f"Platform changed from {original_platform!r} to "
            f"{widget._selected_platform!r} despite _locked=True"
        )

    @given(first_platform=platform_strategy)
    @settings(max_examples=100, deadline=None)
    def test_unchecked_toggle_does_not_change_selection(self, first_platform):
        """When _on_radio_toggled is called with checked=False,
        no selection change occurs regardless of lock state."""
        from gui_ac import PlatformSelectWidget

        widget = PlatformSelectWidget()

        # First, make a valid selection
        first_radio = None
        for radio in widget._radio_buttons:
            if radio.property("platform_key") == first_platform:
                first_radio = radio
                break

        assert first_radio is not None
        first_radio.setChecked(True)

        assert widget.selected_platform == first_platform

        # Now call _on_radio_toggled with checked=False — should not change anything
        widget._on_radio_toggled(False)

        assert widget.selected_platform == first_platform, (
            "Selection should not change on unchecked toggle event"
        )
        assert widget._locked is True, (
            "Lock state should not change on unchecked toggle event"
        )
