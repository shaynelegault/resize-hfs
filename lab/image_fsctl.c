// SPDX-License-Identifier: MIT
// macOS-only helper for the fixed 192 MiB disposable-image experiment.
#ifndef __APPLE__
#include <stdio.h>
int main(void) { fputs("The image helper requires macOS.\n", stderr); return 2; }
#else
#include <CoreFoundation/CoreFoundation.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

#define MEDIA_BYTES UINT64_C(201326592)
#define TARGET_BYTES UINT64_C(100663296)
#define HFS_SHRINK _IOW('h', 2, uint64_t)
_Static_assert(HFS_SHRINK == 0x80086802U, "Unexpected HFS fsctl ABI");

static void refuse(const char *message)
{
    fprintf(stderr, "Image operation refused: %s\n", message);
    exit(2);
}

static CFTypeRef field(CFDictionaryRef d, const char *name)
{
    CFStringRef key = CFStringCreateWithCString(NULL, name, kCFStringEncodingUTF8);
    CFTypeRef value = CFDictionaryGetValue(d, key);
    CFRelease(key);
    if (!value) refuse("missing image evidence field");
    return value;
}

static void text(CFTypeRef value, char *out, size_t count)
{
    if (CFGetTypeID(value) != CFStringGetTypeID() ||
        !CFStringGetCString(value, out, (CFIndex)count, kCFStringEncodingUTF8))
        refuse("invalid evidence string");
}

static bool equal(CFTypeRef value, const char *expected)
{
    char out[PATH_MAX];
    text(value, out, sizeof(out));
    return strcmp(out, expected) == 0;
}

static uint64_t number(CFTypeRef value)
{
    int64_t n = -1;
    if (CFGetTypeID(value) != CFNumberGetTypeID() ||
        !CFNumberGetValue(value, kCFNumberSInt64Type, &n) || n < 0)
        refuse("invalid evidence number");
    return (uint64_t)n;
}

static bool boolean(CFTypeRef value)
{
    if (CFGetTypeID(value) != CFBooleanGetTypeID()) refuse("invalid evidence boolean");
    return CFBooleanGetValue(value);
}

static CFTypeRef parse(const unsigned char *data, size_t count)
{
    CFDataRef bytes = CFDataCreate(NULL, data, (CFIndex)count);
    CFPropertyListRef p = CFPropertyListCreateWithData(NULL, bytes,
        kCFPropertyListImmutable, NULL, NULL);
    CFRelease(bytes);
    if (!p || CFGetTypeID(p) != CFDictionaryGetTypeID()) refuse("invalid evidence plist");
    return p;
}

static CFDictionaryRef command(char *const argv[])
{
    int pipes[2], status = 0;
    if (pipe(pipes)) refuse("evidence pipe unavailable");
    pid_t pid = fork();
    if (pid < 0) refuse("evidence process unavailable");
    if (pid == 0) {
        close(pipes[0]);
        if (dup2(pipes[1], STDOUT_FILENO) < 0) _exit(126);
        close(pipes[1]);
        execv(argv[0], argv);
        _exit(127);
    }
    close(pipes[1]);
    size_t capacity = 4U * 1024U * 1024U, count = 0;
    unsigned char *buffer = malloc(capacity);
    if (!buffer) refuse("evidence buffer unavailable");
    while (count < capacity) {
        ssize_t n = read(pipes[0], buffer + count, capacity - count);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) refuse("evidence read failed");
        if (!n) break;
        count += (size_t)n;
    }
    close(pipes[0]);
    while (waitpid(pid, &status, 0) < 0) { if (errno != EINTR) refuse("evidence wait failed"); }
    if (count == capacity || !WIFEXITED(status) || WEXITSTATUS(status))
        refuse("host image evidence unavailable");
    CFDictionaryRef result = (CFDictionaryRef)parse(buffer, count);
    free(buffer);
    return result;
}

static void regular(const char *path, const struct stat *expected, uint64_t uid)
{
    struct stat st;
    if (lstat(path, &st) || !S_ISREG(st.st_mode) || st.st_nlink != 1 ||
        (uint64_t)st.st_uid != uid || st.st_dev != expected->st_dev ||
        st.st_ino != expected->st_ino || st.st_size != expected->st_size)
        refuse("image file identity changed");
}

int main(int argc, char **argv)
{
    if (argc != 3 || (strcmp(argv[1], "probe") && strcmp(argv[1], "shrink")))
        refuse("use probe or shrink with a lab-generated plist");
    bool shrink = strcmp(argv[1], "shrink") == 0;
    char plist_path[PATH_MAX], image[PATH_MAX], mount[PATH_MAX], device[64];
    char token[128], volume[128], canonical[PATH_MAX];
    struct stat manifest_stat, image_stat;
    if (!realpath(argv[2], plist_path) || strcmp(argv[2], plist_path))
        refuse("lab receipt needs its canonical absolute path");
    int receipt = open(plist_path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK);
    if (receipt < 0 || fstat(receipt, &manifest_stat) || !S_ISREG(manifest_stat.st_mode) ||
        manifest_stat.st_nlink != 1 || manifest_stat.st_size <= 0 || manifest_stat.st_size > 65536 ||
        (manifest_stat.st_mode & 0077)) refuse("lab receipt must be a private regular file");
    unsigned char input[65536];
    ssize_t length = pread(receipt, input, (size_t)manifest_stat.st_size, 0);
    close(receipt);
    if (length != manifest_stat.st_size) refuse("lab receipt read failed");
    CFDictionaryRef manifest = (CFDictionaryRef)parse(input, (size_t)length);
    if (!equal(field(manifest, "kind"), "resize-hfs-disposable-image-v1"))
        refuse("unknown image experiment");
    text(field(manifest, "image"), image, sizeof(image));
    text(field(manifest, "mount"), mount, sizeof(mount));
    text(field(manifest, "device"), device, sizeof(device));
    text(field(manifest, "token"), token, sizeof(token));
    text(field(manifest, "volume_name"), volume, sizeof(volume));
    uint64_t uid = number(field(manifest, "owner_uid"));
    bool read_only = boolean(field(manifest, "read_only"));
    if ((uint64_t)manifest_stat.st_uid != uid || (getuid() != 0 && getuid() != uid) ||
        number(field(manifest, "media_bytes")) != MEDIA_BYTES ||
        number(field(manifest, "target_bytes")) != TARGET_BYTES || strlen(token) != 36)
        refuse("unexpected experiment identity or size");
    if (!realpath(image, canonical) || strcmp(image, canonical) ||
        !realpath(mount, canonical) || strcmp(mount, canonical))
        refuse("image or mount path is aliased");
    char *parent_end = strrchr(plist_path, '/');
    size_t parent_len = (size_t)(parent_end - plist_path) + 1;
    if (strncmp(image, plist_path, parent_len) || strncmp(mount, plist_path, parent_len) ||
        strchr(image + parent_len, '/') || strchr(mount + parent_len, '/'))
        refuse("image and mount must be direct children of the lab directory");
    if (shrink && (strcmp(image + parent_len, "fixture.dmg") || read_only))
        refuse("shrink accepts the fresh writable fixture only");
    if (lstat(image, &image_stat) || !S_ISREG(image_stat.st_mode) ||
        number(field(manifest, "image_inode")) != (uint64_t)image_stat.st_ino ||
        number(field(manifest, "image_device")) != (uint64_t)image_stat.st_dev ||
        number(field(manifest, "image_bytes")) != (uint64_t)image_stat.st_size)
        refuse("image identity differs from its receipt");
    regular(image, &image_stat, uid);
    char *hdi_argv[] = {"/usr/bin/hdiutil", "info", "-plist", NULL};
    CFDictionaryRef images = command(hdi_argv);
    CFArrayRef array = field(images, "images");
    if (CFGetTypeID(array) != CFArrayGetTypeID()) refuse("image inventory unavailable");
    unsigned matches = 0;
    for (CFIndex i = 0; i < CFArrayGetCount(array); i++) {
        CFDictionaryRef entry = CFArrayGetValueAtIndex(array, i);
        if (CFGetTypeID(entry) != CFDictionaryGetTypeID()) refuse("invalid image inventory");
        if (!equal(field(entry, "image-path"), image)) continue;
        if (number(field(entry, "owner-uid")) != uid || boolean(field(entry, "image-encrypted")) ||
            boolean(field(entry, "writeable")) == read_only ||
            number(field(entry, "blocksize")) != 512 ||
            number(field(entry, "blockcount")) != MEDIA_BYTES / 512)
            refuse("attached image properties differ");
        CFArrayRef entities = field(entry, "system-entities");
        if (CFGetTypeID(entities) != CFArrayGetTypeID() || CFArrayGetCount(entities) != 1)
            refuse("fixture must have one whole-volume entity");
        CFDictionaryRef entity = CFArrayGetValueAtIndex(entities, 0);
        if (CFGetTypeID(entity) != CFDictionaryGetTypeID()) refuse("invalid image entity");
        if (!equal(field(entity, "dev-entry"), device) || !equal(field(entity, "mount-point"), mount))
            refuse("image backing or mount differs");
        matches++;
    }
    if (matches != 1) refuse("image backing is ambiguous");
    char *disk_argv[] = {"/usr/sbin/diskutil", "info", "-plist", device, NULL};
    CFDictionaryRef disk = command(disk_argv);
    if (!equal(field(disk, "DeviceNode"), device) || !equal(field(disk, "MountPoint"), mount) ||
        !equal(field(disk, "VirtualOrPhysical"), "Virtual") ||
        !equal(field(disk, "BusProtocol"), "Disk Image") ||
        !equal(field(disk, "FilesystemType"), "hfs") || !equal(field(disk, "VolumeName"), volume) ||
        boolean(field(disk, "Internal")) || boolean(field(disk, "OSInternalMedia")) ||
        boolean(field(disk, "SystemImage")) || !boolean(field(disk, "WholeDisk")) ||
        boolean(field(disk, "WritableVolume")) == read_only ||
        number(field(disk, "IOKitSize")) != MEDIA_BYTES)
        refuse("mount is not the expected disposable virtual HFS volume");
    int dir = open(mount, O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
    struct statfs fs;
    if (dir < 0 || fstatfs(dir, &fs) || strcmp(fs.f_fstypename, "hfs") ||
        strcmp(fs.f_mntonname, mount) || strcmp(fs.f_mntfromname, device) ||
        ((fs.f_flags & MNT_RDONLY) != 0) != read_only)
        refuse("live mount differs from image evidence");
    int marker = openat(dir, ".resize-hfs-token", O_RDONLY | O_NOFOLLOW);
    char check_token[128] = {0}; struct stat marker_stat;
    if (marker < 0 || fstat(marker, &marker_stat) || !S_ISREG(marker_stat.st_mode) ||
        marker_stat.st_size != 36 || pread(marker, check_token, 36, 0) != 36 || strcmp(check_token, token))
        refuse("fixture token differs");
    close(marker);
    regular(image, &image_stat, uid);
    if (shrink) {
        if ((uint64_t)fs.f_blocks * fs.f_bsize != MEDIA_BYTES)
            refuse("fixture has already been resized");
        uint64_t target = TARGET_BYTES;
        errno = 0;
        int result = ffsctl(dir, HFS_SHRINK, &target, 0), error = errno;
        printf("{\"fsctl_return\":%d,\"errno\":%d}\n", result, error);
        close(dir);
        return result ? 1 : 0;
    }
    printf("{\"volume_bytes\":%" PRIu64 ",\"media_bytes\":%" PRIu64 ",\"read_only\":%s,\"extents\":[",
           (uint64_t)fs.f_blocks * fs.f_bsize, MEDIA_BYTES, read_only ? "true" : "false");
    int file = openat(dir, "late.bin", O_RDONLY | O_NOFOLLOW);
    struct stat st;
    if (file < 0 || fstat(file, &st) || !S_ISREG(st.st_mode) || st.st_size != 4 * 1024 * 1024)
        refuse("relocation fixture is missing");
    off_t cursor = 0; unsigned pieces = 0;
    while (cursor < st.st_size) {
        struct log2phys mapping = {.l2p_flags = 0, .l2p_contigbytes = st.st_size - cursor,
                                  .l2p_devoffset = cursor};
        if (++pieces > 4096 || fcntl(file, F_LOG2PHYS_EXT, &mapping) ||
            mapping.l2p_contigbytes <= 0 || mapping.l2p_devoffset < 0 ||
            mapping.l2p_contigbytes > st.st_size - cursor)
            refuse("file extent mapping unavailable");
        printf("%s{\"logical\":%" PRIu64 ",\"physical\":%" PRIu64 ",\"bytes\":%" PRIu64 "}",
               pieces > 1 ? "," : "", (uint64_t)cursor,
               (uint64_t)mapping.l2p_devoffset, (uint64_t)mapping.l2p_contigbytes);
        cursor += mapping.l2p_contigbytes;
    }
    puts("]}");
    close(file); close(dir);
    CFRelease(disk); CFRelease(images); CFRelease(manifest);
    return 0;
}
#endif
