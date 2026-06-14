"""
AutoCommenter â€“ PySide6 GUI Application

Main window with license integration, platform selection placeholder,
progress display, start/stop controls, and settings access.
"""

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox,
    QMessageBox, QDialog, QDialogButtonBox, QFormLayout, QRadioButton
)
from PySide6.QtCore import Qt, QTimer, Signal

import sys

from license_manager import LicenseManager, get_hardware_fingerprint, get_machine_id
from config_ac import PRODUCT, APP_NAME, validate_campaign_url, validate_api_key, LocalStorage
from campaign_client import CampaignServerClient
from browser_engine import PLATFORM_STRATEGY_MAP
from models_ac import WorkerConfig
from worker import CommentWorker

# â”€â”€â”€ Module-level stylesheet â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
QSS_STYLESHEET = """
/* Global Application Styles */
QApplication {
    font-family: "Segoe UI", sans-serif;
    font-size: 9pt;
    color: #212529;
}

/* Main Window */
QMainWindow {
    background-color: #FFFFFF;
}

/* Group Boxes - Clean section headers */
QGroupBox {
    font-weight: bold;
    font-size: 10pt;
    border: 1px solid #DEE2E6;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 16px;
}

QGroupBox::title {
    subcontrol-origin: padding;
    left: 8px;
    top: -8px;
    color: #495057;
}

/* Labels */
QLabel {
    color: #212529;
    background-color: transparent;
}

/* Line Edits - Clean form fields */
QLineEdit {
    border: 1px solid #CED4DA;
    border-radius: 3px;
    padding: 4px 8px;
    background-color: #FFFFFF;
    min-height: 24px;
    font-size: 9pt;
}

QLineEdit:focus {
    border-color: #0066CC;
    outline: none;
}

QLineEdit:read-only {
    background-color: #F8F9FA;
    color: #6C757D;
}

/* Buttons - Modern flat design */
QPushButton {
    border: 1px solid #DEE2E6;
    border-radius: 4px;
    padding: 6px 16px;
    background-color: #FFFFFF;
    color: #495057;
    min-height: 32px;
    font-size: 9pt;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #F8F9FA;
    border-color: #ADB5BD;
}

QPushButton:pressed {
    background-color: #E9ECEF;
}

QPushButton:disabled {
    background-color: #F8F9FA;
    color: #ADB5BD;
    border-color: #E9ECEF;
}

/* Primary action button (Start) */
QPushButton#start_button {
    background-color: #0066CC;
    color: #FFFFFF;
    border-color: #0066CC;
}

QPushButton#start_button:hover {
    background-color: #0056B3;
    border-color: #0056B3;
}

QPushButton#start_button:pressed {
    background-color: #004085;
}

QPushButton#start_button:disabled {
    background-color: #6CA0DC;
    color: #E0E0E0;
    border-color: #6CA0DC;
}

/* Stop button */
QPushButton#stop_button {
    background-color: #DC3545;
    color: #FFFFFF;
    border-color: #DC3545;
}

QPushButton#stop_button:hover {
    background-color: #C82333;
    border-color: #BD2130;
}

QPushButton#stop_button:pressed {
    background-color: #A71D2A;
}

QPushButton#stop_button:disabled {
    background-color: #F8F9FA;
    color: #ADB5BD;
    border-color: #E9ECEF;
}

/* Text Edit - Log panel */
QTextEdit {
    border: 1px solid #DEE2E6;
    border-radius: 3px;
    background-color: #FFFFFF;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 9pt;
    line-height: 1.4;
    padding: 4px;
}

QTextEdit:focus {
    border-color: #0066CC;
}

/* Status display styling */
QLabel#status_label {
    color: #495057;
    font-weight: 500;
    padding: 4px 0px;
}

/* Highlighted alerts (e.g. trial expired) */
QLabel#status_label[statusLevel="danger"] {
    background-color: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
    border-radius: 4px;
    padding: 6px 8px;
}

/* Tagline styling */
QLabel[tagline="true"] {
    color: #6C757D;
    font-size: 8pt;
    font-style: italic;
}

/* Frame styling for subtle grouping */
QFrame {
    border: none;
    background-color: transparent;
}

/* Scroll bars - minimal styling */
QScrollBar:vertical {
    width: 12px;
    background-color: #F8F9FA;
}

QScrollBar::handle:vertical {
    background-color: #ADB5BD;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #6C757D;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}
"""


# â”€â”€â”€ Platform Selection Widget â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Display names for each platform key
_PLATFORM_DISPLAY_NAMES: dict[str, str] = {
    "facebook": "Facebook",
    "twitter": "Twitter/X",
    "instagram": "Instagram",
    "tiktok": "TikTok",
}


class PlatformSelectWidget(QWidget):
    """Platform selection widget with radio buttons.

    Displays a radio button for each platform in PLATFORM_STRATEGY_MAP.
    Once a platform is selected the choice is locked for the session:
    all radio buttons are disabled and an informational label is shown.

    If PLATFORM_STRATEGY_MAP is empty, a "No platforms available" message
    is displayed instead of radio buttons.
    """

    platform_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_platform: str | None = None
        self._locked: bool = False
        self._radio_buttons: list[QRadioButton] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)

        if not PLATFORM_STRATEGY_MAP:
            # Edge case: no platforms available
            no_platforms_label = QLabel("No platforms available.")
            no_platforms_label.setStyleSheet("color: #DC3545; font-weight: bold;")
            self._layout.addWidget(no_platforms_label)
            return

        # Radio button row
        radio_layout = QHBoxLayout()
        radio_layout.setSpacing(16)

        for platform_key in PLATFORM_STRATEGY_MAP:
            display_name = _PLATFORM_DISPLAY_NAMES.get(platform_key, platform_key.capitalize())
            radio = QRadioButton(display_name)
            radio.setProperty("platform_key", platform_key)

            # Facebook is the primary platform â€” add tooltip emphasis
            if platform_key == "facebook":
                radio.setToolTip("Primary platform â€“ recommended for best results")
                radio.setStyleSheet("font-weight: bold;")

            radio.toggled.connect(self._on_radio_toggled)
            self._radio_buttons.append(radio)
            radio_layout.addWidget(radio)

        radio_layout.addStretch()
        self._layout.addLayout(radio_layout)

        # Locked status label (hidden until selection is made)
        self._locked_label = QLabel("")
        self._locked_label.setStyleSheet("color: #0066CC; font-style: italic;")
        self._locked_label.hide()
        self._layout.addWidget(self._locked_label)

    @property
    def selected_platform(self) -> str | None:
        """Return the selected platform name (lowercase) or None if nothing selected."""
        return self._selected_platform

    def _on_radio_toggled(self, checked: bool) -> None:
        """Handle a radio button being toggled."""
        if not checked or self._locked:
            return

        sender = self.sender()
        if sender is None:
            return

        platform_key = sender.property("platform_key")
        if not platform_key:
            return

        # Lock the selection
        self._selected_platform = platform_key
        self._locked = True

        # Disable all radio buttons
        for radio in self._radio_buttons:
            radio.setEnabled(False)

        # Show informational message
        display_name = _PLATFORM_DISPLAY_NAMES.get(platform_key, platform_key.capitalize())
        self._locked_label.setText(f"Platform locked for this session: {display_name}")
        self._locked_label.show()

        # Emit signal
        self.platform_selected.emit(platform_key)


# â”€â”€â”€ Trial Dialog â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TrialDialog(QDialog):
    """Modal dialog for starting an AutoCommenter trial (email â†’ code verification)."""

    def __init__(self, license_manager, parent=None):
        super().__init__(parent)
        self.license_manager = license_manager
        self.setWindowTitle("Start AutoCommenter Trial")
        self.setModal(True)
        self.resize(400, 200)

        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            "Enter your email to start a 14-day free trial of AutoCommenter.\n"
            "We'll send a 6-digit verification code to confirm."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Email input
        form_layout = QFormLayout()
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your.email@example.com")
        form_layout.addRow("Email:", self.email_input)

        # Code input (initially hidden)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("123456")
        self.code_input.setMaxLength(6)
        self.code_input.hide()
        form_layout.addRow("Verification code:", self.code_input)

        layout.addLayout(form_layout)

        # Buttons
        self.button_box = QDialogButtonBox()
        self.send_code_button = QPushButton("Send code")
        self.send_code_button.clicked.connect(self.send_code)
        self.button_box.addButton(self.send_code_button, QDialogButtonBox.ButtonRole.AcceptRole)

        self.verify_button = QPushButton("Verify code")
        self.verify_button.clicked.connect(self.verify_code)
        self.verify_button.setEnabled(False)
        self.verify_button.hide()
        self.button_box.addButton(self.verify_button, QDialogButtonBox.ButtonRole.AcceptRole)

        self.cancel_button = self.button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_button.clicked.connect(self.reject)

        layout.addWidget(self.button_box)

        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def send_code(self):
        email = self.email_input.text().strip()
        if not email:
            self.status_label.setText("Please enter an email address.")
            return

        if "@" not in email or "." not in email:
            self.status_label.setText("Please enter a valid email address.")
            return

        self.send_code_button.setEnabled(False)
        self.send_code_button.setText("Sending...")
        self.status_label.setText("Sending verification code...")

        QTimer.singleShot(100, lambda: self._send_code_async(email))

    def _send_code_async(self, email):
        success, message = self.license_manager.start_trial(email)
        self.send_code_button.setEnabled(True)
        self.send_code_button.setText("Send code")

        if success:
            self.status_label.setText("Code sent! Check your email and enter the 6-digit code below.")
            self.email_input.setEnabled(False)
            self.send_code_button.hide()
            self.code_input.show()
            self.verify_button.show()
            self.verify_button.setEnabled(True)
            self.code_input.setFocus()
        else:
            self.status_label.setText(f"Error: {message}")

    def verify_code(self):
        code = self.code_input.text().strip()
        if len(code) != 6 or not code.isdigit():
            self.status_label.setText("Please enter a valid 6-digit code.")
            return

        self.verify_button.setEnabled(False)
        self.verify_button.setText("Verifying...")
        self.status_label.setText("Verifying code...")

        QTimer.singleShot(100, lambda: self._verify_code_async(code))

    def _verify_code_async(self, code):
        success, message = self.license_manager.verify_trial_code(code)
        self.verify_button.setEnabled(True)
        self.verify_button.setText("Verify code")

        if success:
            self.status_label.setText("Trial activated successfully!")
            QTimer.singleShot(1500, self.accept)
        else:
            self.status_label.setText(f"Error: {message}")


# â”€â”€â”€ Credential Dialog â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class CredentialDialog(QDialog):
    """Username/password entry dialog for social media login.

    Emits credentials_submitted(username, password) on successful submission.
    The Submit button is disabled until both fields contain non-empty input.
    """

    credentials_submitted = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Social Media Login")
        self.setModal(True)
        self.resize(400, 180)

        layout = QVBoxLayout(self)

        # Form fields
        form_layout = QFormLayout()

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        self.username_input.textChanged.connect(self._update_submit_state)
        form_layout.addRow("Username:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.textChanged.connect(self._update_submit_state)
        form_layout.addRow("Password:", self.password_input)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.submit_button = QPushButton("Submit")
        self.submit_button.setEnabled(False)
        self.submit_button.clicked.connect(self._on_submit)
        button_layout.addWidget(self.submit_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _update_submit_state(self):
        """Enable submit only when both fields are non-empty."""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        self.submit_button.setEnabled(bool(username) and bool(password))

    def _on_submit(self):
        """Emit credentials and accept the dialog."""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        if username and password:
            self.credentials_submitted.emit(username, password)
            self.accept()


# â”€â”€â”€ Settings Dialog â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class SettingsDialog(QDialog):
    """Campaign Server settings dialog.

    Allows the user to configure the Campaign Server URL and API key.
    Validates URL format, tests connectivity, and persists on success.
    Pre-populates saved settings on launch; retains form values on
    validation failure.
    """

    settings_saved = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Campaign Server Settings")
        self.setModal(True)
        self.resize(500, 250)

        self._storage = LocalStorage()

        layout = QVBoxLayout(self)

        # Form fields
        form_layout = QFormLayout()

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://campaign.example.com/api")
        self.url_input.setMaxLength(2048)
        form_layout.addRow("Campaign Server URL:", self.url_input)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter API key")
        self.api_key_input.setMaxLength(256)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("API Key:", self.api_key_input)

        layout.addLayout(form_layout)

        # Status label for feedback
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self._on_test_connection)
        button_layout.addWidget(self.test_button)

        button_layout.addStretch()

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        # Pre-populate saved settings
        self._load_saved_settings()

    def _load_saved_settings(self):
        """Pre-populate fields from locally stored configuration."""
        config = self._storage.load_campaign_config()
        if config:
            self.url_input.setText(config.get("campaign_server_url", ""))
            self.api_key_input.setText(config.get("api_key", ""))

    def _on_test_connection(self):
        """Test connectivity to the Campaign Server and show result."""
        url = self.url_input.text().strip()
        api_key = self.api_key_input.text().strip()

        # Basic validation before attempting connection
        if not validate_campaign_url(url):
            self.status_label.setStyleSheet("color: #DC3545;")
            self.status_label.setText(
                "Invalid URL. Must start with \"https://\" and be well-formed."
            )
            return

        if not validate_api_key(api_key):
            self.status_label.setStyleSheet("color: #DC3545;")
            self.status_label.setText(
                "Invalid API key. Must be between 1 and 256 characters."
            )
            return

        self.status_label.setStyleSheet("color: #495057;")
        self.status_label.setText("Testing connection...")
        self.test_button.setEnabled(False)

        # Use QTimer to avoid blocking UI during the network call
        QTimer.singleShot(100, lambda: self._do_test_connection(url, api_key))

    def _do_test_connection(self, url: str, api_key: str):
        """Perform the actual connection test."""
        try:
            client = CampaignServerClient(url, api_key)
            success = client.validate_connection()
        except Exception:
            success = False

        self.test_button.setEnabled(True)

        if success:
            self.status_label.setStyleSheet("color: #28A745;")
            self.status_label.setText("Connection successful! Server is reachable.")
        else:
            self.status_label.setStyleSheet("color: #DC3545;")
            self.status_label.setText(
                "Connection failed. Server is unreachable or credentials are invalid."
            )

    def _on_save(self):
        """Validate inputs, test connection, and save on success."""
        url = self.url_input.text().strip()
        api_key = self.api_key_input.text().strip()

        # Validate URL
        if not validate_campaign_url(url):
            self.status_label.setStyleSheet("color: #DC3545;")
            self.status_label.setText(
                "Invalid URL. Must start with \"https://\" and be well-formed."
            )
            return

        # Validate API key
        if not validate_api_key(api_key):
            self.status_label.setStyleSheet("color: #DC3545;")
            self.status_label.setText(
                "Invalid API key. Must be between 1 and 256 characters."
            )
            return

        # Test connection before saving
        self.status_label.setStyleSheet("color: #495057;")
        self.status_label.setText("Validating connection before saving...")
        self.save_button.setEnabled(False)

        QTimer.singleShot(100, lambda: self._do_save(url, api_key))

    def _do_save(self, url: str, api_key: str):
        """Perform connection test and persist if successful."""
        try:
            client = CampaignServerClient(url, api_key)
            success = client.validate_connection()
        except Exception:
            success = False

        self.save_button.setEnabled(True)

        if success:
            # Persist configuration
            self._storage.save_campaign_config(url, api_key)
            self.status_label.setStyleSheet("color: #28A745;")
            self.status_label.setText("Settings saved successfully!")
            self.settings_saved.emit({
                "campaign_server_url": url,
                "api_key": api_key,
            })
            # Close the dialog after a brief success indication
            QTimer.singleShot(800, self.accept)
        else:
            self.status_label.setStyleSheet("color: #DC3545;")
            self.status_label.setText(
                "Connection failed. Settings were NOT saved. "
                "Check URL and API key, then try again."
            )


# â”€â”€â”€ Main Application Window â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AutoCommenterApp(QMainWindow):
    """Main application window for AutoCommenter."""

    def __init__(self, test_mode: bool = False):
        super().__init__()
        self.test_mode = test_mode
        title = "AutoCommenter \u2013 Social Media Automation"
        if test_mode:
            title += " [TEST MODE]"
        self.setWindowTitle(title)
        self.setGeometry(100, 100, 800, 600)

        # Flags
        self.stop_requested = False
        self._worker = None

        # Initialize license manager
        self.hardware_fingerprint = get_hardware_fingerprint()
        self.license_manager = LicenseManager(
            self.hardware_fingerprint,
            self.append_log,
            self.set_status,
            self.open_url_or_copy,
            self.update_license_button,
        )

        self._setup_ui()

        # Start with main controls disabled until license is confirmed active
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)

        # Log hardware fingerprint
        self.append_log(f"\U0001f527 Hardware fingerprint: {self.hardware_fingerprint}")

        if test_mode:
            # Test mode: skip license check, enable start immediately
            self.append_log("ðŸ§ª TEST MODE â€” license check skipped, using local CSV files")
            self.start_button.setEnabled(True)
            self.set_status("Test mode â€” ready")
        else:
            # Normal mode: check license on startup
            is_active, info = self.license_manager.check_license_status(show_messages=False)
            if is_active:
                self.start_button.setEnabled(True)

    def _setup_ui(self):
        """Build the full UI layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # â”€â”€ Platform Selection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        platform_group = QGroupBox("Platform")
        platform_layout = QVBoxLayout(platform_group)
        platform_layout.setSpacing(8)

        self.platform_select_widget = PlatformSelectWidget()
        self.platform_select_widget.platform_selected.connect(self.on_platform_selected)
        platform_layout.addWidget(self.platform_select_widget)

        main_layout.addWidget(platform_group)

        # â”€â”€ Actions group â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout(actions_group)
        actions_layout.setSpacing(8)

        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("start_button")
        self.start_button.clicked.connect(self.on_start_clicked)
        actions_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stop_button")
        self.stop_button.clicked.connect(self.on_stop_clicked)
        actions_layout.addWidget(self.stop_button)

        self.login_confirm_button = QPushButton("I'm Logged In")
        self.login_confirm_button.setObjectName("start_button")  # Green styling
        self.login_confirm_button.clicked.connect(self.on_login_confirmed)
        self.login_confirm_button.hide()  # Hidden until login is needed
        actions_layout.addWidget(self.login_confirm_button)

        self.license_button = QPushButton("Start trial")
        self.license_button.clicked.connect(self.toggle_license)
        actions_layout.addWidget(self.license_button)

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.open_settings)
        actions_layout.addWidget(self.settings_button)

        self.reset_button = QPushButton("Reset Progress")
        self.reset_button.clicked.connect(self.on_reset_progress)
        actions_layout.addWidget(self.reset_button)

        actions_layout.addStretch()
        main_layout.addWidget(actions_group)

        # â”€â”€ Status line â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.status_label = QLabel("Status: Idle")
        self.status_label.setObjectName("status_label")
        main_layout.addWidget(self.status_label)

        # â”€â”€ Progress display â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(4)

        self.progress_post_label = QLabel("No active run.")
        self.progress_post_label.setStyleSheet("color: #6C757D;")
        progress_layout.addWidget(self.progress_post_label)

        self.progress_remaining_label = QLabel("")
        self.progress_remaining_label.setStyleSheet("color: #6C757D;")
        progress_layout.addWidget(self.progress_remaining_label)

        self.progress_comment_label = QLabel("")
        self.progress_comment_label.setStyleSheet("color: #495057; font-style: italic;")
        self.progress_comment_label.setWordWrap(True)
        progress_layout.addWidget(self.progress_comment_label)

        main_layout.addWidget(progress_group)

        # â”€â”€ License Information â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        license_info_group = QGroupBox("License Information")
        license_info_layout = QVBoxLayout(license_info_group)
        license_info_layout.setSpacing(4)

        # Machine ID display
        machine_id_layout = QHBoxLayout()
        machine_id_layout.addWidget(QLabel("Computer ID:"))
        machine_id = get_machine_id()[:16] + "..."
        machine_id_label = QLabel(f"<code>{machine_id}</code>")
        machine_id_label.setTextFormat(Qt.TextFormat.RichText)
        machine_id_layout.addWidget(machine_id_label)
        machine_id_layout.addStretch()
        license_info_layout.addLayout(machine_id_layout)

        # License status display
        license_status_layout = QHBoxLayout()
        license_status_layout.addWidget(QLabel("License:"))
        self.license_status_value_label = QLabel("Checking...")
        license_status_layout.addWidget(self.license_status_value_label)
        license_status_layout.addStretch()
        license_info_layout.addLayout(license_status_layout)

        main_layout.addWidget(license_info_group)

        # â”€â”€ Tagline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        tagline = QLabel("Send feature requests and bug reports to your-email@example.com")
        tagline.setProperty("tagline", True)
        main_layout.addWidget(tagline)

        # â”€â”€ Activity Log â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(200)
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_group)

    # â”€â”€ UI callback methods (passed to LicenseManager) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def set_status(self, text: str):
        """Update the status label. Highlight danger states."""
        self.status_label.setText(f"Status: {text}")
        is_danger = any(kw in text for kw in ("expired", "failed"))
        current_level = self.status_label.property("statusLevel") or ""
        target_level = "danger" if is_danger else ""
        if current_level != target_level:
            self.status_label.setProperty("statusLevel", target_level)
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)

    def append_log(self, msg: str):
        """Append a message to the activity log and auto-scroll."""
        self.log_text.append(msg)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def append_log_with_timestamp(self, message: str):
        """Append a message to the activity log with HH:MM:SS timestamp prefix."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.append_log(f"[{timestamp}] {message}")

    def open_url_or_copy(self, url: str) -> None:
        """Open a URL in the default browser, or copy to clipboard as fallback."""
        import webbrowser
        import os
        import platform

        opened = False
        try:
            opened = bool(webbrowser.open_new_tab(url))
        except Exception:
            opened = False

        if not opened and platform.system().lower().startswith("win"):
            try:
                os.startfile(url)
                opened = True
            except Exception:
                opened = False

        if not opened:
            clipboard = QApplication.clipboard()
            clipboard.setText(url)
            QMessageBox.information(
                self,
                "Open Link",
                "Couldn't open your browser automatically.\n\n"
                "The link has been copied to your clipboard.\n"
                "Paste it into your browser to continue.",
            )

    def update_license_button(self, text: str, run_enabled: bool):
        """Update license button text and enable/disable main controls."""
        self.license_button.setText(text)
        self.start_button.setEnabled(run_enabled)
        # Update the license status value label based on current state
        if run_enabled:
            self.license_status_value_label.setText("Active")
        elif "Manage" in text:
            self.license_status_value_label.setText("Expired")
        elif "Start trial" in text:
            self.license_status_value_label.setText("Never activated")

    # â”€â”€ License button handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def toggle_license(self):
        """
        Handle license/trial button clicks.
        Shows TrialDialog for never_activated, or calls license_manager.toggle_license.
        """
        is_active, info = self.license_manager.check_license_status(show_messages=False)

        if not is_active:
            status = info.get("status")
            if status == "never_activated":
                # Show trial dialog
                trial_dialog = TrialDialog(self.license_manager, self)
                if trial_dialog.exec() == QDialog.DialogCode.Accepted:
                    # Trial activated â€” refresh status
                    is_active, info = self.license_manager.check_license_status(show_messages=False)
            else:
                # Expired â€” open Stripe checkout
                self.license_manager.toggle_license()
        else:
            # Active â€” manage/cancel
            self.license_manager.toggle_license()

    # â”€â”€ Platform selection handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def on_platform_selected(self, platform: str):
        """Handle platform selection from the PlatformSelectWidget."""
        display_name = _PLATFORM_DISPLAY_NAMES.get(platform, platform.capitalize())
        self.append_log(f"ðŸŒ Platform selected: {display_name}")

    # â”€â”€ Start / Stop handlers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def on_start_clicked(self):
        """Handle the Start button click.

        Reads campaign config, creates a CommentWorker, wires signals, and starts.
        In test mode, uses LocalCampaignClient with local CSVs instead of server.
        """
        # Verify license (skip in test mode)
        if not self.test_mode:
            is_active, info = self.license_manager.check_license_status(show_messages=True)
            if not is_active:
                return

        # Verify a platform is selected
        platform = self.platform_select_widget.selected_platform
        if not platform:
            QMessageBox.warning(
                self,
                "No Platform Selected",
                "Please select a platform before starting.",
            )
            return

        # Determine campaign client
        if self.test_mode:
            # Test mode: use local CSV files
            from local_campaign_client import LocalCampaignClient
            posts_csv = "test_data/posts.csv"
            comments_csv = "test_data/comments.csv"
            campaign_client = LocalCampaignClient(posts_csv, comments_csv)
            if not campaign_client.validate_connection():
                QMessageBox.warning(
                    self,
                    "Missing Test Data",
                    f"Test CSV files not found:\n  {posts_csv}\n  {comments_csv}\n\n"
                    "Create these files in the test_data/ folder.",
                )
                return
            campaign_url = f"local://posts"
            api_key = "test-mode"
            self.append_log(f"ðŸ“‹ Using local CSVs: {posts_csv}, {comments_csv}")
        else:
            # Normal mode: read campaign config from LocalStorage
            campaign_client = None
            storage = LocalStorage()
            campaign_config = storage.load_campaign_config()
            if not campaign_config:
                QMessageBox.warning(
                    self,
                    "No Campaign Settings",
                    "Please configure Campaign Server settings before starting.\n"
                    "Go to Settings to enter the server URL and API key.",
                )
                return

            campaign_url = campaign_config.get("campaign_server_url", "")
            api_key = campaign_config.get("api_key", "")

            if not campaign_url or not api_key:
                QMessageBox.warning(
                    self,
                    "Incomplete Settings",
                    "Campaign Server URL or API key is missing.\n"
                    "Please update your settings.",
                )
                return

        # Load stored cursor for this platform/campaign combo
        storage = LocalStorage()
        cursors = storage.load_cursors()
        cursor_key = f"{platform}|{campaign_url}"
        stored_cursor = None
        if cursor_key in cursors:
            stored_cursor = cursors[cursor_key].get("post_cursor")

        # Create WorkerConfig (no credentials â€” login is manual)
        config = WorkerConfig(
            platform=platform,
            campaign_server_url=campaign_url,
            api_key=api_key,
            post_cursor=stored_cursor,
        )

        # Create CommentWorker with injected client (test mode) or default (normal)
        self._worker = CommentWorker(config, campaign_client=campaign_client if self.test_mode else None)
        self._worker.progress_signal.connect(self.on_progress_update)
        self._worker.error_signal.connect(self.on_error_logged)
        self._worker.status_signal.connect(self.on_status_changed)
        self._worker.auth_required_signal.connect(self.on_auth_required)
        self._worker.finished_signal.connect(self.on_run_finished)

        # Update UI state
        self.stop_requested = False
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.set_status("Running...")
        self.append_log("\U0001f680 Starting AutoCommenter run...")

        # Start the worker thread
        self._worker.start()

    def on_stop_clicked(self):
        """Handle the Stop button click.

        Requests the worker to stop gracefully and disables the stop button
        to prevent multiple clicks. The worker checks stop_requested between
        posts so the current post operation completes before halting.
        """
        self.append_log_with_timestamp("â¹ï¸ User requested stop. Finishing current operation...")
        self.stop_requested = True
        self.stop_button.setEnabled(False)
        self.set_status("Stopping after current operation...")

        if self._worker is not None:
            self._worker.request_stop()

    def on_reset_progress(self):
        """Delete the cursor file to reset all progress."""
        from config_ac import _get_appdata_dir
        cursor_path = _get_appdata_dir() / "cursors.json"
        if cursor_path.exists():
            cursor_path.unlink()
            self.append_log_with_timestamp("ðŸ”„ Progress reset â€” cursor file deleted. Next run will start from the beginning.")
        else:
            self.append_log_with_timestamp("â„¹ï¸ No progress to reset (cursor file doesn't exist).")

    # â”€â”€ Settings â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def open_settings(self):
        """Open the SettingsDialog for Campaign Server configuration."""
        dialog = SettingsDialog(self)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self, config: dict):
        """Handle successful settings save from the dialog."""
        self.append_log(
            f"\u2699\ufe0f Campaign Server settings saved: {config.get('campaign_server_url', '')}"
        )

    # â”€â”€ Worker signal handlers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def on_progress_update(self, current: int, total: int, comment_preview: str):
        """Update progress labels when the worker reports progress.

        Args:
            current: Current post index (1-based).
            total: Total number of posts in List_A.
            comment_preview: First 100 characters of the comment being posted.
        """
        remaining = total - current
        self.progress_post_label.setText(f"Post {current} of {total}")
        self.progress_post_label.setStyleSheet("color: #212529; font-weight: bold;")
        self.progress_remaining_label.setText(f"Posts remaining: {remaining}")
        self.progress_remaining_label.setStyleSheet("color: #495057;")
        preview = comment_preview[:100]
        self.progress_comment_label.setText(f'"{preview}"')

    def on_error_logged(self, message: str, timestamp: str):
        """Append an error to the activity log with the provided timestamp.

        Args:
            message: The error description.
            timestamp: Pre-formatted HH:MM:SS timestamp from the worker.
        """
        self.append_log(f"[{timestamp}] âŒ {message}")

    def on_status_changed(self, status: str):
        """Update the status label when the worker emits a status change.

        Args:
            status: Status text from the worker (e.g. "Logging in...",
                    "Rate limited â€” resuming in 30s").
        """
        self.set_status(status)

    def on_auth_required(self, reason: str):
        """Handle auth_required_signal from the worker.

        Shows a prominent "I'm Logged In" button. The worker is blocked
        waiting for confirm_login() to be called.

        Args:
            reason: Description (e.g. "Please log in to your account...")
        """
        self.set_status("Waiting for you to log in...")
        self.append_log_with_timestamp(f"ðŸ” {reason}")

        # Show the login confirmation button
        self.login_confirm_button.setEnabled(True)
        self.login_confirm_button.show()

    def on_login_confirmed(self):
        """User clicked 'I'm Logged In' â€” tell the worker to proceed."""
        self.login_confirm_button.setEnabled(False)
        self.login_confirm_button.hide()
        self.set_status("Login confirmed â€” starting comments...")
        self.append_log_with_timestamp("âœ… User confirmed login")

        if self._worker is not None:
            self._worker.confirm_login()

    def on_run_finished(self, summary):
        """Display the completion summary and reset controls.

        Args:
            summary: A RunSummary dataclass instance, or None if the run
                     was aborted before producing meaningful results.
        """
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(True)

        # Re-check license status after run (skip in test mode)
        if not self.test_mode:
            try:
                is_active, info = self.license_manager.check_license_status(show_messages=False)
                if not is_active:
                    self.start_button.setEnabled(False)
            except Exception:
                pass  # Don't crash the GUI if license check fails

        if summary is None:
            self.progress_post_label.setText("Run aborted.")
            self.progress_post_label.setStyleSheet("color: #DC3545; font-weight: bold;")
            self.progress_remaining_label.setText("")
            self.progress_comment_label.setText("")
            self.set_status("Idle")
            self.append_log_with_timestamp("Run aborted before completion.")
            return

        # Display completion summary
        self.progress_post_label.setText(
            f"Run complete. Posted: {summary.comments_posted}, "
            f"Skipped: {summary.posts_skipped}, Errors: {summary.errors}"
        )
        self.progress_post_label.setStyleSheet("color: #28A745; font-weight: bold;")
        self.progress_remaining_label.setText("")
        self.progress_comment_label.setText("")
        self.set_status("Idle")
        self.append_log_with_timestamp(
            f"âœ… Run finished. Posted: {summary.comments_posted}, "
            f"Skipped: {summary.posts_skipped}, Errors: {summary.errors}"
        )


# â”€â”€â”€ Entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main(test_mode: bool = False):
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS_STYLESHEET)

    window = AutoCommenterApp(test_mode=test_mode)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

