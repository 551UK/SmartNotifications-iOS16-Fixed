#import <Foundation/Foundation.h>
#import <AVFoundation/AVFoundation.h>
#import <objc/runtime.h>
#import <dlfcn.h>
#import <math.h>

// Runtime declarations from ToneLibrary headers; no private framework link at launch.
@interface SNTLConfiguration : NSObject
- (instancetype)initWithType:(long long)type;
@property(nonatomic,copy) NSURL *externalToneFileURL;
@property(nonatomic) float audioVolume;
@property(nonatomic) BOOL shouldIgnoreRingerSwitch;
@property(nonatomic) BOOL shouldForcePlayingAtUserSelectedAudioVolume;
@property(nonatomic) BOOL shouldRepeat;
@property(nonatomic) double maximumDuration;
@end
@interface SNTLAlert : NSObject
+ (long long)bb_toneLibraryAlertTypeForSectionID:(NSString *)section;
+ (instancetype)alertWithConfiguration:(id)configuration;
- (void)play;
- (void)stop;
@end

static void SNPlayAlert(NSURL *url, NSDictionary *prefs, NSTimeInterval duration) {
    // All alert ownership is main-queue confined; each event has its own snapshot.
    NSCAssert([NSThread isMainThread], @"main queue required");
    static NSMutableSet *active;
    static void *toneLibrary;
    if (!toneLibrary) toneLibrary=dlopen("/System/Library/PrivateFrameworks/ToneLibrary.framework/ToneLibrary",RTLD_LAZY|RTLD_LOCAL);
    Class configClass=NSClassFromString(@"TLAlertConfiguration");
    Class alertClass=NSClassFromString(@"TLAlert");
    if (!configClass || !alertClass) { NSLog(@"[SNAudio] ToneLibrary unavailable"); return; }
    NSArray *required=@[@"initWithType:",@"setExternalToneFileURL:",@"setAudioVolume:",
        @"setShouldIgnoreRingerSwitch:",@"setShouldForcePlayingAtUserSelectedAudioVolume:",
        @"setShouldRepeat:",@"setMaximumDuration:"];
    for (NSString *name in required) if (![configClass instancesRespondToSelector:NSSelectorFromString(name)]) {
        NSLog(@"[SNAudio] Missing %@",name); return;
    }
    if (![alertClass respondsToSelector:@selector(bb_toneLibraryAlertTypeForSectionID:)] ||
        ![alertClass respondsToSelector:@selector(alertWithConfiguration:)] ||
        ![alertClass instancesRespondToSelector:@selector(play)] ||
        ![alertClass instancesRespondToSelector:@selector(stop)]) return;
    BOOL custom=[prefs[@"fourthValue"] boolValue];
    float volume=1.0f;
    id value=prefs[@"volumeLevel"];
    if (custom && [value respondsToSelector:@selector(floatValue)]) volume=[value floatValue];
    if (!isfinite(volume)) volume=1.0f;
    volume=fmaxf(0,fminf(1,volume));
    if (custom && volume==0) return;
    @try {
        // Let BulletinBoard choose the app-notification type rather than guessing an enum.
        long long type=[(id)alertClass bb_toneLibraryAlertTypeForSectionID:@"com.551uk.smartnotifications"];
        SNTLConfiguration *config=[[(id)configClass alloc] initWithType:type];
        config.externalToneFileURL=url;
        config.shouldRepeat=NO;
        config.maximumDuration=30;
        config.shouldIgnoreRingerSwitch=[prefs[@"secondValue"] boolValue];
        // Explicit custom volume is absolute for this alert, not PCM attenuation
        // multiplied by media/ringer volume. Default mode leaves audioVolume unset.
        config.shouldForcePlayingAtUserSelectedAudioVolume=!custom;
        if (custom) config.audioVolume=volume;
        SNTLAlert *alert=[(id)alertClass alertWithConfiguration:config];
        if (!alert) return;
        if (!active) active=[NSMutableSet new];
        // Bound lifetime and concurrency without depending on private completion ABI.
        if (active.count>=8) return;
        [active addObject:alert];
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW,(int64_t)((duration+1)*NSEC_PER_SEC)),dispatch_get_main_queue(),^{
            @try { [alert stop]; } @catch (NSException *e) { NSLog(@"[SNAudio] stop: %@",e.name); }
            [active removeObject:alert];
        });
        [alert play];
    } @catch (NSException *e) { NSLog(@"[SNAudio] playback: %@",e.name); }
}

// A new selector, not a replacement of AVAudioPlayer's play/session methods.
// The original binary calls this only after its notification-policy checks.
@interface AVAudioPlayer (SNIndependentAudio)
- (BOOL)snPlayPrefs:(NSDictionary *)prefs;
@end
@implementation AVAudioPlayer (SNIndependentAudio)
- (BOOL)snPlayPrefs:(NSDictionary *)prefs {
    if (![prefs isKindOfClass:NSDictionary.class]) return NO;
    NSURL *url=self.url;
    if (!url.isFileURL || !isfinite(self.duration) || self.duration<=0 || self.duration>30) return NO;
    NSString *root=@"/var/jb/Library/Application Support/SmartNotifications/";
    if (![url.path.stringByStandardizingPath hasPrefix:root]) return NO;
    NSDictionary *snapshot=[prefs copy];
    NSTimeInterval duration=self.duration;
    dispatch_async(dispatch_get_main_queue(),^{ SNPlayAlert(url,snapshot,duration); });
    return YES;
}
@end
