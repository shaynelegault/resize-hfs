// SPDX-License-Identifier: MIT
// Target-pinned passive inventory. No user-client opens or image attachments.
#include <CoreFoundation/CoreFoundation.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/sysctl.h>
#include "hdix_candidate_layout.h"

#if !defined(__arm__) || defined(__LP64__)
#error This capability probe is intended for ARMv7 iOS.
#endif
_Static_assert(sizeof(uintptr_t) == 4, "probe pointer must be ARMv7 width");
_Static_assert(sizeof(off_t) == 8, "probe file offsets must be 64-bit");

typedef uint32_t rhfs_io_object_t;
typedef int rhfs_kern_return_t;
rhfs_kern_return_t IOObjectRelease(rhfs_io_object_t);
rhfs_kern_return_t IOObjectGetClass(rhfs_io_object_t, char *);
CFMutableDictionaryRef IOServiceMatching(const char *);
rhfs_kern_return_t IOServiceGetMatchingServices(uint32_t, CFDictionaryRef, rhfs_io_object_t *);
rhfs_io_object_t IOIteratorNext(rhfs_io_object_t);

static int target_matches(void)
{
    char model[64] = {0}, build[64] = {0};
    size_t model_size = sizeof(model), build_size = sizeof(build);
    if (sysctlbyname("hw.machine", model, &model_size, NULL, 0) ||
        sysctlbyname("kern.osversion", build, &build_size, NULL, 0) ||
        model_size == 0 || model_size >= sizeof(model) ||
        build_size == 0 || build_size >= sizeof(build)) return 0;
    return !strcmp(model, "iPad2,5") && !strcmp(build, "13G36");
}

static const char *category(const char *path)
{
    struct stat item;
    if (lstat(path, &item)) return errno == ENOENT || errno == ENOTDIR ? "missing" : "unavailable";
    if (S_ISREG(item.st_mode)) return "regular";
    if (S_ISLNK(item.st_mode)) return "symlink";
    if (S_ISDIR(item.st_mode)) return "directory";
    return "other";
}

static int exact_count(const char *class_name, unsigned *out)
{
    rhfs_io_object_t iterator = 0, entry;
    CFMutableDictionaryRef match = IOServiceMatching(class_name);
    unsigned checked = 0;
    *out = 0;
    if (!match || IOServiceGetMatchingServices(0, match, &iterator) || !iterator) return 0;
    while ((entry = IOIteratorNext(iterator)) != 0) {
        char name[128] = {0};
        if (++checked > 64 || IOObjectGetClass(entry, name) || name[127] != 0) {
            IOObjectRelease(entry);
            IOObjectRelease(iterator);
            return 0;
        }
        if (!strcmp(name, class_name)) (*out)++;
        IOObjectRelease(entry);
    }
    IOObjectRelease(iterator);
    return 1;
}

int main(int argc, char **argv)
{
    (void)argv;
    if (argc != 1 || !target_matches()) {
        puts("target=refused");
        return 2;
    }
    puts("target=ipad2,5-ios9-13g36");
    printf("pointer_bytes=%u\n", (unsigned)sizeof(uintptr_t));
    printf("off_t_bytes=%u\n", (unsigned)sizeof(off_t));
    printf("candidate_create_block_bytes=%u\n", (unsigned)sizeof(struct rhfs_hdix_candidate64));
    printf("candidate_address_offset=%u\n", (unsigned)offsetof(struct rhfs_hdix_candidate64, serialized_user_address));
    printf("candidate_length_offset=%u\n", (unsigned)offsetof(struct rhfs_hdix_candidate64, serialized_length));
    printf("file=diskimages-framework status=%s\n", category("/System/Library/PrivateFrameworks/DiskImages.framework/DiskImages"));
    printf("file=hdiutil status=%s\n", category("/usr/bin/hdiutil"));
    printf("file=usr-hdik status=%s\n", category("/usr/sbin/hdik"));
    printf("file=sbin-hdik status=%s\n", category("/sbin/hdik"));
    printf("file=mount-hfs status=%s\n", category("/sbin/mount_hfs"));
    printf("file=fsck-hfs status=%s\n", category("/sbin/fsck_hfs"));
    unsigned count = 0;
    if (exact_count("IOHDIXController", &count)) printf("class=IOHDIXController exact_count=%u\n", count);
    else puts("class=IOHDIXController exact_count=unavailable");
    if (exact_count("IOHDIXHDDriveInKernel", &count)) printf("class=IOHDIXHDDriveInKernel exact_count=%u\n", count);
    else puts("class=IOHDIXHDDriveInKernel exact_count=unavailable");
    puts("user_client_open_attempted=false");
    puts("image_attach_attempted=false");
    return 0;
}
