#import <Cocoa/Cocoa.h>

static NSString *gLink = nil;

static void LogMessage(NSString *message) {
    NSString *line = [NSString stringWithFormat:@"%@ %@\n", [NSDate date], message];
    fprintf(stderr, "%s", line.UTF8String);

    NSString *logPath = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Logs/AirDropShareLink.log"];
    NSFileHandle *handle = [NSFileHandle fileHandleForWritingAtPath:logPath];
    if (!handle) {
        [[NSFileManager defaultManager] createFileAtPath:logPath contents:nil attributes:nil];
        handle = [NSFileHandle fileHandleForWritingAtPath:logPath];
    }
    if (handle) {
        [handle seekToEndOfFile];
        [handle writeData:[line dataUsingEncoding:NSUTF8StringEncoding]];
        [handle closeFile];
    }
}

@interface AppDelegate : NSObject <NSApplicationDelegate, NSSharingServiceDelegate>
@property (strong) NSWindow *window;
@end

@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    NSString *link = gLink;
    if (link.length == 0) {
        link = [[[NSProcessInfo processInfo] environment] objectForKey:@"AIRDROP_SHARE_LINK"];
    }
    if (link.length == 0) {
        LogMessage(@"No link provided");
        [NSApp terminate:nil];
        return;
    }

    self.window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 420, 120)
                                              styleMask:NSWindowStyleMaskTitled
                                                backing:NSBackingStoreBuffered
                                                  defer:NO];
    [self.window setTitle:@"AirDrop Share"];
    [self.window center];
    [self.window makeKeyAndOrderFront:nil];
    [NSApp activateIgnoringOtherApps:YES];

    NSURL *url = [NSURL URLWithString:link];
    if (!url) {
        LogMessage(@"Invalid URL");
        [NSApp terminate:nil];
        return;
    }

    NSSharingService *service = [NSSharingService sharingServiceNamed:NSSharingServiceNameSendViaAirDrop];
    NSArray *items = @[url];
    if (![service canPerformWithItems:items]) {
        items = @[link, url];
    }
    if (![service canPerformWithItems:items]) {
        LogMessage(@"AirDrop cannot share this item");
        [NSApp terminate:nil];
        return;
    }

    service.delegate = self;
    [service performWithItems:items];
    LogMessage([NSString stringWithFormat:@"AirDrop sheet opened for %@", link]);
}

- (NSWindow *)sharingService:(NSSharingService *)sharingService
    sourceWindowForShareItems:(NSArray *)items
        sharingContentScope:(NSSharingContentScope *)sharingContentScope {
    return self.window;
}

- (void)sharingService:(NSSharingService *)sharingService didShareItems:(NSArray *)items {
    LogMessage([NSString stringWithFormat:@"Share completed: %@", items]);
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(3 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
        [NSApp terminate:nil];
    });
}

- (void)sharingService:(NSSharingService *)sharingService
 didFailToShareItems:(NSArray *)items
               error:(NSError *)error {
    if (error && error.code == NSUserCancelledError) {
        LogMessage(@"Share cancelled by user");
    } else {
        LogMessage([NSString stringWithFormat:@"Share failed: %@ (code %ld)", error.localizedDescription, error ? (long)error.code : 0L]);
    }
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(2 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
        [NSApp terminate:nil];
    });
}

@end

int main(int argc, char *argv[]) {
    @autoreleasepool {
        if (argc >= 2) {
            gLink = @(argv[1]);
        }

        NSApplication *application = [NSApplication sharedApplication];
        [application setActivationPolicy:NSApplicationActivationPolicyRegular];
        AppDelegate *delegate = [[AppDelegate alloc] init];
        [application setDelegate:delegate];
        [application run];
    }
    return 0;
}
