// SPDX-License-Identifier: MIT
// Candidate wire layout from the preserved 13G36 instruction observations.
#ifndef RHFS_HDIX_CANDIDATE_LAYOUT_H
#define RHFS_HDIX_CANDIDATE_LAYOUT_H
#include <stddef.h>
#include <stdint.h>

struct rhfs_hdix_candidate64 {
    uint32_t magic;
    uint32_t serialization_mode;
    uint64_t serialized_user_address;
    uint64_t serialized_length;
    uint8_t reserved[232];
};

_Static_assert(sizeof(struct rhfs_hdix_candidate64) == 256, "candidate input must be 256 bytes");
_Static_assert(offsetof(struct rhfs_hdix_candidate64, serialized_user_address) == 8,
               "candidate address offset must be eight");
_Static_assert(offsetof(struct rhfs_hdix_candidate64, serialized_length) == 16,
               "candidate length offset must be sixteen");
#endif
