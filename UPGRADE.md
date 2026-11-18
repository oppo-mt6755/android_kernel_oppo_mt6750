# A37 kernel history and Android 8.1 port

The original `Lollipop` branch is preserved. The following branches are
reproducible and intentionally separate the stages of the port:

* `reconstructed/oppo-3.10.72` attaches the four vendor commits to the
  Linux `v3.10.72` parent. The reconstructed parent is inferred from the
  stock `Makefile`; it is not a claim that the missing vendor history was
  recovered.
* `integration/oppo-3.10.108` merges Linux `v3.10.108`, then ports the
  Binder and sdcardfs versions from `ibilux/android_kernel_xiaomi_hermes`
  (`lineage-16.0`). The required mount-aware VFS interfaces are included in
  the commits immediately after the Android driver port.

The OPPO evidence report and path-only archive are generated outside the
kernel repository so large generated archives are not committed:

```sh
python3 scripts/oppo-history.py audit \
  --output ../mt6750-upgrade-artifacts/vendor-audit
```

Path names and `VENDOR_EDIT` markers are evidence for review; they do not
prove that every line is an OPPO change. A clean OPPO-only patch requires a
matching pre-OPPO MediaTek source tree.

For A37 / `oppo6750_15127`, the Android 8.1 debug configuration and full
kernel build were verified with the repository's AArch64 GCC 4.9 toolchain:

```sh
make O=/tmp/oppo-mt6750-hermes ARCH=arm64 \
  CROSS_COMPILE="$PWD/../../../prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/bin/aarch64-linux-android-" \
  oppo6750_15127_debug_defconfig
make O=/tmp/oppo-mt6750-hermes ARCH=arm64 \
  CROSS_COMPILE="$PWD/../../../prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/bin/aarch64-linux-android-" -j12
```

The resulting image is `arch/arm64/boot/Image.gz-dtb`. The build has warnings
from the legacy MediaTek code, but no compilation errors.

The Oreo bring-up additionally backports SELinux policy version 30 / extended
ioctl permissions from Hermes commit `8b967fe4ba6`, its LSM audit support, and
conditional-rule correction `c9bab6a7516`. This is required for Oreo policy
loading even while the development image is permissive. Standard version 29
policies remain supported. A37 on-device testing confirmed Oreo policy loading
and both init stages. The first boot blocker was init's mandatory mmap ASLR
check: `/proc/sys/vm/mmap_rnd_bits` did not exist and init deliberately rebooted.

Backport the mmap entropy sysctls, ARM64/compat mmap randomization and
`get_random_long()` from Hermes commits `bd30f10fbc4`, `42afae76b53`,
`7df537cb0d7`, and the ARM64 portion of `7b9d9900110`. Adapt the sysctl placement
to this MTK tree. Native and compat bounds remain 18..24 and 11..16 bits;
Oreo init successfully selects 24 and 16 on the actual A37.

MTK firmware, touch firmware, modem firmware, MD32 files and vendor module
paths now use `/system/vendor`. The generic firmware loader also searches
`/system/vendor/firmware` and `/system/vendor/etc/firmware`, retaining its
normal Linux fallback directories. Shell/interpreter and `/data` paths remain
unchanged. A separate fix releases the VFS rename name snapshot after use.
