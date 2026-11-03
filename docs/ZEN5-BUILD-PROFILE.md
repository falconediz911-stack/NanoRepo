# Zen 5 build profile

## Purpose

Provide opt-in AMD Zen 5 optimized builds without reducing compatibility of the generic NanoOS repository.

GCC and AMD's AOCC documentation describe `znver5` as the AMD Zen 5 compiler target. The profile below is therefore a build-host-independent target for eligible C/C++ packages.

## Initial C/C++ profile

```make
CFLAGS="-O2 -pipe -march=znver5"
CXXFLAGS="${CFLAGS}"
```

This is an example for a dedicated Zen 5 build environment. It must not be copied into the global `/etc/makepkg.conf` on a generic NanoOS installation.

## Rules

- Never use `-march=native` for distributable packages.
- Do not apply Zen 5 flags to the generic stable or testing baseline.
- Do not add speculative flags such as `-Ofast`, `-ffast-math`, or blanket LTO without package-specific correctness and benchmark evidence.
- Build and test the Zen 5 channel on known Zen 5 hardware or a controlled builder with the appropriate target toolchain.
- Record compiler version, target flags, package source revision, and build environment.
- Label CPU-specific packages clearly and require explicit user opt-in.
- Test runtime behavior, not only whether compilation succeeds.

## Package eligibility

A package should enter this channel only when:
1. Its source compiles correctly for the Zen 5 target.
2. Its tests pass on a compatible system.
3. The optimized build has a measurable benefit or a documented compatibility reason.
4. Its full runtime dependency chain is compatible with the channel.
5. It has a distinct package name or an otherwise unambiguous isolation mechanism.

## Language toolchains

This initial profile specifies C/C++ flags only. Rust, Go, JIT runtimes, kernels, and prebuilt upstream binaries need separately verified target configuration; do not assume CFLAGS control them.
