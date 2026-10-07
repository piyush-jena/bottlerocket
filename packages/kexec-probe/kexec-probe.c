/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

/* Neither deliberately invalid argument set can install a replacement kernel. */
static bool read_text(const char *path, char *buffer, size_t capacity)
{
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        fprintf(stderr, "open %s: %s\n", path, strerror(errno));
        return false;
    }
    size_t used = 0;
    while (used < capacity - 1) {
        ssize_t n = read(fd, buffer + used, capacity - 1 - used);
        if (n < 0 && errno == EINTR)
            continue;
        if (n < 0) {
            fprintf(stderr, "read %s: %s\n", path, strerror(errno));
            close(fd);
            return false;
        }
        if (n == 0) {
            buffer[used] = '\0';
            close(fd);
            printf("CONTEXT %s\n%s\n", path, buffer);
            return true;
        }
        used += (size_t)n;
    }
    fprintf(stderr, "refusing truncated context from %s\n", path);
    close(fd);
    return false;
}

static bool initial_user_namespace(void)
{
    char self[128], init[128];
    ssize_t a = readlink("/proc/self/ns/user", self, sizeof(self) - 1);
    ssize_t b = readlink("/proc/1/ns/user", init, sizeof(init) - 1);
    if (a < 0 || b < 0 || a >= (ssize_t)sizeof(self) - 1 ||
        b >= (ssize_t)sizeof(init) - 1) {
        fprintf(stderr, "cannot read user namespace identities\n");
        return false;
    }
    self[a] = '\0';
    init[b] = '\0';
    printf("NAMESPACE self=%s init=%s\n", self, init);
    return strcmp(self, init) == 0;
}

static bool unlimited_if_present(const char *path)
{
    char text[128];
    if (access(path, F_OK) != 0) {
        if (errno == ENOENT) {
            printf("CONTEXT %s unsupported\n", path);
            return true;
        }
        return false;
    }
    return read_text(path, text, sizeof(text)) && strcmp(text, "-1\n") == 0;
}

static bool context(bool disabled)
{
    char text[16384];
    unsigned long long capabilities = 0;
    if (!read_text("/proc/self/status", text, sizeof(text)))
        return false;
    const char *caps = strstr(text, "\nCapEff:");
    if (!caps || sscanf(caps, "\nCapEff: %llx", &capabilities) != 1 ||
        !(capabilities & (1ULL << 22)) ||
        !strstr(text, "\nSeccomp:\t0\n") ||
        !strstr(text, "\nNoNewPrivs:\t0\n") ||
        !initial_user_namespace()) {
        fprintf(stderr, "need initial user namespace, CAP_SYS_BOOT and no seccomp filter\n");
        return false;
    }
    if (!read_text("/proc/self/attr/current", text, sizeof(text)) ||
        !read_text("/sys/kernel/security/lockdown", text, sizeof(text)))
        return false;
    if (!disabled && !strstr(text, "[none]")) {
        fprintf(stderr, "permissive calibration requires lockdown=none\n");
        return false;
    }
    if (!read_text("/proc/sys/kernel/kexec_load_disabled", text, sizeof(text)) ||
        strcmp(text, disabled ? "1\n" : "0\n") != 0) {
        fprintf(stderr, "unexpected kexec_load_disabled value\n");
        return false;
    }
    return unlimited_if_present("/proc/sys/kernel/kexec_load_limit_reboot") &&
           unlimited_if_present("/proc/sys/kernel/kexec_load_limit_panic") &&
           read_text("/sys/kernel/kexec_loaded", text, sizeof(text)) &&
           read_text("/sys/kernel/kexec_crash_loaded", text, sizeof(text));
}

static bool report(const char *name, long result, int error, int expected,
                   bool supported)
{
    printf("SYSCALL %s return=%ld errno=%d (%s) expected_errno=%d status=%s\n",
           name, result, error, strerror(error), expected,
           !supported ? "unsupported" :
           result == -1 && error == expected ? "matched" : "mismatch");
    return result == -1 && error == expected;
}

int main(int argc, char **argv)
{
    if (argc != 2 ||
        (strcmp(argv[1], "--expect-permissive") != 0 &&
         strcmp(argv[1], "--expect-disabled") != 0)) {
        fprintf(stderr, "usage: kexec-probe --expect-permissive|--expect-disabled\n");
        return 2;
    }
    bool disabled = strcmp(argv[1], "--expect-disabled") == 0;
    if (!context(disabled))
        return 2;
    int expected = disabled ? EPERM : EINVAL;
    errno = 0;
    long result = syscall(SYS_kexec_load, 0UL, 17UL, NULL, 0UL);
    int error = errno;
#if defined(__aarch64__)
    /* The consumed ARM kernel disables legacy loading; ENOSYS is not hardening. */
    bool legacy_ok = report("kexec_load", result, error, ENOSYS, false);
#elif defined(__x86_64__)
    bool legacy_ok = report("kexec_load", result, error, expected, true);
#else
#error Unsupported calibration architecture
#endif
    errno = 0;
    result = syscall(SYS_kexec_file_load, -1, -1, 0UL, NULL, 0x8000UL);
    error = errno;
    bool file_ok = report("kexec_file_load", result, error, expected, true);
    puts("Nonloading probes only; successful native-kernel loading calibration is separate.");
    return legacy_ok && file_ok ? 0 : 1;
}
