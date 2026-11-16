#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <objc/runtime.h>
#import <objc/message.h>
#import <math.h>

static NSString *const SNDirectory=@"/var/jb/Library/Application Support/SmartNotifications-plist/";
@interface SNAudioSettings : UITableViewController
@property(nonatomic,copy) NSString *path;
@property(nonatomic,strong) UILabel *volumeLabel;
@end
@implementation SNAudioSettings
- (void)viewDidLoad {
    [super viewDidLoad]; self.title=@"Notification Audio";
    self.tableView.rowHeight=UITableViewAutomaticDimension;
    self.tableView.estimatedRowHeight=56;
}
- (NSDictionary *)settings { return [NSDictionary dictionaryWithContentsOfFile:self.path] ?: @{}; }
- (BOOL)save:(NSDictionary *)changes {
    NSMutableDictionary *prefs=[[self settings] mutableCopy];
    [prefs addEntriesFromDictionary:changes];
    if ([prefs[@"firstValue"] boolValue] && ![prefs[@"NotificationAlert"] length]) prefs[@"NotificationAlert"]=@"alert.mp3";
    if ([prefs writeToFile:self.path atomically:YES]) return YES;
    UIAlertController *error=[UIAlertController alertControllerWithTitle:@"Could not save" message:@"Reinstall SmartNotifications to repair its settings folder permissions." preferredStyle:UIAlertControllerStyleAlert];
    [error addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
    [self presentViewController:error animated:YES completion:nil];
    return NO;
}
- (NSInteger)numberOfSectionsInTableView:(UITableView *)table { return 3; }
- (NSInteger)tableView:(UITableView *)table numberOfRowsInSection:(NSInteger)section { return section==1 ? 2 : 1; }
- (NSString *)tableView:(UITableView *)table titleForFooterInSection:(NSInteger)section {
    if (section==0) return @"Uses this app’s chosen custom sound. If none is selected, alert.mp3 is used.";
    if (section==1) return @"Independent volume applies only to this app’s notification: 100% requests full alert volume, 0% is silent. Turn it off to follow Ringtone and Alerts volume.";
    return @"Bypass Mute lets only this app’s custom notification sound play in silent mode. Other apps continue to follow silent mode. Existing Focus and notification-blocking settings still apply.";
}
- (void)toggle:(UISwitch *)sender {
    NSString *key=sender.tag==0 ? @"firstValue" : sender.tag==1 ? @"fourthValue" : @"secondValue";
    NSMutableDictionary *changes=[@{key:@(sender.on)} mutableCopy];
    if (sender.on && sender.tag!=0) changes[@"firstValue"]=@YES;
    if (sender.on && sender.tag==1 && ![self settings][@"volumeLevel"]) changes[@"volumeLevel"]=@1.0;
    [self save:changes]; [self.tableView reloadData];
}
- (void)slide:(UISlider *)sender {
    self.volumeLabel.text=[NSString stringWithFormat:@"%.0f%%",sender.value*100];
}
- (void)saveSlider:(UISlider *)sender {
    [self save:@{@"volumeLevel":@(sender.value)}];
}
- (UITableViewCell *)tableView:(UITableView *)table cellForRowAtIndexPath:(NSIndexPath *)index {
    UITableViewCell *cell=[[UITableViewCell alloc] initWithStyle:UITableViewCellStyleDefault reuseIdentifier:nil];
    cell.selectionStyle=UITableViewCellSelectionStyleNone;
    NSDictionary *prefs=[self settings];
    if (index.section==1 && index.row==1) {
        UISlider *slider=[UISlider new]; slider.minimumValue=0; slider.maximumValue=1;
        id stored=prefs[@"volumeLevel"];
        float value=[stored respondsToSelector:@selector(floatValue)] ? [stored floatValue] : 1;
        slider.value=isfinite(value) ? fmaxf(0,fminf(1,value)) : 1;
        slider.enabled=[prefs[@"fourthValue"] boolValue];
        slider.accessibilityLabel=@"Independent notification volume";
        [slider addTarget:self action:@selector(slide:) forControlEvents:UIControlEventValueChanged];
        [slider addTarget:self action:@selector(saveSlider:) forControlEvents:UIControlEventTouchUpInside|UIControlEventTouchUpOutside|UIControlEventTouchCancel];
        self.volumeLabel=[UILabel new];
        self.volumeLabel.font=[UIFont monospacedDigitSystemFontOfSize:16 weight:UIFontWeightRegular];
        [self slide:slider];
        UIStackView *stack=[[UIStackView alloc] initWithArrangedSubviews:@[slider,self.volumeLabel]];
        stack.spacing=12; stack.alignment=UIStackViewAlignmentCenter; stack.translatesAutoresizingMaskIntoConstraints=NO;
        [cell.contentView addSubview:stack];
        UILayoutGuide *g=cell.contentView.layoutMarginsGuide;
        [NSLayoutConstraint activateConstraints:@[[stack.leadingAnchor constraintEqualToAnchor:g.leadingAnchor],
            [stack.trailingAnchor constraintEqualToAnchor:g.trailingAnchor],
            [stack.topAnchor constraintEqualToAnchor:g.topAnchor constant:8],
            [stack.bottomAnchor constraintEqualToAnchor:g.bottomAnchor constant:-8],
            [self.volumeLabel.widthAnchor constraintEqualToConstant:55]]];
    } else {
        UISwitch *toggle=[UISwitch new]; toggle.tag=index.section;
        NSString *key=index.section==0 ? @"firstValue" : index.section==1 ? @"fourthValue" : @"secondValue";
        toggle.on=[prefs[key] boolValue];
        [toggle addTarget:self action:@selector(toggle:) forControlEvents:UIControlEventValueChanged];
        cell.accessoryView=toggle;
        cell.textLabel.text=@[@"Custom notification sound",@"Independent volume",@"Bypass mute"][index.section];
        cell.textLabel.numberOfLines=0;
    }
    return cell;
}
@end

static IMP oldAppear;
static char pathKey;
static void OpenAudio(UIViewController *controller,SEL cmd,id sender) {
    NSString *path=objc_getAssociatedObject(controller,&pathKey);
    if (!path.length) return;
    SNAudioSettings *page=[[SNAudioSettings alloc] initWithStyle:UITableViewStyleInsetGrouped];
    page.path=path;
    [controller.navigationController pushViewController:page animated:YES];
}
static void DetailAppeared(UIViewController *controller,SEL cmd,BOOL animated) {
    ((void(*)(id,SEL,BOOL))oldAppear)(controller,cmd,animated);
    if (![controller respondsToSelector:NSSelectorFromString(@"datesPlistPath")]) return;
    // The original method returns the selected app's exact preference path.
    NSString *path=((id(*)(id,SEL))objc_msgSend)(controller,NSSelectorFromString(@"datesPlistPath"));
    if (![path isKindOfClass:NSString.class] || ![path hasPrefix:SNDirectory] ||
        ![path.stringByDeletingLastPathComponent isEqualToString:[SNDirectory substringToIndex:SNDirectory.length-1]] ||
        ![path.pathExtension isEqualToString:@"plist"]) return;
    objc_setAssociatedObject(controller,&pathKey,path,OBJC_ASSOCIATION_COPY_NONATOMIC);
    NSMutableArray *items=[controller.navigationItem.rightBarButtonItems mutableCopy] ?: [NSMutableArray new];
    for (UIBarButtonItem *item in items) if (item.action==@selector(snOpenAudio:)) return;
    [items addObject:[[UIBarButtonItem alloc] initWithTitle:@"Audio" style:UIBarButtonItemStylePlain target:controller action:@selector(snOpenAudio:)]];
    controller.navigationItem.rightBarButtonItems=items;
}
static void InstallDetailUI(void) {
    static BOOL installed;
    if (installed) return;
    Class cls=NSClassFromString(@"SmartDetailView");
    if (!cls) return;
    Method appear=class_getInstanceMethod(cls,@selector(viewDidAppear:));
    if (!appear) return;
    if (!class_addMethod(cls,@selector(snOpenAudio:),(IMP)OpenAudio,"v@:@")) return;
    oldAppear=method_getImplementation(appear);
    // Add an override on this class, never mutate UIViewController's inherited method.
    if (!class_addMethod(cls,@selector(viewDidAppear:),(IMP)DetailAppeared,method_getTypeEncoding(appear)))
        oldAppear=method_setImplementation(class_getInstanceMethod(cls,@selector(viewDidAppear:)),(IMP)DetailAppeared);
    installed=YES;
}
__attribute__((constructor)) static void InstallSettings(void) {
    @autoreleasepool {
        // Filter is Preferences only. Bundle notification handles lazy pane loading.
        [[NSNotificationCenter defaultCenter] addObserverForName:NSBundleDidLoadNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) { InstallDetailUI(); }];
        dispatch_async(dispatch_get_main_queue(),^{ InstallDetailUI(); });
    }
}
