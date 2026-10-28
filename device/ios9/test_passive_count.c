// SPDX-License-Identifier: MIT
// The production counter is included unchanged. Every registry API is mocked.
#define RHFS_PASSIVE_HOST_TEST 1
#define main rhfs_unexecuted_probe_main
#include "ios9_image_capabilities.c"
#undef main
#include <stdlib.h>

enum { MAX_ENTRIES = 66, ENTRY_BASE = 256, ITERATOR = 65536 };
static const char requested_class[] = "IOHDIXController";
static unsigned checks, cases;
static const char *case_name;

#define CHECK(condition) do { \
    ++checks; \
    if (!(condition)) { \
        fprintf(stderr, "passive counter case=%s line=%u failed: %s\n", \
            case_name, (unsigned)__LINE__, #condition); \
        exit(1); \
    } \
} while (0)

typedef struct {
    const char *classes[MAX_ENTRIES];
    unsigned entries, returned, class_calls, next_calls, valid_calls;
    unsigned matching_calls, released_entries, released_iterators;
    unsigned live[MAX_ENTRIES];
    unsigned fail_next_call, fail_valid_call, invalid_valid_call, fail_class_call;
    unsigned empty_class_call, unterminated_class_call;
    int match_missing, query_failed, null_iterator, null_success_next;
} fixture;

static fixture current;
static unsigned char matching_token;

static void reset(const char *name, unsigned entries)
{
    CHECK(entries <= MAX_ENTRIES);
    case_name = name;
    ++cases;
    memset(&current, 0, sizeof(current));
    current.entries = entries;
    for (unsigned i = 0; i < entries; ++i) current.classes[i] = requested_class;
}

CFMutableDictionaryRef IOServiceMatching(const char *name)
{
    ++current.matching_calls;
    CHECK(!strcmp(name, requested_class));
    return current.match_missing ? NULL : (CFMutableDictionaryRef)&matching_token;
}

rhfs_kern_return_t IOServiceGetMatchingServices(uint32_t master, CFDictionaryRef match,
                                               rhfs_io_object_t *iterator)
{
    CHECK(master == 0 && match == (CFDictionaryRef)&matching_token);
    *iterator = 0;
    if (current.query_failed) return (int)0xe00002bdU;
    if (!current.null_iterator) *iterator = ITERATOR;
    return 0;
}

rhfs_kern_return_t io_iterator_is_valid(rhfs_io_object_t iterator, uint32_t *valid)
{
    CHECK(iterator == ITERATOR && current.released_iterators == 0);
    ++current.valid_calls;
    *valid = 0;
    if (current.valid_calls == current.fail_valid_call) return (int)0x10000003U;
    if (current.valid_calls != current.invalid_valid_call) *valid = 1;
    return 0;
}

rhfs_kern_return_t io_iterator_next(rhfs_io_object_t iterator, rhfs_io_object_t *entry)
{
    CHECK(iterator == ITERATOR && current.released_iterators == 0);
    ++current.next_calls;
    *entry = 0;
    if (current.next_calls == current.fail_next_call) return (int)0x10000003U;
    if (current.null_success_next) return 0;
    if (current.returned == current.entries) return (int)0xe00002c0U;
    unsigned index = current.returned++;
    CHECK(!current.live[index]);
    current.live[index] = 1;
    *entry = ENTRY_BASE + index;
    return 0;
}

rhfs_kern_return_t IOObjectGetClass(rhfs_io_object_t entry, char *name)
{
    CHECK(entry >= ENTRY_BASE && entry < ENTRY_BASE + current.entries);
    CHECK(current.live[entry - ENTRY_BASE] == 1);
    ++current.class_calls;
    if (current.class_calls == current.fail_class_call) return (int)0xe00002bdU;
    if (current.class_calls == current.unterminated_class_call) {
        memset(name, 'x', 128);
        return 0;
    }
    if (current.class_calls == current.empty_class_call) {
        name[0] = 0;
        return 0;
    }
    size_t length = strlen(current.classes[entry - ENTRY_BASE]);
    CHECK(length < 128);
    memcpy(name, current.classes[entry - ENTRY_BASE], length + 1);
    return 0;
}

rhfs_kern_return_t IOObjectRelease(rhfs_io_object_t entry)
{
    if (entry == ITERATOR) {
        CHECK(current.released_iterators == 0);
        ++current.released_iterators;
    } else {
        CHECK(entry >= ENTRY_BASE && entry < ENTRY_BASE + current.entries);
        unsigned index = entry - ENTRY_BASE;
        CHECK(current.live[index] == 1);
        current.live[index] = 0;
        ++current.released_entries;
    }
    return 0;
}

static void count_result(int complete, unsigned expected)
{
    unsigned count = 99;
    CHECK(exact_count(requested_class, &count) == complete);
    if (complete) CHECK(count == expected);
    CHECK(current.matching_calls == 1);
    CHECK(current.released_entries == current.returned);
    CHECK(current.released_iterators ==
        (unsigned)(!current.match_missing && !current.query_failed && !current.null_iterator));
    for (unsigned i = 0; i < current.returned; ++i) CHECK(!current.live[i]);
}

int main(void)
{
    case_name = "initialization";
    reset("matching allocation fails", 0);
    current.match_missing = 1;
    count_result(0, 0);
    CHECK(current.next_calls == 0 && current.valid_calls == 0);

    reset("matching query fails", 0);
    current.query_failed = 1;
    count_result(0, 0);
    CHECK(current.next_calls == 0 && current.valid_calls == 0);

    reset("successful null iterator means empty", 0);
    current.null_iterator = 1;
    count_result(1, 0);
    CHECK(current.next_calls == 0 && current.valid_calls == 0);

    reset("valid NoDevice end means empty", 0);
    count_result(1, 0);
    CHECK(current.next_calls == 1 && current.valid_calls == 2);

    reset("mixed classes count only exact matches", 3);
    current.classes[0] = "IOHDIXControllerSubclass";
    current.classes[2] = "OtherClass";
    count_result(1, 1);
    CHECK(current.class_calls == 3);

    reset("partial next RPC failure with valid iterator", 2);
    current.fail_next_call = 2;
    count_result(0, 0);
    CHECK(current.returned == 1 && current.class_calls == 1);

    reset("invalid before first next", 1);
    current.invalid_valid_call = 1;
    count_result(0, 0);
    CHECK(current.next_calls == 0);

    reset("validity RPC fails before first next", 1);
    current.fail_valid_call = 1;
    count_result(0, 0);
    CHECK(current.next_calls == 0);

    reset("invalid after returned entry", 1);
    current.invalid_valid_call = 2;
    count_result(0, 0);
    CHECK(current.returned == 1 && current.class_calls == 0);

    reset("validity RPC fails after returned entry", 1);
    current.fail_valid_call = 2;
    count_result(0, 0);
    CHECK(current.returned == 1 && current.class_calls == 0);

    reset("invalid after NoDevice end", 1);
    current.invalid_valid_call = 4;
    count_result(0, 0);
    CHECK(current.returned == 1 && current.next_calls == 2);

    reset("validity RPC fails after NoDevice end", 1);
    current.fail_valid_call = 4;
    count_result(0, 0);

    reset("success with null next entry is incomplete", 0);
    current.null_success_next = 1;
    count_result(0, 0);

    reset("class RPC fails after a partial count", 2);
    current.fail_class_call = 2;
    count_result(0, 0);
    CHECK(current.returned == 2 && current.class_calls == 2);

    reset("empty class is incomplete", 1);
    current.empty_class_call = 1;
    count_result(0, 0);

    reset("unterminated class is incomplete", 1);
    current.unterminated_class_call = 1;
    count_result(0, 0);

    reset("exactly 64 entries complete", 64);
    count_result(1, 64);
    CHECK(current.class_calls == 64 && current.next_calls == 65);

    reset("65th entry exceeds the bound", 65);
    count_result(0, 0);
    CHECK(current.returned == 65 && current.class_calls == 64);

    reset("nonmatches consume the inspection bound", 65);
    for (unsigned i = 0; i < current.entries; ++i) current.classes[i] = "OtherClass";
    count_result(0, 0);
    CHECK(current.returned == 65 && current.class_calls == 64);

    printf("passive_counter_cases=%u checks=%u external_registry_calls=0\n", cases, checks);
    return 0;
}
