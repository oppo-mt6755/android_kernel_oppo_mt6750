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
  the commits immediately before the Android driver port.

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
  CROSS_COMPILE="$PWD/../../prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/bin/aarch64-linux-android-" \
  oppo6750_15127_debug_defconfig
make O=/tmp/oppo-mt6750-hermes ARCH=arm64 \
  CROSS_COMPILE="$PWD/../../prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/bin/aarch64-linux-android-" -j12
```

The resulting image is `arch/arm64/boot/Image.gz-dtb`. The build has warnings
from the legacy MediaTek code, but no compilation errors.
