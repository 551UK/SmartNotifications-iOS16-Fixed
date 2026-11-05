#import <Foundation/Foundation.h>
#import <dlfcn.h>
#include <stdbool.h>

// The original tweak and its Settings bundle both use selectedFakeApp.plist.
// The "fakeNotifications" key is the enable switch; these other keys are the
// same ones passed to sendBulletin(Sender, Message, SelectedBundleIdentifier).
static NSString *const kFakePrefsPath =
    @"/var/jb/Library/Application Support/SmartNotifications-plist/selectedFakeApp.plist";

typedef void (*SNOriginalSendBulletin)(NSString *, NSString *, NSString *);
static SNOriginalSendBulletin originalSendBulletin = NULL;

BOOL SNShouldSuppressFakeNotification(NSDictionary *prefs,
                                      NSString *sender,
                                      NSString *message,
                                      NSString *bundleIdentifier) {
    if (![prefs isKindOfClass:[NSDictionary class]]) return NO;
    NSString *savedSender = prefs[@"Sender"];
    NSString *savedMessage = prefs[@"Message"];
    NSString *savedBundle = prefs[@"SelectedBundleIdentifier"];

    // A missing or malformed preference must never suppress unrelated bulletins.
    if (![savedSender isKindOfClass:[NSString class]] ||
        ![savedMessage isKindOfClass:[NSString class]] ||
        savedSender.length == 0 || savedMessage.length == 0 ||
        ![savedSender isEqualToString:sender] ||
        ![savedMessage isEqualToString:message]) return NO;

    // A normal notification with the same text from a different app should pass.
    if ([savedBundle isKindOfClass:[NSString class]] &&
        savedBundle.length > 0 &&
        [bundleIdentifier isKindOfClass:[NSString class]] &&
        ![savedBundle isEqualToString:bundleIdentifier]) return NO;

    id enabled = prefs[@"fakeNotifications"];
    // Never treat absent / invalid enable keys as ON.
    return !([enabled respondsToSelector:@selector(boolValue)] && [enabled boolValue]);
}

static void SNGuardedSendBulletin(NSString *sender,
                                NSString *message,
                                NSString *bundleIdentifier) {
    @autoreleasepool {
        NSDictionary *prefs = [NSDictionary dictionaryWithContentsOfFile:kFakePrefsPath];
        if (SNShouldSuppressFakeNotification(prefs, sender, message, bundleIdentifier))
            return;
    }
    if (originalSendBulletin)
        originalSendBulletin(sender, message, bundleIdentifier);
}

#ifndef SMARTNOTIFICATIONS_TEST
__attribute__((constructor))
static void SNInstallFakeNotificationGuard(void) {
    @autoreleasepool {
        const char *paths[] = {
            "/var/jb/Library/MobileSubstrate/DynamicLibraries/SmartNotificationsiOS16.dylib",
            "/Library/MobileSubstrate/DynamicLibraries/SmartNotificationsiOS16.dylib"
        };
        void *target = NULL;
        for (unsigned i = 0; i < sizeof(paths) / sizeof(paths[0]); i++) {
            void *library = dlopen(paths[i], RTLD_NOW | RTLD_LOCAL);
            if (!library) continue;
            target = dlsym(library, "_Z12sendBulletinP8NSStringS0_S0_");
            if (target) break;
        }
        if (!target)
            target = dlsym(RTLD_DEFAULT, "_Z12sendBulletinP8NSStringS0_S0_");
        if (!target) return;

        typedef void (*MSHookFunctionPtr)(void *, void *, void **);
        MSHookFunctionPtr hook = (MSHookFunctionPtr)dlsym(RTLD_DEFAULT, "MSHookFunction");
        if (!hook) return;
        hook(target, (void *)&SNGuardedSendBulletin, (void **)&originalSendBulletin);
    }
}
#endif
