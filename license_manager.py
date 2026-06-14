"""
License manager stub.

This module provides the public interface for license management.
Implement your own licensing logic by filling in the method bodies.
"""

import hashlib
import platform
import uuid


def get_hardware_fingerprint() -> str:
    """Return a string that uniquely identifies this machine's hardware."""
    raise NotImplementedError("Provide your own hardware fingerprinting implementation.")


def get_machine_id() -> str:
    """Return a deterministic, hashed machine identifier."""
    try:
        node = platform.node()
    except Exception:
        node = "unknown-node"

    try:
        mac = uuid.getnode()
    except Exception:
        mac = 0

    raw = f"{node}-{mac}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class LicenseManager:
    """
    Manages license state (trial, paid, expired).

    Parameters
    ----------
    hardware_fingerprint : str
        Result of get_hardware_fingerprint().
    append_log_callback : callable
        GUI callback to append a log message.
    set_status_callback : callable
        GUI callback to set the status bar text.
    open_url_callback : callable
        GUI callback to open a URL (or copy to clipboard).
    update_license_button_callback : callable
        GUI callback to update the license button label/state.
    """

    def __init__(
        self,
        hardware_fingerprint: str,
        append_log_callback,
        set_status_callback,
        open_url_callback,
        update_license_button_callback,
    ):
        self.hardware_fingerprint = hardware_fingerprint
        self.append_log = append_log_callback
        self.set_status = set_status_callback
        self.open_url_or_copy = open_url_callback
        self.update_license_button = update_license_button_callback

        self.license_started = False
        self.has_paid_license = False
        self.checkout_started = False
        self.checkout_url = None
        self.trial_email = None
        self.verification_code = None

    def check_license_status(self, show_messages: bool = False) -> tuple[bool, dict]:
        """
        Check whether this machine has an active license.

        Returns
        -------
        tuple[bool, dict]
            (is_active, info_dict) where info_dict contains status details.
        """
        raise NotImplementedError("Implement license status checking.")

    def start_trial(self, email: str) -> tuple[bool, str]:
        """
        Initiate a trial for the given email address.

        Returns
        -------
        tuple[bool, str]
            (success, message)
        """
        raise NotImplementedError("Implement trial start logic.")

    def verify_trial_code(self, code: str) -> tuple[bool, str]:
        """
        Verify a trial activation code.

        Returns
        -------
        tuple[bool, str]
            (success, message)
        """
        raise NotImplementedError("Implement trial code verification.")

    def toggle_license(self):
        """
        Manage the license: open customer portal if paid, or start checkout flow.
        """
        raise NotImplementedError("Implement license management/toggle.")
