# Independent notification audio

## Findings

The original arm64 binary calls `setMediaVolume:` at 0xafec and changes SpringBoard’s shared AVAudioSession category at 0xb410/0xb438. Its per-app keys are `firstValue` (custom sound), `secondValue` (bypass mute), `fourthValue` (custom volume), `volumeLevel` (0–1), and `NotificationAlert` (filename). `muteValue` controls vibration, not mute bypass.

The removed 1.0.5-2 build had global method replacements, inferred app identity from recent calls, and packaged its patched original binary without a signing step. The unsigned modification is a plausible startup-failure cause, not a confirmed diagnosis without the device log.

## Design

Both original media/session mutation calls are neutralized. Only the two original custom playback sites are redirected to a new AVAudioPlayer category method. Existing notification filtering and lock-only checks run first. The bridge passes the current invocation’s dictionary directly; there is no last-app cache, process-wide play/session replacement, or audio-server injection. A missing category method returns without messaging an absent selector.

A new TLAlertConfiguration is made per event, with `externalToneFileURL`, `shouldIgnoreRingerSwitch`, and an explicit `audioVolume` when custom volume is enabled. `shouldForcePlayingAtUserSelectedAudioVolume` is false in custom-volume mode. Default mode leaves `audioVolume` unset. No media or ringer setting is rewritten. Runtime availability checks guard every private selector used. Alert ownership is serialized on the main queue, bounded to eight active records and 31 seconds. Sounds longer than 30 seconds are rejected; there is no fallback to the old media route.

The Settings helper hooks only SmartDetailView once its bundle loads. It obtains the app path using the original `datesPlistPath` method and uses the original keys. Writes merge fresh file contents and report errors. This avoids the withdrawn implementation’s app-name guessing. Its `Audio` navigation button opens the new page. Enabling volume or bypass enables custom sound and supplies the packaged alert.mp3 if none was selected.

ToneLibrary declarations were checked against https://github.com/nst/iOS-Runtime-Headers/blob/master/PrivateFrameworks/ToneLibrary.framework/TLAlertConfiguration.h and TLAlert.h. The runtime resolves the notification alert type through BulletinBoard’s `bb_toneLibraryAlertTypeForSectionID:` method, rather than hard-coding an enum. Private API behaviour requires confirmation on the target iOS build.

## Verification

The build checks the original package SHA-256, verifies the existing fake-toggle patch, rejects unknown binary instructions, and confines edits to named callsites, an unused selector slot and a vacant executable cave. Unicorn executes the bridge with and without the helper on both architecture layouts, checking arguments, stack, preserved registers and return flow. It also rejects repatching or an altered input.

GitHub Actions compiles both helpers for arm64 and arm64e with warnings treated as errors, signs **all three** dylibs (including the patched original), verifies signatures and architectures, then checks packaged dylibs byte-for-byte against signed inputs. No release/tag replacement occurs.

## Device acceptance

These checks cannot establish device loudness or a successful respring. Before merging:

1. Install this branch’s package on the target iOS 16/Dopamine phone; verify Settings, respring and userspace reboot.
2. App A: enable independent volume at 100%, set media and Ringtone/Alerts sliders low (then zero). Send a real notification; compare with full-volume baseline. System sliders must stay unchanged.
3. App A: test 50% and 0%; 0% must suppress only its custom sound.
4. Silent mode on: A bypass enabled, B bypass disabled. Alternate and burst notifications from both. Only A should sound. Repeat unlocked and locked.
5. Disable independent volume: notification loudness should follow Ringtone and Alerts, not media volume.
6. Verify calls, stock message sounds, music, vibration, Focus/block rules, lock-only rules, saved settings after reopening, and fake notifications OFF.
7. Check custom filenames, missing/invalid files, and rapid notifications. Missing private selectors log `[SNAudio]` and must not crash.

If the runtime lacks the private capabilities, or absolute alert volume is still clamped on this OS, this branch needs further device-backed work; static/build checks do not prove the feature works on-device.
