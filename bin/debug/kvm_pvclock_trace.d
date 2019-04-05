#!/usr/sbin/dtrace -qCs

struct pvclock_vcpu_time_info {
    uint32_t   version;
    uint32_t   pad0;
    uint64_t   tsc_timestamp;
    uint64_t   system_time;
    uint32_t   tsc_to_system_mul;
    char    tsc_shift;
    unsigned char    flags;
    unsigned char    pad[2];
};

struct pvclock_vcpu_time_info *pvclock;

sdt:kvm:kvm_write_guest_time:kvm_write_pvclock
{
	pvclock = (struct pvclock_vcpu_time_info *)arg0;
	printf("host ts: %lu; tsc_timestamp: %lu; tsc_to_system_mul: %u; system_time: %lu; version: %i\n", timestamp, pvclock->tsc_timestamp, pvclock->tsc_to_system_mul, pvclock->system_time, pvclock->version);
}

