# SmartNotifications iOS16 Fixed

This branch adds per-app notification audio controls to the 1.0.3 baseline.

Open **Settings → SmartNotifications → Customize Apps → an app → Audio**.

- **Independent volume:** 0–100% for this app’s custom notification sound. 100% requests full alert volume independently of media and ringer sliders; 0% is silent. Off follows Ringtone and Alerts volume.
- **Bypass mute:** allows this app’s custom notification sound in silent mode. Other apps retain normal mute behaviour.
- Enabling either option also enables custom sound for this app. If no sound is selected, `alert.mp3` is used. Select another sound on the original app page.

The branch keeps the settings-save repair and fake-notification switch fix. Builds are attached to the **Build independent notification audio** workflow; the main release remains 1.0.3.

Implementation and checks: [audio notes](docs/independent-audio.md).
