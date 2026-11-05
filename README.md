# SmartNotifications iOS16 Fixed

Single rootless package for iOS 15–16, based on EliasSfeir's original SmartNotifications iOS16.

- Fixes preferences that fail to save by repairing the writable settings folders and the All Apps preference path.
- **1.0.3:** Applies the Fake Notifications switch check inside the original fake-bulletin sender. A disabled switch prevents that sender from issuing a bulletin; when enabled, the original sender and Volume Up → Volume Down shortcut remain unchanged.
- The 1.0.2 companion guard was removed completely. There is **no extra helper dylib or filter** in 1.0.3, and no added startup notification code.
- Builds from the original tweak binary plus the existing 1.0.1 preferences repair, with an arm64/arm64e patch that is ad-hoc signed in GitHub Actions.

The binary patch passes static branch and package-integrity checks for both architectures, and the signed package builds successfully. On-device behaviour still requires testing after a respring and userspace reboot.

[Download the single current DEB from Releases](https://github.com/551UK/SmartNotifications-iOS16-Fixed/releases/tag/DEB).
