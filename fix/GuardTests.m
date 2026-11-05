#import <Foundation/Foundation.h>
extern BOOL SNShouldSuppressFakeNotification(NSDictionary *, NSString *, NSString *, NSString *);
static void Check(BOOL ok, NSString *message) {
    if (!ok) { NSLog(@"FAILED: %@", message); exit(1); }
}
int main(void) {
    @autoreleasepool {
        NSDictionary *off = @{
            @"Sender": @"Fake Sender",
            @"Message": @"Fake Message",
            @"SelectedBundleIdentifier": @"com.example.fake",
            @"fakeNotifications": @NO
        };
        NSMutableDictionary *on = [off mutableCopy];
        on[@"fakeNotifications"] = @YES;

        Check(SNShouldSuppressFakeNotification(off, @"Fake Sender", @"Fake Message", @"com.example.fake"),
              @"OFF must block configured fake bulletin");
        Check(!SNShouldSuppressFakeNotification(on, @"Fake Sender", @"Fake Message", @"com.example.fake"),
              @"ON must allow configured fake bulletin");
        Check(!SNShouldSuppressFakeNotification(off, @"Real Sender", @"Fake Message", @"com.example.fake"),
              @"OFF must not block ordinary sender");
        Check(!SNShouldSuppressFakeNotification(off, @"Fake Sender", @"Other Message", @"com.example.fake"),
              @"OFF must not block ordinary message");
        Check(!SNShouldSuppressFakeNotification(off, @"Fake Sender", @"Fake Message", @"com.example.real"),
              @"OFF must not block another app");
        Check(!SNShouldSuppressFakeNotification(nil, @"Fake Sender", @"Fake Message", @"com.example.fake"),
              @"Missing preferences must never block ordinary notifications");
        Check(SNShouldSuppressFakeNotification(@{
            @"Sender": @"Fake Sender", @"Message": @"Fake Message"
        }, @"Fake Sender", @"Fake Message", @"com.example.fake"),
              @"Missing enable preference should mean OFF");
        NSLog(@"PASS: all fake-toggle guard cases");
    }
    return 0;
}
