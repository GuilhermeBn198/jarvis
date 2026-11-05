# Linux ARM64 build checkpoint

Status: resumed on 2026-10-26 after the user's instruction to continue the Linux
port. The original pause checkpoint was commit
`30dd7d9e09d2e569804000f6cbb4d6db2152a5b4`. The branch remains
`feat/linux-port`; preserve the pre-existing worktree changes. Gentoo ARM64
now has a completed build and Portage lifecycle smoke under QEMU; Guix ARM64
is still building and remains unverified in the distro matrix. Historical
progress entries below describe the state at their recorded timestamps.

Stale generated Slackware output and intermediate Flatpak source/repository
caches were removed on 2026-10-26, raising free space above Gentoo Node.js's
22 GiB check-reqs threshold while preserving the Flatpak bundle evidence.

## Gentoo ARM64

- Docker container: `jarvis-gentoo-aarch64` (`gentoo/stage3:latest`, ARM64 under
  QEMU); preserve it, do not remove it.
- Build command at pause: `sh scripts/build-package.sh --target gentoo
  --arch aarch64 --output /out` from `/src`.
- Historical pause state: `emerge --onlydeps` was compiling Node.js 26.12.0;
  the retained log ended at Ninja `[101/3417]` in ICU. The current resumed
  Ninja build is recorded separately below.
- Portage log inside the container:
  `/tmp/tmp.o7uf6mIw3M/tmp/portage/net-libs/nodejs-26.12.0/temp/build.log`.
- `/out` is the host bind mount `/tmp/jarvis-gentoo-aarch64/out`.
- `/out` contained no package artifacts at the last check. `/src` is a
  read-only bind mount of this worktree.
- A fresh `emerge --pretend --verbose --onlydeps` for the local Jarvis overlay
  resolved only Node.js 26.12.0 and `dev-python/pip` (9,084 KiB). Installed pip
  from the binary repository and verified `python3.14 -m pip --version`; Node
  is now the only unmet dependency and its ARM64 build is running.
- Latest poll 2026-10-26 21:50 UTC: Node.js ARM64 is compiling with Ninja `-j6`;
  the current log reports `[1322/2473]` (53.5% of this Ninja subtarget), in
  ARM64 codegen objects. Six active `cc1plus` workers were confirmed at about
  595% aggregate CPU; the log counter has held since 21:19:38, but all six
  workers remain active. No cgroup OOM events were recorded. Large V8 object
  compilations take minutes. No build errors
  observed.
  Log and exit marker are under
  `/tmp/tmp.o7uf6mIw3M/tmp/portage/net-libs/nodejs-26.12.0/temp/`.
- Portage integration detail: the retained manual Ninja command builds the
  `node` target, while the Gentoo Node.js ebuild's `src_compile` runs
  `eninja -C out/Release` (the full default graph). A fresh dependency
  resolution with the staged Jarvis overlay still selects only Node.js
  26.12.0; however, `emerge --resume --pretend` reports that no merge queue is
  saved and the masked Node.js item is dropped. Once the manual target
  finishes, use the ebuild phase interface with
  `FEATURES="${FEATURES} noauto"` and the retained `PORTAGE_TMPDIR`, `PKGDIR`,
  overlay, keywords and USE flags to run `compile install package qmerge` on
  `/var/db/repos/gentoo/net-libs/nodejs/nodejs-26.12.0.ebuild`. `noauto` is
  required here: without it, ebuild automatically invokes preceding phases,
  including unpack, which would discard the manually compiled work tree. The
  configured Node.js `out/Release` directory, ebuild and binpkg directory were
  confirmed present at 2026-10-26 17:02 UTC. Do not treat the target executable
  alone as a completed Portage dependency.


## Guix ARM64

- Original failed container: `jarvis-guix-rust190-seccomp`, image
  `metacall/guix:v20260216`, exited with `OOMKilled=true`; after committing its
  state to `jarvis-guix-rust190-resume:cached` (18.99 GB), the stopped container
  and two failed launch containers were removed, freeing about 5 GB.
  Serial fallback container: `jarvis-guix-rust190-resumed3`, paused at 705/1,566
  Rust checksums. Active container: `jarvis-guix-rust190-resumed4`; it uses the
  saved image, the same `/src` host mount, `seccomp=unconfined`, two Guix cores,
  and the Rust recipe's one-core bootstrap.
- Prepared a fresh source snapshot from this worktree at
  `/tmp/jarvis-guix-eval.y9LJB2/jarvis-guix-source.tar.gz`, with the current
  ARM64 OpenCode binary and the three Guix recipe files beside it. The
  previous source mount was empty, so the mounted host directory and entry
  script were restored before restarting the container.
- `guix build --dry-run --system=aarch64-linux -f ./jarvis.scm` passed in a
  disposable container using the same staged inputs.
- The real build is running in `jarvis-guix-rust190-resumed4` with fallback
  enabled, `--cores=2 --max-jobs=1`. The first resumed attempt showed Guix's
  core limit did not change Rust's internal `x.py -j4`; Rust itself was still
  OOM-killed. I fixed the recipe in `packaging/guix/rust-toolchain.scm` to set
  `#:parallel-build?` false for the bootstrap, then verified the revised
  recipe with a successful Guix dry-run. Guix's `generate-all-checksums` uses
  `parallel-job-count`, so one core made this phase unnecessarily serial. The
  current run uses two cores for checksum tasks; the separate Rust bootstrap
  setting remains `x.py -j1`. One restart also failed because the new container
  lacked `seccomp=unconfined`, so Guix could not set process personality. The
  active container has the required security option. Its log and exit marker
  are `/tmp/jarvis-guix-eval.y9LJB2/build-resume4.log` and
  `/tmp/jarvis-guix-eval.y9LJB2/build-resume4.exit`. oneDNN is configured for AArch64; CMake codegen
  completed. At 2026-10-26 18:42 UTC, the Guix Python CTranslate2 wheel
  derivation and all 14 AArch64 extension objects are built. The first
  `python-dunamai` check failed because its timestamp-window test exceeded 60
  seconds under QEMU. A targeted recipe change excludes that timing-sensitive
  test and the upstream shallow-clone test, which attempts network access from
  Guix's isolated build. The rerun passed 55 tests, skipped 6, and deselected
  those 2 cases; the derivation succeeded. Guix has advanced to building Rust
  1.89.0. Its Cargo checksum phase completed for all 1,566 vendored crates
  after 1,372.8 seconds. Guix has started the Rust bootstrap build, compiling
  crates including `lzma-sys`, `clap_lex`, and `crossbeam-epoch`; the earlier
  stage listed 196 crate compilation entries, but Cargo exposes no total for
  this stage. The previous build failed when the host OOM killer sent SIGKILL
  to rustc compiling `rustc_target`; the host had 212 MiB free RAM and all
  23 GiB of swap used. The saved image was restarted with the corrected recipe
  and required seccomp setting. The previous two-core run remains paused at
  705/1,566 checksums. At the 20:15 UTC poll the current two-core run had begun
  Rust 1.89.0's checksum phase and processed 920/1,566 crates (58.7%). A live
  process poll confirmed two concurrent AArch64 `sha256sum` workers, so the
  configured parallel checksum phase is active. At 20:21 UTC this phase was
  at 1,530/1,566 crates (97.7%) at 20:39 UTC. At 20:40 UTC it had advanced to
  1,547/1,566 (98.8%), with checksums through `zerocopy-0.7.35`. At 20:41 UTC
  it had reached 1,562/1,566 (99.7%), through `zerovec-0.11.2`. At 20:42 UTC
  all 1,566 checksums were complete and Rust 1.89 bootstrap compilation had
  started (`typenum`, `shlex`, `crossbeam-utils`, among others). At 20:50 UTC,
  Rust's `build_helper` was actively compiling. By 20:58 that compile had
  completed and Cargo advanced through `quote`, `syn`, `libc`, `cfg-if`,
  `synstructure`, `memchr` and `cc`. At 21:00, 73 `Compiling` entries had
  appeared. By 21:02 it had advanced through `allocator-api2`, `bitflags`,
  `equivalent`, `hashbrown`, `getrandom`, `lock_api` and `indexmap`; the log
  shows 83 `Compiling` entries. Bootstrap/Cargo/rustc processes remained
  active. At 21:03 it had advanced to 88 entries, including `generic-array`
  and `tracing-core`; at 21:04, 91 entries included `tracing-attributes`.
  At 21:05, 94 entries included `crossbeam-utils`, `pin-project-lite` and
  `tracing`; at 21:06 it reached 96 entries, including `rustix`. At 21:07 it
  reached 100 entries, including `rustc_macros` and `linux-raw-sys`; at 21:08,
  the log had 105 entries and was compiling `rustc_hashes` alongside vendored
  crates. At 21:09, rustc was still compiling `rustc_hashes` at about 99% CPU
  (424 MiB RSS). At 21:10, 112 `Compiling` entries had appeared, including
  `stacker`, `fastrand` and `thin-vec`; by 21:11 the count was 117, including
  `unic-langid-impl` and `digest`. At 21:12, 118 entries included
  `crossbeam-deque`; Rust bootstrap remains active. By 21:18 the log reached
  136 `Compiling` entries, including `rustc_graphviz` and the large
  `rustc_data_structures` crate; rustc was actively compiling it. At 21:19,
  the log had advanced to 142 entries, including `sha2`, `sha1` and `md-5`;
  by 21:20 it reached 145 entries, including `rustc_span`. At 21:21 the
  `rustc_span` rustc process remained active at 99% CPU and 497 MiB RSS. At
  21:22 it remained active after 2m12s (422 MiB RSS). At 21:23, 147 entries
  included `zerofrom-derive` and `zerofrom`, with rustc still compiling. At
  21:24, 151 entries included `thiserror`, `yoke` and `zerovec-derive`. At
  21:30, the compile log had reached 164 entries, including
  `icu_locid_transform_data` and `icu_locid`. At 21:31, this count held while
  rustc remained active on the current large crate at about 99% CPU and 446 MiB
  RSS. At 21:32, the count was 166 with the log at `rand_chacha`; at 21:33 it
  reached 172 entries, including `wasmparser` and `rustc_lexer`. At 21:34,
  there were 174 entries, including `rand`; rustc remained active. At 21:35,
  179 entries included `object`, `ryu` and `icu_list_data`; at 21:36 the
  rustc process was still active at 99% CPU (341 MiB RSS). At 21:37, the log
  reached 180 entries, including `rustc_abi`; at 21:38 it reached 181 entries
  with `icu_locid_transform`. At 21:39, Cargo/rustc were still active (about
  99% CPU for the compiler). At 21:40, the same Rust phase remained active
  (99% CPU, 423 MiB RSS). At 21:41 the log reached 182 entries, including
  `rustc_ast`; at 21:42 rustc remained active on this phase (99% CPU, 534 MiB
  RSS). At 21:43 the same compiler was active after 2m09s (99% CPU, 537 MiB
  RSS). By 21:49 the log had reached 184 entries, including `itertools` and
  `rustc_ast_pretty`; at 21:50 rustc remained active on that compile after
  2m46s (99% CPU, 638 MiB RSS). This
  stage exposes no total, so no percentage is available. The Guix build remains
  active; no exit marker exists yet. Host memory cgroup reports zero OOM
  events. The Jarvis output and lifecycle are not ready. The disposable profile
  lifecycle script is mounted at
  `/src/test-guix-package.sh`.
  At 2026-10-26 21:51 UTC, the Guix bootstrap advanced to 187 `Compiling`
  entries (`type-map` and `regex-automata`); the Guix process and container
  remained live, with no exit marker. Gentoo's Ninja build advanced from
  1,322 to 1,324 of 2,473 targets (`state-values-utils` and
  `simplified-operator-reducer`) and the log grew, confirming forward progress.
  At 21:52 UTC, Gentoo reached 1,325/2,473 Ninja targets, compiling V8's
  `pipeline` object. Guix reached 189 `Compiling` entries (including
  `strsim`); both containers were using CPU, and Guix's cgroup OOM counters
  remained zero.
  At 21:53 UTC, Gentoo advanced to 1,328/2,473 Ninja targets, compiling
  `simplified-lowering` and `turbofan-enabled`. Guix remained at 191 completed
  `Compiling` log entries while `darling_core` was actively compiling; its
  container continued using CPU.
  At 21:54 UTC, Gentoo reached 1,330/2,473 Ninja targets (`turbofan-graph`),
  and Guix reached 192 `Compiling` entries (`icu_list`). Both were still using
  CPU; the Guix exit marker remained absent.
  At 21:55 UTC, Guix reached 194 `Compiling` entries and was compiling
  `rustc_target`. Gentoo's Ninja count remained 1,330 during a long V8 compile,
  while the container continued using about 5.8 CPU cores; the log timestamp
  had not changed, so no additional Ninja targets are counted yet.
  At 21:56 UTC, Gentoo advanced to 1,333/2,473 Ninja targets (53.9%), with
  V8 `turbofan-types` among the latest objects. Guix was still compiling
  `rustc_target` at about one CPU core, with no exit marker.
  At 21:56:49 UTC, Gentoo reached 1,334/2,473 targets, compiling
  `turbofan-typer`. Guix remained active in `rustc_target`; the compilation
  count held at 194 while that crate continued, with no exit marker.
  At 21:57:52 UTC, Gentoo advanced to 1,335/2,473 targets (54.0%), compiling
  V8's `turboshaft` assembler object. Guix continued compiling `rustc_target`
  at 194 logged `Compiling` entries; it had no exit marker.
  At 21:59 UTC, Gentoo remained on that Ninja target, with six active
  `cc1plus` processes each using substantial CPU; the Ninja log had not
  advanced. Guix's `rustc_target` compilation also remained active under
  QEMU, at 194 logged entries and with no exit marker. Neither build was
  restarted.
  At 22:00 UTC, Gentoo advanced to 1,336/2,473 Ninja targets (54.0%),
  compiling `turboshaft/copying-phase`. Guix remained active compiling
  `rustc_target`, with 194 logged entries and no exit marker.
  At 22:00:54 UTC, Gentoo reached 1,338/2,473 Ninja targets, compiling
  `block-instrumentation-reducer`. Guix was still compiling `rustc_target`
  with 194 log entries and no exit marker.
  At 22:02 UTC the Ninja target count had not advanced, but six `cc1plus`
  workers remained active near 92–95% CPU each (about 7.8 GiB total container
  memory); Guix's rustc process also remained active near one CPU core. The
  host filesystem had 15 GiB free, so no competing Rust build was started.
  At 22:02:51 UTC, Gentoo reached 1,339/2,473 Ninja targets, compiling V8's
  `block-instrumentation-phase`. Guix remained on `rustc_target` with 194
  logged entries, and a rustc process was present; no exit marker existed.
  At 22:03 UTC, Gentoo remained at 1,339/2,473. The host has 12 CPUs but only
  6.7 GiB available RAM and 18 GiB swap in use, so the current six-job Gentoo
  build was left unchanged to avoid making memory pressure worse; Guix still
  compiles `rustc_target` under QEMU.
  At 22:03:53 UTC, six Gentoo `cc1plus` workers were still compiling distinct
  V8 translation units under QEMU; the longest had accumulated about 449 CPU
  seconds. Ninja remained at 1,339/2,473 while these large translation units
  compiled, and both build containers continued using CPU.
  At 22:05:20 UTC, Gentoo advanced to 1,340/2,473 targets, compiling
  `csa-effects-computation`. Guix remained at 194 log entries compiling
  `rustc_target`, with no exit marker.
  At 22:06:15 UTC, Gentoo reached 1,341/2,473 Ninja targets, compiling
  `code-elimination-and-simplification-phase`. Guix was still compiling
  `rustc_target` at 194 log entries; both containers continued using CPU.
  At 22:07 UTC, Ninja remained at 1,341 while six separate V8 phase
  translation units (`csa-memory-optimization`, branch/load elimination,
  debug-feature lowering, and related phases) were still compiling under
  QEMU. Guix's rustc process remained active; its log count was 194.
  At 22:08:13 UTC, Gentoo reached 1,342/2,473 targets, compiling
  `csa-branch-elimination-phase`. Guix remained active in `rustc_target` at
  194 logged entries. The disposable Guix profile lifecycle script passed
  `sh -n`; its install/runtime/removal assertions remain unexecuted until the
  package derivation produces an output.
  At 22:08:44 UTC, Gentoo remained at 1,342/2,473 while the Ninja log showed
  the next V8 objects in progress; the container was still using about 5.2
  CPU cores. Guix continued compiling `rustc_target` at 194 entries and had
  no exit marker.
  At 22:09:17 UTC, Gentoo reached 1,343/2,473 Ninja targets, compiling
  `debug-feature-lowering-phase`; six `cc1plus` processes remained active.
  Guix was still compiling `rustc_target` with 194 logged entries and no exit
  marker.
  At 22:09:49 UTC, Gentoo remained at 1,343/2,473 in the log, with the V8
  compiler processes still using CPU; no compiler error or Ninja failure
  marker was present. Guix remained active at 194 log entries, with no exit
  marker.
  At 22:10:25 UTC, Gentoo advanced to 1,345/2,473 Ninja targets (54.4%),
  compiling V8 `csa-late-escape-analysis-phase`; no compiler error was
  present. Guix continued compiling `rustc_target` at 194 logged entries,
  without an exit marker.
  At 22:11:06 UTC, Gentoo advanced to 1,346/2,473 targets, compiling
  `decompression-optimization-phase`. Guix reached 195 logged `Compiling`
  entries (`fluent-syntax`) while `rustc_target` continued; no exit marker
  existed.
  At 22:11:42 UTC, Gentoo remained at 1,346/2,473 with V8 compilation still
  active and no reported error. Guix advanced to 197 `Compiling` entries,
  including `rustc_attr_data_structures` and `intl_pluralrules`; the exit
  marker remained absent.
  At 22:12:30 UTC, Gentoo reached 1,348/2,473 Ninja targets, compiling
  `csa-load-elimination-phase`. Guix reached 199 logged `Compiling` entries,
  including `fluent-langneg` and `odht`; its Rust bootstrap remained active
  without an exit marker.
  At 22:12:56 UTC, Gentoo remained at 1,348/2,473 while the build continued
  through V8's decompression optimization and load elimination. Guix reached
  201 logged entries, including `fluent-bundle`; no output or exit marker for
  Jarvis was present.
  At 22:13:23 UTC, Gentoo advanced to 1,349/2,473 targets, compiling V8's
  `graph-visualizer`. Guix remained at 201 logged entries while `fluent-bundle`
  compiled; the process was active and no exit marker existed.
  At 22:13:58 UTC, Gentoo reached 1,350/2,473 Ninja targets, compiling
  `turboshaft/graph`; Guix reached 202 logged entries and advanced into
  `rustc_hir`. Both builds remained active without exit markers.
  At 22:14:45 UTC, Gentoo reached 1,351/2,473 targets, compiling
  `csa-memory-optimization-phase`; four `cc1plus` workers were active at
  roughly 98% CPU each. Guix remained at 202 logged entries while compiling
  `rustc_hir`, with no exit marker.
  At 22:15:44 UTC, Gentoo advanced to 1,353/2,473 Ninja targets, compiling
  `late-escape-analysis-reducer`. Guix remained at 202 logged entries while
  `rustc_hir` compiled; both containers remained active without exit markers.
  At 22:16:21 UTC, Gentoo remained at 1,353/2,473; the checked Gentoo
  `/usr`, Portage cache and temporary build paths had no completed Node binary.
  Guix reached 204 logged `Compiling` entries (`rustc_baked_icu_data` and
  `darling_macro`); its Rust bootstrap remained active without an exit marker.
  At 22:16:42 UTC, Gentoo advanced to 1,354/2,473 targets, compiling V8's
  `loop-finder`. Guix reached 205 logged entries (`icu_provider_adapters`)
  while compiling Rust bootstrap; neither build had an exit marker or logged
  compiler failure.
  At 22:18:04 UTC, Gentoo remained at 1,354/2,473 while six-job V8 compilation
  continued at about 5.9 CPU cores; no Ninja failure marker appeared. Guix
  reached 208 logged `Compiling` entries (`annotate-snippets`) and remained
  active without an exit marker.
  At 22:18:22 UTC, Gentoo advanced to 1,357/2,473 Ninja targets, compiling
  `loop-unrolling-reducer`. Guix reached 209 logged entries and began compiling
  `rustc_type_ir`; neither build had an exit marker.
  At 22:18:58 UTC, Gentoo remained at 1,357/2,473, still with no Node output.
  Guix remained at 209 entries while `rustc_type_ir` compiled; both containers
  were active and no Jarvis output or exit marker was found.
  At 22:20:15 UTC, Gentoo remained at 1,357/2,473 and continued using about
  5.9 CPU cores. Guix reached 210 `Compiling` entries and continued building
  `rustc_error_messages`; no Jarvis output or exit marker existed.
  At 22:21:25 UTC, Gentoo remained at 1,357/2,473 while five sampled
  `cc1plus` workers used about 98% CPU each; the container used about 10 GiB
  memory. Guix reached 211 entries (`darling`) with rustc active. Host swap
  had 1.3 GiB free, so no additional builds were started.
  At 22:21:52 UTC, Gentoo remained at 1,357/2,473 and Guix at 211 entries;
  both remained active. Host swap fell to about 347 MiB free, available RAM
  was 6.3 GiB, and both build cgroups still reported zero OOM events. No
  additional build was started.
  At 22:22:47 UTC, Gentoo advanced to 1,358/2,473 targets (`turboshaft`
  `operations`). Guix remained at 211 entries while `darling` compiled. Host
  available RAM was 5.6 GiB with about 435 MiB swap free; both build cgroups
  still showed zero OOM events.
  At 22:17:14 UTC, Gentoo remained at 1,354/2,473 and still had no Node output.
  Guix reached 206 `Compiling` entries, including `rustc_type_ir_macros`, while
  the Rust bootstrap remained active; no Jarvis output or exit marker existed.
  No percentage is available for the Rust bootstrap compile yet. The earlier
  failed attempt's log remains `/tmp/jarvis-guix-eval.y9LJB2/build.log`; the
  active log and exit marker are
  `/tmp/jarvis-guix-eval.y9LJB2/build-resume4.log` and
  `/tmp/jarvis-guix-eval.y9LJB2/build-resume4.exit`.
- The package lifecycle and installed runtime smoke test are still pending.
  Keep this target `unverified` until both pass.

## Resume procedure

Gentoo is compiling Node.js ARM64. Guix's two-core run is active, and its
one-core fallback is paused. Check each container state, current log, and exit
marker before resuming; do not restart a live build. Do
not count either target as supported until its native package lifecycle and
runtime smoke pass.

The earlier pause instruction is superseded by the user's 2026-10-26 request to
continue the Linux port.

  At 22:23:30 UTC, Gentoo advanced to 1,359/2,473 Ninja targets (54.9%),
  compiling V8 memory optimization; no Ninja failure marker appeared. Guix reached
  212 logged `Compiling` entries (`derive_setters`) and remained active without
  an exit marker. Host available memory was 7.4 GiB, but swap was essentially
  full (872 KiB free); build cgroups still reported zero OOM events. Neither
  package lifecycle nor runtime smoke has completed.

  At 22:23:52 UTC, Gentoo advanced to 1,360/2,473 Ninja targets (55.0%),
  compiling V8 loop peeling; there were no Ninja failure markers. Guix reached
  213 logged `Compiling` entries and was compiling `rustc_lint_defs`; it remained
  active without an exit marker. Host available RAM was 7.5 GiB and free swap
  recovered to 1.7 GiB; both build cgroups reported zero OOM events.

  At 22:24:09 UTC, Gentoo remained at 1,360/2,473 Ninja targets, but the
  active `cc1plus` worker had spent over eight minutes compiling V8's
  `loop-unrolling-phase` under QEMU; Ninja remained live and showed no failure.
  Guix reached 214 logged `Compiling` entries and was compiling
  `rustc_fluent_macro`; its build remained live. Host available RAM was 7.5 GiB,
  free swap 1.6 GiB, and no package lifecycle output was ready.

  At 22:25:10 UTC, Gentoo advanced to 1,361/2,473 Ninja targets (55.0%),
  completing `loop-unrolling-phase`; no Ninja error marker appeared. Guix reached
  218 logged `Compiling` entries and was compiling `rustc_errors`; it remained
  active without an exit marker. Available RAM was 6.6 GiB and free swap 1.0 GiB;
  Gentoo remained CPU-bound under QEMU and Guix used about one core.

  At 22:25:25 UTC, Gentoo advanced to 1,362/2,473 Ninja targets (55.1%),
  compiling V8's main phase object; no error marker or exit file appeared. Guix
  remained at 218 `Compiling` entries while `rustc_errors` compiled, with active
  Rust processes and no exit marker. Host available RAM was 7.9 GiB and free swap
  2.1 GiB; both cgroups remained free of OOM events.

  At 22:26:24 UTC, the Gentoo log remained at 1,363/2,473 for about 40 seconds
  on V8's `representations` object, but Ninja was live and the container used
  about 5.9 CPU cores; no error marker appeared. Guix stayed at 218 logged
  compilations while `rustc_errors` continued; its container used about one CPU
  core and had no exit marker. Host available RAM was 6.9 GiB, swap free 1.8 GiB,
  and no cgroup OOM events were recorded.

  At 22:26:40 UTC, Gentoo remained at 1,363/2,473 and Ninja/cc1plus stayed
  CPU-active with no failure marker; Guix remained at 218 entries with its Rust
  compiler active and no exit file. Host available RAM was 6.8 GiB and swap free
  1.1 GiB. Static review of the portal pointer path confirmed it uses the selected
  stream's compositor-coordinate `size` (or `logical_size`) and passes those
  coordinates with the stream ID; this matches the current XDG ScreenCast and
  RemoteDesktop contract. The prior failed pointer probe therefore remains an
  environment/runtime issue to reproduce, not a confirmed code defect.

  At 22:27:11 UTC, Gentoo advanced to 1,366/2,473 Ninja targets (55.2%),
  compiling V8 optimize phase; no failure marker or exit file appeared. Guix
  remained at 218 logged `Compiling` entries (`rustc_errors`), but the container
  was CPU-active and had no exit marker. Host available RAM rose to 9.3 GiB and
  free swap to 3.5 GiB; the prepared Guix package lifecycle script remains at
  `/tmp/jarvis-guix-eval.y9LJB2/test-guix-package.sh` for use after build output.

  At 22:27:57 UTC, Gentoo advanced to 1,368/2,473 Ninja targets (55.3%),
  compiling V8 simplify loops and side table objects; no Ninja failure marker
  appeared. Guix still had 218 `Compiling` log entries (`rustc_errors`); its
  container remained CPU-active without an exit marker. Host available RAM was
  9.6 GiB, swap free 2.5 GiB.

  At 22:29:30 UTC, both builds were rechecked by process table: Gentoo still had
  the live Ninja parent and multiple `cc1plus` workers (including active V8
  translation units), while Guix had a live `rustc` process and five recently
  written stage0 dependency artifacts. Logs remained at 1,368 Ninja completions
  and 218 Cargo `Compiling` announcements; the artifact updates confirm the
  Guix bootstrap is doing work despite no new crate announcement.

  At 22:30:02 UTC, Gentoo advanced to 1,369/2,473 Ninja targets (55.4%),
  compiling V8 string escape analysis; nine `cc1plus` processes and Ninja were
  visible, with no failure marker. Guix remained at 218 Cargo `Compiling`
  announcements, while one `rustc` process and five recently modified stage0
  artifacts confirmed ongoing bootstrap work; no exit marker or OOM event existed.
  Host available RAM was 6.6 GiB and swap free 1.8 GiB.

  At 22:30:21 UTC, Gentoo remained active at 1,369/2,473; Ninja showed no
  failure. Guix remained active at 218 Cargo `Compiling` announcements. Host
  available RAM was 6.8 GiB and swap free 1.8 GiB. During this wait I performed
  a non-invasive recipe review: Slackware SlackBuild parses with `sh -n`, and
  the Solus recipe contains its native build, pinned npm install, package stage,
  and glibc addon pruning. These checks are static and do not replace distro
  package lifecycle evidence.

  At 22:31:05 UTC, Gentoo advanced to 1,370/2,473 Ninja targets (55.4%),
  compiling V8 type parser; no failure marker. Guix remained at 218 Cargo
  announcements; the bootstrap log had no new announcement, so I checked live
  artifacts and process state separately. Host swap had only 678 MiB free, so no
  other build or test process was started.

  At 22:31:31 UTC, Gentoo reached 1,371/2,473 Ninja targets (55.4%),
  compiling V8 pipelines; nine `cc1plus` workers remained active with no failure
  marker. Guix advanced to 219 Cargo `Compiling` announcements (`rustc_feature`),
  with a new stage0 artifact, no exit marker and zero cgroup OOM events. Host
  available RAM was 7.7 GiB and swap free 1.9 GiB.

  At 22:31:49 UTC, Gentoo advanced to 1,371/2,473 Ninja completions (55.4%);
  no error or exit marker, and the Node binary was not yet present in out/Release.
  Guix remained at 219 Cargo `Compiling` announcements and was compiling
  `rustc_feature`; no Jarvis store output or exit marker existed. Both containers
  remained CPU-active. Host available RAM was 7.2 GiB and swap free 1.8 GiB.

  At 22:32:04 UTC, Gentoo remained at 1,371/2,473 completed targets and its
  log had no failure marker; container CPU usage remained near six cores, so
  Ninja/cc1plus were still working. Guix remained at 219 Cargo announcements
  while `rustc_feature` compiled; its process stayed active and no exit marker
  existed. Neither package output was ready. Host available RAM was 6.5 GiB and
  swap free 1.9 GiB. The prepared Guix lifecycle script is present and awaits
  the derivation output.

  At 22:33:03 UTC, Gentoo remained at 1,371/2,473 Ninja completions while
  `cc1plus` workers continued at about six CPU cores; no failure marker. Guix
  advanced from 219 to 221 `Compiling` announcements, compiling `rustc_session`,
  and wrote seven recent stage0 dependency artifacts; it remained active without
  an exit marker or OOM event. Host available RAM was 6.1 GiB and swap free fell
  to 731 MiB, so no extra jobs were started.

  At 22:33:21 UTC, Gentoo remained at 1,371/2,473 completed Ninja targets;
  its container used about 5.9 CPU cores, Node was still unavailable, and no
  failure marker existed. Guix remained at 221 Cargo announcements (`rustc_session`)
  and had eight recent stage0 artifacts; it remained active without an exit marker.
  Host available RAM was 5.9 GiB but swap free fell to 278 MiB. Existing builds
  were left running; no additional compilation was launched.

  At 22:33:42 UTC, Gentoo remained at 1,371/2,473 targets with Ninja and nine
  `cc1plus` workers using about six CPU cores; no failure marker. Guix remained
  at 221 Cargo announcements (`rustc_session`), with one `rustc` process and
  five recent stage0 artifacts; no exit marker. Both build cgroups showed zero
  OOM events. Host available RAM was 5.7 GiB, but swap had only 696 KiB free; I
  started no other tasks.

  At 22:34:01 UTC, Gentoo remained at 1,371/2,473 completions with about six
  CPU cores in use; no Ninja error or exit marker. Guix remained at 221 Cargo
  announcements (`rustc_session`), with six recently modified stage0 artifacts;
  both containers were active and their cgroup OOM counters remained zero. Host
  available RAM was 5.0 GiB while swap free fell to 140 KiB; no new process was
  launched.

  At 22:34:23 UTC, Gentoo still showed 1,371/2,473 completed targets; the
  container used about six CPU cores and the log tail contained a GCC ABI note,
  not an error. Guix remained at 221 Cargo announcements and had six recent
  stage0 artifacts. Both builds were active and cgroup OOM counters stayed zero.
  A manual review of Linux desktop-ID resolution and launcher invocation found
  no confirmed code defect; no edit was made. Host available RAM was 5.7 GiB and
  swap free 102 MiB, so additional builds/tests remain deferred.

  At 22:34:50 UTC, Gentoo's log remained at 1,371/2,473 completed targets and
  contained only a GCC ABI note at the tail, not an error; Ninja and six-core
  compiler load remained active. Guix stayed at 221 Cargo announcements
  (`rustc_session`) with three recent stage0 artifacts and active `rustc`. Both
  cgroups still showed zero OOM events. Host available RAM was 4.8 GiB and swap
  free just 28 MiB; no additional jobs were started.

  At 22:34:50 UTC, Gentoo remained at 1,371/2,473 targets with active Ninja
  and cc1plus workers; no error marker. Guix remained at 221 Cargo compile
  announcements, with rustc active and three fresh artifacts. Host available RAM
  was 4.8 GiB and swap free 28 MiB. The matrix was unchanged at 169 passed, 2
  unverified (Gentoo/Guix AArch64 lifecycles), and 1 partial (Ollama/OpenCode
  local latency). No further work could be safely launched alongside the builds.

  At 22:35:37 UTC, Gentoo remained at 1,371/2,473 targets; Ninja/cc1plus
  remained CPU-active at about six cores, the log tail showed only a GCC ABI
  note, and no exit/error marker existed. Guix remained at 221 Cargo announcements
  with `rustc_session` active and one fresh stage0 artifact. Both cgroup OOM
  counters remained zero. Host available RAM fell to 4.4 GiB, with 128 KiB swap
  free; no additional commands that build or test were started.

  At 22:35:55 UTC, Gentoo remained at 1,371/2,473 completions; its live
  container used about 11.0 GiB and six CPU cores. The log tail had a GCC ABI
  note only, no failure or exit marker. Guix remained at 221 Cargo announcements
  (`rustc_session`) with one recent stage0 artifact and a live Rust compiler.
  Both cgroups still showed zero OOM events. Host available RAM was 3.9 GiB and
  swap free 28 MiB; no additional workload was started.

  At 22:36:19 UTC, Gentoo still had no new Ninja completion after target 1,371;
  the tail contained C++ ABI warnings only, with zero error markers. The container
  memory estimate dropped to 7.5 GiB while remaining near six CPU cores. Guix
  remained at 221 Cargo announcements (`rustc_session`) with active `rustc`; no
  new stage0 artifact appeared in the two-minute window. Both cgroups reported
  zero OOM events. Host available RAM recovered to 7.7 GiB and swap free to
  699 MiB; no extra build was launched.

  At 22:36:37 UTC, Gentoo advanced to 1,375/2,473 Ninja targets (55.6%),
  compiling V8 `utils.o`; no failure/exit marker and cgroup OOM counters stayed
  zero. Guix remained at 221 Cargo announcements (`rustc_session`) with its
  container CPU-active but no new artifact in the last two minutes. Host available
  RAM was 7.6 GiB and swap free 58 MiB; no extra process was started.

  At 22:36:52 UTC, Gentoo remained at 1,375/2,473 Ninja completions (55.6%),
  with an active compiler, no error/exit marker, and no Node binary. Guix remained
  at 221 Cargo announcements (`rustc_session`), with one recent stage0 artifact
  and active CPU use; no exit marker. Both cgroups had zero OOM events. Host
  available RAM was 6.9 GiB and swap free 189 MiB; no new workload was launched.

  At 22:37:07 UTC, Gentoo remained at 1,375/2,473 completions, with Ninja
  using about six CPU cores and no error marker. Guix remained at 221 Cargo
  announcements (`rustc_session`) with two stage0 artifacts refreshed in the
  previous two minutes. Both cgroup OOM counters remained zero. Host available
  RAM was 7.0 GiB and swap free 163 MiB; no additional work was launched.

  At 22:37:26 UTC, Gentoo remained at 1,375/2,473 completed targets and the
  log file was still growing with V8/GCC diagnostic notes; no error marker or
  exit file. Guix stayed at 221 Cargo announcements (`rustc_session`) while its
  process remained CPU-active; three stage0 artifacts were recent. Both cgroups
  reported zero OOM events. Host available RAM was 6.5 GiB and swap free 382 MiB.

  At 22:37:45 UTC, Gentoo advanced to 1,377/2,473 Ninja targets (55.6%),
  compiling `turbolev-graph-builder.o`; no error or exit marker. Guix remained at
  221 Cargo announcements (`rustc_session`), with four recent stage0 artifacts
  and an active Rust process. Both cgroups reported zero OOM events. Host available
  RAM was 8.8 GiB and swap free 1.2 GiB.

  At 22:38:00 UTC, Gentoo advanced to 1,377/2,473 Ninja targets (55.6%),
  compiling `turbolev-graph-builder.o`; the Node binary remained unavailable,
  with no build error or exit marker. Guix remained at 221 Cargo announcements
  (`rustc_session`), with four recent stage0 artifacts and active `rustc`. Both
  cgroups reported zero OOM events. Host available RAM was 8.3 GiB and swap free
  1.1 GiB.

  At 22:38:15 UTC, Gentoo reached 1,378/2,473 Ninja targets (55.6%), compiling
  `type-cache.o`; no error/exit marker. Guix stayed at 221 Cargo announcements
  (`rustc_session`) with five fresh stage0 artifacts and active `rustc`. Both
  cgroups showed zero OOM events. Host available RAM was 8.7 GiB and swap free
  1.1 GiB.

  At 22:38:29 UTC, Gentoo advanced to 1,379/2,473 Ninja targets (55.7%),
  compiling V8 typed optimizations; no error/exit marker, and the Node binary
  remained absent. Guix stayed at 221 Cargo announcements (`rustc_session`) but
  had six fresh stage0 artifacts and an active compiler. Both cgroups reported
  zero OOM events. Host available RAM recovered to 10 GiB; swap free was 875 MiB.

  At 22:38:53 UTC, Gentoo advanced to 1,381/2,473 Ninja targets (55.8%),
  compiling V8 `use-map.o`; Node remained unavailable and no failure/exit marker
  appeared. Guix remained at 221 Cargo announcements (`rustc_session`) with seven
  recent stage0 artifacts and active Rust compilation. Both cgroups showed zero
  OOM events. Host available RAM was 12 GiB and swap free 1.5 GiB. The matrix
  remained 169 passed, 2 unverified, 1 partial.

  At 22:39:13 UTC, Gentoo advanced to 1,382/2,473 targets (55.8%), compiling
  `zone-stats.o`; Node remained unavailable, with no failure or exit marker.
  Guix remained at 221 Cargo announcements (`rustc_session`) with seven fresh
  stage0 artifacts and active Rust compilation. Both cgroups reported zero OOM
  events. Host available RAM was 11 GiB and swap free 1.6 GiB.

  At 22:39:29 UTC, Gentoo advanced to 1,383/2,473 Ninja targets (55.9%),
  compiling V8 type narrowing; Node was not yet available and no error/exit
  marker appeared. Guix remained at 221 Cargo announcements (`rustc_session`)
  with seven recent stage0 artifacts and an active compiler. Both cgroups reported
  zero OOM events. Host available RAM was 11 GiB and swap free 1.6 GiB.

  At 22:39:45 UTC, Gentoo remained at 1,383/2,473 targets; Ninja/cc1plus
  remained active around six CPU cores with no error/exit marker and Node absent.
  Guix remained at 221 Cargo announcements (`rustc_session`) with eight recent
  stage0 artifacts and active Rust compilation. Both cgroups showed zero OOM
  events. Host available RAM was 10 GiB and swap free 1.6 GiB.

  At 22:40:02 UTC, Gentoo advanced to 1,384/2,473 Ninja targets (56.0%),
  compiling V8 value-numbering reducer; Node remained unavailable and no error
  or exit marker appeared. Guix remained at 221 Cargo announcements (`rustc_session`)
  with eight fresh stage0 artifacts and active `rustc`; no exit marker. Both
  cgroups reported zero OOM events. Host available RAM was 10 GiB and swap free
  1.7 GiB.

  At 22:40:17 UTC, Gentoo remained at 1,384/2,473 targets; Ninja stayed CPU-active
  with no error or exit marker and Node still unavailable. Guix remained at 221 Cargo
  announcements (`rustc_session`), with eight recent stage0 artifacts and an active
  compiler. Both cgroups reported zero OOM events. Host available RAM was 10 GiB
  and swap free 1.3 GiB.

  At 22:40:32 UTC, Gentoo remained at 1,384/2,473 completed targets; six-core
  CPU activity and no error/exit marker persisted. Guix remained at 221 Cargo
  announcements (`rustc_session`) but had nine fresh stage0 artifacts and active
  `rustc`. Node was still unavailable. Both cgroups showed zero OOM events. Host
  available RAM was 9.9 GiB and swap free 1.3 GiB.

  At 22:40:49 UTC, Gentoo advanced to 1,385/2,473 Ninja targets (56.0%),
  compiling V8 verifier; no failure or exit marker. Guix advanced from 221 to
  223 Cargo announcements (`rustc_apfloat`, `datafrog`) and remained active; two
  recent stage0 artifacts were present, with no exit marker. Both cgroups reported
  zero OOM events. Host available RAM was 10 GiB and swap free 1.5 GiB.

  At 22:41:05 UTC, Gentoo advanced to 1,387/2,473 Ninja targets (56.0%),
  compiling V8 typed optimization; Node remained unavailable and no error/exit
  marker appeared. Guix advanced to 224 Cargo announcements (`polonius-engine`)
  with five fresh stage0 artifacts; Rust remained active. Both cgroups showed zero
  OOM events. Host available RAM was 11 GiB and swap free 1.5 GiB.

  At 22:41:19 UTC, Gentoo remained at 1,387/2,473 completed targets with active
  Ninja/cc1plus work and no failure/exit marker. Guix remained at 224 Cargo
  announcements (`polonius-engine`) with eight fresh stage0 artifacts and active
  Rust compilation. Both cgroups reported zero OOM events. Host available RAM was
  10 GiB and swap free 1.6 GiB.

  At 22:41:33 UTC, Gentoo remained at 1,387/2,473 Ninja completions; no error
  or exit marker, with the container still using about six CPU cores. Guix advanced
  from 224 to 225 Cargo announcements and began `rustc_query_system`; ten recent
  stage0 artifacts were present, with no exit marker. Both cgroups reported zero
  OOM events. Host available RAM was 10 GiB and swap free 1.5 GiB.

  At 22:41:48 UTC, Gentoo remained at 1,387/2,473 targets with active compiler
  load and no error/exit marker. Guix advanced to 225 Cargo announcements and
  began `rustc_query_system`; eleven recent stage0 artifacts were present. Both
  cgroups reported zero OOM events. Host available RAM was 11 GiB and swap free
  2.0 GiB.

  At 22:42:03 UTC, Gentoo advanced to 1,389/2,473 Ninja targets (56.1%),
  compiling V8 Wasm debug memory lowering; Node remained unavailable, with no
  error/exit marker. Guix remained at 225 Cargo announcements (`rustc_query_system`)
  with twelve fresh stage0 artifacts and active Rust compilation. Both cgroups
  showed zero OOM events. Host available RAM was 11 GiB and swap free 2.3 GiB.

  At 22:42:19 UTC, Gentoo remained at 1,389/2,473 completed targets with
  six-core CPU activity and no failure/exit marker. Guix remained at 225 Cargo
  announcements (`rustc_query_system`) with twelve recent stage0 artifacts and
  active compilation. Both cgroups reported zero OOM events. Host available RAM
  was 10 GiB and swap free 2.5 GiB.

  At 22:42:34 UTC, Gentoo remained at 1,389/2,473 Ninja completions with active
  six-core compiler load and no failure/exit marker. Guix remained at 225 Cargo
  announcements (`rustc_query_system`) with seventeen recent stage0 artifacts and
  active compilation. Both cgroups showed zero OOM events. Host available RAM was
  9 GiB and swap free 2.5 GiB.

  At 22:42:49 UTC, Gentoo advanced to 1,390/2,473 Ninja targets (56.2%),
  compiling V8 int64 lowering; Node remained unavailable and no error/exit marker
  appeared. Guix advanced to 226 Cargo announcements (`rustc_hir_pretty`) with
  eleven recent stage0 artifacts; Rust remained active. Both cgroups reported zero
  OOM events. Host available RAM was 10 GiB and swap free 2.6 GiB.

  At 22:43:05 UTC, Gentoo remained at 1,390/2,473 Ninja completions; Node and
  package output were not ready, and no failure/exit marker appeared. Guix remained
  at 226 Cargo announcements (`rustc_hir_pretty`) with ten recent stage0 artifacts
  and active Rust compilation. Both cgroups showed zero OOM events. Host available
  RAM was 9.6 GiB and swap free 2.6 GiB.

  At 22:43:20 UTC, Gentoo advanced to 1,391/2,473 targets (56.2%), compiling
  the ARM64 code generator; Node remained unavailable and no error/exit marker
  appeared. Guix remained at 226 Cargo announcements (`rustc_hir_pretty`) with
  seven recent stage0 artifacts and active compilation. Both cgroups showed zero
  OOM events. Host available RAM was 10 GiB and swap free 2.7 GiB.

  At 22:43:35 UTC, Gentoo advanced to 1,392/2,473 Ninja targets (56.3%),
  compiling V8 int64 lowering phase; no failure/exit marker. Guix remained at 226
  Cargo announcements (`rustc_hir_pretty`) with seven recent stage0 artifacts and
  active `rustc`. Both cgroups showed zero OOM events. Host available RAM was
  9.9 GiB and swap free 2.7 GiB.

  At 22:43:50 UTC, Gentoo remained at 1,392/2,473 Ninja completions with active
  CPU load, no error/exit marker and Node unavailable. Guix advanced to 227 Cargo
  announcements (`gsgdt`) with six recent stage0 artifacts and active compilation.
  Both cgroups showed zero OOM events. Host available RAM was 10 GiB and swap
  free 2.8 GiB.

  At 22:44:05 UTC, Gentoo advanced to 1,393/2,473 Ninja targets (56.3%),
  compiling the ARM64 instruction selector; no failure/exit marker. Guix remained
  at 227 Cargo announcements (`gsgdt`) with six recent stage0 artifacts and active
  Rust compilation. Both cgroups showed zero OOM events. Host available RAM was
  11 GiB and swap free 2.8 GiB.

  At 22:44:19 UTC, Gentoo remained at 1,393/2,473 Ninja completions; its
  container stayed CPU-active with no error/exit marker, and Node was unavailable.
  Guix remained at 227 Cargo announcements (`gsgdt`) with nine recent stage0
  artifacts and active compilation. Both cgroups reported zero OOM events. Host
  available RAM was 10 GiB and swap free 2.8 GiB.

  At 22:44:34 UTC, Gentoo remained at 1,393/2,473 completed targets with
  active compiler load and no error/exit marker. Guix remained at 227 Cargo
  announcements (`gsgdt`) with sixteen recent stage0 artifacts, confirming active
  Rust work despite unchanged announcement count. Both cgroups reported zero OOM
  events. Host available RAM was 10 GiB and swap free 2.9 GiB.

  At 22:44:49 UTC, Gentoo remained at 1,393/2,473 Ninja completions, with active
  six-core compiler load and no failure/exit marker. Guix advanced to 228 Cargo
  announcements and began `rustc_middle`; six recent stage0 artifacts were present.
  Both cgroups showed zero OOM events. Host available RAM was 9.7 GiB and swap
  free 2.9 GiB.

  At 22:45:03 UTC, Gentoo remained at 1,393/2,473 targets with active six-core
  compiler load and no error/exit marker. Guix remained at 228 Cargo announcements
  (`rustc_middle`) with four recent stage0 artifacts and active Rust compilation.
  Both cgroups reported zero OOM events. Host available RAM was 9.0 GiB and swap
  free 2.9 GiB.

  At 22:45:18 UTC, Gentoo remained at 1,393/2,473 Ninja completions with active
  compiler load and no error/exit marker. Guix remained at 228 Cargo announcements
  (`rustc_middle`) with five recent stage0 artifacts and active compilation. Both
  cgroups showed zero OOM events. Host available RAM was 8.5 GiB and swap free
  2.9 GiB.

  At 22:45:33 UTC, Gentoo remained at 1,393/2,473 targets with active six-core
  compiler load, no error/exit marker, and Node unavailable. Guix remained at 228
  Cargo announcements (`rustc_middle`); its compiler remained active, using 621 MiB,
  with five recent stage0 artifacts. Both cgroups showed zero OOM events. Host
  available RAM was 8.0 GiB and swap free 2.9 GiB.

  At 22:45:48 UTC, Gentoo advanced to 1,394/2,473 Ninja targets (56.4%),
  compiling V8 Wasm GC typed optimization; no failure/exit marker. Guix remained
  at 228 Cargo announcements (`rustc_middle`) with three recent stage0 artifacts
  and active compilation. Both cgroups reported zero OOM events. Host available
  RAM was 9.2 GiB and swap free 2.9 GiB.

  At 22:46:05 UTC, Gentoo remained at 1,394/2,473 targets with active compiler
  load and no error/exit marker. Guix remained at 228 Cargo announcements
  (`rustc_middle`) with two recent stage0 artifacts; rustc remained active. Both
  cgroups showed zero OOM events. Host available RAM was 8.3 GiB and swap free
  2.9 GiB.

  At 22:47:09 UTC, both ARM64 builds were confirmed live. Gentoo remained at
  1,394/2,473 Ninja targets with no failure or exit marker; its active compiler
  was building a V8 Wasm optimization object. Guix remained at 228 Cargo
  announcements (`rustc_middle`), with its Guix/bootstrap processes still live.
  Gentoo cgroup memory.events showed zero OOM events. No package artifact was
  ready for lifecycle validation at this checkpoint.

  At 22:47:55 UTC, Gentoo advanced to 1,396/2,473 Ninja targets (56.5%); at
  22:48:23 UTC it remained on the same V8 Wasm dead-code-elimination object,
  with ~592% CPU, no failure/exit marker, and Node still unavailable. Guix remained
  active at 228 Cargo announcements (`rustc_middle`), near one CPU core, with no
  completion marker. Both builds are still running; no package lifecycle can be
  performed yet.

  At 22:48:40 UTC, Gentoo advanced to 1,397/2,473 Ninja targets (56.5%),
  compiling a V8 Wasm shuffle reducer. At 22:49:09 UTC it remained on that target
  but retained ~597% CPU, with zero Ninja failure markers and no exit marker;
  Node was still unavailable. Guix stayed at 228 Cargo announcements on
  `rustc_middle`, with the container using ~98% CPU and no terminal marker.

  At 22:50:51 UTC, Gentoo advanced to 1,398/2,473 Ninja targets (56.5%),
  compiling another V8 Wasm object; there were zero failure markers and no exit
  marker, with Node still unavailable. Guix remained active at 228 Cargo
  announcements (`rustc_middle`). Both cgroups reported zero OOM events.

  At 22:52:00 UTC, Gentoo reached 1,401/2,473 Ninja targets (56.7%), still
  compiling Node/V8 with ~591% CPU, no Ninja failures or exit marker. Guix stayed
  at 228 Cargo announcements in `rustc_middle`, using ~100% CPU; no completion
  marker. Neither package artifact is ready for install/runtime validation.

  At 22:53:16 UTC, Gentoo advanced to 1,405/2,473 Ninja targets (56.8%),
  compiling a V8 Wasm SIMD phase. The build remains active with no failure or
  exit marker; Node is unavailable. Guix remains active at 228 Cargo announcements
  in `rustc_middle`, also without an exit marker. No package artifacts are ready.

  At 22:58:19 UTC, Gentoo advanced to 1,448/2,473 Ninja targets (58.6%),
  compiling a V8 libplatform object. There are no Ninja failure markers or exit
  marker; Node remains unavailable. Guix remains at 228 Cargo announcements in
  `rustc_middle`; its rustc process accumulated 13m33s CPU time over 13m44s
  elapsed and the container used 1.08 GiB, with zero OOM events. Both builds are
  demonstrably live; package artifacts are not ready yet.

  At 23:03:34 UTC, Gentoo advanced to 1,455/2,473 Ninja targets (58.8%),
  compiling a V8 builtins object. No failure or exit marker is present and Node
  is not yet available. Guix remains at 228 Cargo announcements in `rustc_middle`
  with ~99% CPU and 1.07 GiB container memory; cgroup OOM counters remain zero.
  No installable Gentoo/Guix package artifact has appeared.

  At 23:04:24 UTC, Gentoo remained at 1,455/2,473 completed targets but was
  still CPU-active (~596%) compiling a large V8 builtins object; memory rose to
  7.38 GiB and there were no failure/exit markers. Guix remained in
  `rustc_middle` (228 Cargo announcements); the recent stage0 artifact count
  increased from one to two and rustc remained CPU-active at 19m06s CPU time.
  Both cgroups show zero OOM events, so these are slow active compilations, not
  terminal failures. No installable artifacts yet.

  At 23:05:12 UTC, Gentoo advanced to 1,459/2,473 targets (59.0%) while
  continuing the Node/V8 build; no failure or exit marker. The Guix log stayed
  at 228 Cargo announcements in `rustc_middle`, but its recent stage0 artifact
  count increased from two to three. Rust remained CPU-active; both cgroups
  reported zero OOM events. Guix store contains the completed ONNX Runtime and
  oneDNN inputs, but no built Jarvis assistant output yet.

  At 23:06:12 UTC, Gentoo advanced to 1,461/2,473 targets (59.1%). Four active
  cross-compiler processes were visible, with no Ninja failure/exit marker; Node
  remains unavailable. Guix remains at 228 Cargo announcements in `rustc_middle`,
  using ~99% CPU, with zero OOM events. The currently staged package image and
  Jarvis outputs are still absent, so lifecycle testing must wait for build output.

  At 23:07:10 UTC, Gentoo advanced to 1,463/2,473 targets (59.2%), still
  within Node/V8 builtins generation; no failures or exit marker, Node unavailable.
  Guix stayed at 228 Cargo announcements in `rustc_middle`, but rustc accumulated
  further CPU time and recent stage0 artifacts continued to appear. Cgroups remain
  free of OOM events; neither target has an installable package yet.

  At 23:07:59 UTC, Gentoo remained at 1,465/2,473 Ninja targets, still on the
  same V8 builtins object, with ~595% CPU and no error/exit marker.
  Guix remained at 228 announcements in `rustc_middle`; `.rustc-real` reached
  23m14s CPU time and six stage0 files were modified in the last five minutes.
  Both cgroups report zero OOM events.

  At 23:08:57 UTC, Gentoo reached 1,467/2,473 targets (59.3%), compiling
  V8 builtins; there are no failure or exit markers, and Node is still not built.
  Guix remains at 228 Cargo announcements in `rustc_middle`; two stage0 files
  were modified in the last two minutes and the compiler remains active. Both
  cgroups report zero OOM events; package lifecycle is still waiting on outputs.

  At 23:09:39 UTC, Gentoo reached 1,468/2,473 targets (59.4%), with active
  ARM64 compilers, no failure markers and no exit marker. Guix remained at 228
  Cargo announcements in `rustc_middle`; its rustc process remains near one full
  CPU core and both cgroups show zero OOM events. Neither package is installable
  yet.

  At 23:10:24 UTC, Gentoo reached 1,469/2,473 Ninja targets (59.4%),
  compiling V8 builtins. A recent package-work file was written; there are no
  failure/exit markers and Node is not built. Guix remains in `rustc_middle`
  (228 Cargo announcements); three stage0 files were modified in the last two
  minutes. Both containers remain CPU-active with zero OOM events.

  At 23:11:07 UTC, Gentoo stayed at 1,471/2,473 targets while six compiler
  workers continued the same V8 builtins object; no failure/exit marker and Node
  unavailable. Guix remained in `rustc_middle` (228 announcements) with three
  recent stage0 files. Both builds stayed CPU-active and reported zero OOM events.

  At 23:11:50 UTC, Gentoo remained at 1,472/2,473 completed targets for ~30s,
  but the active Ninja compiler remained CPU-bound (~594%) on a V8 builtins object
  and wrote a recent work file. No failure/exit markers appeared. Guix remained in
  `rustc_middle` (228 announcements) with three recent stage0 artifacts and ~99%
  CPU. Both builds remain active; no OOM events or package outputs.

  At 23:12:48 UTC, Gentoo advanced to 1,473/2,473 targets (59.5%), continuing
  V8 builtins, with no failure or exit marker and Node unavailable. Guix remained
  at 228 Cargo announcements in `rustc_middle`; four recent stage0 files were
  observed and the compiler stayed active. Both cgroups reported zero OOM events.

  At 23:13:33 UTC, Gentoo advanced to 1,477/2,473 targets (59.7%), compiling
  V8 builtins; no Ninja failures or exit marker, Node not yet available. Guix
  remained at 228 Cargo announcements in `rustc_middle`, while three recent
  stage0 files were present and `.rustc-real` continued CPU-bound. Both builds
  remain active with zero OOM events; lifecycle checks are pending artifacts.

  At 23:14:21 UTC, Gentoo reached 1,478/2,473 targets (59.8%), still compiling
  Node/V8 builtins, with no failures or exit marker and one recent package-work
  file. Guix remains at 228 Cargo announcements in `rustc_middle`; three recent
  stage0 outputs and 28m52s rustc CPU time confirm continuing work. Both cgroups
  report zero OOM events; package installation remains pending build completion.

  At 23:15:15 UTC, Gentoo advanced to 1,480/2,473 targets (59.8%), with no
  failure or exit marker; Node remains unavailable. Guix advanced from
  `rustc_middle` to `rustc_parse_format` (229 Cargo announcements); container
  memory fell to 267.8 MiB while Rust stayed CPU-active, and six stage0 files were
  modified in the last two minutes. The host and Docker daemon are x86_64 with
  12 CPUs, so no native ARM64 runner is available here; the existing emulated
  builds remain the active route. Both cgroups report zero OOM events.

  At 23:21:07 UTC, Gentoo advanced to 1,489/2,473 targets (60.2%), now
  compiling Node/V8 accessors; no failures or exit marker, Node remains unavailable.
  Guix advanced to 232 Cargo announcements and started `rustc_infer`, after
  `rustc_parse_format`; it used 447 MiB with recent stage0 output and ~99% CPU.
  Both cgroups remain at zero OOM events; package outputs are not ready.

  At 23:21:53 UTC, Gentoo advanced to 1,491/2,473 targets (60.3%), still in
  V8 builtins, with no failure/exit marker and Node unavailable. Guix remained in
  `rustc_infer` (232 Cargo announcements); seven recent stage0 artifacts and a
  live rustc process confirm compilation. Both cgroups continue to report zero
  OOM events; there are no Jarvis package outputs yet.

  At 23:27:39 UTC, Gentoo reached 1,500/2,473 targets (60.7%) and entered
  ARM64-specific V8 builtins; no failure or exit marker, Node remains unavailable.
  Guix advanced to 235 Cargo announcements and `rustc_trait_selection`, after
  `rustc_infer`; six recent stage0 files were observed and memory remained below
  0.5 GiB with active CPU. Both cgroups report zero OOM events; artifacts still
  need package install/runtime validation.

  At 23:28:26 UTC, Gentoo advanced to 1,501/2,473 targets (60.7%) and moved
  from ARM64 builtins to Torque-generated V8 objects; no failure/exit marker,
  Node still unavailable. Guix remained at 235 Cargo announcements around
  `rustc_trait_selection`, with a live Rust compiler and no OOM events. No package
  artifact has been produced yet.

  At 23:29:26 UTC, Gentoo advanced to 1,503/2,473 targets (60.8%); Node/V8
  Torque-generated objects continue, with zero failure markers and no exit marker.
  Its Node object tree is 188 MiB; the final Node binary is not built. Guix remains
  at 235 Cargo announcements in `rustc_infer`, but rustc time increased to 3m11s
  and two stage0 artifacts changed in the last three minutes. Both cgroups show
  zero OOM events.

  At 23:30:21 UTC, Gentoo advanced to 1,505/2,473 targets (60.9%) among
  Torque-generated V8 objects, with no failure or exit marker; Node remains
  unavailable. Guix stayed at 235 Cargo announcements in `rustc_trait_selection`
  with the Rust process and one recent stage0 artifact still active. Both cgroups
  show zero OOM events; no package output is ready for lifecycle testing.

  At 23:31:28 UTC, Gentoo advanced to 1,506/2,473 targets (61.0%) in
  Torque-generated V8 objects, with no failures or exit marker; Node unavailable.
  Guix remained at 235 Cargo announcements in `rustc_trait_selection`, and its
  Rust compiler plus recent stage0 output remain active. Both cgroups show zero
  OOM events; package outputs are still pending.

  At 23:32:11 UTC, Gentoo advanced to 1,507/2,473 targets (60.9%), compiling
  V8 Torque-generated builtins; one recent package-work file, no failure or exit
  marker, and Node remains unavailable. Guix remains at 235 Cargo announcements
  in `rustc_trait_selection` with a live Rust compiler and recent stage0 output.
  Both cgroups continue to show zero OOM events; no package artifacts are ready.

  At 23:33:00 UTC, Gentoo advanced to 1,508/2,473 targets (61.0%), with the
  active Ninja build compiling V8 Torque-generated objects; no failure or exit
  marker and Node unavailable. Guix remains in `rustc_trait_selection` at 235
  Cargo announcements, with a live compiler and a recent stage0 output. Both
  builds remain CPU-active and free of cgroup OOM events.

  At 23:34:13 UTC, Gentoo remained at 1,511/2,473 targets for about one minute,
  but Ninja still used ~596% CPU compiling a V8 Torque-generated builtin and
  wrote a recent build file; no failure/exit marker. Guix remained at 235 Cargo
  announcements in `rustc_trait_selection` with a live CPU-bound rustc process.
  Both cgroups remain at zero OOM events; no package artifacts are available.

  At 23:34:56 UTC, Gentoo remained at 1,512/2,473 targets for ~30s while
  compiling a V8 Torque-generated builtin; container CPU stayed near six cores,
  with no error or exit marker. Node is unavailable. Guix remained at 235 Cargo
  announcements in `rustc_trait_selection`; its Rust compiler remained active
  with recent output. Both builds continue without OOM events.

  At 23:35:39 UTC, Gentoo reached 1,513/2,473 targets (61.2%) and continued
  through Torque-generated V8 builtins; zero failure markers, no exit marker, and
  Node unavailable. Guix remains at 235 Cargo announcements in
  `rustc_trait_selection`; the Rust process is still CPU-active, though no new
  stage0 file appeared in this short interval. Both cgroups report zero OOM.

  At 23:36:31 UTC, Gentoo advanced to 1,514/2,473 targets (61.2%), continuing
  Torque-generated V8 objects; no failures or exit marker, Node remains unavailable.
  Guix stayed in `rustc_trait_selection` at 235 Cargo announcements; rustc reached
  10m11s CPU time and remains active, with zero OOM events. No package output is
  available for lifecycle validation.

  At 23:37:14 UTC, Gentoo reached 1,515/2,473 targets (61.2%); no Ninja
  failures or exit marker and Node still unavailable. Guix remained at 235 Cargo
  announcements in `rustc_trait_selection`; `.rustc-real` reached 10m54s CPU and
  stays active (~99% container CPU), though no new stage0 file appeared in the
  last two minutes. Both cgroups report zero OOM events; package artifacts are
  still pending.

  At 23:37:59 UTC, Gentoo reached 1,517/2,473 targets (61.3%), still on
  Torque-generated V8 builtins, with no errors/exit marker and Node unavailable.
  Guix remained at 235 Cargo announcements in `rustc_trait_selection`; rustc time
  rose to 11m38s and stayed CPU-bound, although no stage0 files changed in the
  last two minutes. Both cgroups have zero OOM events; package outputs are absent.

  At 23:38:45 UTC, Gentoo reached 1,518/2,473 targets (61.3%), still in
  Torque-generated V8 builtins, with no failure/exit marker and Node unavailable.
  Guix remained at 235 Cargo announcements in `rustc_trait_selection`; rustc
  accumulated 12m24s CPU and remains active, though no stage0 output appeared in
  the last two minutes. Both cgroups report zero OOM events; no packages are ready.

  At 23:39:41 UTC, Gentoo reached 1,519/2,473 targets (61.4%) with no
  failure/exit marker; Node remains unavailable. Guix remains in
  `rustc_trait_selection` at 235 announcements, but `.rustc-real` accumulated
  13m20s CPU and continues to consume a full core. No recent artifact was emitted
  in the last three minutes; both builds remain active and have zero OOM events.

  At 23:40:25 UTC, Gentoo reached 1,521/2,473 targets (61.4%), continuing
  Torque-generated V8 builtins with no errors/exit marker; Node is unavailable.
  Guix remains at 235 Cargo announcements in `rustc_trait_selection`; `.rustc-real`
  reached 14m04s CPU time and still saturates one core, with no stage0 file emitted
  in the last two minutes. No OOM events or installable packages.

  At 23:41:09 UTC, Gentoo advanced to 1,522/2,473 targets (61.5%) and remained
  in Torque-generated V8 builtins; no failures/exit marker, Node unavailable.
  Guix remained at 235 Cargo announcements in `rustc_trait_selection`; rustc
  reached 14m47s CPU time and remains near one full core, with no stage0 files
  changed in the last two minutes. Both builds are active with zero OOM events.

  At 23:41:53 UTC, Gentoo stayed at 1,523/2,473 targets for 30s while its
  compiler remained near six cores on a V8 generated builtin; no failure/exit
  marker, Node unavailable. Guix remained at 235 Cargo announcements in
  `rustc_trait_selection`; rustc CPU time rose to 15m30s with ~99% container CPU,
  but no recent stage0 artifact. Both processes remain live and cgroup OOM counts
  remain zero.

  At 23:47:45 UTC, Gentoo reached 1,533/2,473 targets (62.0%), with active
  ARM64 compiler processes, no failures/exit marker, and Node unavailable. Guix
  remained at 235 Cargo announcements in `rustc_trait_selection`; `.rustc-real`
  reached 21m19s CPU and two stage0 files changed recently, indicating active
  compilation. Both cgroups show zero OOM events; package outputs remain absent.

  At 23:48:32 UTC, Gentoo reached 1,534/2,473 targets (62.0%), with no
  failure/exit marker and Node unavailable. Guix remained at 235 Cargo announcements
  in `rustc_trait_selection`; `.rustc-real` accumulated 22m05s CPU and two stage0
  artifacts changed recently, while container CPU stayed near 99%. Both cgroups
  report zero OOM events; there are no installable package outputs.

  At 23:49:51 UTC, Gentoo reached 1,535/2,473 targets (62.1%); no Ninja
  failures/exit marker and Node unavailable. Guix remained at 235 Cargo announcements
  in `rustc_trait_selection`; rustc reached 23m23s CPU, remained CPU-active, and
  one stage0 output appeared in the last two minutes. Both cgroups report zero
  OOM events; package artifacts are still absent.

  At 23:52:31 UTC, Gentoo reached 1,548/2,473 targets (62.6%); Ninja remained
  active with no failure marker or exit file, and Node is still unavailable. Guix
  remains in `rustc_trait_selection` at 98.5% container CPU; cgroup OOM counters
  are zero. Neither ARM64 package artifact is available yet.

  At 23:58:47 UTC, Gentoo reached 1,552/2,473 targets (62.7%); Ninja remains
  active without failure markers or an exit file. Guix remains in
  `rustc_trait_selection`; stage0 codegen-unit objects changed in the last two
  minutes while CPU stayed near one core and OOM counters stayed at zero. ARM64
  package artifacts are not available yet.

  At 00:01:32 UTC on 2026-10-27, Gentoo reached 1,556/2,473 targets (62.8%),
  with no Ninja failures or exit marker. Guix remains in
  `rustc_trait_selection`; its stage0 objects are still changing and cgroup OOM
  counters remain zero. No ARM64 package artifact has been produced.

  At 00:01:50 UTC, Gentoo reached 1,557/2,473 targets (62.9%), with no Ninja
  failures or exit marker. Guix remains in `rustc_trait_selection`; stage0
  objects changed in the last three minutes and cgroup OOM counters remain zero.
  Host Btrfs has 14.75 GiB free (96% used). A Pacman cache prune dry-run found
  no duplicate package versions to remove; active build data was left intact.

  At 00:05:53 UTC, Gentoo reached 1,563/2,473 targets (63.1%), with no Ninja
  failures or exit marker. Guix's bootstrap has advanced to `x.py -j1 build
  --stage=2 library/std src/tools/cargo`; a Rust compiler process is active in
  that stage, and OOM counters remain zero. The host still has 14.75 GiB free.

  At 00:07:06 UTC, Gentoo reached 1,564/2,473 targets (63.2%) and remains
  active without a Ninja exit marker. Guix stage 2 is compiling additional
  compiler crates (`rustc_attr_parsing`, `rustc_trait_selection`) with a Rust
  process active and zero cgroup OOM events. Host free space remains 14.75 GiB.

  At 00:08:42 UTC, Gentoo reached 1,569/2,473 targets (63.4%), still active
  with no exit marker. Guix remains active in stage 2 compiling Rust compiler
  crates at about one core; both cgroups report zero OOM events. No ARM64
  package output is available, and host free space is still about 15 GiB.

  At 00:11:14 UTC, Gentoo reached 1,570/2,473 targets (63.5%) with no exit
  marker. Guix stage 2 progressed to compiling `aho-corasick` alongside Rust
  compiler crates; its process remains active and OOM counters remain zero.
  Host free space remains about 15 GiB. The private-runtime voice suite also
  completed at 530 passed and one desktop-session skip.

  At 00:12:08 UTC, Gentoo reached 1,575/2,473 targets (63.7%) with no exit
  marker. Guix stage 2 is compiling `regex-syntax` and compiler crates; CPU
  remains active and OOM counters are zero. The Linux package/install regression
  passed 95 tests; no ARM64 package artifact is available yet.

  At 00:16:49 UTC, Gentoo reached 1,582/2,473 targets (64.0%), with no Ninja
  failures or exit marker. Guix stage 2 advanced to `regex-automata`; both builds
  remain CPU-active with zero OOM events and about 15 GiB free on the host.

  At 00:18:27 UTC, Gentoo reached 1,587/2,473 targets (64.2%), with no error
  marker or exit file. Guix remains CPU-active in stage 2 compiling Rust crates;
  both cgroups report zero OOM events. The OpenCode TypeScript suite also passed
  120 tests; neither ARM64 package is ready yet.

  At 00:19:15 UTC, Gentoo reached 1,588/2,473 targets (64.2%), with no error
  marker or exit file. Guix remains active in stage 2 and both cgroups report
  zero OOM events. The two MCP suites passed (16 and 17 tests); ARM64 package
  outputs are still absent.

  At 00:20:43 UTC, Gentoo reached 1,589/2,473 targets (64.3%) without Ninja
  failures or an exit marker. Guix stage 2 advanced through `rand_chacha`,
  `regex`, and `rand`; its Rust process remains CPU-active and OOM counters stay
  zero. No ARM64 package artifacts are ready.

  At 00:21:05 UTC, Gentoo remained active at 1,589/2,473. The retained temporary
  Portage tree and local Jarvis ebuild are present, the binpkg directory is
  empty, and `out/Release/node` is not yet available. This confirms that the
  package phase must wait for the current dependency build; no re-extraction or
  new package invocation was started.

  At 00:21:47 UTC, Gentoo advanced to 1,593/2,473 targets (64.4%), with no
  Ninja errors or exit marker. Guix stage 2 advanced to `rustc_parse`; both
  builds remain CPU-active and cgroup OOM counters are zero. Gentoo Node and
  the package artifact remain unavailable.

  At 00:23:48 UTC, Gentoo reached 1,597/2,473 targets (64.5%), with no Ninja
  errors or exit marker; multiple ARM64 `cc1plus` workers remain active. Guix
  emitted `librustc_parse.rmeta` while still compiling stage 2. Both cgroups
  report zero OOM events; the Node executable and package artifacts are absent.

  At 00:24:47 UTC, Gentoo advanced to 1,598/2,473 targets (64.5%), still
  without a Ninja error or exit marker. Guix remains CPU-active in `rustc_parse`
  with no OOM events. Node and the ARM64 package outputs remain unavailable.

  At 00:25:11 UTC, Gentoo reached 1,600/2,473 targets (64.7%), with no Ninja
  failure or exit marker; `out/Release/node` remains absent. Guix is still
  compiling stage 2 `rustc_parse` and its stage0 `librustc_parse.rmeta` is
  present. Both cgroups report zero OOM events; no packages are ready.

  At 00:35:36 UTC, Gentoo reached 1,616/2,473 targets (65.3%) without error
  or exit marker. Guix remained active in stage 2 `rustc_parse`; both cgroups
  report zero OOM events and the root filesystem remains at 15 GiB free. The
  x86-64 Tauri tests/build also passed using a temporary tmpfs target, which was
  cleaned after validation; no ARM64 package output is available yet.

  At 00:40:55 UTC, both ARM64 build containers were still running. Gentoo
  remained at 1,625/2,473 Ninja targets while four V8 C++ compile processes
  were actively using CPU; there was no exit marker and no Node binary yet.
  Guix advanced through the Rust 1.89 bootstrap (`rustc_ast_passes`,
  `rustc_proc_macro`, and compression crates); Docker reported about 99% CPU
  and 453 MiB resident memory, with no exit marker or Jarvis store output.
  Root disk had 15 GiB free; `/dev/shm` was mostly empty. No package lifecycle
  result is available until these builds and their package phases complete.

  At 00:42:32 UTC, Gentoo advanced to 1,630/2,473 targets (65.9%), still
  compiling V8 without a failure marker; the Node executable is not present.
  Guix remains CPU-active in the Rust bootstrap, compiling `rustc_parse`,
  `rustc_ast_passes`, `rustc_proc_macro`, and `rustc_expand`; no package output
  or exit marker exists. Docker reported 5.4 GiB for Gentoo and 630 MiB for
  Guix; root disk remained at 15 GiB free.

  At 00:44:54 UTC, Gentoo reached 1,635/2,473 targets (66.1%), still building
  V8. Guix's stage-2 Rust compiler process was directly observed at 99% CPU
  for 3:30 elapsed, confirming the apparently unchanged log is a long-running
  compile rather than a stopped build. There is no Guix exit marker or Jarvis
  store output yet.

  At 00:45:56 UTC, Gentoo advanced to 1,636/2,473 targets (66.1%). Guix's
  `.rustc-real` process remained at 99% CPU for 4:33 elapsed; the build log
  still shows the stage-2 compiler crates and has no error or exit marker.
  Neither ARM64 package is ready for lifecycle testing.

  At 00:46:13 UTC, Gentoo remained at 1,636/2,473 targets and continued
  compiling V8. Guix still had `.rustc-real` at 99% CPU; filesystem inspection
  found a recently emitted `librustc_expand` metadata artifact in the stage-0
  compiler build tree. The package build has not completed and no Jarvis store
  output is available.

  At 00:47:20 UTC, Gentoo reached 1,640/2,473 Ninja targets (66.3%), still
  building V8 without an exit marker. Guix generated fresh `rustc_expand`
  codegen object files during the last two minutes; the active `.rustc-real`
  process remains at about 99% CPU and cgroup OOM counters are zero. Neither
  package has reached lifecycle testing.

  At 00:48:14 UTC, Gentoo advanced to 1,641/2,473 targets (66.4%); five
  `cc1plus` processes were actively compiling V8. Guix emitted another
  `rustc_expand` codegen object at 00:48:07; `.rustc-real` remained at 99% CPU
  and all cgroup OOM counters were zero. No package output is available yet.

  At 00:49:35 UTC, Gentoo reached 1,644/2,473 targets (66.5%), with active
  `cc1plus` processes compiling V8. Guix wrote another `rustc_expand` codegen
  object at 00:49:33 while `.rustc-real` remained at about 99% CPU; no OOM or
  build failure was recorded.

  At 00:50:21 UTC, Gentoo advanced to 1,646/2,473 targets (66.5%) with active
  V8 compilation. Guix emitted additional `rustc_expand` codegen objects at
  00:49:59 and 00:50:16; `.rustc-real` remained active and cgroup OOM counters
  stayed at zero. No ARM64 package artifact is ready for installation tests.

  At 00:51:13 UTC, Gentoo reached 1,647/2,473 targets (66.6%), still compiling
  V8. Guix emitted further `rustc_expand` codegen objects at 00:50:53 and
  00:51:08; the compiler remained at about 99% CPU and OOM counters stayed
  zero. No package build has completed yet.

  At 00:52:06 UTC, Gentoo remained at 1,647/2,473 while three `cc1plus`
  processes were actively compiling V8. Guix produced additional `rustc_expand`
  codegen objects at 00:51:52 and 00:52:04; `.rustc-real` remained at 99% CPU
  and its cgroup OOM counters were zero. `ollama ps` showed no loaded model.

  At 00:52:52 UTC, Gentoo reached 1,651/2,473 targets (66.7%) with four active
  V8 `cc1plus` processes. Guix emitted more `rustc_expand` codegen objects at
  00:52:31 and 00:52:45; `.rustc-real` stayed at 99% CPU and OOM counters were
  zero. Both builds remain in progress.

  At 00:53:39 UTC, Gentoo reached 1,652/2,473 targets (66.8%). Guix completed
  the `rustc_expand` stage-0 fingerprint and moved on to the `object` crate's
  build script; the Rust process remains active and the cgroup OOM counters
  are zero. The Guix Jarvis derivation has not completed.

  At 00:54:36 UTC, Gentoo advanced to 1,653/2,473 targets (66.8%), compiling
  another V8 object. Guix's log progressed through `object`, `flate2`, and
  `ruzstd` to `unicode-script`; `.rustc-real` was CPU-active and OOM counters
  remained zero. No ARM64 Jarvis package is ready yet.

  At 00:55:23 UTC, Gentoo reached 1,655/2,473 targets (66.9%), compiling V8
  objects. Guix completed `unicode-script` (Cargo fingerprint recorded) and
  advanced to `unicode-security`; the compiler remains active and OOM counters
  are zero. Package output is still pending.

  At 00:56:45 UTC, Gentoo reached 1,658/2,473 targets (67.0%) with V8 C++
  compilation active. Guix recorded the `unicode-security` fingerprint and
  produced a 1.5 MiB `full.rmeta` in the Rust build tree. `.rustc-real` remained
  CPU-active and OOM counters stayed at zero; the Guix package is still pending.

  At 00:57:29 UTC, Gentoo reached 1,659/2,473 targets; V8 `cc1plus` workers
  remained active. Guix emitted an 8.4 MiB `libobject` metadata artifact and
  remained CPU-active with zero OOM events. The package derivation has not
  completed yet.

  At 00:58:24 UTC, Gentoo reached 1,661/2,473 targets (67.2%) with active V8
  compilation. Guix continued code-generating the `object` crate; new object
  files appeared through 00:58:23 and OOM counters remained zero. No package
  artifact is available.

  At 00:59:58 UTC, Gentoo reached 1,663/2,473 targets (67.3%), compiling V8
  objects. Guix's log remained on `regex-syntax`; `.rustc-real` was still CPU-
  active and its OOM counters stayed zero. Neither package build has finished.

  At 01:00:41 UTC, Gentoo reached 1,665/2,473 targets (67.3%), compiling V8
  objects. Guix continued `regex-syntax` code generation; a new CGU object was
  written at 01:00:39, `.rustc-real` remained CPU-active, and OOM counters were
  zero. Neither ARM64 package is ready.

  At 01:01:26 UTC, Gentoo reached 1,666/2,473 targets (67.4%). Guix recorded
  the `regex-syntax` fingerprint and moved to `fallible-iterator`; its Rust
  compiler remained CPU-active and OOM counters stayed at zero.

  At 01:02:09 UTC, Gentoo reached 1,668/2,473 targets (67.5%). Guix completed
  `fallible-iterator` and began compiling `rustc_symbol_mangling`; the Rust
  compiler remained active and cgroup OOM counters were zero.

  At 01:03:21 UTC, Gentoo reached 1,670/2,473 targets (67.5%), compiling V8
  heap objects. Guix completed `rustc-demangle` and remained in
  `rustc_symbol_mangling`; its Rust process was CPU-active and cgroup OOM
  counters stayed at zero.

  At 01:04:04 UTC, Gentoo reached 1,671/2,473 targets (67.6%). Guix emitted
  new codegen objects for `rustc_symbol_mangling`; `.rustc-real` remained
  active and cgroup OOM counters stayed at zero. Neither package is ready.

  At 01:04:47 UTC, Gentoo reached 1,673/2,473 targets (67.7%). Guix completed
  the `rustc_symbol_mangling` fingerprint and advanced to `gimli`; both
  compilers remained active and Guix OOM counters were zero.

  At 01:05:29 UTC, Gentoo remained at 1,674/2,473 targets (67.7%) with V8
  compilation active. Guix produced `librustc_symbol_mangling` and a 2.1 MiB
  `full.rmeta` while compiling `gimli`; `.rustc-real` remained active and OOM
  counters were zero. The Guix package output is still pending.

  At 01:06:17 UTC, Gentoo remained at 1,675/2,473 targets (67.7%) with active
  V8 C++ workers. Guix produced a 6.8 MB `libgimli.rmeta` and continued emitting
  `gimli` codegen objects; the Rust process remained active and OOM counters
  were zero.

  At 01:07:05 UTC, Gentoo reached 1,676/2,473 targets (67.8%). Guix recorded
  the `gimli` fingerprint, emitted `libregex_automata.rmeta`, and continued
  compiling `regex-automata`; the compiler remained CPU-active and OOM counters
  were zero.

  At 01:07:49 UTC, Gentoo reached 1,679/2,473 targets (67.9%). Guix recorded
  the `regex-automata` fingerprint and advanced to `rustc_metadata`; both
  builds remained active, with Guix OOM counters at zero.

  At 01:08:32 UTC, Gentoo remained at 1,680/2,473 targets (67.9%) with V8
  compilers active. Guix produced a 1.7 MB `full.rmeta` while compiling
  `rustc_metadata`; the compiler remains active and OOM counters are zero.

  At 01:09:16 UTC, Gentoo reached 1,681/2,473 targets (68.0%). Guix emitted
  `librustc_metadata.rmeta` (1.95 MB); the Rust compiler remained active and
  cgroup OOM counters were zero. No package output is available yet.

  At 01:10:30 UTC, Gentoo reached 1,683/2,473 targets (68.1%) with active V8
  compilation. Guix remained in `rustc_metadata`; `.rustc-real` was CPU-active
  for 2:42 and OOM counters stayed at zero, although no newer Rust artifact
  appeared in this interval.

  At 01:11:44 UTC, Gentoo reached 1,687/2,473 targets (68.2%) with V8
  compilation active. Guix remained in `rustc_metadata`; `.rustc-real` used
  about 99% CPU and OOM counters were zero, though no new Rust output appeared
  in the most recent two-minute window.

  At 01:13:37 UTC, Gentoo reached 1,689/2,473 targets (68.3%). Guix's process
  command line confirmed the active QEMU-emulated Rust 1.88 bootstrap compiler
  is compiling `rustc_metadata`; it had used CPU for 5:49, with zero OOM events.
  This explains the long interval without new Cargo log lines; no package output
  is ready yet.

  At 01:14:23 UTC, Gentoo reached 1,692/2,473 targets (68.4%). Guix remained
  in `rustc_metadata` and emitted codegen objects `cgu.00` and `cgu.08`; the
  compiler remained CPU-active and OOM counters stayed at zero.

  At 01:15:06 UTC, Gentoo reached 1,693/2,473 targets (68.5%). Guix emitted
  another `rustc_metadata` codegen object (`cgu.05`) at 01:15:02; `.rustc-real`
  remained CPU-active and OOM counters stayed at zero.

  At 01:16:21 UTC, Gentoo reached 1,696/2,473 targets (68.6%). Guix remained
  in `rustc_metadata` and emitted another codegen object (`cgu.04`) at 01:16:04;
  `.rustc-real` stayed CPU-active and OOM counters were zero.

  At 01:17:37 UTC, Gentoo reached 1,698/2,473 targets (68.6%). Guix remained
  in `rustc_metadata` and emitted codegen objects `cgu.10` and `cgu.12`; the
  QEMU compiler stayed CPU-active and OOM counters were zero.

  At 01:18:21 UTC, Gentoo reached 1,699/2,473 targets (68.6%). Guix remained
  in `rustc_metadata` and emitted codegen objects `cgu.12` and `cgu.02`; the
  compiler was active and cgroup OOM counters stayed at zero.

  At 01:19:09 UTC, Gentoo reached 1,701/2,473 targets (68.8%). Guix remained
  in `rustc_metadata` and emitted codegen object `cgu.15` at 01:18:57; the
  compiler remained CPU-active and OOM counters were zero.

  At 01:19:54 UTC, Gentoo reached 1,703/2,473 targets (68.9%). Guix remained
  in `rustc_metadata` and emitted codegen objects `cgu.01` and `cgu.03`; the
  QEMU compiler stayed CPU-active and OOM counters remained zero.

  At 01:20:39 UTC, Gentoo reached 1,704/2,473 targets (68.9%). Guix remained
  in `rustc_metadata` and emitted codegen objects `cgu.11` and `cgu.13`; the
  compiler stayed active and OOM counters remained zero.

  At 00:59:16 UTC, Gentoo reached 1,662/2,473 targets (67.2%), still compiling
  V8 object files. Guix recorded completed `libloading` and `punycode` crates
  and advanced to `regex-syntax`; the Rust build remained CPU-active with zero
  cgroup OOM events. No package artifact is ready.

  At the resumed check on 2026-10-27, Gentoo had advanced to 1,705/2,473
  targets (68.9%) and was actively compiling V8 generated-object C++ files
  under QEMU. Guix had moved on from `rustc_metadata` to `rustc_lint` in the
  Rust 1.89 bootstrap; no final Jarvis package was present yet. Both builds
  remained active, so neither target's package lifecycle is verified.

  A short live poll on 2026-10-27 confirmed the Gentoo Ninja process is active
  and advanced to 1,706/2,473 targets (69.0%), completing another V8 generated
  object. Guix remains in the Rust 1.89 bootstrap at `rustc_lint`; its build
  log has not yet reached the Jarvis derivation. Neither target is terminal.

  At 01:22 UTC on 2026-10-27, both ARM64 builds were confirmed CPU-active.
  Gentoo Ninja remained at 1,706/2,473 while four AArch64 C++ compiler jobs
  were using about 99% CPU each; 12 Node/V8 object files had changed within
  three minutes. Guix `.rustc-real` was using about 99% CPU and six Rust
  bootstrap files had changed within three minutes, still compiling
  `rustc_metadata`/`rustc_lint`. No completion markers or final package were
  present.

  At 01:23 UTC, the live Gentoo build advanced again to 1,709/2,473 targets
  (69.1%), with eight Node/V8 objects modified during the preceding two
  minutes. Guix remained CPU-active in `rustc_metadata`/`rustc_lint` bootstrap
  codegen and changed six files in its Rust build tree in the same interval.
  Both package builds are still incomplete.

  At 01:28 UTC on 2026-10-27, Gentoo reached 1,720/2,473 Node targets
  (69.6%). Guix remained in Rust 1.89 bootstrap codegen at `rustc_metadata` /
  `rustc_lint`; `.rustc-real` was CPU-active and no exit marker existed.

  At 01:29 UTC, Gentoo advanced to 1,721/2,473 targets (69.6%); eight object
  files changed within the last two minutes. Guix stayed in `rustc_metadata` /
  `rustc_lint` but changed two files in its Rust build tree in that interval;
  `.rustc-real` remained CPU-active, and cgroup OOM counters were all zero.

  At the latest live poll (01:30 UTC, 2026-10-27), Gentoo advanced to
  1,723/2,473 targets (69.7%). The Guix Rust bootstrap log remained on
  `rustc_metadata`/`rustc_lint`, while three files in its build tree changed
  in the preceding two minutes. Both builders remained active.

  At 01:31 UTC, the next short poll had not completed a further Ninja target;
  six Gentoo object files and three Guix Rust build files were nevertheless
  modified within two minutes, and the Guix bootstrap compiler remained at
  approximately 99% CPU. No build exit marker or final package was present.

  At 01:31 UTC on 2026-10-27, Gentoo reached 1,724/2,473 targets (69.7%).
  Guix's active compiler was in `rustc_lint` codegen; five codegen objects for
  that crate existed, though none changed in the last short poll. CPU remained
  active and OOM counters stayed at zero. No final package was ready.

  At 01:32 UTC, the Gentoo build advanced to 1,725/2,473 targets (69.8%).
  Guix remained in the Rust 1.89 bootstrap at `rustc_metadata` and `rustc_lint`,
  with `.rustc-real` still CPU-active. Neither build had an exit marker or
  final Jarvis package.

  At 01:32 UTC, the Gentoo Node build reached 1,726/2,473 targets (69.8%).
  The Guix bootstrap remained on `rustc_metadata`/`rustc_lint`; both builders
  were active and no package artifact or terminal marker was present.

  At 01:33 UTC, Gentoo reached 1,728/2,473 targets (69.9%). Its current
  `ninja -j6` build used about six CPU cores and 5.4 GiB; Guix used one core
  and 0.9 GiB. Both remained active, with Guix still compiling Rust bootstrap
  crates and no package artifact ready.

  At 01:33 UTC, host capacity review showed 12 CPUs and 16 GiB available RAM,
  while the Gentoo QEMU build used six CPUs. I stopped only the Ninja process
  with SIGINT (exit 130), confirmed its compiler workers had exited, and
  resumed incrementally with `ninja -j8`; the last completed subtarget was
  1,729/2,473. At 01:34 UTC the resumed build was using about eight CPUs and
  4.4 GiB, with no exit marker; Guix continued its Rust bootstrap on one CPU.

  At 01:35 UTC, Gentoo's `-j8` Ninja run remained active at the 1,729-target
  restart checkpoint; nine Node/V8 object files were modified in the last two
  minutes and memory use was about 7.1 GiB. Guix remained in Rust `rustc_lint`
  codegen and emitted additional CGUs, with no OOM events or package output.

  At 01:36 UTC, Gentoo had not yet logged a target completion after switching
  to `-j8`, but eight active C++ workers were each compiling generated V8
  Intl/locale files for about 2m43s at full CPU. Guix's Rust codegen tree had
  eight `rustc_lint` CGUs updated in the last five minutes. Both cgroups still
  reported zero OOM events.

  At 01:37 UTC, the resumed Gentoo graph showed 2/744 remaining actions
  completed (equivalent to 1,731/2,473 total, 70.0%). `-j8` used about 9.7
  GiB and host memory still had 14 GiB available; both containers' OOM counters
  remained zero. Guix's Rust codegen tree received five new CGUs in three
  minutes, with no package output yet.

  At 01:38 UTC, Gentoo completed 7/744 remaining actions after the `-j8`
  restart, equivalent to 1,736/2,473 targets (70.1%). Guix remained in
  `rustc_metadata`/`rustc_lint` bootstrap and wrote three Rust codegen objects
  in the preceding two minutes. Both builds remained active without OOM events.

  At 01:38 UTC, Gentoo reached 8/744 resumed actions (1,737/2,473 total,
  70.2%). Guix remained in Rust bootstrap, with five `rustc_lint` codegen
  objects changed within three minutes. Both builders were active and their
  OOM counters remained zero.

  At 01:39 UTC, Gentoo remained at 8/744 resumed actions (1,737/2,473 total)
  while ten Node/V8 object files changed in two minutes. Guix advanced from
  `rustc_lint` to `rustc_mir_dataflow` in the Rust bootstrap. Both builders
  remained active; cgroup OOM counters were zero.

  At 01:39 UTC, Gentoo remained at 8/744 resumed actions (1,737/2,473 total)
  while 16 object files changed within three minutes and eight compiler jobs
  were CPU-active. Guix remained in `rustc_mir_dataflow` codegen under a
  CPU-active `.rustc-real`; both OOM counters remained zero and neither package
  had finished.

  At 01:40 UTC, Gentoo completed 11/744 resumed actions (1,740/2,473 total,
  70.4%), including the V8 init dependency stamp. Guix continued in Rust
  `rustc_metadata`/`rustc_lint`/`rustc_mir_dataflow` and changed six files in
  the last two minutes. Both remained active without OOM events.

  At 01:41 UTC, Gentoo advanced to 12/744 resumed actions (1,741/2,473 total,
  70.4%), beginning the generated `js-to-js` initializer object. Guix remained
  in Rust `rustc_metadata`/`rustc_lint`/`rustc_mir_dataflow` with three build
  files changed in the latest two-minute window. Both jobs were CPU-active and
  OOM counters remained zero.

  At 01:41 UTC, Gentoo remained at 12/744 resumed actions (1,741/2,473 total)
  while six output objects changed within three minutes. Its memory use was
  10.1 GiB, with 12 GiB available host memory and zero OOM events. Guix stayed
  in `rustc_mir_dataflow` bootstrap and changed 11 files during the same window;
  no final packages or exit markers were present.

  At 01:42 UTC, Gentoo advanced from 13/744 to 33/744 resumed actions,
  equivalent to 1,762/2,473 total (71.3%). Node's `js2c`, V8 snapshot, and
  AArch64 libffi objects/archive completed. Guix remained in Rust bootstrap at
  `rustc_metadata`/`rustc_lint`/`rustc_mir_dataflow`, with 13 files changed in
  the last two minutes. Neither build had finished; OOM counters remained 0.

  At 01:43 UTC, Gentoo reached 39/744 resumed actions (1,768/2,473 total,
  71.5%), progressing through V8 builtins and snapshot objects. Guix advanced
  beyond the compiler crates into Rust dependencies (`lazy_static`, `leb128`,
  `overload`, `cfg_aliases`); 40 build files changed in two minutes and the
  compiler remained CPU-active. No OOM events or final packages.

  At 01:43 UTC, Gentoo reached 44/744 resumed actions (1,773/2,473 total,
  71.7%), including the V8 init archive and `node_base` dependency stamp.
  Guix advanced to Rust `rustc_llvm` and the `pulldown-cmark` dependency.
  Both builds remained active without terminal markers.

  At 01:44 UTC, Gentoo advanced to 57/744 resumed actions (1,786/2,473 total,
  72.2%), including V8 wasm builtins and zstd compression/decompression
  objects. Guix continued the Rust bootstrap dependencies and changed 61 build
  files over the latest short window. Both builds remained active.

  At 01:44 UTC, Gentoo advanced to 69/744 resumed actions (1,798/2,473 total,
  72.7%), compiling zstd compression code and the V8 empty snapshot. Guix
  remained in Rust `rustc_mir_dataflow`/`rustc_llvm` bootstrap and changed 56
  build files over two minutes. Neither target had produced its final package.

  At 01:45 UTC, Gentoo advanced to 90/744 resumed actions (1,819/2,473 total,
  73.6%), compiling zstd and uvwasi AArch64 objects. Guix remained in the Rust
  `rustc_llvm` bootstrap crate with 12 build files changed in the latest two
  minutes. Both builds remained active without OOM events.

  At 01:46 UTC, Gentoo reached 101/744 resumed actions, exactly 1,830/2,473
  total (74.0%), including llhttp, inspector-protocol and nbytes objects.
  Guix advanced through the `wasm-encoder` dependency while continuing the Rust
  bootstrap; 19 build files changed over two minutes. Both builds remained live.

  At 01:47 UTC, Gentoo reached 116/744 resumed actions (1,845/2,473 total,
  74.6%) and successfully linked `mksnapshot`, completing the V8 snapshot
  dependency stamp. Guix continued through the `wasm-encoder` dependency with
  22 changed files in two minutes. Both builds remained active.

  At 01:47 UTC, Gentoo reached 122/744 resumed actions (1,851/2,473 total,
  74.8%); the V8 snapshot source and embedded object were generated, and work
  continued in zstd, ncrypto and LIEF. Guix advanced to `sharded-slab` and
  changed 32 files in two minutes. No build had completed.

  At 01:48 UTC, Gentoo reached 125/744 resumed actions (1,854/2,473 total,
  75.0%), continuing through LIEF C++ objects. Guix remained in Rust's
  `wasm-encoder`/`sharded-slab` dependencies with 12 build files changed over
  two minutes. Both jobs remained active.

  At 01:49 UTC, Gentoo reached 133/744 resumed actions (1,862/2,473 total,
  75.3%), continuing LIEF BinaryStream/JSON/Symbol objects. The compiler
  emitted a non-fatal `-Wshift-negative-value` warning in upstream
  `BinaryStream.cpp`; Ninja continued successfully. Guix remained in the
  `wasm-encoder`/`sharded-slab` dependency group with 11 changed build files.

  At 01:50 UTC, Gentoo reached 135/744 resumed actions (1,864/2,473 total,
  75.4%), continuing LIEF utility/logging objects; the earlier warning remained
  non-fatal. Guix stayed in `wasm-encoder`/`sharded-slab` dependency compilation;
  one build file changed during the latest short window and `.rustc-real`
  remained active. Both builds had zero OOM events.

  At 01:50 UTC, Gentoo reached 137/744 resumed actions (1,866/2,473 total,
  75.5%), continuing LIEF relocation/ASN.1 reader objects. Guix remained in
  `wasm-encoder`/`sharded-slab`; one build file changed in the latest two
  minutes while `.rustc-real` remained CPU-active. Both cgroups reported zero
  OOM events.

  At 01:51 UTC, Gentoo reached 144/744 resumed actions (1,873/2,473 total,
  75.7%), continuing through LIEF stream/header/ELF objects. Guix remained in
  `rustc_llvm`; the Rust build had spawned its C++ build script, with `cc1plus`
  at about 98% CPU. Both cgroups had zero OOM events.

  At 01:52 UTC, Gentoo reached 147/744 resumed actions (1,876/2,473 total,
  75.9%) in LIEF parser/section/node objects. Guix remained in `rustc_llvm`
  bootstrap with three files changed over three minutes and compiler CPU still
  active. Both builders had zero OOM events.

  At 01:52 UTC, Gentoo reached 149/744 resumed actions (1,878/2,473 total,
  75.9%), continuing LIEF DynamicEntry objects. Guix remained in the C++ phase
  of `rustc_llvm`; `cc1plus` was CPU-active and four Rust build files changed
  in the latest two-minute window. Both builders reported zero OOM events.

  At 01:53 UTC, Gentoo reached 152/744 resumed actions (1,881/2,473 total,
  76.1%), continuing through LIEF debug-info/dynamic-library objects. Guix
  advanced to `matchers` and `thorin-dwp` in the Rust bootstrap; 18 build files
  changed over two minutes and `.rustc-real` was CPU-active. No OOM events.

  At 01:54 UTC, Gentoo reached 155/744 resumed actions (1,884/2,473 total,
  76.2%), with more LIEF ELF handler/array/enum objects completed. Guix advanced
  to `ar_archive_writer` in the Rust dependency build; 24 files changed in the
  latest two minutes. Both builders remained active, without OOM events.

  At 01:55 UTC, Gentoo reached 158/744 resumed actions (1,887/2,473 total,
  76.3%), continuing LIEF ELF dynamic-entry objects. Guix advanced to the
  `bstr` dependency after `ar_archive_writer`; 19 files changed in the last
  two minutes. Both builders remained active with zero OOM events.

  At 01:56 UTC, Gentoo reached 163/744 resumed actions (1,892/2,473 total,
  76.4%), continuing ELF processor/layout/builder/dynamic-runpath objects.
  Guix remained on `bstr` in the Rust dependency graph, with 14 build files
  changed over the last two minutes. Both builders remained active.

  At 01:56 UTC, Gentoo reached 167/744 resumed actions (1,896/2,473 total,
  76.6%), progressing through LIEF ELF hash/relocation/header/string objects.
  Guix advanced into the Rust compiler crate `rustc_ty_utils`; 13 files changed
  over two minutes and `.rustc-real` remained CPU-active. No OOM events.

  At 01:57 UTC, Gentoo reached 169/744 resumed actions (1,898/2,473 total,
  76.8%) in LIEF symbol-version objects. Guix remained in `rustc_ty_utils`
  bootstrap with seven Rust build files changed in the last two minutes; both
  builders were still active and OOM counters were zero.

  At 01:58 UTC, Gentoo reached 177/744 resumed actions (1,906/2,473 total,
  77.1%), continuing LIEF ELF symbol/version/relocation objects. Guix remained
  in `rustc_ty_utils`, with six build files changed during the last two
  minutes; both builds were active and reported no OOM events.

  At 01:59 UTC, Gentoo reached 179/744 resumed actions (1,908/2,473 total,
  77.2%), including LIEF SysV hash. Guix remained in `rustc_ty_utils`, with one
  file changed in the last two minutes while its compiler stayed active. Both
  cgroups remained free of OOM events.

  At 01:59 UTC, Gentoo reached 184/744 resumed actions (1,913/2,473 total,
  77.4%), continuing LIEF parser/segment/note objects. Guix remained in
  `rustc_ty_utils`; `.rustc-real` was active though no files changed in the
  last short poll. Both cgroups reported zero OOM events.

  At 02:00 UTC, Gentoo reached 187/744 resumed actions (1,916/2,473 total,
  77.5%), continuing LIEF ELF note/property/auxv objects. Guix stayed in
  `rustc_ty_utils`; `.rustc-real` remained CPU-active though it produced no
  files in the latest two-minute interval. OOM counters remained zero.

  At 02:01 UTC, Gentoo reached 192/744 resumed actions (1,921/2,473 total,
  77.7%), compiling LIEF ELF note/property metadata objects. Guix remained in
  `rustc_ty_utils`; `.rustc-real` stayed at full CPU and four build files
  changed in the latest two-minute window. No OOM events were recorded.

  At 02:02 UTC, Gentoo reached 198/744 resumed actions (1,927/2,473 total,
  77.9%), compiling LIEF PE enum/codepage and ELF core-note objects. Guix
  remained in `rustc_ty_utils` with seven files changed over the latest two
  minutes. Both builders remained active with zero OOM events.

  At 02:02 UTC, Gentoo reached 202/744 resumed actions (1,931/2,473 total,
  78.1%), progressing through LIEF PE code-integrity/data-directory/delay-import
  objects. Guix remained in `rustc_ty_utils`; eight files changed during the
  latest two-minute window. Both builders remained active without OOM events.

  At 02:03 UTC, Gentoo reached 204/744 resumed actions (1,933/2,473 total,
  78.2%), continuing through LIEF PE objects. Guix remained in `rustc_ty_utils`
  and changed seven files during the latest two-minute window. Both builds
  remained active and OOM counters were zero.

  At 02:04 UTC, Gentoo reached 207/744 resumed actions (1,936/2,473 total,
  78.3%), continuing LIEF PE delay-import/export/builder objects. Guix remained
  in `rustc_ty_utils`; seven build files changed in two minutes. Both builds
  remained active and OOM counters were zero.

  At 02:05 UTC, Gentoo reached 215/744 resumed actions (1,944/2,473 total,
  78.5%), progressing through PE resource/export/parser/optional-header objects.
  Guix advanced from `rustc_ty_utils` to `rustc_incremental`; six build files
  changed in two minutes. Both builders remained active, without OOM events.

  At 02:05 UTC, Gentoo reached 216/744 resumed actions (1,945/2,473 total,
  78.6%), continuing the PE import-entry objects. Guix remained in
  `rustc_incremental` after `rustc_ty_utils`; six build files changed in two
  minutes. Both builds remained active, without OOM events.

  At 02:06 UTC, Gentoo reached 218/744 resumed actions (1,947/2,473 total,
  78.7%), progressing through PE rich-entry and relocation objects. Guix remained
  in `rustc_incremental`; one Rust build file changed in the latest two-minute
  window while the compiler stayed active. Both cgroups had zero OOM events.

  At 02:07 UTC, Gentoo reached 223/744 resumed actions (1,952/2,473 total,
  78.9%), compiling PE relocation/resource/rich-header objects. Guix remained
  in `rustc_incremental`; three build files changed over two minutes. Both
  processes remained active and OOM counters were zero.

At 2026-10-27 02:09 UTC, the Gentoo AArch64 resumed Node.js Ninja build advanced to 244/744 resumed actions (32.8%), or 1,973/2,473 total graph actions (79.8% including the 1,729 completed before resume). The process remains active with no exit marker; the latest targets are LIEF PE signature attributes. Guix AArch64's Rust 1.89 bootstrap remains active and has advanced to `rustc_pattern_analysis`; no final package output or exit marker is present. No lifecycle result is recorded for either target yet.

At 2026-10-27 02:10 UTC, Gentoo AArch64 advanced to 252/744 resumed Node.js Ninja actions (33.9%), or 1,981/2,473 total graph actions (80.1%). The build remains active in LIEF PE signature parsing/signing objects. Guix AArch64 remains active compiling Rust bootstrap crates `rustc_ty_utils`, `rustc_incremental`, and `rustc_pattern_analysis`; there is still no final output or exit marker. Package lifecycle checks remain pending for both targets.

At 2026-10-27 02:11 UTC, the Gentoo Node.js Ninja build reached 253/744 resumed actions (34.0%), equivalent to 1,982/2,473 total actions (80.2%). Guix remains in `rustc_ty_utils`/`rustc_incremental`/`rustc_pattern_analysis`; the `.rustc-real` process was confirmed active at 99.5% CPU. Both containers are live, no exit markers exist, and package lifecycle verification is still outstanding.

At 2026-10-27 02:12 UTC, Gentoo reached 256/744 resumed Node.js actions (34.4%), or 1,985/2,473 total graph actions (80.3%). Guix remains CPU-active in the Rust compiler crates `rustc_ty_utils`, `rustc_incremental`, and `rustc_pattern_analysis`; no output or exit marker yet. Host storage has 15 GiB free (97% used), so both builds are being monitored without pruning unrelated artifacts; no package lifecycle has completed.

At 2026-10-27 02:12:54 UTC, Gentoo reached 258/744 resumed Node.js actions (34.7%), or 1,987/2,473 total graph actions (80.3%); it compiled LIEF PE load-configuration objects. Guix advanced to Rust bootstrap dependencies `thread_local` and `unicase`; `.rustc-real` remained active at 98.6% CPU and six files changed in the last two minutes. Neither builder has exited, and neither distro package lifecycle has run yet.

At 2026-10-27 02:13 UTC, Gentoo advanced to 259/744 resumed Node.js Ninja actions (34.8%), or 1,988/2,473 total graph actions (80.4%). Guix advanced to Rust bootstrap crate `rustc_codegen_ssa`; both build processes remain active with no exit markers. Host free space is still 15 GiB (97% used). The package lifecycle scripts are ready, but neither target has produced an installable Jarvis artifact.

At 2026-10-27 02:13 UTC (02:13:27 poll), Gentoo reached 262/744 resumed actions (35.2%), or 1,991/2,473 total actions (80.5%), compiling LIEF PE load-configuration and dynamic-relocation objects. Guix remains in `rustc_codegen_ssa`; 14 build dependency files changed in the previous two-minute window. Both processes are live without failure/exit markers; 15 GiB host disk space remains free.

At 2026-10-27 02:15 UTC, the Gentoo Ninja build was resumed incrementally with `-j10` after host measurements showed 19 GiB available memory, 5.2 GiB Gentoo cgroup usage at `-j8`, and zero cgroup OOM events. The previous run had completed through action 264/744; the new run retains the same `out/Release` object tree and has ten active `cc1plus` workers. Its new log is `build-resume-j10.log`; no new action has completed yet in this brief observation window. Guix remains active in `rustc_codegen_ssa` with `.rustc-real` near 99% CPU. Host free disk remains 15 GiB.

At 2026-10-27 02:16 UTC, the Gentoo incremental `-j10` run recognized 264 completed objects from the previous Ninja run and reduced the outstanding graph from 744 to 480 actions. It has now completed 2/480 new actions; cumulative progress is approximately 1,995/2,473 actions (80.7%). Gentoo cgroup usage is 5.4 GiB with ten workers and no OOM events; the host has 15 GiB free disk. Guix remains CPU-active in `rustc_codegen_ssa`, with no final output or exit marker.

At 2026-10-27 02:17 UTC, Gentoo's 10-worker incremental run advanced to 3/480 newly scheduled actions, or about 1,996/2,473 cumulative actions (80.7%). Cgroup memory stayed around 5.3 GiB with CPU near 9.3 cores; no OOM events. Guix's `rustc_codegen_ssa` remains CPU-active; one dependency file changed in the recent two-minute window. No package output is ready.

At 2026-10-27 02:17:57 UTC, Gentoo's 10-worker incremental Ninja build reached 12/480 actions (2.5% of the remaining subgraph), about 2,005/2,473 cumulative actions (81.1%). The latest completions are LIEF PE debug and dynamic-relocation objects. Guix remains in `rustc_codegen_ssa`; its `.rustc-real` compiler was active at 98.9% CPU. Both builds have no exit marker; host free disk remains 15 GiB.

At 2026-10-27 02:18:41 UTC, Gentoo advanced to 14/480 actions in the current Ninja subgraph, corresponding to about 2,007/2,473 cumulative actions (81.2%). Guix's Rust compiler remained active at 99.0% CPU in `rustc_codegen_ssa`; no exit marker or Jarvis store output exists yet. Neither AArch64 package lifecycle has completed.

At 2026-10-27 02:19 UTC, Gentoo reached 18/480 in the current `-j10` Ninja run, approximately 2,011/2,473 cumulative actions (81.3%). The latest objects cover PE debug metadata and resources; CPU remained near ten cores, with no OOM signal. Guix's `.rustc-real` remained at 99% CPU in `rustc_codegen_ssa`. Both target artifacts and lifecycle checks are still pending.

At 2026-10-27 02:20 UTC, Gentoo reached 22/480 incremental Ninja actions, about 2,015/2,473 cumulative actions (81.5%). It is compiling LIEF AArch64 unwind/resource/debug objects with ten workers and about 4.1 GiB cgroup usage. Guix remains in `rustc_codegen_ssa` with `.rustc-real` CPU-active; its final store output has not appeared. Package lifecycle validation remains pending for both distros.

At 2026-10-27 02:21 UTC, Gentoo reached 24/480 incremental Ninja actions, approximately 2,017/2,473 cumulative actions (81.6%). The completed objects include AArch64 and x86_64 PE exception/unwind metadata. Guix remains in `rustc_codegen_ssa`, with the Rust compiler still CPU-active and no OOM/exit marker; host free disk remains 15 GiB.

At 2026-10-27 02:22 UTC, Gentoo advanced to 30/480 incremental Ninja actions, or about 2,023/2,473 cumulative actions (81.8%). Guix remains in `rustc_codegen_ssa`; `.rustc-real` is active at 99.1% CPU and its cgroup OOM counters are all zero. Portage reports `/var/cache/binpkgs` as `PKGDIR`; the Gentoo package lifecycle will use the local binpkg/ebuild flow after Node.js finishes. No Jarvis AArch64 artifact exists yet.

At 2026-10-27 02:23 UTC, Gentoo advanced to 35/480 incremental actions (7.3%), approximately 2,028/2,473 cumulative actions (82.0%), in LIEF COFF and PE resource code. The 10-worker build used about 3.7 GiB and stayed near ten CPUs. Guix continued compiling `rustc_codegen_ssa`; its cgroup OOM counters remain zero and two build files changed recently. No package output is ready.

At 2026-10-27 02:24 UTC, Gentoo reached 39/480 incremental Ninja actions, approximately 2,032/2,473 cumulative actions (82.2%). Guix remained CPU-active at 99.1% in `rustc_codegen_ssa`; neither build has exited. An independent whole-branch review is still pending: `gh pr list --head feat/linux-port --state all` returned no pull requests for the branch.

At 2026-10-27 02:25 UTC, Gentoo reached 42/480 incremental Ninja actions (8.8%), about 2,035/2,473 cumulative actions (82.3%), compiling PE resources and COFF objects. Guix remains in `rustc_codegen_ssa`; `.rustc-real` is CPU-active at 99.1%, and two dependency files changed in the last minute. Both builds remain error-free and active; no package artifact is ready.

At 2026-10-27 02:25 UTC, Gentoo reached 43/480 incremental Ninja actions, approximately 2,036/2,473 cumulative actions (82.3%). Guix's Rust bootstrap remains in `rustc_codegen_ssa`, with four build files changed in the latest two-minute window. Both builders remain CPU-active; host disk has 15 GiB free and neither final package exists.

At 2026-10-27 02:26 UTC, Gentoo reached 45/480 incremental Ninja actions (9.4%), approximately 2,038/2,473 cumulative actions (82.4%). CPU usage is near ten cores and memory around 5.2 GiB. Guix remains in `rustc_codegen_ssa`, with three build files changed recently and `.rustc-real` near 99% CPU. Physical audio/portal validation authorization has been requested asynchronously; no user response is recorded yet. Package artifacts remain unavailable.

At 2026-10-27 02:26 UTC, Gentoo reached 48/480 incremental Ninja actions (10.0%), approximately 2,041/2,473 cumulative actions (82.5%). The build remains active without compiler errors. Guix remains in `rustc_codegen_ssa`; four build files changed recently and its compiler is active at 99.1% CPU. Host storage remains at 15 GiB free. No response to the real audio/desktop validation authorization request has arrived.

At 2026-10-27 02:27 UTC, Gentoo reached 50/480 incremental Ninja actions (10.4%), about 2,043/2,473 cumulative actions (82.6%). Guix remains in `rustc_codegen_ssa` with four recent build-file changes and `.rustc-real` at 99.1% CPU. Neither build has failed or produced a final package; disk headroom remains 15 GiB.

At 2026-10-27 02:27 UTC, Gentoo reached 51/480 incremental Ninja actions (10.6%), approximately 2,044/2,473 cumulative actions (82.7%). Guix remains compiling `rustc_codegen_ssa`; `.rustc-real` has spent 14 minutes on the crate at 99.1% CPU, with five build files modified in the latest three-minute window and no OOM events. Both containers remain active; no AArch64 Jarvis package artifact is ready. Real-session audio/desktop permission remains unanswered.

At 2026-10-27 02:27:58 UTC, Gentoo reached 53/480 incremental Ninja actions (11.0%), approximately 2,046/2,473 cumulative actions (82.7%). Ten `cc1plus` workers were active at roughly 95–97% CPU each; Gentoo cgroup usage was 5.5 GiB with zero OOM events, and host available memory was 18 GiB. Guix `.rustc-real` remains active at 99% in `rustc_codegen_ssa`; six files changed recently. No final artifacts are available.

At 2026-10-27 02:28 UTC, Gentoo reached 57/480 incremental Ninja actions (11.9%), approximately 2,050/2,473 cumulative actions (82.9%), compiling LIEF Mach-O and COFF metadata objects. Guix is still in `rustc_codegen_ssa`; `.rustc-real` has been active for 15 minutes at 99.1% CPU and five build files changed recently. Both processes remain live with no fatal errors or OOM events. Real-session test authorization remains unanswered.

At 2026-10-27 02:29 UTC, Gentoo reached 58/480 incremental Ninja actions (12.1%), about 2,051/2,473 cumulative actions (82.9%). Guix remains in `rustc_codegen_ssa`; `.rustc-real` continues at 99.1% CPU and three build files changed in the last minute. Both build processes remain live, with 15 GiB host disk free and no package artifacts yet.

At 2026-10-27 02:29 UTC, Gentoo reached 62/480 incremental Ninja actions (12.9%), about 2,055/2,473 cumulative actions (83.1%), progressing through LIEF Mach-O code-signature and dyld metadata. Guix's `rustc_codegen_ssa` compilation has run 16 minutes at 99.1% CPU; four build files changed recently and OOM counters remain zero. Both build containers are active; host has 15 GiB free disk.

At 2026-10-27 02:29 UTC, Gentoo reached 65/480 incremental Ninja actions (13.5%), about 2,058/2,473 cumulative actions (83.2%), continuing LIEF Mach-O code-signature and dyld objects. Guix's Rust compiler remains active in `rustc_codegen_ssa` at 99.1% CPU after 16m38s; four build files changed recently. Neither output is ready and both builds remain live without fatal errors.

At 2026-10-27 02:30 UTC, Gentoo reached 66/480 incremental Ninja actions (13.8%), approximately 2,059/2,473 cumulative actions (83.3%). Guix is still compiling `rustc_codegen_ssa`; its compiler has run for 16m54s at 99.1% CPU and six build files changed in the last three minutes, confirming ongoing work. No failure/exit marker or final package artifact exists.

At 2026-10-27 02:30:55 UTC, Gentoo reached 69/480 incremental Ninja actions (14.4%), approximately 2,062/2,473 cumulative actions (83.4%). Guix continues `rustc_codegen_ssa`; `.rustc-real` remains around 99% CPU, with two build files updated in the last minute and OOM counters still zero. No build failure or package output.

At 2026-10-27 02:31 UTC, Gentoo reached 75/480 incremental Ninja actions (15.6%), approximately 2,068/2,473 cumulative actions (83.5%). Guix completed the long `rustc_codegen_ssa` bootstrap compile: `librustc_codegen_ssa` `.rmeta` (4.8 MB) and `.rlib` (12.2 MB) now exist in the AArch64 stage0 deps directory. The Rust bootstrap has moved to `pulldown_cmark`; its rustc process is CPU-active. Both builds continue without a final Jarvis package artifact.

At 2026-10-27 02:32 UTC, Gentoo reached 78/480 incremental Ninja actions (16.3%), approximately 2,071/2,473 cumulative actions (83.7%). Guix's `rustc_codegen_ssa` artifact is present and the bootstrap is now actively compiling `pulldown_cmark`; its AArch64 `.rmeta` has appeared, while the `.rlib` is not yet complete. Both builds remain active without errors; disk free space is 15 GiB.

At 2026-10-27 02:32 UTC, Gentoo reached 80/480 incremental Ninja actions (16.7%), about 2,073/2,473 cumulative actions (83.8%). Guix continues compiling `pulldown_cmark`; its `.rmeta` is present, the `.rlib` is still pending, and 13 stage0 dependency files changed within two minutes while rustc stayed near 99% CPU. No failure or final package artifact.

At 2026-10-27 02:32:54 UTC, Gentoo reached 82/480 incremental Ninja actions (17.1%), approximately 2,075/2,473 cumulative actions (83.9%). Guix completed `pulldown_cmark` (both AArch64 `.rmeta` and `.rlib` exist) and has advanced to `tracing-subscriber`; three dependency files changed recently. Both builds remain active and error-free, with 15 GiB host disk free.

At 2026-10-27 02:33:46 UTC, Gentoo reached 87/480 incremental Ninja actions (18.1%), approximately 2,080/2,473 cumulative actions (84.1%). Guix has moved beyond `pulldown_cmark` and is compiling `tracing-subscriber`; its rustc process is CPU-active, with two files changed within the last minute. Both builds remain active, with no fatal errors or final package artifacts.

At 2026-10-27 02:34 UTC, Gentoo reached 90/480 incremental Ninja actions (18.8%), approximately 2,083/2,473 cumulative actions (84.2%). Guix is compiling `tracing-subscriber`; its rustc process is CPU-active and three dependency files changed within the last two minutes. Both builds remain live without fatal errors; the Jarvis package outputs are not ready.

At 2026-10-27 02:34 UTC, Gentoo reached 94/480 incremental Ninja actions (19.6%), approximately 2,087/2,473 cumulative actions (84.4%). Guix remains in `tracing-subscriber`; its Rust compiler is active at 99% CPU and three dependency files changed recently. Neither builder has produced a Jarvis output or exit marker; host free disk remains 15 GiB.

At 2026-10-27 02:35:10 UTC, Gentoo reached 96/480 incremental Ninja actions (20.0%), approximately 2,089/2,473 cumulative actions (84.5%). Guix is still compiling `tracing-subscriber`; the active rustc process is near 99% CPU and nine build dependency files changed in the last minute. Both builds remain live without fatal errors; no Jarvis output is ready.

At 2026-10-27 02:36 UTC, Gentoo reached 101/480 incremental Ninja actions (21.0%), approximately 2,094/2,473 cumulative actions (84.7%). Guix completed `tracing-subscriber` (AArch64 `.rmeta` and `.rlib` are present) and advanced to `rustc_mir_build`; its rustc process is active. Both builds remain live with no fatal errors or final Jarvis package artifact.

At 2026-10-27 02:36 UTC, Gentoo reached 103/480 incremental Ninja actions (21.5%), approximately 2,096/2,473 cumulative actions (84.8%). Guix has advanced to compiling `rustc_mir_build` after `tracing-subscriber`; the new rustc process is active. Both builds remain live without fatal errors, and no final Jarvis output has appeared.

At 2026-10-27 02:37 UTC, Gentoo reached 108/480 incremental Ninja actions (22.5%), approximately 2,101/2,473 cumulative actions (85.0%). Guix remains compiling `rustc_mir_build`; `.rustc-real` is active near 99% CPU and one stage0 dependency file changed in the last minute. Both build containers remain live without fatal errors or final package outputs.

At 2026-10-27 02:37 UTC, Gentoo reached 110/480 incremental Ninja actions (22.9%), approximately 2,093/2,473 cumulative actions (84.6%). Guix remains in `rustc_mir_build`; its compiler is active at 99% CPU, with three stage0 files changed recently. No Jarvis store output or build exit marker exists, and host disk free space remains 15 GiB.

At 2026-10-27 02:37 UTC, Gentoo reached 111/480 incremental Ninja actions (23.1%), approximately 2,104/2,473 cumulative actions (85.1%). Guix is still compiling `rustc_mir_build`; `.rustc-real` is active near 99% CPU after 1m52s and three dependency files changed recently. Both processes remain live with 15 GiB disk free and no final package outputs.

At 2026-10-27 02:37:52 UTC, Gentoo reached 114/480 incremental Ninja actions (23.8%), approximately 2,107/2,473 cumulative actions (85.2%). Guix remains compiling `rustc_mir_build`; rustc is active near 99% CPU with two stage0 dependency files changed recently. Neither build has exited or produced a final Jarvis package.

At 2026-10-27 02:38 UTC, Gentoo reached 115/480 incremental Ninja actions (24.0%), approximately 2,108/2,473 cumulative actions (85.2%). Guix remains compiling `rustc_mir_build`; `.rustc-real` has run 2m25s near 99% CPU and one stage0 file changed in the latest two-minute window. Neither build has produced a final Jarvis package or exit marker.

At 2026-10-27 02:39 UTC, Gentoo reached 118/480 incremental Ninja actions (24.6%), approximately 2,111/2,473 cumulative actions (85.4%). Guix's `rustc_mir_build` has emitted its 1.96 MB `.rmeta`; the rustc process remains CPU-active while producing the link artifact, and the `.rlib` has not appeared yet. OOM counters remain zero. Both package lifecycles remain pending.

At 2026-10-27 02:40 UTC, Gentoo reached 121/480 incremental Ninja actions (25.2%), approximately 2,114/2,473 cumulative actions (85.5%). Guix is still in the `rustc_mir_build` link phase: the `.rmeta` exists, `.rlib` is pending, and rustc has run 4m19s near 99% CPU with no OOM events. Both builds remain active without fatal errors.

At 2026-10-27 02:40 UTC, Gentoo reached 122/480 incremental Ninja actions (25.4%), approximately 2,115/2,473 cumulative actions (85.5%). Guix remains linking `rustc_mir_build`: only its `.rmeta` is present, while rustc stays CPU-active near 99% after 4m39s; cgroup OOM counters remain zero. No final package outputs or build exit markers yet.

At 2026-10-27 02:40:45 UTC, Gentoo reached 123/480 incremental Ninja actions (25.6%), approximately 2,116/2,473 cumulative actions (85.6%). Guix's `rustc_mir_build` link is still running at 99% CPU after five minutes; its `.rmeta` exists, `.rlib` is pending, and all cgroup OOM counters remain zero. No final Jarvis package or build exit marker yet.

At 2026-10-27 02:41 UTC, Gentoo reached 127/480 incremental Ninja actions (26.5%), approximately 2,120/2,473 cumulative actions (85.7%). Guix's `rustc_mir_build` link remains CPU-active at 99% after 5m19s; the `.rmeta` is present, `.rlib` pending, and OOM counters remain zero. Both containers have no exit markers or fatal errors.

At 2026-10-27 02:41 UTC, Gentoo reached 129/480 incremental Ninja actions (26.9%), approximately 2,122/2,473 cumulative actions (85.8%). Guix's `rustc_mir_build` link remains active at 98.9% CPU after 5m37s; `.rmeta` is present, `.rlib` is pending, and OOM counters remain zero. Both builds have no exit marker or fatal error.

At 2026-10-27 02:42 UTC, Gentoo reached 137/480 incremental Ninja actions (28.5%), approximately 2,130/2,473 cumulative actions (86.1%). Guix's `rustc_mir_build` link remains CPU-active at 98.9% after 6m54s; its `.rmeta` exists, `.rlib` is still pending, and OOM counters remain zero. No final package artifacts or failure markers yet.

At 2026-10-27 02:43 UTC, Gentoo reached 141/480 incremental Ninja actions (29.4%), approximately 2,134/2,473 cumulative actions (86.2%), entering the LIEF mbedTLS sources. Guix's `rustc_mir_build` link remains CPU-active at 98.9% after 7m12s; `.rmeta` exists and `.rlib` is pending, with OOM counters zero. Both targets remain unverified until package lifecycle runs.

At 2026-10-27 02:43 UTC, Gentoo reached 148/480 incremental Ninja actions (30.8%), approximately 2,141/2,473 cumulative actions (86.6%). Guix `rustc_mir_build` linking remains active at 98.9% CPU after 7m34s; two build files changed recently, `.rlib` is pending, and OOM counters are zero. Both package build/lifecycle gates remain incomplete.

At 2026-10-27 02:44 UTC, Gentoo reached 172/480 incremental Ninja actions (35.8%), approximately 2,165/2,473 cumulative actions (87.5%). Guix `rustc_mir_build` remains active at 99% CPU after 8m19s; the build log has not advanced beyond this crate, no exit marker exists, and cgroup OOM counters remain zero. Both package lifecycle gates remain incomplete.

At 2026-10-27 02:45 UTC, Gentoo reached 233/480 incremental Ninja actions (48.5%), approximately 2,226/2,473 cumulative actions (90.0%). Guix `rustc_mir_build` remains active at 99% CPU after 9m16s; three build files changed in the last minute, its log remains on the same crate, and cgroup OOM counters remain zero. Neither final package lifecycle has completed.

At 2026-10-27 02:45 UTC, Gentoo reached 255/480 incremental Ninja actions (53.1%), approximately 2,254/2,473 cumulative actions (91.1%). Guix `rustc_mir_build` remains active at 99% CPU after 9m35s; three stage0 dependency files changed recently, with no OOM events or build exit marker. Gentoo is still compiling the native dependency graph; neither Jarvis package lifecycle has completed.

At 2026-10-27 02:46 UTC, Gentoo reached 263/480 incremental Ninja actions (54.8%), approximately 2,256/2,473 cumulative actions (91.2%). Guix `rustc_mir_build` remains active at 99% CPU after 10m23s; new codegen-unit object files are being emitted (including one observed at 516,736 bytes), no `.rlib` or build exit marker exists yet, and cgroup OOM counters remain zero. Both targets still need their Jarvis package lifecycle and runtime smoke.

At 2026-10-27 02:46 UTC, Gentoo reached 265/480 incremental Ninja actions (55.2%), approximately 2,258/2,473 cumulative actions (91.3%). Guix `rustc_mir_build` remains active at 99% CPU after 10m43s; additional codegen-unit objects have appeared, including a recent zero-length object still being written, and OOM counters remain zero. Neither build has produced a final Jarvis package.

At 2026-10-27 02:47 UTC, Gentoo reached 271/480 incremental Ninja actions (56.5%), approximately 2,264/2,473 cumulative actions (91.5%). Guix `rustc_mir_build` remains CPU-active at 99% after 11m28s; dependency outputs continue changing and OOM counters remain zero. Its final Rust archive and the Guix Jarvis package are still pending.

At 2026-10-27 02:49 UTC, Gentoo reached 284/480 incremental Ninja actions (59.2%), approximately 2,277/2,473 cumulative actions (92.1%), with no build failure marker. Guix `rustc_mir_build` remains active at 99% CPU after 13m30s; five dependency files changed in the last two minutes and cgroup OOM counters remain zero. Both Jarvis package lifecycle gates remain pending.

At 2026-10-27 02:50 UTC, Gentoo reached 291/480 incremental Ninja actions (60.6%), approximately 2,284/2,473 cumulative actions (92.4%). Guix completed and emitted `librustc_mir_build-8e9d06b554c93d1c.rlib` (8,632,762 bytes) and advanced to compiling `rustc_privacy`; the Rust bootstrap remains active and cgroup OOM counters are zero. The Guix Jarvis package and both package lifecycle validations remain pending.

At 2026-10-27 02:51 UTC, Gentoo reached 294/480 incremental Ninja actions (61.3%), approximately 2,287/2,473 cumulative actions (92.5%). Guix's `rustc_mir_build` archive remains present; bootstrap is actively compiling `rustc_privacy` at 98.7% CPU, with one dependency file updated in the latest minute and OOM counters still zero. No final package outputs yet.

At 2026-10-27 02:52 UTC, Gentoo reached 306/480 incremental Ninja actions (63.8%), approximately 2,299/2,473 cumulative actions (93.0%). Guix emitted `librustc_privacy-4e11652c680bdc87.rlib` (2,160,202 bytes) and advanced to the next Rust crate; bootstrap remains active and OOM counters are zero. The Jarvis package phases remain pending on both targets.

At 2026-10-27 02:54 UTC, Gentoo reached 315/480 incremental Ninja actions (65.6%), approximately 2,302/2,473 cumulative actions (93.1%). Guix is actively compiling `rustc_const_eval` at 99% CPU after 1m17s; OOM counters remain zero. Its previous `rustc_privacy` archive and `rustc_mir_build` archive are present; final Rust bootstrap and Jarvis package lifecycle are pending.

At 2026-10-27 02:55 UTC, Gentoo reached 323/480 incremental Ninja actions (67.3%), approximately 2,316/2,473 cumulative actions (93.6%). Guix `rustc_const_eval` remains CPU-active at 99% after 2m57s, with RSS increasing to about 718 MiB and OOM counters zero; its final archive is pending. Neither native Jarvis package lifecycle has completed.

At 2026-10-27 02:57 UTC, Gentoo reached 333/480 incremental Ninja actions (69.4%), approximately 2,326/2,473 cumulative actions (94.1%). Guix `rustc_const_eval` remains CPU-active at 99% after 4m26s, RSS about 825 MiB, with no new dependency file in the last minute and OOM counters zero. Its Rust archive and both Jarvis package lifecycle validations remain pending.

At 2026-10-27 02:58 UTC, Gentoo reached 340/480 incremental Ninja actions (70.8%), approximately 2,333/2,473 cumulative actions (94.3%). Guix `rustc_const_eval` has emitted its 5.6 MB `.rmeta` and remains active at 99% CPU after 5m30s while producing the link artifact; OOM counters remain zero. The Rust `.rlib` and Guix/Gentoo Jarvis package lifecycle results are still pending.

At 2026-10-27 02:59 UTC, Gentoo reached 348/480 incremental Ninja actions (72.5%), approximately 2,341/2,473 cumulative actions (94.7%). Guix `rustc_const_eval` remains active at 99% CPU after 6m54s, RSS stable near 827 MiB, and OOM counters zero; its `.rlib` is pending. No package build failure or final Jarvis artifact has appeared.

At 2026-10-27 03:00 UTC, Gentoo reached 351/480 incremental Ninja actions (73.1%), approximately 2,344/2,473 cumulative actions (94.8%). Guix `rustc_const_eval` remains CPU-active at 99% after 7m40s, RSS about 831 MiB, and OOM counters zero; no `.rlib` yet. Both builds are live with no reported failure.

At 2026-10-27 03:02 UTC, Gentoo reached 366/480 incremental Ninja actions (76.3%), approximately 2,359/2,473 cumulative actions (95.4%). Guix `rustc_const_eval` remains active at 99% CPU after 9m18s; RSS is about 665 MiB, no dependency output changed in the last minute, and cgroup OOM counters remain zero. Its `.rlib` and both package lifecycle results are still pending.

At 2026-10-27 03:03 UTC, Gentoo reached 379/480 incremental Ninja actions (79.0%), approximately 2,372/2,473 cumulative actions (95.9%). Guix `rustc_const_eval` remains active at 99% CPU after 10m43s; two dependency files changed during the latest minute and cgroup OOM counters remain zero. The final Rust archive and Gentoo/Guix Jarvis package lifecycle runs are pending.

At 2026-10-27 03:05 UTC, Gentoo reached 395/480 incremental Ninja actions (82.3%), approximately 2,388/2,473 cumulative actions (96.6%). Guix `rustc_const_eval` remains CPU-active at 99% after 12m24s; two dependency files changed in the latest minute and OOM counters remain zero. The Rust `.rlib` and native package lifecycle outputs are still pending.

At 2026-10-27 03:06 UTC, Gentoo reached 408/480 incremental Ninja actions (85.0%), approximately 2,401/2,473 cumulative actions (97.1%). Guix `rustc_const_eval` remains active at 99% CPU after 13m45s; three build files changed during the last minute and OOM counters remain zero. No final package artifacts or build exit markers exist.

At 2026-10-27 03:08 UTC, Gentoo reached 421/480 incremental Ninja actions (87.7%), approximately 2,414/2,473 cumulative actions (97.6%). Guix `rustc_const_eval` remains CPU-active at 99% after 15m22s; two dependency files changed in the latest minute, no `.rlib` exists yet, and cgroup OOM counters remain zero.

At 2026-10-27 03:09 UTC, Gentoo reached 429/480 incremental Ninja actions (89.4%), approximately 2,422/2,473 cumulative actions (97.9%), currently compiling Node crypto objects. Guix `rustc_const_eval` remains active at 99% CPU after 16m06s; three dependency files changed in the last minute and OOM counters remain zero. Neither final Jarvis package exists yet.

At 2026-10-27 03:10 UTC, Gentoo reached 438/480 incremental Ninja actions (91.3%), approximately 2,431/2,473 cumulative actions (98.3%). Guix `rustc_const_eval` remains active at 99% CPU after 17m44s; codegen-unit objects were emitted continuously through 03:10:37, the latest object is still being written, and OOM counters remain zero. Its final `.rlib` and both Jarvis package lifecycles remain pending.

At 2026-10-27 03:11 UTC, Gentoo reached 441/480 incremental Ninja actions (91.9%), approximately 2,434/2,473 cumulative actions (98.4%). Guix completed `rustc_const_eval` and emitted its 13,412,376-byte `.rlib`, then advanced to `rustc_sanitizers`; the new compiler process is active and OOM counters remain zero. The remaining Guix bootstrap and native package lifecycle are pending.

At 2026-10-27 03:13 UTC, the Gentoo Node.js `node` target completed successfully (480/480, exit 0; 117 MiB binary). The subsequent full ebuild compile initially failed because manual Ninja had left `out/Release/obj/deps/googletest/src` and sibling object directories owned by root (0755), so Portage's `portage` user could not create test objects. Confirmed with `runuser -u portage` writeability checks. Changed ownership of the temporary `out/Release` build tree to `portage:portage`; this is confined to the retained Portage work directory. At 03:21 UTC, the retried ebuild compile is active in the default 56-action graph at 32/56, compiling cctest objects, with no repeat of the permission error so far. Guix emitted `rustc_const_eval` and `rustc_sanitizers` archives and is compiling `rustc_hir_analysis`; its compiler is CPU-active with OOM counters zero. Package lifecycle validations remain incomplete.

At 2026-10-27 03:24 UTC, the Gentoo Node.js ebuild completed `compile install package qmerge` with exit 0. Portage created `/var/cache/binpkgs/net-libs/nodejs/nodejs-26.12.0-1.gpkg.tar` (37,795,840 bytes), merged `net-libs/nodejs-26.12.0`, and runtime checks returned Node v26.12.0 and npm 11.20.0. At 03:29 UTC, a fresh `scripts/build-package.sh --target gentoo --arch aarch64 --output /out` run from the current `/src` worktree has generated a new source archive/overlay, resolved dependencies, and is compiling Jarvis with Cargo (18/548 units; 324 crates downloaded). Guix advanced from `rustc_hir_analysis` to `rustc_ast_lowering`; the compiler remains active and OOM counters are zero. The current-worktree Gentoo Jarvis binpkg and Guix package remain pending.

At 2026-10-27 03:33 UTC, the current-worktree Gentoo package build reached 84/548 Cargo units (15.3%) after downloading dependencies, with no Rust errors reported. Guix is still compiling `rustc_ast_lowering` at 99% CPU, with five dependency files updated in the latest minute and OOM counters zero. The Node.js dependency lifecycle is complete; Jarvis package creation and Guix AArch64 lifecycle remain in progress.

At 2026-10-27 03:34 UTC, the current Gentoo Jarvis Cargo build reached 114/548 units (20.8%), without reported errors. Guix completed `rustc_ast_lowering` and advanced to `rustc_traits`; the Rust compiler remains active and cgroup OOM counters are zero. The Gentoo Jarvis binpkg and Guix package are still pending.

At 2026-10-27 03:37 UTC, the current Gentoo Jarvis Cargo build reached 173/548 units (31.6%), with no error output. Guix remains in `rustc_traits` at 99.6% CPU after 3m01s; six dependency files changed in the latest minute and OOM counters remain zero. Both final package artifacts are pending.

At 2026-10-27 03:40 UTC, the current Gentoo Jarvis Cargo build reached 207/548 units (37.8%), with no Rust error output. Guix advanced to `rustc_borrowck`, active at 99.5% CPU after 1m12s; one dependency file changed in the latest minute and OOM counters remain zero. Both package artifacts remain pending.

At 2026-10-27 03:43 UTC, the current Gentoo Jarvis Cargo build reached 265/548 units (48.4%), without error output. Guix `rustc_borrowck` remains active at 99.5% CPU after 4m23s with RSS about 1.07 GiB; no dependency file changed in the latest two-minute window, but the process remains live and OOM counters are zero. Final package outputs remain pending.

At 2026-10-27 03:45 UTC, the current Gentoo Jarvis Cargo build reached 290/548 units (52.9%); recent `.rmeta` and codegen objects are being written, with no errors reported. Guix `rustc_borrowck` remains active at 99.5% CPU after 6m08s, RSS about 1.08 GiB, with no dependency files updated in the latest minute and OOM counters zero. Both final package artifacts remain pending.

At 2026-10-27 03:47 UTC, Gentoo's current-worktree Cargo build reached 311/548 units (56.8%), with no errors reported. Guix `rustc_borrowck` remains active at 99.5% CPU after 8m05s, RSS about 1.11 GiB; no dependency outputs changed in the latest minute, and OOM counters remain zero. Final Gentoo/Guix Jarvis artifacts are pending.

At 2026-10-27 03:50 UTC, the Gentoo Jarvis build reached 351/548 Cargo units (64.1%), emitting current-worktree Tauri dependency artifacts without errors. Guix `rustc_borrowck` remains active at 99.6% CPU after 10m50s, RSS about 989 MiB; two dependency files changed in the last minute and OOM counters remain zero. Both packages are still pending.

At 2026-10-27 03:53 UTC, Gentoo's current-worktree Jarvis build reached 363/548 Cargo units (66.2%), compiling GTK/Tauri Rust dependencies, with no errors reported. Guix `rustc_borrowck` remains active at 99.6% CPU after 13m50s; codegen-unit objects continue to be emitted (latest observed 1.33 MB) and OOM counters remain zero. Package lifecycle gates remain incomplete.

At 2026-10-27 03:54 UTC, Gentoo reached 370/548 Cargo units (67.5%) and is still compiling the GTK dependency, with no errors reported. Guix `rustc_borrowck` remains active at 99.6% CPU after 15m14s; codegen-unit objects continue to be written and OOM counters remain zero. The current Gentoo Jarvis binpkg and Guix package remain pending.

At 2026-10-27 03:56 UTC, Gentoo's current-worktree Cargo build reached 374/548 units (68.2%), compiling GTK and its Rust dependencies without errors. Guix `rustc_borrowck` remains active at 99.6% CPU after 17m00s; codegen-unit objects continue to appear and OOM counters remain zero. Both final package artifacts are pending.

At 2026-10-27 03:56 UTC, Gentoo advanced to 377/548 Cargo units (68.8%), with the log still compiling GTK dependencies and no errors. Guix `rustc_borrowck` remains active at 99.6% CPU after 17m21s; new codegen-unit objects have appeared through 03:56:30, one is currently being written, and OOM counters remain zero. Both final package outputs are pending.

At 2026-10-27 03:58 UTC, Gentoo's current-worktree Cargo build reached 398/548 units (72.6%) with no errors reported. Guix completed `rustc_borrowck` and emitted `librustc_borrowck-85d715fac32d954e.rlib` (24,071,810 bytes), then advanced to `rustc_passes`; the compiler remains active and OOM counters are zero. Package lifecycle outputs remain pending.

At 2026-10-27 04:01 UTC, Gentoo's current-worktree Cargo build reached 423/548 units (77.2%), compiling GTK/WebKit dependencies without errors; the compiler processes are live and the filesystem has 14 GiB available. Guix remains active in `rustc_passes`, with four dependency outputs updated in the latest two minutes and OOM counters zero. Neither final package artifact nor ARM64 lifecycle result is available yet.

At 2026-10-27 04:02 UTC, Gentoo advanced to 440/548 units (80.3%), with live Cargo/rustc processes and no reported errors. Guix's single-job Rust bootstrap remains in the `rustc_passes` stage; eight dependency outputs were updated in the latest two minutes and OOM counters remain zero. Both final package outputs are still pending.

At 2026-10-27 04:03 UTC, Gentoo reached 450/548 units (82.1%) and started compiling `webkit2gtk`; Cargo/rustc are live and no errors are reported. Guix remains active in `rustc_passes`, with eleven dependency outputs updated in the latest two minutes and OOM counters zero. Package artifacts and lifecycle checks are still pending.

At 2026-10-27 04:04 UTC, Gentoo reached 451/548 units and is compiling `webkit2gtk`/Brotli; two `rustc` processes remain CPU-active (about 99% each), with no error or final output yet. Guix's `rustc_passes` compile remains CPU-active, with two outputs updated in the latest two minutes and OOM counters zero. Both ARM64 package lifecycle gates remain open.

At 2026-10-27 04:05 UTC, Gentoo advanced to 457/548 units (83.4%); `webkit2gtk` and Brotli `.rlib` outputs were produced, and the build continues without reported errors. Guix remains live in the Rust compiler bootstrap through `rustc_hir_typeck`, with three dependency files updated in the latest two minutes and OOM counters zero. Neither package lifecycle has started because the final ARM64 packages are not yet available.

At 2026-10-27 04:07 UTC, Gentoo reached 463/548 units (84.5%), compiling `syn` and `serde_with` dependencies; live `rustc` processes and no errors are reported. Guix's Rust bootstrap remains active in `rustc_hir_typeck`, with one dependency output updated in the latest two minutes and OOM counters zero. The two ARM64 package artifacts and lifecycle checks remain pending.

At 2026-10-27 04:07 UTC, Gentoo advanced to 468/548 units (85.4%) and remains in the GTK/WebKit dependency graph; active `rustc` processes have no reported errors. Guix's `rustc_hir_typeck` compiler remains CPU-active at 99.5% (RSS about 1.17 GiB), though it emitted no new dependency file during this two-minute sample; OOM counters remain zero. Neither final package artifact exists yet.

At 2026-10-27 04:08 UTC, Gentoo reached 475/548 units (86.7%), compiling the remaining GTK/WebKit dependencies without reported errors. Guix's `rustc_hir_typeck` process remains active at 99.5% CPU after 4m43s (RSS about 1.17 GiB); no dependency output appeared in the latest two-minute window, but the process is live and OOM counters remain zero. Final package outputs remain pending.

At 2026-10-27 04:09 UTC, Gentoo advanced to 481/548 units (87.8%) and is compiling `tauri-utils`/ICO dependencies without errors. Guix's `rustc_hir_typeck` remains CPU-active at 99.5% after 5m28s (RSS about 1.17 GiB), with no recent output file and zero OOM events. The build process remains live; package artifacts are still pending.

At 2026-10-27 04:10 UTC, Gentoo reached 485/548 units (88.5%) and continues through `tauri-utils`/`sha2`, with no errors reported. Guix's `rustc_hir_typeck` remains active at 99.5% CPU after 6m14s (RSS about 1.17 GiB), with no dependency output in the latest two-minute sample and OOM counters zero. Final package outputs remain unavailable.

At 2026-10-27 04:10 UTC, Gentoo advanced to 486/548 units; `async-io` and `zvariant_utils` artifacts were emitted, with two `rustc` processes CPU-active and no errors. Guix's `rustc_hir_typeck` remains active at 99.5% CPU after 6m59s, RSS about 1.17 GiB; no new output appeared in the last two minutes and OOM counters remain zero. Neither package output is ready.

At 2026-10-27 04:11 UTC, Gentoo remained at 486/548 Cargo units while emitting `tauri_utils` and `zvariant_utils` codegen objects; both Rust compilers remain CPU-active, with no errors. Guix's `rustc_hir_typeck` remains active at 99.7% CPU after 7m50s (RSS about 973 MiB), and OOM counters remain zero. Both package artifacts and lifecycle checks remain pending.

At 2026-10-27 04:12 UTC, Gentoo advanced to 487/548 units, compiling the Tauri D-Bus dependency, with no errors reported. Guix's `rustc_hir_typeck` remains active at 99.6% CPU after 8m35s (RSS about 1.03 GiB); one dependency output appeared in the latest two minutes and OOM counters remain zero. Package artifacts and lifecycle gates are still pending.

At 2026-10-27 04:13 UTC, Gentoo remained at 487/548 Cargo units while codegen objects for `dbus` and `tauri_utils` continued to be written; two `rustc` processes are CPU-active and no errors are reported. Guix's `rustc_hir_typeck` is CPU-active at 99.6% after 9m39s (RSS about 1.14 GiB), with two outputs updated in three minutes and OOM counters zero. Both builds remain live and their package lifecycle checks are pending.

At 2026-10-27 04:14 UTC, Gentoo reached 489/548 units and continues compiling the Tauri D-Bus dependencies, with no errors reported. Guix's `rustc_hir_typeck` remains active at 99.6% after 10m37s (RSS about 1.04 GiB); four dependency outputs appeared in the latest three minutes and OOM counters remain zero. Both package artifacts remain pending.

At 2026-10-27 04:15 UTC, Gentoo advanced to 507/548 units (92.5%) and started compiling `tao`; the 548-unit Cargo build remains error-free and the package output directory is still empty. Guix's `rustc_hir_typeck` remains CPU-active after 11m27s (RSS about 1.03 GiB), with five dependency outputs updated in three minutes and OOM counters zero. Package lifecycle checks remain pending.

At 2026-10-27 04:16 UTC, Gentoo reached 508/548 units (92.7%) and is compiling `tao`/`tauri-codegen`, with no errors and no final artifact yet. Guix's `rustc_hir_typeck` remains CPU-active after 12m18s (RSS about 1.03 GiB), with seven outputs updated in the latest three minutes; OOM counters remain zero. Package lifecycle tests are still pending.

At 2026-10-27 04:17 UTC, Gentoo advanced to 515/548 units (94.0%), compiling the `wry` Tauri runtime and its dependencies without reported errors. Guix's `rustc_hir_typeck` remains active at 99.6% CPU after 13m09s (RSS about 1.03 GiB), with six outputs updated in three minutes and zero OOM events. Final package outputs are not yet available.

At 2026-10-27 04:17 UTC, Gentoo reached 522/548 units (95.3%), compiling Tauri serialization dependencies after `wry`; no errors are reported and `/out` is still empty. Guix's `rustc_hir_typeck` remains CPU-active at 99.6% after 13m59s (RSS about 1.02 GiB), with six outputs updated in the latest three minutes and OOM counters zero. Final package artifacts and lifecycle checks remain pending.

At 2026-10-27 04:18 UTC, Gentoo advanced to 525/548 units (95.8%), compiling `muda` and Tokio; no errors are reported and no package artifact exists yet. Guix's `rustc_hir_typeck` remains CPU-active after 14m48s (RSS about 1.04 GiB), with seven outputs updated in three minutes and OOM counters zero. Both package lifecycle gates remain open.

At 2026-10-27 04:19 UTC, Gentoo reached 526/548 units (95.9%) and started `async-process`; no errors are reported and `/out` remains empty. Guix's `rustc_hir_typeck` remains active at 99.6% CPU after 15m43s (RSS about 1.04 GiB), with seven recent outputs and no OOM events. Final packages remain pending.

At 2026-10-27 04:20 UTC, Gentoo advanced to 530/548 units (96.7%), compiling `tauri-macros` and Tauri runtime dependencies without errors; `/out` remains empty. Guix's compiler process remains live through a rustc phase transition and OOM counters remain zero; two dependency outputs were updated in the latest three minutes. Both final package artifacts remain pending.

At 2026-10-27 04:20 UTC, Gentoo reached 534/548 units (97.4%), compiling async executor/broadcast dependencies, with no reported errors or package output yet. Guix advanced into `rustc_codegen_llvm`; the bootstrap remains active, three dependency outputs were updated in five minutes, and OOM counters remain zero. Both package lifecycle gates remain open.

At 2026-10-27 04:21 UTC, Gentoo reached 542/548 units (98.9%), compiling the final `zbus`/Tauri crates without reported errors; no binpkg has appeared yet. Guix remains active in `rustc_codegen_llvm`, with three dependency outputs in five minutes and OOM counters zero. Once Gentoo's package command exits, inspect its status and artifact before running lifecycle validation.

At 2026-10-27 04:22 UTC, Gentoo remains at 542/548 while code-generating the final `tauri` and `zbus` crates; `.rmeta` files and Tauri codegen objects are being emitted, and two Rust compilers are CPU-active with no errors. Guix's bootstrap is active in `rustc_codegen_llvm` with three recent outputs and zero OOM events. No final package artifacts are available yet.

At 2026-10-27 04:23 UTC, Gentoo remains at 542/548; more Tauri codegen-unit objects were emitted through 04:23:47 while both Rust compiler processes stayed above 98% CPU. Guix remains active in `rustc_codegen_llvm`, with one output in the latest three minutes and OOM counters zero. The package output directory is still empty; both builds are live without reported errors.

At 2026-10-27 04:24 UTC, Gentoo reached 546/548 units (99.6%), completed the main `jarvis-overlay` crate and is compiling the final Tauri single-instance plugin; no errors or package artifact yet. Guix remains active in `rustc_codegen_llvm`, with three dependency outputs in the latest three minutes and OOM counters zero. Gentoo's final package and its lifecycle validation remain pending.

At 2026-10-27 04:25 UTC, Gentoo remains at 546/548 while the final `zbus` crate emits codegen objects; its rustc process is live and no compiler error is reported. Guix remains active in `rustc_codegen_llvm`, with five outputs in the latest three minutes and OOM counters zero. No Gentoo binpkg has been produced yet.

At 2026-10-27 04:26 UTC, Gentoo reached 547/548; Cargo completed the final dependency units and is compiling the `jarvis-overlay` binary. No error or binpkg is reported yet. Guix remains active in `rustc_codegen_llvm`, with eight outputs in three minutes and zero OOM events. The Gentoo package command and both ARM64 lifecycle checks remain pending.

At 2026-10-27 04:26 UTC, Gentoo remains at 547/548 while rustc compiles the main `jarvis-overlay` binary (process live at 158% CPU, RSS about 1.3 GiB); the D-Bus library archive has been produced and no errors are reported. Guix's `rustc_codegen_llvm` stage remains active with eleven recent dependency outputs and zero OOM events. `/out` is still empty.

At 2026-10-27 04:27 UTC, Gentoo remains at 547/548; the main binary rustc process is live at about 177% CPU with RSS about 1.1 GiB, though no new release file appeared in the last two minutes. Guix remains active in `rustc_codegen_llvm`, with twelve recent outputs and OOM counters zero. No compiler failure or package output is present.

At 2026-10-27 04:29 UTC, Gentoo remains at 547/548 and has entered `jarvis-overlay` code generation; four large `.rcgu.o` files were written (up to about 2.5 MB), with rustc active at about 185% CPU. Guix remains active in `rustc_mir_transform`, with three recent outputs and OOM counters zero. Neither package output is ready.

At 2026-10-27 04:30 UTC, Gentoo's main binary remains in codegen at 547/548; additional `.rcgu.o` files up to about 1.2 MB were emitted during the last minute, with no errors. Guix's `rustc_mir_transform` remains CPU-active at 99.5% (RSS about 947 MiB), with three recent outputs and OOM counters zero. The final package outputs are still pending.

At 2026-10-27 04:31 UTC, Gentoo remains at 547/548 and continues main-binary codegen; new `.rcgu.o` files were emitted through 04:31:08, with rustc active at about 187% CPU and no reported errors. Guix remains CPU-active in `rustc_mir_transform`, with two outputs in the latest three minutes and OOM counters zero. No final package artifact exists yet.

At 2026-10-27 04:32 UTC, the Gentoo AArch64 `jarvis-overlay` executable was produced: ELF64 PIE for ARM aarch64, 13,681,832 bytes. Cargo still reports 547/548 while the Portage compile phase completes; npm audit reported zero vulnerabilities, but `/out` contains no binpkg yet. Guix remains active in `rustc_mir_transform` with no OOM events.

At 2026-10-27 04:32 UTC, Portage moved beyond Cargo and is now running `scripts/fetch-opencode.py --target aarch64-glibc`; this is the active stage after producing the AArch64 executable. The Gentoo package output directory remains empty until fetch/install/package stages finish. Guix's Rust bootstrap remains active and OOM counters are zero.

At 2026-10-27 04:34 UTC, the Gentoo build fetched and verified OpenCode 1.18.23 for aarch64-glibc, completed the compile phase, and entered `src_install` running `prepare-package.py`; Portage's container emitted an `unshare: EPERM` sandbox warning but continued into install. `/out` remains empty until the package phase. Guix advanced to `rustc_mir_transform` and remains OOM-free.

At 2026-10-27 04:34 UTC, Gentoo's image tree contains the 13.7 MB ARM64 `jarvis-overlay` executable and packaged application files; `prepare-package.py` is resolving/downloading Python voice-runtime wheels for aarch64. The package artifact is still pending. Guix remains in `rustc_mir_transform` with OOM counters zero.

At 2026-10-27 04:35 UTC, Gentoo's `prepare-package.py` is still running pip for voice/MCP dependencies; the staging image is about 258 MB and pip is downloading the 34.1 MB Piper TTS AArch64 wheel. The process is live, `/out` remains empty, and Guix is still compiling with OOM counters zero.

At 2026-10-27 04:38 UTC, Gentoo's Python runtime install progressed beyond the Piper wheel and is fetching the `faster-whisper` and AArch64 PyAV wheels; pip remains live and `/out` is still empty. Guix remains active in `rustc_mir_transform`, with eight outputs in the latest five-minute window and OOM counters zero.

At 2026-10-27 04:38 UTC, the Gentoo pip process is actively transferring/unpacking ARM64 voice wheels: Piper's 34.1 MB wheel is present in the temporary unpack directory and the PyAV wheel had reached 13.6 MB of 33.6 MB. The staging image remains about 258 MB; final `.gpkg.tar` output is still pending. Guix continues without OOM.

At 2026-10-27 04:40 UTC, Gentoo completed the 33.6 MB PyAV and 34.1 MB Piper wheel downloads and moved to the 18.9 MB AArch64 CTranslate2 wheel, alongside MCP/HTTP dependencies. The image is still staging and `/out` remains empty. Guix advanced to `rustc_resolve`; its bootstrap remains active without OOM.

At 2026-10-27 04:42 UTC, Gentoo downloaded the complete PyAV, Piper, and 18.9 MB CTranslate2 AArch64 wheels; pip is now fetching the 21.4 MB ONNX Runtime AArch64 wheel (about 4 MB present at the latest poll). The staging image remains around 258 MB and no binpkg is available. Guix is still compiling with OOM counters zero.

At 2026-10-27 04:43 UTC, the ONNX Runtime AArch64 wheel had reached 20.9 MB of 21.4 MB; PyAV, Piper and CTranslate2 downloads are complete. Pip remains active installing the private Python runtime, the staging image is about 258 MB, and `/out` has no binpkg yet. Guix remains active in `rustc_resolve` with OOM counters zero.

At 2026-10-27 04:44 UTC, pip completed the 21.4 MB ONNX Runtime wheel and moved on to the 15.7 MB NumPy AArch64 wheel, after downloading the remaining Faster-Whisper dependencies. Gentoo image preparation is active, `/out` remains empty, and Guix remains active in `rustc_resolve` without OOM.

At 2026-10-27 04:45 UTC, the Gentoo pip process had downloaded 11.0 MB of the 15.7 MB NumPy AArch64 wheel; prior major AArch64 wheels are complete. Package staging remains active and `/out` remains empty. Guix's `rustc_resolve` compile is active, with four recent outputs and OOM counters zero.

At 2026-10-27 04:46 UTC, Gentoo completed the 15.7 MB NumPy wheel and proceeded through Pydantic/core and cryptography AArch64 wheels; pip continues staging Python dependencies and `/out` remains empty. Guix's `rustc_resolve` stage remains active with eight outputs in the last three minutes and OOM counters zero.

At 2026-10-27 04:51 UTC, the Gentoo AArch64 binpkg build exited 0 and produced a 209,950,720-byte GPKG (SHA-256 `27ddec294ac0e43bb57cd9939a58a5ae5307b2ead47e2e3f5441e7b6fd3bb6fe`). Portage installed it successfully; `jarvis --doctor`, OpenCode 1.18.23, private runtime imports, Python ABI 3.14 and ELF AArch64 checks passed. `emerge --unmerge` removed the package and left the user data sentinel intact. This QEMU container smoke does not validate native ARM hardware, GUI or physical audio. Guix's Rust bootstrap remains active in `rustc_builtin_macros`, with eight outputs in the last three minutes and OOM counters zero.

At 2026-10-27 04:52 UTC, the Gentoo results were reconciled in the matrix (170 passed, one unverified, one partial; 172 total), and the artifact SHA-256 was rechecked. Guix remains CPU-active in `rustc_builtin_macros`; five codegen objects were written through 04:52:29 and OOM counters remain zero.

At 2026-10-27 04:53 UTC, Guix remains in `rustc_builtin_macros` codegen; six additional codegen-unit objects were written from 04:52:39 through 04:53:14. The compiler is active at 99.7% CPU, and cgroup OOM counters remain zero. The Gentoo lifecycle is complete under QEMU; Guix remains the only unverified package combination.

At 2026-10-27 04:54 UTC, Guix completed `rustc_builtin_macros`, emitted `librustc_builtin_macros-524d1a364f2d7a75.rlib` (8,228,720 bytes), and advanced to `rustc_query_impl`. The next compiler process is active, and OOM counters remain zero.

At 2026-10-27 04:55 UTC, Guix remains in `rustc_query_impl`; `full.rmeta` (6,749,485 bytes) was emitted while rustc stayed active at 99.6% CPU (RSS about 980 MiB). OOM counters remain zero.

At 2026-10-27 04:56 UTC, Guix's `rustc_query_impl` emitted its `rmeta` (8,007,878 bytes) and remains in codegen. The compiler is still live at 99.6% CPU (RSS about 1.18 GiB); no dependency artifact changed in the latest two-minute sample, and OOM counters remain zero. Approximately 13 GiB remain on the host filesystem.

At 2026-10-27 04:58 UTC, Guix's `rustc_query_impl` remains CPU-active at 99.6% after about four minutes in codegen (RSS about 1.28 GiB). No new dep file has appeared since `full.rmeta`; the process remains live and cgroup OOM counters are zero.

At 2026-10-27 04:58 UTC, inspection of the live rustc thread list identified an active `opt cgu.13` codegen worker inside `rustc_query_impl`, confirming it is optimizing a codegen unit rather than waiting on I/O. The `rmeta` remains the latest completed artifact; OOM counters remain zero.

At 2026-10-27 04:59 UTC, the active rustc optimization worker advanced from codegen unit `cgu.13` to `cgu.03`; `rustc_query_impl` is still CPU-bound at 99.6% and emits no completed `.rlib` yet. This thread change confirms ongoing compiler progress. OOM counters remain zero.

At 2026-10-27 05:00 UTC, the active rustc optimization worker moved on to `cgu.04` in `rustc_query_impl`; the process remains at 99.6% CPU (RSS about 1.30 GiB), with no completed archive yet and OOM counters zero.

At 2026-10-27 05:01 UTC, the rustc codegen worker advanced from `cgu.04` to `cgu.10` within `rustc_query_impl`; the compiler remains at 99.6% CPU (RSS about 1.30 GiB). No `.rlib` has appeared yet and OOM counters remain zero.

At 2026-10-27 05:01 UTC, the active codegen worker moved from `cgu.10` to `cgu.07`; `rustc_query_impl` remains CPU-bound at 99.6% (RSS about 1.30 GiB), without a final archive yet. OOM counters remain zero.

At 2026-10-27 05:02 UTC, Guix rustc transitioned from per-CGU optimization into `lto cgu.00` for `rustc_query_impl`; the process remains CPU-active at 99.7%, OOM counters zero. This is the link-time optimization stage before the crate archive is emitted.

At 2026-10-27 05:03 UTC, `rustc_query_impl` remains in `lto cgu.00`; its corresponding `.rcgu.o` file has appeared and is being written (currently zero bytes). The rustc process remains CPU-active, with OOM counters zero.

At 2026-10-27 05:04 UTC, Guix LTO emitted `rustc_query_impl` CGU objects: `cgu.00` reached 2,716,456 bytes and `cgu.02` reached 1,038,784 bytes; the live worker advanced to `lto cgu.03`. Rustc remains at 99.7% CPU and OOM counters remain zero.

At 2026-10-27 05:05 UTC, LTO wrote the `rustc_query_impl` `cgu.03` object (2,789,968 bytes) and advanced its active worker to `cgu.05`; rustc remains CPU-active at 99.7%, with OOM counters zero.

At 2026-10-27 05:06 UTC, LTO emitted additional `rustc_query_impl` objects (`cgu.05` 1,834,008 bytes, `cgu.01` 2,243,544 bytes, `cgu.07` 994,440 bytes) and advanced to `cgu.14`. Rustc remains active at 99.7% CPU with zero OOM events.

At 2026-10-27 05:07 UTC, LTO emitted `cgu.14` (1,605,640 bytes) and `cgu.08` (1,215,184 bytes), then started `cgu.10`. The `rustc_query_impl` compiler remains active at 99.7% CPU and OOM counters remain zero.

At 2026-10-27 05:08 UTC, LTO completed `cgu.10` (1,514,104 bytes) and advanced to `cgu.04`; its output file has started writing. Rustc remains CPU-active at 99.7% and OOM counters remain zero.

At 2026-10-27 05:09 UTC, LTO wrote `cgu.04` (688,408 bytes), `cgu.09` (1,302,536 bytes), and `cgu.15` (851,536 bytes), then started `cgu.06`. The compiler remains at 99.7% CPU with OOM counters zero.

At 2026-10-27 05:10 UTC, LTO completed `cgu.06` (724,016 bytes), `cgu.12` (1,133,672 bytes) and `cgu.13` (1,497,624 bytes), and advanced to `cgu.11`. Rustc remains at 99.7% CPU with OOM counters zero.

At 2026-10-27 05:11 UTC, Guix completed `rustc_query_impl` and emitted `librustc_query_impl-fbb2a8423c63312e.rlib` (34,770,968 bytes); Cargo advanced to `rustc_smir`, which has produced `rmeta` and begun codegen. OOM counters remain zero.

At 2026-10-27 05:12 UTC, `rustc_smir` entered LTO at `cgu.00` after emitting its 3,591,500-byte `rmeta`; the codegen object has begun writing. Rustc remains active and OOM counters are zero.

At 2026-10-27 05:12 UTC, `rustc_smir` LTO emitted seven more codegen objects (`cgu.07`, `.10`, `.11`, `.08`, `.01`, `.04`, `.09`; sizes 231–455 KB) and advanced to `cgu.03`. The process remains CPU-active and OOM counters remain zero.

At 2026-10-27 05:13 UTC, Guix completed `rustc_smir` (7,492,760-byte `.rlib`) and `stable_mir` (13,718-byte `.rlib`), then began `rustc_interface`; its 608,425-byte `rmeta` is present and optimization of `cgu.00` is active. OOM counters remain zero.

At 2026-10-27 05:14 UTC, `rustc_interface` continues through CGU optimization; the live rustc worker advanced to `cgu.04` at 99.6% CPU. Its `rmeta` remains present, and OOM counters remain zero.

At 2026-10-27 05:15 UTC, the `rustc_interface` optimization worker advanced from `cgu.04` to `cgu.10`; rustc remains active at 99.6% CPU, with `rmeta` already produced and OOM counters zero.

At 2026-10-27 05:15 UTC, `rustc_interface` emitted its `cgu.10` object (611,376 bytes) and advanced into LTO `cgu.11`. Rustc remains active, with OOM counters zero.

At 2026-10-27 05:16 UTC, `rustc_interface` LTO emitted five additional CGU objects (`cgu.11`, `.01`, `.04`, `.12`, `.06`; 318–743 KB) and advanced to `cgu.08`. Rustc remains CPU-active and OOM counters remain zero.

At 2026-10-27 05:17 UTC, `rustc_interface` LTO emitted `cgu.08` (443,008 bytes), `.13` (359,488 bytes) and `.05` (459,712 bytes), then started `.03`. The compiler is active at 99.7% CPU with OOM counters zero.

At 2026-10-27 05:18 UTC, `rustc_interface` LTO emitted five more objects (`cgu.03`, `.09`, `.00`, `.07`, `.15`; 341–433 KB) and advanced to `.02`. Rustc remains CPU-active at 99.7% with OOM counters zero.

At 2026-10-27 05:19 UTC, Guix completed `rustc_interface` and emitted `librustc_interface-aa446b3e994f6366.rlib` (8,608,142 bytes), then advanced to `ctrlc`, `rustc_log`, and `jiff` dependencies. OOM counters remain zero.

At 2026-10-27 05:20 UTC, Guix completed `ctrlc` and `rustc_log` dependencies; `jiff` produced a 7,870,589-byte `rmeta` and is compiling, with rustc active at 99.6% CPU. OOM counters remain zero.

At 2026-10-27 05:20 UTC, `jiff` entered LTO and emitted seven codegen objects before `cgu.02`; rustc remains active at 99.8% CPU, OOM counters zero.

At 2026-10-27 05:21 UTC, Guix completed `jiff` (9,756,920-byte `.rlib`) and advanced to `rustc_driver_impl`, which has produced a 674,488-byte `rmeta` and is compiling. OOM counters remain zero.

At 2026-10-27 05:22 UTC, `rustc_driver_impl` remains in codegen; its optimization worker reached `cgu.10`, rustc is active at 99.6% CPU, and OOM counters remain zero.

At 2026-10-27 05:23 UTC, `rustc_driver_impl` LTO emitted `cgu.02` (546,480 bytes) and `cgu.05` (896,184 bytes), advancing its worker to `cgu.11`. Rustc remains CPU-active at 99.7% with OOM counters zero.

At 2026-10-27 05:24 UTC, `rustc_driver_impl` LTO emitted five more objects (`cgu.11`, `.13`, `.14`, `.15`, `.12`; 199–624 KB) and advanced to `cgu.00`. Rustc remains at 99.7% CPU; OOM counters remain zero.

At 2026-10-27 05:25 UTC, the Guix Rust 1.89 bootstrap completed the optimized compiler build (`Finished release profile [optimized]`) and created the stage1 sysroot. It is now building `wasm-component-ld` and compiling serde for that host tool; the build remains live, with cgroup OOM counters at zero.

At 2026-10-27 05:26 UTC, the active Guix bootstrap moved from `serde` to the `wasm-component-ld` dependency graph (`bitflags`, `foldhash`, `hashbrown`, `quote`, and `libc`); new AArch64 dependency archives were emitted in the last minute. The build is live and cgroup OOM counters remain zero.

At 2026-10-27 05:27 UTC, Guix's `wasm-component-ld` dependency graph advanced through `wasmparser`, `indexmap`, and a complete `syn` AArch64 archive; `semver` is now compiling. The Rust process remains CPU-active and cgroup OOM counters remain zero.

At 2026-10-27 05:28 UTC, `semver` and `memchr` completed in the active Guix build; `wasmparser` is in optimized codegen and has emitted its metadata. Rustc remains CPU-active, with OOM counters zero.

At 2026-10-27 05:29 UTC, `wasmparser` metadata grew to about 9.9 MB during AArch64 optimized compilation; no archive has been emitted yet. The compiler is still live at 99.6% CPU, and cgroup OOM counters remain zero.

At 2026-10-27 05:30 UTC, `wasmparser` progressed from metadata generation into codegen and emitted its first AArch64 CGU object (about 594 KB). The compiler remains CPU-active; OOM counters remain zero.

At 2026-10-27 05:31 UTC, `wasmparser` LTO continued producing AArch64 codegen objects across CGUs 00, 01, 07, 02, 03, 12, 06, 08, and 05; CGU 14 has started. The rustc process is CPU-active, and OOM counters remain zero.

At 2026-10-27 05:32 UTC, Guix completed both `wasmparser` dependency variants (15,298,156-byte and 4,405,100-byte `.rlib` archives) and moved on to `wasm-encoder` plus `serde_json` for `wasm-component-ld`. The build remains live with zero OOM events.

At 2026-10-27 05:33 UTC, the Guix bootstrap advanced past `wasm-encoder` into terminal/output dependencies (`anstyle`, `getrandom`, `rustix`, `ryu`, and `anstream`); `serde_json` metadata is present and its optimized compilation is underway. OOM counters remain zero.

At 2026-10-27 05:34 UTC, `serde_json` completed and the bootstrap advanced into optimized codegen for `wasm-encoder`; its first two AArch64 CGU objects have been emitted. The process remains live, and OOM counters remain zero.

At 2026-10-27 05:35 UTC, both `wasm-encoder` variants completed and emitted AArch64 archives (4.4 MB and 3.3 MB); Guix moved to the `errno` dependency. The bootstrap remains active and OOM counters remain zero.

At 2026-10-27 05:36 UTC, the Guix bootstrap compiled `errno`, `serde_derive`, `unicode-width`, `log`, `strsim`, `id-arena`, `linux-raw-sys`, and `unicode-xid`; the latest target dependency archives were emitted successfully. The build is live and OOM counters remain zero.

At 2026-10-27 05:37 UTC, Guix moved through `heck`, `cfg-if`, and `bumpalo`, then began compiling `clap_builder` for the bootstrap tool; its metadata has been emitted. Rustc remains CPU-active, and OOM counters remain zero.

At 2026-10-27 05:38 UTC, `clap_builder` is in LTO and has emitted multiple AArch64 CGU objects (`cgu.11`, `.04`, `.03`, `.09`, `.10`, `.14`, `.12`, `.13`, `.08`, `.05`). Rustc remains CPU-active, and OOM counters remain zero.

At 2026-10-27 05:39 UTC, `clap_builder` completed its AArch64 archive (4,112,720 bytes); Guix advanced into `wast` 235.0.0, whose metadata has reached about 12.8 MB during compilation. Rustc remains CPU-active with zero OOM events.

At 2026-10-27 05:40 UTC, `wast` metadata generation completed and the crate moved into optimized codegen/LTO; its first CGU object has started writing. A live `opt cgu.06` worker was observed earlier, followed by the LTO object. OOM counters remain zero.

At 2026-10-27 05:41 UTC, `wast` LTO has emitted seven AArch64 CGU objects (`cgu.00`, `.01`, `.08`, `.02`, `.11`, `.04`, `.13`) since its first object; rustc remains active and cgroup OOM counters remain zero.

At 2026-10-27 05:42 UTC, `wast` completed with a 17,341,880-byte AArch64 `.rlib`; `getrandom` also completed, and the bootstrap moved on to `clap_derive`. No OOM events were recorded.

At 2026-10-27 05:43 UTC, `clap_derive` completed and the Rust bootstrap advanced into `wit-parser` 0.229.0; its metadata has been emitted and optimized compilation is active. OOM counters remain zero.

At 2026-10-27 05:44 UTC, `wit-parser` remains in LTO (`lto cgu.00` worker observed); no new archive has been emitted yet, but rustc is CPU-active and OOM counters remain zero.

At 2026-10-27 05:45 UTC, `wit-parser` LTO began emitting AArch64 CGUs (`cgu.00`, `.12`, `.13`, `.15`, `.07`, `.08`); the compiler remains active and OOM counters are still zero.

At 2026-10-27 05:46 UTC, `wit-parser` LTO emitted eight additional AArch64 CGU objects (`cgu.04`, `.01`, `.03`, `.06`, `.09`, `.14`, `.05`, plus prior CGUs from 05:45). Rustc is CPU-active and cgroup OOM counters remain zero.

At 2026-10-27 05:47 UTC, the bootstrap advanced beyond `wit-parser`, completed AArch64 `rustix` (4,835,520-byte `.rlib), and began `wasm-metadata` codegen; multiple CGU objects are appearing. OOM counters remain zero.

At 2026-10-27 05:48 UTC, Guix proceeded through `wasm-metadata`, `fastrand`, `once_cell`, and `tempfile`, then began `wit-component` 0.229.0; metadata has been emitted and optimized compilation is active. OOM counters remain zero.

At 2026-10-27 05:49 UTC, `wit-component` is still in optimized codegen; a live `opt cgu.08` worker confirms compilation is progressing despite no `.rlib` yet. Memory remains within the container limit and OOM counters remain zero.

At 2026-10-27 05:50 UTC, `wit-component` LTO emitted six additional AArch64 CGU objects (`cgu.01`, `.09`, `.00`, `.10`, `.13`, `.04`). The bootstrap remains CPU-active with OOM counters at zero.

At 2026-10-27 05:50 UTC, `wit-component` LTO emitted another eight CGUs (`cgu.11`, `.06`, `.14`, `.02`, `.15`, `.08`, with prior outputs `.10`, `.13`, `.04`) and started `.05`. Rustc remains CPU-active, OOM counters zero.

At 2026-10-27 05:51 UTC, `wit-component` completed (5,840,638-byte `.rlib`); `wit-parser` (6,175,884 bytes) and `wasm-metadata` (297,888 bytes) are also confirmed complete. Guix moved through `clap`, `wat`, and the WASI adapter provider into `wasm-component-ld` codegen, with several CGU objects emitted. OOM counters remain zero.

At 2026-10-27 05:52 UTC, the stage0 `wasm-component-ld` tool and its wrapper completed successfully (`Finished release profile [optimized]`); bootstrap advanced to building `llvm-bitcode-linker` for AArch64, currently compiling `syn`. OOM counters remain zero.

At 2026-10-27 05:53 UTC, the next Rust bootstrap tool, `llvm-bitcode-linker`, is compiling its logging/terminal dependencies (`tracing-core`, `anstyle`, and `anstream`); AArch64 archives are appearing. Build remains active and OOM-free.

At 2026-10-27 05:54 UTC, `llvm-bitcode-linker` dependencies advanced through `overload`, `heck`, `clap_derive`, and `nu-ansi-term`; the latter has begun AArch64 codegen. Rust build remains live with zero OOM events.

At 2026-10-27 05:55 UTC, the `llvm-bitcode-linker` build completed `nu-ansi-term` and `tracing-log` and is in LTO for `clap_builder` (`lto cgu.00` worker observed). The process is active, with about 13 GiB free on the filesystem and zero cgroup OOM events.

At 2026-10-27 05:56 UTC, `clap_builder` LTO for `llvm-bitcode-linker` emitted ten AArch64 CGU objects and started another; rustc remains CPU-active and cgroup OOM counters are zero.

At 2026-10-27 05:57 UTC, Guix moved beyond `clap_builder` through `sharded-slab`, `thread_local`, `thiserror-impl`, `tracing-attributes`, and `smallvec`; `tracing-subscriber` is now compiling for `llvm-bitcode-linker`. AArch64 outputs continue to appear, with OOM counters zero.

At 2026-10-27 05:58 UTC, the `llvm-bitcode-linker` dependency graph finished (`tracing-subscriber`, `tracing`, `clap`, `anyhow`); the tool crate itself is now compiling for AArch64. OOM counters remain zero.

At 2026-10-27 05:59 UTC, `llvm-bitcode-linker` completed successfully (`Finished release profile [optimized]`, executable produced); Rust bootstrap advanced to stage1 library artifacts for AArch64, beginning with `compiler_builtins` and `core`. OOM counters remain zero.

At 2026-10-27 06:00 UTC, stage1 library compilation is active in `core` after launching the AArch64 compiler-builtins/core builds. The core rustc process has run over a minute at high CPU with about 0.9 GiB RSS; no final core artifact yet and OOM counters remain zero.

At 2026-10-27 06:01 UTC, stage1 `core` emitted 46,907,935 bytes of AArch64 compiler metadata and remains in codegen; rustc is active at about 1.1 GiB RSS, with cgroup OOM counters zero.

At 2026-10-27 06:02 UTC, stage1 `core` completed its AArch64 `.rlib` (48,319,462 bytes); `compiler_builtins` has emitted 2.0 MB metadata and begun codegen across numerous CGUs. Rustc is active and cgroup OOM counters remain zero.

At 2026-10-27 06:02 UTC, stage1 `compiler_builtins` completed (3,731,914-byte AArch64 `.rlib`); Rust advanced through `rustc-std-workspace-core`, `alloc`, and workspace-alloc, and started `libc`. OOM counters remain zero.

At 2026-10-27 06:03 UTC, stage1 completed `alloc` (6,877,100-byte `.rlib`), workspace-alloc, `libc` (3,662,018 bytes), and progressed through `object`, `unwind`, `gimli`, `adler2`, and `memchr`; the `std` crate is now compiling. OOM counters remain zero.

At 2026-10-27 06:04 UTC, the stage1 `std` dependency graph progressed through `miniz_oxide` and `addr2line`; the Rust bootstrap remains active with low memory usage and zero OOM events.

At 2026-10-27 06:05 UTC, stage1 `std` progressed through `panic_unwind`, `std_detect`, and `hashbrown`, and completed `rustc-demangle` and `panic_abort`; `std` itself is still compiling. OOM counters remain zero.

At 2026-10-27 06:06 UTC, stage1 `std` emitted metadata and began AArch64 codegen; CGU 13 produced a 573 KB object and CGU 12 has started. Rustc remains active at about 0.6 GiB RSS, with cgroup OOM counters zero.

At 2026-10-27 06:07 UTC, stage1 `std` LTO emitted nine more AArch64 CGUs (`cgu.08`, `.04`, `.10`, `.11`, `.15`, `.02`, `.05`, `.07`, `.01`) and started `.14`. The compiler remains CPU-active and OOM counters remain zero.

At 2026-10-27 06:08 UTC, stage1 `std` completed (13,016,698-byte AArch64 `.rlib`); bootstrap advanced through workspace-std, `unicode-width`, `getopts`, and `rustc-literal-escaper` into `proc_macro` codegen, with multiple CGUs emitted. OOM counters remain zero.

At 2026-10-27 06:09 UTC, stage1 `proc_macro` completed (2,873,054-byte AArch64 `.rlib`) and Rust advanced into the `test` library, which has metadata and multiple codegen units underway. OOM counters remain zero.

At 2026-10-27 06:10 UTC, stage1 library artifacts completed successfully, including `std` and `test` (4,044,818-byte AArch64 `.rlib`); Rust bootstrap advanced to stage1→stage2 compiler artifacts, starting with proc-macro dependencies. OOM counters remain zero.

At 2026-10-27 06:11 UTC, stage1→stage2 compiler dependency builds progressed through `libc` (5,678,872-byte AArch64 `.rlib`), `cfg-if`, `synstructure`, and into `memchr`; the bootstrap remains live and OOM-free.

At 2026-10-27 06:12 UTC, the stage2 compiler dependency graph progressed through `stable_deref_trait`, `smallvec`, `once_cell`, `equivalent`, `bitflags`, `foldhash`, and `allocator-api2`, and is compiling `hashbrown`. Outputs are being generated and OOM counters remain zero.

At 2026-10-27 06:13 UTC, stage2 dependencies completed `indexmap`, `version_check`, and `getrandom`; `tracing-core` is compiling and has begun codegen. The build remains active with zero OOM events.

At 2026-10-27 06:14 UTC, stage2 dependencies progressed through `tracing-core`, `tracing`, and `generic-array`; `parking_lot` is in codegen, while its dependency `crossbeam-utils` is also compiling. OOM counters remain zero.

At 2026-10-27 06:15 UTC, stage2 compiler dependencies completed both `parking_lot` variants (about 318–321 KB each), plus `rustc-stable-hash`, `rustc-hash`, and `rustc_hashes`; the build progressed to `rustc_macros`, `zerocopy`, and `rustix`. OOM counters remain zero.

At 2026-10-27 06:16 UTC, stage2 dependency compilation advanced through `crypto-common`, `block-buffer`, `tinystr`, `stacker`, `fastrand`, `thin-vec`, and `rustc-hash`; `rustc_serialize` is compiling. AArch64 archives continue to appear and OOM counters remain zero.

At 2026-10-27 06:17 UTC, stage2 dependencies completed `rustc_serialize` (443,778-byte `.rlib`), `crossbeam-deque`, `psm`, `zerocopy` (5,022,806 bytes), and `rustc_macros`; the build is progressing through `tempfile`, `unic-langid-impl`, and `digest`. OOM counters remain zero.

At 2026-10-27 06:18 UTC, stage2 dependency compilation confirmed `digest` and `crossbeam-deque` archives and advanced through `rustc_index_macros`, `arrayvec`, `either`, `unic-langid-macros-impl`, `ppv-lite86`, `rustc_thread_pool`, and into `measureme`. OOM counters remain zero.

At 2026-10-27 06:19 UTC, stage2 compiler dependencies advanced through `measureme`, `ena`, `elsa`, `blake3`, `memmap2`, and `jobserver`; `rustc_graphviz` completed, and `rustc_data_structures` is compiling. The process remains active, with zero OOM events.

At 2026-10-27 06:19 UTC, stage2 dependency builds completed `blake3`, `sha2`, and `sha1`; `rustc_data_structures` continues alongside checksum dependencies. AArch64 archives are appearing, and cgroup OOM counters remain zero.

At 2026-10-27 06:20 UTC, stage2 dependencies completed `md-5`, `derive-where`, and `scoped-tls`; the Rust compiler's `rustc_span` crate is in AArch64 codegen after producing 2.37 MB metadata. OOM counters remain zero.

At 2026-10-27 06:21 UTC, `rustc_span` completed (4,163,854-byte AArch64 `.rlib`); the compiler dependency graph moved on to `zerofrom`, `yoke`, `thiserror` 2.x, and `zerovec` derives. OOM counters remain zero.

At 2026-10-27 06:23 UTC, the stage2 compiler build advanced through `zerovec`, `rand_core`, `crc32fast`, `serde`, `tinystr`, and `writeable`; `rustc_ast_ir` is compiling, alongside ICU locale crates. OOM counters remain zero.

At 2026-10-27 06:24 UTC, `rustc_ast_ir` completed both AArch64 variants, and stage2 dependencies completed `icu_locid` (1,495,620-byte `.rlib`), `serde` (5,927,724 bytes), and `unic-langid-macros`; the build moved into `rand_chacha`. OOM counters remain zero.

At 2026-10-27 06:25 UTC, stage2 dependencies progressed through `icu_provider_macros`, `unicode-properties`, `wasmparser` 0.234.0, `serde_json`, and `rustc_lexer` (198,690-byte `.rlib`); `icu_provider` completed and `rand` is compiling. OOM counters remain zero.

At 2026-10-27 06:26 UTC, stage2 completed `serde_json` (2,003,892-byte `.rlib`), `unic-langid`, `ryu`, and `rustc_abi` (1,576,690 bytes); compiler dependencies also advanced through `object`, `icu_list_data`, and `rand_xoshiro`. OOM counters remain zero.

At 2026-10-27 06:27 UTC, stage2 completed `icu_locid_transform` (1,104,282-byte `.rlib`) and is compiling `wasmparser` 0.234.0 after finishing `rustc_abi` and `serde_json`. Rustc remains active and OOM counters remain zero.

At 2026-10-27 06:28 UTC, stage2 `wasmparser` completed (4,423,334-byte AArch64 `.rlib`); `rustc_ast` metadata and archive are now present (6,804,106 bytes), and the compiler continues with the next frontend crates. OOM counters remain zero.

At 2026-10-27 06:29 UTC, `rustc_ast` completed (6,835,312-byte AArch64 `.rlib`); the stage2 compiler moved on to `itertools` 0.12.1. The process remains active with zero OOM events.

At 2026-10-27 06:30 UTC, stage2 completed `itertools` (2,972,100-byte `.rlib`) and `rustc_ast_pretty` (968,374 bytes); `thiserror` is complete and the compiler dependency build has moved to `object`. OOM counters remain zero.

At 2026-10-27 06:31 UTC, `object` entered AArch64 codegen and emitted multiple CGU objects (including `.03`, `.14`, `.13`, `.10`, `.04`, `.09`, `.05`, `.12`, `.11`); rustc remains active and OOM counters are zero.

At 2026-10-27 06:32 UTC, stage2 `object` completed (9,791,684-byte AArch64 `.rlib`); the build advanced through `icu_list_data`, `rustc_fs_util`, `type-map`, `regex-automata`, and `darling_core`, and is compiling `icu_list`. OOM counters remain zero.

At 2026-10-27 06:33 UTC, stage2 completed `icu_list` (1,689,694-byte `.rlib`) and `intl-memoizer`; `rustc_target` is compiling with 4.37 MB metadata emitted. OOM counters remain zero.

At 2026-10-27 06:35 UTC, stage2 `rustc_target` moved from metadata/optimization into LTO codegen and emitted its first AArch64 CGU object (about 662 KB); rustc remains CPU-active and OOM counters remain zero.

At 2026-10-27 06:36 UTC, `rustc_target` LTO emitted four additional AArch64 codegen objects (`cgu.14`, `.06`, `.07`, `.08`) and started `.03`; the compiler remains CPU-active and OOM counters remain zero.

At 2026-10-27 06:37 UTC, `rustc_target` LTO produced five more AArch64 CGU objects (`cgu.03`, `.11`, `.10`, `.09`, `.13`, `.04`) and started `.02`; compiler remains active, OOM counters remain zero.

At 2026-10-27 06:38 UTC, stage2 `rustc_target` completed (8,487,564-byte AArch64 `.rlib`); compilation advanced to localization and attribute crates (`fluent-syntax`, `rustc_attr_data_structures`, `fluent-langneg`, `intl_pluralrules`, `odht`). OOM counters remain zero.

At 2026-10-27 06:39 UTC, stage2 completed `fluent-syntax` (504,378-byte `.rlib`), `fluent-bundle` (948,836 bytes), `odht`, and `self_cell`; `rustc_hir` has emitted 3.33 MB metadata and is compiling. OOM counters remain zero.

At 2026-10-27 06:40 UTC, stage2 `rustc_hir` completed (4,691,302-byte AArch64 `.rlib`); the bootstrap advanced to `rustc_baked_icu_data`, `darling_macro`, `icu_provider_adapters`, `rustc_type_ir_macros`, and `annotate-snippets`. OOM counters remain zero.

At 2026-10-27 06:41 UTC, stage2 completed `fluent-bundle` (1,493,362-byte `.rlib`) and `rustc_type_ir` (5,220,018 bytes); `annotate-snippets` also completed, and `rustc_error_messages` metadata is being compiled. OOM counters remain zero.

At 2026-10-27 06:42 UTC, stage2 completed `rustc_error_messages` (628,712-byte `.rlib`) and moved on to `darling`, `derive_setters`, and `rustc_lint_defs`; OOM counters remain zero.

At 2026-10-27 06:43 UTC, `rustc_lint_defs` completed (812,488-byte AArch64 `.rlib`); `rustc_fluent_macro`, `termize`, `rustc_error_codes`, and `termcolor` progressed, and `rustc_errors` metadata is emitted during compilation. OOM counters remain zero.

At 2026-10-27 06:44 UTC, `rustc_errors` is in LTO and has emitted several AArch64 CGU objects (`cgu.13`, `.01`, `.00`; `.02` started). The compiler remains active and OOM counters remain zero.

At 2026-10-27 06:45 UTC, stage2 `rustc_errors` completed (5,206,910-byte AArch64 `.rlib`); compilation moved to `rustc_feature`. OOM counters remain zero.

At 2026-10-27 06:46 UTC, stage2 completed `rustc_feature` (784,948-byte AArch64 `.rlib`) and `getopts` (345,360 bytes); `rustc_session` metadata is emitted and compiling. OOM counters remain zero.

At 2026-10-27 06:47 UTC, `rustc_session` has progressed into AArch64 LTO/codegen, emitting CGUs `.01` and `.04` and starting `.06`; rustc remains CPU-active with zero OOM events.

At 2026-10-27 06:48 UTC, `rustc_session` completed (5,462,274-byte AArch64 `.rlib`); stage2 advanced to `rustc_apfloat`. The build remains active and OOM counters remain zero.

At 2026-10-27 06:49 UTC, stage2 completed `rustc_apfloat` (799,162-byte `.rlib`) and `polonius-engine`; `rustc_query_system` completed (1,832,474 bytes), while `rustc_hir_pretty` is compiling. OOM counters remain zero.

At 2026-10-27 06:50 UTC, stage2 completed `rustc_hir_pretty` (792,502-byte `.rlib`) and `gsgdt` (570,498 bytes), then advanced into `rustc_middle`; the build is active and OOM counters remain zero.

At 2026-10-27 06:52 UTC, the active `rustc_middle` stage2 compile remains CPU-bound at roughly 1.2 GiB RSS; no metadata/archive for this build instance yet. Container cgroup reports no memory limit and zero OOM events; about 13 GiB filesystem space remains.

At 2026-10-27 06:53 UTC, the active stage2 `rustc_middle` compile emitted 26,831,264 bytes of metadata and remains CPU-active at about 1.4 GiB RSS; OOM counters remain zero.

At 2026-10-27 06:54 UTC, the stage2 `rustc_middle` compile is in optimized codegen (`opt cgu.11` worker observed); it remains CPU-active around 1.4 GiB RSS, with no final archive yet and zero OOM events.

At 2026-10-27 06:55 UTC, the long `rustc_middle` optimized codegen worker advanced from CGU 11 to CGU 07, confirming ongoing work despite no emitted codegen object in the latest sample. OOM counters remain zero and about 13 GiB filesystem space remains.

At 2026-10-27 06:56 UTC, `rustc_middle` advanced from optimized CGU 08 into LTO; AArch64 CGU 00 object reached 1,021,304 bytes and CGU 06 started. Rustc remains CPU-active with zero OOM events.

At 2026-10-27 06:57 UTC, `rustc_middle` LTO emitted additional AArch64 objects for CGUs 06, 09, 14, and 04 (alongside CGU 00); the active LTO worker is on CGU 11. OOM counters remain zero.

At 2026-10-27 06:58 UTC, `rustc_middle` LTO emitted CGUs 11, 15, and 07 since the last note; CGU 12 has started and is the active LTO worker. Rustc remains CPU-active, with zero OOM events.

At 2026-10-27 06:59 UTC, `rustc_middle` LTO emitted CGUs 12, 08, 01, and 10; the active worker advanced to CGU 13. Compilation remains CPU-active and OOM-free.

At 2026-10-27 07:00 UTC, Guix completed `rustc_middle` and emitted `librustc_middle-dca0112f1e1e148e.rlib` (38,201,386 bytes). Cargo advanced to `polonius-engine`, `rustc_query_system`, `rustc_hir_pretty`, and other dependencies; a new rustc process is active at 99.5% CPU. The Rust bootstrap exit marker is still absent and cgroup OOM counters remain zero.

At 2026-10-27 07:01 UTC, Guix's Rust bootstrap completed `rustc_parse_format` and `rustc_transmute`; the next large compiler crate `rustc_infer` emitted 2,447,467 bytes of metadata and is compiling. Cargo remains active, with rustc at 99.6% CPU and about 640 MiB RSS; cgroup OOM counters remain zero.

At 2026-10-27 07:02 UTC, Guix remains in optimized codegen for `rustc_infer`; rustc's active worker is `opt cgu.07` at 99.6% CPU. No archive has been emitted yet, but the live optimization worker confirms the build is progressing; cgroup OOM counters are zero and 13 GiB remain on the host filesystem.

At 2026-10-27 07:03 UTC, `rustc_infer` is advancing through optimized AArch64 codegen: CGU objects 04, 07, 12, 09, 01, and 02 were written between 07:02:40 and 07:03:15 UTC. Rustc remains at 99.7% CPU; cgroup OOM counters remain zero.

At 2026-10-27 07:04 UTC, `rustc_infer` produced additional optimized codegen objects through CGU 14; CGU 15 has started. Rustc remains active at 99.7% CPU and cgroup OOM counters remain zero.

At 2026-10-27 07:04 UTC, Guix completed `rustc_infer` and emitted its AArch64 archive (7,451,340 bytes), then advanced to `rustc_next_trait_solver`. The bootstrap remains active and cgroup OOM counters remain zero.

At 2026-10-27 07:05 UTC, Guix completed `rustc_next_trait_solver` (2,527,520-byte AArch64 archive) and moved into `rustc_trait_selection`, whose dependency metadata has appeared and whose compiler remains active at 99.5% CPU. OOM counters remain zero.

At 2026-10-27 07:06 UTC, Guix is compiling `rustc_trait_selection`; its `full.rmeta` (1,834,815 bytes) was emitted. The active rustc process is at 99.6% CPU (about 926 MiB RSS) with cgroup OOM counters still zero.

At 2026-10-27 07:07 UTC, `rustc_trait_selection` metadata grew from 1.8 MB to 5.97 MB during active compilation. Rustc remains at 99.6% CPU (about 1.1 GiB RSS); OOM counters remain zero.

At 2026-10-27 07:08 UTC, `rustc_trait_selection` is in optimized codegen (`opt cgu.02`), with its rustc process at 99.6% CPU and about 1.17 GiB RSS. No new dependency artifact was emitted in the latest two-minute sample; the optimization worker is live and OOM counters remain zero.

At 2026-10-27 07:09 UTC, the live `rustc_trait_selection` optimization worker advanced from `opt cgu.02` to `opt cgu.04`. The process remains CPU-active at 99.6% (about 1.18 GiB RSS), with OOM counters zero.

At 2026-10-27 07:09 UTC, the `rustc_trait_selection` worker advanced to `opt cgu.10`; the stage remains active at 99.6% CPU with about 1.18 GiB RSS. No OOM event was recorded.

At 2026-10-27 07:10 UTC, the same Guix stage remains live and `rustc_trait_selection`'s optimizer advanced from CGU 10 to CGU 06. Rustc is near 100% CPU at about 1.19 GiB RSS; the host has 13 GiB free and the container reports no OOM events.

At 2026-10-27 07:11 UTC, `rustc_trait_selection` progressed out of per-CGU optimization and into LTO (`lto cgu.02`). Rustc remains active at 99.7% CPU with cgroup OOM counters zero.

At 2026-10-27 07:12 UTC, Guix LTO for `rustc_trait_selection` emitted CGU 02 (761,400 bytes) and CGU 10 (1,128,056 bytes); the active worker is on CGU 11. Rustc remains at 99.7% CPU and OOM counters remain zero.

At 2026-10-27 07:13 UTC, Guix LTO emitted `rustc_trait_selection` CGUs 11 (1,268,704 bytes) and 06 (1,439,512 bytes); the active LTO worker advanced to CGU 00. Rustc remains CPU-active at 99.7%, with zero OOM events.

At 2026-10-27 07:13 UTC, `rustc_trait_selection` LTO emitted CGUs 00 (1,452,064 bytes) and 01 (853,072 bytes); worker advanced to CGU 14. Compilation remains active at 99.7% CPU, with zero OOM events.

At 2026-10-27 07:15 UTC, Guix LTO for `rustc_trait_selection` emitted CGUs 14 (1,291,304 bytes) and 04 (793,528 bytes), then advanced to CGU 12. Rustc remains active at 99.7% CPU; OOM counters remain zero.

At 2026-10-27 07:15 UTC, Guix LTO emitted `rustc_trait_selection` CGUs 12 (1,059,728 bytes) and 07 (1,452,680 bytes); the worker advanced to CGU 15. Rustc remains near one full CPU with OOM counters zero.

At 2026-10-27 07:16 UTC, Guix LTO emitted `rustc_trait_selection` CGUs 15 (829,880 bytes) and 13 (1,025,664 bytes); CGU 05 is actively being written and is the current LTO worker. Rustc remains at 99.7% CPU; OOM counters remain zero.

At 2026-10-27 07:17 UTC, Guix LTO emitted `rustc_trait_selection` CGUs 09 (639,000 bytes) and 03 (817,392 bytes); worker advanced to CGU 08. Rustc remains near one CPU, with OOM counters zero.

At 2026-10-27 07:18 UTC, Guix completed `rustc_trait_selection` and emitted `librustc_trait_selection-dd30df8e72f49ce5.rlib` (25,302,240 bytes). Cargo advanced to `unicode-normalization` and `rustc_attr_parsing`; the new rustc process is active in optimized codegen (`opt cgu.14`). OOM counters remain zero.

At 2026-10-27 07:19 UTC, Guix `rustc_attr_parsing` generated 12 AArch64 CGU objects and entered LTO (`lto cgu.12`). The rustc process is active at 99.7% CPU; cgroup OOM counters remain zero.

At 2026-10-27 07:20 UTC, Guix completed `rustc_attr_parsing` (3,871,646-byte AArch64 archive) and `unicode-normalization` (1,888,630-byte archive), then advanced through `aho-corasick` and into `regex-syntax`. The build remains active and OOM counters remain zero.

At 2026-10-27 07:21 UTC, Guix completed `aho-corasick` (2,479,772-byte AArch64 archive); `regex-syntax` emitted metadata and began LTO, with multiple CGU objects written and `lto cgu.03` active. OOM counters remain zero.

At 2026-10-27 07:22 UTC, Guix completed `regex-syntax` (7,320,448-byte AArch64 archive) and advanced to `regex-automata`, which has emitted 4.58 MB of metadata and entered optimized codegen (`opt cgu.03`). The build remains active with OOM counters zero.

At 2026-10-27 07:23 UTC, Guix `regex-automata` advanced through AArch64 CGU optimization and entered LTO (`lto cgu.04`); eight CGU objects were written in this interval. Rustc remains active at 99.8% CPU and OOM counters remain zero.

At 2026-10-27 07:24 UTC, Guix completed `regex-automata` (6,937,350-byte AArch64 archive), then advanced through `getrandom`, `rand_core`, and into `rand_chacha`/`regex`. The active rustc worker is in optimized codegen; OOM counters remain zero.

At 2026-10-27 07:25 UTC, Guix completed `rand_core`, `rand_chacha`, `regex`, and `rand`, then started compiling `rustc_parse`; its metadata has been emitted and optimized compilation is active. OOM counters remain zero.

At 2026-10-27 07:26 UTC, `rustc_parse` metadata reached 3,247,471 bytes and optimized codegen began at CGU 00. Rustc remains CPU-active at about 99.6% with OOM counters zero.

At 2026-10-27 07:27 UTC, `rustc_parse`'s optimized-codegen worker advanced from CGU 00 to CGU 09; rustc remains active at 99.6% CPU with zero OOM events.

At 2026-10-27 07:28 UTC, Guix `rustc_parse` completed optimized codegen and entered LTO (`lto cgu.00`); its first LTO object has started writing. Rustc remains CPU-active and OOM counters remain zero.

At 2026-10-27 07:29 UTC, Guix LTO for `rustc_parse` emitted CGUs 00 (2,364,848 bytes), 01, 03, 15, and 08; the active LTO worker advanced to CGU 07. Rustc remains CPU-active and OOM counters remain zero.

At 2026-10-27 07:30 UTC, `rustc_parse` LTO has emitted CGUs through 12 (including 06, 09, 02, 11, 14, 13, and 04 since the prior note); worker advanced to CGU 10. Rustc remains at 99.7% CPU, with zero OOM events.

At 2026-10-27 07:30 UTC, Guix completed `rustc_parse` and emitted its 10,723,228-byte AArch64 archive, then advanced through `static_assertions` and `twox-hash` into `rustc_ast_passes` optimized codegen (`opt cgu.02`). OOM counters remain zero.

At 2026-10-27 07:31 UTC, Guix `rustc_ast_passes` produced metadata and several AArch64 objects, then entered LTO (`lto cgu.00`). Rustc is active at 99.8% CPU; OOM counters remain zero.

At 2026-10-27 07:32 UTC, Guix completed `rustc_ast_passes` (2,032,380-byte AArch64 archive) and advanced to `rustc_proc_macro`, whose optimized codegen is active at CGU 03. OOM counters remain zero.

At 2026-10-27 07:33 UTC, Guix completed `rustc_proc_macro` (2,087,066-byte AArch64 archive), compiled `adler2` and began `rustc_expand` optimized codegen at CGU 00. OOM counters remain zero.

At 2026-10-27 07:34 UTC, `rustc_expand` advanced optimized codegen from CGU 01 to CGU 10; the process remains at 99.6% CPU and cgroup OOM counters are zero.

At 2026-10-27 07:34 UTC, `rustc_expand` moved from optimized codegen into LTO (`lto cgu.00`); CGU 01 completed and CGU 00 began. Rustc remains CPU-active at 99.7% with zero OOM events.

At 2026-10-27 07:35 UTC, `rustc_expand` LTO emitted CGUs 00, 02, 08, 15, and 11; the worker advanced to CGU 09. Rustc remains near one CPU with OOM counters zero.

At 2026-10-27 07:36 UTC, `rustc_expand` LTO emitted CGUs 09, 07, 14, 12, and 13; CGU 05 is actively being written. Rustc remains at 99.7% CPU; OOM counters remain zero.

At 2026-10-27 07:37 UTC, Guix completed `rustc_expand` (9,018,054-byte AArch64 archive), then advanced through `object` and `flate2` into `ruzstd` optimized codegen (`opt cgu.04`). OOM counters remain zero.

At 2026-10-27 07:37 UTC, Guix completed `ruzstd` (939,460-byte AArch64 archive) and advanced to `unicode-script`, whose optimized codegen is active. The build remains live with zero OOM events.

At 2026-10-27 07:38 UTC, Guix completed `unicode-script` (761,402-byte archive) and `unicode-security` (2,248,238-byte archive); `object` is in optimized codegen with 8.52 MB metadata. The compiler remains active and OOM counters are zero.

At 2026-10-27 07:39 UTC, Guix completed `object` (9,621,244-byte AArch64 archive) and advanced through `libloading`, `fallible-iterator`, `rustc-demangle`, and `punycode`. Build remains active with zero OOM events.

At 2026-10-27 07:40 UTC, Guix compiled `regex-syntax` 0.6.29 after `punycode`; multiple AArch64 CGUs are being linked, with LTO active at CGU 04. Rustc remains CPU-active and OOM counters remain zero.

At 2026-10-27 07:41 UTC, Guix completed the second `regex-syntax` variant (6,558,202-byte archive) and `regex-automata` 0.1.10 (1,721,322-byte archive); `rustc_symbol_mangling` is now compiling, with optimized codegen active. OOM counters remain zero.

At 2026-10-27 07:42 UTC, Guix completed `rustc_symbol_mangling` (1,634,204-byte AArch64 archive) and began `gimli` 0.31.1. The build remains active; cgroup OOM counters remain zero.

At 2026-10-27 07:43 UTC, Guix completed `gimli` (7,739,400-byte AArch64 archive) and advanced to `rustc_metadata`, whose compilation is active. OOM counters remain zero.

At 2026-10-27 07:44 UTC, `rustc_metadata` emitted 1,974,148 bytes of AArch64 metadata and is in optimized codegen (`opt cgu.13`). Rustc remains active at 99.6% CPU, with OOM counters zero.

At 2026-10-27 07:45 UTC, `rustc_metadata` remains in optimized codegen and its live worker advanced from CGU 13 to CGU 07. Rustc is still CPU-active at 99.6%, with no OOM events.

At 2026-10-27 07:46 UTC, `rustc_metadata` advanced from optimization to LTO; AArch64 objects for CGUs 00, 03, and 06 are present, with `lto cgu.07` active. Rustc remains CPU-active and OOM counters remain zero.

At 2026-10-27 07:47 UTC, `rustc_metadata` LTO emitted CGUs 07, 15, and 05; CGU 12 is actively being written and is the current LTO worker. Rustc remains near one CPU with zero OOM events.

At 2026-10-27 07:48 UTC, `rustc_metadata` LTO emitted CGUs 02, 04, 08, and 09; worker advanced to CGU 11. Rustc remains at 99.7% CPU with no OOM events.

At 2026-10-27 07:49 UTC, Guix completed `rustc_metadata` (9,507,336-byte AArch64 archive) and advanced to `rustc_lint`, whose compiler is active. OOM counters remain zero.

At 2026-10-27 07:50 UTC, `rustc_lint` remains in optimized codegen and its worker advanced from CGU 00 to CGU 13. Rustc is CPU-active at 99.6%; OOM counters remain zero.

At 2026-10-27 07:51 UTC, the live optimized worker for `rustc_lint` advanced from CGU 13 to CGU 10; rustc remains at 99.6% CPU and OOM counters remain zero.

At 2026-10-27 07:52 UTC, `rustc_lint` advanced from per-CGU optimization into LTO (`lto cgu.03`); its CGU 13 object was emitted. Rustc remains active at 99.7% CPU with zero OOM events.

At 2026-10-27 07:53 UTC, `rustc_lint` LTO emitted CGUs 01, 09, and 06; CGU 07 is actively being written. Rustc remains at 99.7% CPU with no OOM events.

At 2026-10-27 07:54 UTC, `rustc_lint` LTO emitted CGUs 07, 08, and 02; CGU 11 is now being written. Rustc remains CPU-active with zero OOM events.

At 2026-10-27 07:55 UTC, `rustc_lint` LTO emitted CGUs 11, 10, 14, and 12; the worker advanced to CGU 00. Rustc remains at 99.7% CPU with OOM counters zero.

At 2026-10-27 07:56 UTC, Guix completed `rustc_lint` (15,627,378-byte AArch64 archive) and advanced to `rustc_mir_dataflow`; the new rustc worker is active and OOM counters remain zero.

At 2026-10-27 07:57 UTC, Guix `rustc_mir_dataflow` emitted metadata and advanced through AArch64 codegen into LTO (`lto cgu.15`); multiple CGU objects are present. Rustc remains active at 99.8% CPU and OOM counters remain zero.

At 2026-10-27 07:58 UTC, Guix completed `rustc_mir_dataflow` (3,308,848-byte AArch64 archive) and moved on to `rustc_llvm` plus `pulldown-cmark` and tracing dependencies. The build remains active, with OOM counters zero.

At 2026-10-27 07:59 UTC, Guix advanced through tracing and build dependencies (`overload`, `nu-ansi-term`, `sharded-slab`, and `cc`); `wasm-encoder` is compiling for the toolchain. Rustc remains active and OOM counters are zero.

At 2026-10-27 08:00 UTC, Guix completed `wasm-encoder` (2,339,330-byte AArch64 archive). The build is compiling `rustc_llvm`; its C++ build script is active in `cc1plus` at 98.6% CPU, with OOM counters zero.

At 2026-10-27 08:01 UTC, the Guix `rustc_llvm` C++ build continued and emitted LLVM wrapper objects (`PassWrapper`, `RustWrapper`, `ArchiveWrapper`, `CoverageMappingWrapper`, and `SymbolWrapper`). A fresh `cc1plus` process is CPU-active; cgroup OOM counters remain zero.

At 2026-10-27 08:02 UTC, Guix advanced through `matchers` and `ar_archive_writer` (770,430-byte AArch64 archive), then began `bstr`; the wider bootstrap remains active, with OOM counters zero.

At 2026-10-27 08:03 UTC, Guix completed `bstr` (2,557,956-byte AArch64 archive) and advanced to `rustc_ty_utils`, whose compilation is active. The build remains OOM-free.

At 2026-10-27 08:04 UTC, `rustc_ty_utils` emitted metadata, generated AArch64 CGU objects, and entered LTO (`lto cgu.06`). Rustc remains active at 99.7% CPU; OOM counters are zero.

At 2026-10-27 08:05 UTC, `rustc_ty_utils` LTO emitted multiple AArch64 CGUs (including 06, 05, 07, 04, 08, 12, and 10); CGU 15 is currently being written. The worker remains CPU-active and OOM counters are zero.

At 2026-10-27 08:06 UTC, Guix completed `rustc_ty_utils` (5,727,662-byte AArch64 archive) and advanced to `rustc_incremental`, whose optimized codegen is active. OOM counters remain zero.

At 2026-10-27 08:07 UTC, Guix `rustc_incremental` generated multiple AArch64 CGUs and entered LTO (`lto cgu.00`). Rustc remains active at 99.7% CPU, with zero OOM events.

At 2026-10-27 08:08 UTC, Guix completed `rustc_incremental` (3,799,676-byte AArch64 archive) and advanced to `rustc_pattern_analysis`; the new rustc process is active in LTO (`lto cgu.04`). OOM counters remain zero.

At 2026-10-27 08:09 UTC, Guix completed `rustc_pattern_analysis` (2,579,848-byte AArch64 archive) and advanced through `thread_local`, `pulldown-cmark-escape`, `pathdiff`, and `unicase`. The build remains active and OOM-free.

At 2026-10-27 08:10 UTC, Guix completed `pulldown-cmark` (2,881,608-byte AArch64 archive) and advanced to `rustc_codegen_ssa`; metadata is present and optimized compilation is active. OOM counters remain zero.

At 2026-10-27 08:11 UTC, `rustc_codegen_ssa` metadata grew to 4,859,226 bytes and the optimized worker advanced to CGU 03. Rustc remains active at 99.6% CPU with OOM counters zero.

At 2026-10-27 08:12 UTC, `rustc_codegen_ssa` remains in optimized codegen and its live worker advanced from CGU 04 to CGU 07. Rustc is active at 99.6% CPU; OOM counters remain zero.

At 2026-10-27 08:13 UTC, `rustc_codegen_ssa` advanced from optimized codegen into LTO; CGUs 10 and 06 were emitted, and CGU 09 is being written. Rustc remains CPU-active with zero OOM events.

At 2026-10-27 08:14 UTC, `rustc_codegen_ssa` LTO emitted CGUs 08, 04, 03, 11, and 05; the active worker advanced to CGU 02. Rustc remains active at 99.7% CPU with zero OOM events.

At 2026-10-27 08:15 UTC, `rustc_codegen_ssa` LTO emitted CGUs 02, 13, 12, 01, 07, and 14; the active worker advanced to CGU 15. Rustc remains CPU-active at 99.7% and OOM counters remain zero.

At 2026-10-27 08:16 UTC, Guix completed `rustc_codegen_ssa` (12,096,746-byte AArch64 archive) and advanced to `tracing-subscriber`; the new rustc worker is active. OOM counters remain zero.

At 2026-10-27 08:17 UTC, `tracing-subscriber` generated many AArch64 CGU objects and entered LTO (`lto cgu.03`). The compiler remains active and OOM counters remain zero.

At 2026-10-27 08:17 UTC, Guix completed `tracing-subscriber` (3,570,302-byte AArch64 archive) and advanced to `rustc_mir_build`; its compiler is active and OOM counters remain zero.

At 2026-10-27 08:19 UTC, `rustc_mir_build` remains in optimized codegen and its live worker advanced from CGU 02 to CGU 07. Rustc is CPU-active at 99.6%, with zero OOM events.

At 2026-10-27 08:20 UTC, `rustc_mir_build` advanced from optimized codegen into LTO; CGUs 02, 15, and 00 completed, and CGU 13 is being written. Rustc remains at 99.7% CPU with zero OOM events.

At 2026-10-27 08:21 UTC, `rustc_mir_build` LTO emitted CGUs 13, 05, 11, 07, 09, 12, and 06; the active worker advanced to CGU 08. Rustc remains CPU-active with OOM counters zero.

At 2026-10-27 08:22 UTC, Guix completed `rustc_mir_build` (8,713,336-byte AArch64 archive) and advanced to `rustc_privacy`; its new rustc process is active. OOM counters remain zero.

At 2026-10-27 08:23 UTC, Guix completed `rustc_privacy` (2,186,394-byte AArch64 archive) and advanced to `rustc_const_eval`, whose compilation is active. OOM counters remain zero.

At 2026-10-27 08:24 UTC, `rustc_const_eval` emitted 5,661,787 bytes of AArch64 metadata and is in optimized codegen (`opt cgu.02`). Rustc remains active at 99.6% CPU with OOM counters zero.

At 2026-10-27 08:25 UTC, `rustc_const_eval` remains in optimized codegen and its worker advanced from CGU 02 to CGU 09; rustc stays at 99.6% CPU with no OOM events.

At 2026-10-27 08:26 UTC, `rustc_const_eval` advanced from optimized codegen into LTO; CGUs 00 and 09 were emitted, and CGU 04 is being written. Rustc remains CPU-active with OOM counters zero.

At 2026-10-27 08:27 UTC, `rustc_const_eval` LTO emitted CGUs 15, 08, 10, 07, and 11; the worker advanced to CGU 12. Rustc remains active at 99.7% CPU, with OOM counters zero.

At 2026-10-27 08:28 UTC, `rustc_const_eval` LTO emitted CGUs 12, 05, 02, 13, 03, and 06; CGU 14 is being written. Rustc remains at 99.7% CPU with OOM counters zero.

At 2026-10-27 08:28 UTC, Guix completed `rustc_const_eval` (13,411,630-byte AArch64 archive) and advanced to `rustc_sanitizers`; its compiler is active. OOM counters remain zero.

At 2026-10-27 08:29 UTC, Guix completed `rustc_sanitizers` (1,548,248-byte AArch64 archive) and advanced to `rustc_hir_analysis`; its compiler is active and OOM counters remain zero.

At 2026-10-27 08:30 UTC, `rustc_hir_analysis` emitted 3,700,914 bytes of metadata and is in optimized codegen (`opt cgu.15`). Rustc is active at 99.6% CPU, with OOM counters zero.

At 2026-10-27 08:31 UTC, `rustc_hir_analysis` remains in optimized codegen; its live worker advanced from CGU 01 to CGU 13. The rustc process remains CPU-active and cgroup OOM counters are zero.

At 2026-10-27 08:32 UTC, the optimized-codegen worker for `rustc_hir_analysis` advanced from CGU 13 to CGU 11. The process remains CPU-active with cgroup OOM counters zero.

At 2026-10-27 08:34 UTC, the `rustc_hir_analysis` optimized worker advanced from CGU 05 to CGU 09. Compilation remains CPU-active; cgroup OOM counters remain zero.

At 2026-10-27 08:35 UTC, `rustc_hir_analysis` emitted its first LTO object (CGU 02, 1,014,400 bytes) and advanced to LTO CGU 05. Rustc remains active at 99.7% CPU with zero OOM events.

At 2026-10-27 08:37 UTC, the resumed Guix AArch64 Rust bootstrap advanced through `rustc_hir_analysis` LTO: CGUs 06 and 07 were emitted after the previous poll. The rustc worker remains live (RSS about 862 MiB), and cgroup OOM counters remain zero.

At 2026-10-27 08:38 UTC, `rustc_hir_analysis` LTO emitted CGUs 11 and 10 (CGU 10 is currently an empty in-progress output); the worker remains live at about 828 MiB RSS. Cgroup OOM counters remain zero.

At 2026-10-27 08:39 UTC, Guix Rust bootstrap `rustc_hir_analysis` LTO emitted CGUs 15 and 09 after the 08:38 poll. The stage1 Rust compiler remains live at about 855 MiB RSS; cgroup OOM counters are zero.

At 2026-10-27 08:40 UTC, reconciled stale pending-gate text with the verified Gentoo AArch64 build/lifecycle result already present in the matrix. Guix AArch64 remains the only declared distro/architecture package lifecycle unverified.

At 2026-10-27 08:41 UTC, Guix's `rustc_hir_analysis` LTO emitted CGUs 04, 12, 08 and 01 since 08:39. The stage1 compiler remains live (about 870 MiB RSS); cgroup OOM counters remain zero.

At 2026-10-27 08:42 UTC, the Guix Rust bootstrap completed `rustc_hir_analysis` and advanced to `rustc_ast_lowering`; the new stage1 rustc worker is live at about 650 MiB RSS. The build log confirms the crate transition, and cgroup OOM counters remain zero.

At 2026-10-27 08:43 UTC, `rustc_ast_lowering` remains active: its CPU time increased from 68.7 s to 100.2 s over the latest 35-second observation, with RSS about 680 MiB. It remains in the same crate, and cgroup OOM counters remain zero.

At 2026-10-27 08:43 UTC, the Guix `rustc_ast_lowering` compiler stayed active: CPU time rose from 114.6 s to 142.2 s over 31 seconds and RSS rose to about 576 MiB. The build log remains in this crate; OOM counters are zero.

At 2026-10-27 08:44 UTC, `rustc_ast_lowering` remains the active Guix bootstrap crate; the compiler CPU timer increased to 156.1 s while RSS held near 579 MiB. Cgroup OOM counters remain zero; no package output or exit marker exists yet.

At 2026-10-27 08:46 UTC, the Guix Rust bootstrap completed `rustc_ast_lowering` and advanced to `rustc_traits`; the new stage1 compiler is live at about 426 MiB RSS. Cgroup OOM counters remain zero.

At 2026-10-27 08:47 UTC, Guix has advanced beyond `rustc_ast_lowering` and is compiling `rustc_traits`; the active rustc has about 428 MiB RSS, with cgroup OOM counters zero.

At 2026-10-27 08:48 UTC, Guix `rustc_traits` remains CPU-active (about 423 MiB RSS); cgroup OOM counters remain zero.

At 2026-10-27 08:49 UTC, Guix completed `rustc_traits` and advanced to `rustc_borrowck`; the new stage1 rustc worker is active. Cgroup OOM counters remain zero.

At 2026-10-27 08:49 UTC, Guix `rustc_borrowck` remains active; compiler CPU time reached 46 s and RSS about 782 MiB. OOM counters remain zero.

At 2026-10-27 08:50 UTC, Guix `rustc_borrowck` remains CPU-active; stage1 rustc CPU time reached 88.9 s and RSS about 1.07 GiB. Cgroup OOM counters remain zero.

At 2026-10-27 08:51 UTC, Guix `rustc_borrowck` remains CPU-active (about 171.8 s cumulative rustc CPU time, RSS about 1.08 GiB); the crate has not emitted its completion line. No cgroup OOM events or Guix build exit marker are present.

At 2026-10-27 08:52 UTC, `rustc_borrowck` remains active: cumulative rustc CPU time rose to 211.5 s, with RSS about 1.09 GiB. No crate completion or build exit marker is present; cgroup OOM counters remain zero.

At 2026-10-27 08:53 UTC, `rustc_borrowck` remains active; its cumulative rustc CPU time reached 248.7 s with RSS about 1.09 GiB. The crate/build has not exited, and cgroup OOM counters remain zero.

At 2026-10-27 08:53 UTC, `rustc_borrowck` remained active during another sample: CPU time rose to 293.8 s and RSS to about 1.10 GiB. The crate is still compiling; OOM counters remain zero.

At 2026-10-27 08:54 UTC, `/proc/252056/task` shows the active `rustc_borrowck` worker in optimized codegen at `opt cgu.05`; it remains alive without OOM. This identifies the long crate's current stage even though no `.rcgu.o` file is visible yet.

At 2026-10-27 08:54 UTC, the optimized-codegen worker for `rustc_borrowck` advanced from CGU 05 to CGU 10; aggregate rustc CPU time reached 329.2 s and RSS about 1.11 GiB. Cgroup OOM counters remain zero.

At 2026-10-27 08:55 UTC, `rustc_borrowck` optimized codegen advanced from CGU 06 to CGU 09; cumulative rustc CPU time reached 366.2 s, RSS about 1.11 GiB, and cgroup OOM counters remain zero.

At 2026-10-27 08:55 UTC, a later poll found the active optimized-codegen worker on CGU 08, with total rustc CPU time 393.1 s and RSS about 1.12 GiB. Rustc remains active; cgroup OOM counters are zero.

At 2026-10-27 08:56 UTC, `rustc_borrowck` advanced from optimized codegen to LTO; CGU 11 emitted its first `.rcgu.o` (the active object was 0 bytes at the instant sampled), and the worker is in `lto cgu.11`. RSS is about 902 MiB and cgroup OOM counters remain zero.

At 2026-10-27 08:56 UTC, Guix LTO wrote `rustc_borrowck` CGU 11 at 771,528 bytes and advanced to CGU 00. Rustc CPU time reached 454.9 s (RSS about 950 MiB); OOM counters remain zero.

At 2026-10-27 08:57 UTC, Guix LTO emitted `rustc_borrowck` CGU 00 (1,182,856 bytes) and advanced to CGU 08; rustc CPU time reached 483.3 s, RSS about 966 MiB, with no OOM events.

At 2026-10-27 08:57 UTC, Guix LTO finished `rustc_borrowck` CGU 08 (1,152,664 bytes) and advanced to CGU 12; rustc CPU time reached 521.8 s, RSS about 923 MiB, with cgroup OOM counters still zero.

At 2026-10-27 08:58 UTC, Guix `rustc_borrowck` LTO emitted CGU 12 (909,240 bytes) and advanced to CGU 07. Rustc CPU time reached 549.2 s, RSS about 948 MiB, and OOM counters remain zero.

At 2026-10-27 08:58 UTC, Guix LTO completed `rustc_borrowck` CGU 07 (1,352,048 bytes) and advanced to CGU 14; rustc CPU time reached 577.6 s, RSS about 941 MiB, with no OOM events.

At 2026-10-27 08:59 UTC, `rustc_borrowck` LTO emitted CGU 14 (1,684,504 bytes) and advanced to CGU 13; cumulative rustc CPU time is 612.4 s and RSS about 973 MiB. OOM counters remain zero.

At 2026-10-27 08:59 UTC, Guix LTO emitted `rustc_borrowck` CGU 13 (958,112 bytes) and the worker moved to CGU 05; cumulative rustc CPU time reached 639.1 s, RSS about 924 MiB, no OOM events.

At 2026-10-27 09:00 UTC, Guix LTO emitted `rustc_borrowck` CGU 05 (1,384,480 bytes) and advanced to CGU 10; rustc CPU time reached 693.2 s, RSS about 923 MiB, OOM counters remain zero.

At 2026-10-27 09:01 UTC, Guix LTO emitted `rustc_borrowck` CGU 10 (1,139,520 bytes) and advanced to CGU 02; rustc CPU time reached 728.2 s, RSS about 962 MiB, cgroup OOM counters zero.

At 2026-10-27 09:01 UTC, `rustc_borrowck` LTO emitted CGU 02 (985,016 bytes) and advanced to CGU 03; rustc CPU time reached 754.8 s, RSS about 958 MiB, with no OOM events.

At 2026-10-27 09:02 UTC, Guix `rustc_borrowck` LTO emitted CGU 03 (839,744 bytes) and advanced to CGU 01. Rustc CPU time reached 788.99 s, RSS about 980 MiB; no OOM events.

At 2026-10-27 09:02 UTC, Guix LTO emitted `rustc_borrowck` CGU 01 (1,085,088 bytes) and moved to CGU 06; rustc CPU time reached 814.5 s, RSS about 979 MiB, with cgroup OOM counters zero.

At 2026-10-27 09:03 UTC, Guix `rustc_borrowck` LTO emitted CGU 06 (835,552 bytes) and advanced to CGU 15; rustc CPU time reached 841.1 s, RSS about 967 MiB, with no OOM events.

At 2026-10-27 09:03 UTC, Guix LTO emitted `rustc_borrowck` CGU 15 (636,776 bytes) and advanced to CGU 09; rustc CPU time reached 867.2 s, RSS about 970 MiB, and cgroup OOM counters remain zero.

At 2026-10-27 09:03 UTC, Guix `rustc_borrowck` LTO emitted CGU 09 (707,280 bytes) and advanced to CGU 04; rustc CPU time reached 894.5 s, RSS about 976 MiB, with no OOM events.

At 2026-10-27 09:04 UTC, `rustc_borrowck` completed its LTO and Rust bootstrap advanced to `rustc_passes`; the new stage1 compiler is live at about 613 MiB RSS. The Guix build process remains active and cgroup OOM counters are zero.

At 2026-10-27 09:05 UTC, `rustc_passes` is in optimized codegen at CGU 13; its stage1 rustc worker accumulated about 47 s of CPU time and RSS about 668 MiB. OOM counters remain zero.

At 2026-10-27 09:05 UTC, `rustc_passes` optimized codegen advanced from CGU 13 to CGU 06 (an intervening poll saw CGU 12); stage1 rustc CPU time reached 83.7 s and RSS about 678 MiB. OOM counters remain zero.

At 2026-10-27 09:06 UTC, Guix `rustc_passes` LTO emitted CGUs 05 (1,213,960 bytes), 03 (304,912 bytes), and 06 (276,624 bytes); the worker advanced to CGU 00. Rustc CPU time reached 135.5 s, RSS about 519 MiB, with no OOM events.

At 2026-10-27 09:07 UTC, Guix LTO emitted `rustc_passes` CGUs 00 (614,352 bytes), 11 (237,680 bytes), and 10 (449,664 bytes); the active worker is now on CGU 14. Rustc CPU time is 186.3 s, RSS about 512 MiB; OOM counters remain zero.

At 2026-10-27 09:08 UTC, `rustc_passes` LTO emitted CGUs 04 (393,128 bytes), 07 (313,592 bytes), and 08 (275,072 bytes); the active worker moved to CGU 12. Rustc CPU time reached 226.0 s, RSS about 526 MiB, with OOM counters zero.

At 2026-10-27 09:08 UTC, Guix LTO emitted `rustc_passes` CGUs 12 (271,400 bytes), 09 (311,304 bytes), and 01 (237,624 bytes); CGU 15 is active. Rustc CPU time reached 256.9 s, RSS about 527 MiB, no OOM events.

At 2026-10-27 09:09 UTC, `rustc_passes` completed and the Guix bootstrap advanced to `rustc_hir_typeck`; the new stage1 rustc is active at about 602 MiB RSS with 24 s CPU time. Cgroup OOM counters remain zero.

At 2026-10-27 09:09 UTC, `rustc_hir_typeck` remains CPU-active in compilation; the worker reached 51.2 s CPU time and RSS about 815 MiB. Cgroup OOM counters remain zero.

At 2026-10-27 09:10 UTC, `rustc_hir_typeck` remains CPU-active; its stage1 process reached 85.3 s CPU time and RSS about 1.07 GiB. Cgroup OOM counters remain zero.

At 2026-10-27 09:10 UTC, `rustc_hir_typeck` entered optimized codegen at CGU 00; stage1 rustc CPU time reached 116.8 s and RSS about 1.17 GiB. OOM counters remain zero.

At 2026-10-27 09:11 UTC, `rustc_hir_typeck` optimized codegen advanced from CGU 00 to CGU 15; rustc CPU time reached 143.6 s and RSS about 1.19 GiB. Cgroup OOM counters remain zero.

At 2026-10-27 09:12 UTC, `rustc_hir_typeck` optimized codegen advanced from CGU 15 to CGU 14; cumulative stage1 rustc CPU time reached 179.9 s, RSS about 1.19 GiB, with cgroup OOM counters zero.

At 2026-10-27 09:12 UTC, the optimized-codegen worker for `rustc_hir_typeck` advanced to CGU 13; stage1 rustc CPU time reached 208.1 s and RSS about 1.19 GiB. No OOM events.

At 2026-10-27 09:12 UTC, `rustc_hir_typeck` optimized codegen advanced to CGU 12; stage1 rustc CPU time reached 235.3 s and RSS about 1.19 GiB, with OOM counters zero.

At 2026-10-27 09:13 UTC, `rustc_hir_typeck` optimized codegen advanced from CGU 04 to CGU 05; rustc CPU time reached 270.0 s and RSS about 1.19 GiB. OOM counters remain zero.

At 2026-10-27 09:13 UTC, the `rustc_hir_typeck` optimized-codegen worker advanced to CGU 10; cumulative rustc CPU time reached 297.1 s and RSS about 1.19 GiB. Cgroup OOM counters remain zero.

At 2026-10-27 09:14 UTC, `rustc_hir_typeck` optimized codegen advanced to CGU 09; rustc CPU time reached 324.4 s and RSS about 1.19 GiB. The worker remains active and OOM counters are zero.

At 2026-10-27 09:15 UTC, `rustc_hir_typeck` advanced from optimized codegen (CGU 07) into LTO at CGU 01; rustc CPU time reached 359.0 s and RSS about 966 MiB. Cgroup OOM counters remain zero.

At 2026-10-27 09:15 UTC, Guix LTO emitted `rustc_hir_typeck` CGU 01 (1,182,192 bytes) and advanced to CGU 00; rustc CPU time reached 388.0 s, RSS about 1.02 GiB, no OOM events.

At 2026-10-27 09:16 UTC, `rustc_hir_typeck` LTO remains active in CGU 00; the object file exists but was still 0 bytes at the sample. Rustc CPU time reached 445.1 s, RSS about 1.08 GiB, cgroup OOM counters zero.

At 2026-10-27 09:17 UTC, Guix `rustc_hir_typeck` LTO completed CGU 00 (2,526,968 bytes) and CGU 05 (683,904 bytes), advancing to CGU 15. Rustc CPU time reached 479.7 s, RSS about 1.12 GiB; OOM counters remain zero.

At 2026-10-27 09:17 UTC, `rustc_hir_typeck` LTO emitted CGU 15 (856,616 bytes) and advanced to CGU 07; rustc CPU time reached 506.1 s, RSS about 1.12 GiB, with no OOM events.

At 2026-10-27 09:17 UTC, Guix `rustc_hir_typeck` LTO emitted CGU 07 (1,300,304 bytes) and advanced to CGU 14; rustc CPU time reached 532.6 s, RSS about 1.12 GiB, OOM counters zero.

At 2026-10-27 09:18 UTC, Guix LTO emitted `rustc_hir_typeck` CGU 14 (1,277,920 bytes) and advanced to CGU 10; rustc CPU time reached 567.0 s, RSS about 1.13 GiB, OOM counters zero.

At 2026-10-27 09:18 UTC, Guix LTO completed `rustc_hir_typeck` CGU 10 (1,215,320 bytes) and advanced to CGU 12; rustc CPU time reached 593.6 s, RSS about 1.12 GiB, with no OOM events.

At 2026-10-27 09:19 UTC, Guix LTO emitted `rustc_hir_typeck` CGU 12 (1,502,680 bytes) and began CGU 03; rustc CPU time reached 622.4 s, RSS about 1.13 GiB, OOM counters remain zero.

At 2026-10-27 09:19 UTC, Guix LTO emitted `rustc_hir_typeck` CGU 03 (625,216 bytes) and CGU 09 (911,752 bytes); the active worker advanced to CGU 11. Rustc CPU time reached 650.5 s, RSS about 1.12 GiB, cgroup OOM counters zero.

At 2026-10-27 09:20 UTC, Guix `rustc_hir_typeck` LTO emitted CGU 11 (824,176 bytes) and advanced to CGU 04; rustc CPU time reached 689.2 s, RSS about 1.11 GiB, with OOM counters zero.

At 2026-10-27 09:20 UTC, `rustc_hir_typeck` LTO emitted CGU 04 (813,160 bytes) and CGU 13 (636,848 bytes); the worker advanced to CGU 02. Rustc CPU time reached 716.8 s, RSS about 1.13 GiB; OOM counters zero.

At 2026-10-27 09:21 UTC, Guix LTO emitted `rustc_hir_typeck` CGU 02 (432,520 bytes) and advanced to CGU 06; rustc CPU time reached 743.1 s, RSS about 1.11 GiB, with no OOM events.

At 2026-10-27 09:21 UTC, `rustc_hir_typeck` LTO emitted CGU 06 (466,592 bytes) and advanced to CGU 08; rustc CPU time reached 770.3 s, RSS about 1.13 GiB, cgroup OOM counters zero.

At 2026-10-27 09:22 UTC, `rustc_hir_typeck` completed and the Guix bootstrap advanced to `rustc_codegen_llvm`; the new stage1 compiler is active at about 516 MiB RSS. The Guix/Cargo process chain remains live, and cgroup OOM counters are zero.

At 2026-10-27 09:22 UTC, `rustc_codegen_llvm` entered optimized codegen at CGU 00; stage1 rustc CPU time reached 39.4 s and RSS about 859 MiB. OOM counters remain zero.

At 2026-10-27 09:23 UTC, `rustc_codegen_llvm` optimized codegen advanced from CGU 00 to CGU 02; stage1 rustc CPU time reached 69.4 s and RSS about 890 MiB. Cgroup OOM counters remain zero.

At 2026-10-27 09:23 UTC, `rustc_codegen_llvm` optimized codegen advanced from CGU 13 to CGU 04; stage1 rustc CPU time reached 105.5 s and RSS about 897 MiB. OOM counters remain zero.

At 2026-10-27 09:24 UTC, `rustc_codegen_llvm` optimized codegen advanced to CGU 06; stage1 rustc CPU time reached 132.9 s and RSS about 901 MiB. No cgroup OOM events.

At 2026-10-27 09:24 UTC, `rustc_codegen_llvm` optimized codegen advanced to CGU 08; CPU time reached 159.9 s and RSS about 905 MiB. The worker remains active, cgroup OOM counters remain zero.

At 2026-10-27 09:25 UTC, `rustc_codegen_llvm` advanced from optimized codegen to LTO; CGU 02 emitted 550,704 bytes and the worker is on CGU 07. Stage1 rustc CPU time reached 196.7 s, RSS about 716 MiB, OOM counters zero.

At 2026-10-27 09:25 UTC, Guix LTO emitted `rustc_codegen_llvm` CGUs 07 (552,632 bytes) and 08 (889,496 bytes); active worker advanced to CGU 14. Rustc CPU time reached 224.8 s, RSS about 708 MiB, with no OOM events.

At 2026-10-27 09:26 UTC, `rustc_codegen_llvm` LTO emitted CGU 14 (578,360 bytes) and CGU 01 (428,944 bytes); worker advanced to CGU 04. Rustc CPU time reached 253.2 s, RSS about 715 MiB, OOM counters zero.

At 2026-10-27 09:26 UTC, Guix `rustc_codegen_llvm` LTO emitted CGU 04 (423,104 bytes), CGU 12 (458,576 bytes), and CGU 06 (646,184 bytes); worker advanced to CGU 03. Rustc CPU time reached 289.9 s, RSS about 703 MiB, OOM counters zero.
At 2026-10-27 09:28 UTC, Guix ARM64 `rustc_codegen_llvm` LTO emitted CGUs 13 (549,984 bytes), 15 (523,784 bytes), 11 (401,320 bytes), 03 (552,672 bytes), 06 (646,184 bytes), and 10 (379,056 bytes); CGU 09 is being written. The build remains live and cgroup OOM counters are zero.
At 2026-10-27 09:28 UTC, `rustc_codegen_llvm` completed its LTO and Guix bootstrap advanced to `rustc_mir_transform`; stage1 rustc is active at about 505 MiB RSS. Guix and Cargo remain live, with no cgroup OOM events or build exit marker.
At 2026-10-27 09:29 UTC, Guix `rustc_mir_transform` remains in active compilation: stage1 rustc cumulative CPU time rose to about 431.8 s and RSS to about 758 MiB since the previous sample. Guix/Cargo remain live; cgroup OOM counters and build exit marker are absent.
At 2026-10-27 10:23 UTC, Guix ARM64 `rustc_driver_impl` remains in active compilation; stage1 rustc cumulative CPU time reached about 2,207.7 s and RSS about 465 MiB. Guix/Cargo remain live, no build exit marker exists, and cgroup OOM counters remain zero.
At 2026-10-27 10:24 UTC, Guix ARM64 completed the long `rustc_driver_impl` compilation and advanced stage1 to `rustc_driver`; the new rustc process is CPU-active at about 230 MiB RSS. Guix/Cargo remain live, no exit marker exists, and cgroup OOM counters remain zero.
At 2026-10-27 10:25 UTC, Guix ARM64 Rust stage1 completed its optimized release build after 254m56s and advanced to creation of the stage2 sysroot plus `wasm-component-ld`; Cargo is compiling its serde dependency. The build remains live with no exit marker and zero cgroup OOM events.
At 2026-10-27 10:25 UTC, the Guix ARM64 stage1 `wasm-component-ld` build advanced through `serde`, `proc-macro2`, and `unicode-ident`; its active rustc process remains live at about 297 MiB RSS and cgroup OOM counters remain zero.
At 2026-10-27 10:26 UTC, Guix ARM64 `wasm-component-ld` compilation advanced through `wasmparser`, `libc`, `indexmap`, and related dependencies; active rustc remains live, cgroup OOM counters are zero, and the package build has not exited.
At 2026-10-27 10:26 UTC, Guix ARM64 `wasm-component-ld` is compiling `syn` after its `wasmparser`/`indexmap` dependencies; stage1 rustc CPU rose to about 28.9 s in the sampled process and RSS to about 469 MiB. Build remains live, without an exit marker or cgroup OOM event.
At 2026-10-27 10:27 UTC, Guix ARM64 `wasm-component-ld` progressed beyond the long `syn` compile and is compiling `wasmparser`; active rustc CPU reached about 113 s and RSS about 427 MiB. The build remains live, without an exit marker or cgroup OOM event.
At 2026-10-27 10:27 UTC, the same Guix ARM64 `wasmparser` compile remained CPU-active; cumulative rustc CPU rose to about 387.5 s and RSS to about 584 MiB since process start. No build exit marker or cgroup OOM events are present.
At 2026-10-27 10:28 UTC, the Guix ARM64 `wasmparser` rustc remained CPU-active; cumulative process CPU reached about 769.6 s and RSS about 761 MiB. Guix/Cargo are still live, no exit marker exists, and cgroup OOM counters remain zero.
At 2026-10-27 10:29 UTC, Guix ARM64 `wasmparser` compilation is still advancing: active rustc cumulative CPU reached about 1,095.6 s, with RSS about 755 MiB and eight threads. The same Guix/Cargo processes remain live and cgroup OOM counters remain zero.
At 2026-10-27 10:29 UTC, Guix ARM64 `wasmparser` remains CPU-active rather than stalled: its rustc CPU advanced from about 1,207.7 s to 1,512.0 s across samples; RSS is about 718 MiB. The build tree is 5.8 GiB, the process has no exit marker, and cgroup OOM counters remain zero.
At 2026-10-27 10:30 UTC, the Guix ARM64 `wasmparser` rustc remained active and reached about 1,782.8 s cumulative CPU with roughly 709 MiB RSS; cgroup OOM counters remain zero and Guix has not exited.
At 2026-10-27 10:30 UTC, Guix ARM64 `wasmparser` remains in active compilation; cumulative rustc CPU reached about 2,190.6 s and RSS about 715 MiB. Build/Cargo remain live, no exit marker exists, and cgroup OOM counters are zero.
At 2026-10-27 10:31 UTC, Guix ARM64 `wasmparser` rustc continued consuming CPU and reached about 2,510.9 s cumulative CPU with about 718 MiB RSS. The long compile is still live and OOM counters remain zero.
At 2026-10-27 10:31 UTC, the Guix ARM64 build advanced beyond the long `wasmparser` compile and is running the `serde_json` build script under stage1. Guix/Cargo remain live and OOM counters are zero. The container reports 13 GiB free on its 476 GiB overlay (98% used); `/src` has 13 GiB free. Continue monitoring disk alongside build progress.
At 2026-10-27 10:32 UTC, Guix ARM64 `wasm-component-ld` moved past `serde_json` and began compiling both `wasm-encoder` versions and CLI dependencies; active rustc is compiling `anstyle_query`. Disk remains at about 13 GiB free and OOM counters remain zero.
At 2026-10-27 10:32 UTC, Guix ARM64 has moved on to compile `serde_json` proper after completing its build script; CLI dependency crates including `rustix` and `anstream` also advanced. Disk availability remains stable at 13 GiB, with no OOM events.
At 2026-10-27 10:32 UTC, Guix ARM64 `serde_json` rustc remains CPU-active; cumulative CPU reached about 159.1 s and RSS about 405 MiB. The matrix still records Guix AArch64 as the sole unverified declared package lifecycle and local Ollama latency as partial; build/disk health remains stable with 13 GiB free and zero OOM events.
At 2026-10-27 10:33 UTC, Guix ARM64 completed/advanced past `serde_json` and is compiling `wasm_encoder`; the active rustc process is CPU-active at about 138 s and 418 MiB RSS. No OOM events; disk free remains about 13 GiB.
At 2026-10-27 10:33 UTC, Guix ARM64 is compiling the second `wasm_encoder` dependency version; rustc remains active and available disk space is stable at about 13 GiB. The build remains live with zero cgroup OOM events.
At 2026-10-27 10:34 UTC, Guix ARM64 advanced from the second `wasm-encoder` to `errno` in the stage1 tool dependency graph. The active compiler is live; disk remains at 13 GiB free and cgroup OOM counters are zero.
At 2026-10-27 10:35 UTC, Guix ARM64 progressed through `errno` and `serde_derive` to `strsim` while building `wasm-component-ld`; the worker is CPU-active, disk availability remains stable, and OOM counters are zero.
At 2026-10-27 10:35 UTC, the Guix ARM64 dependency build progressed beyond `strsim` and is compiling `linux_raw_sys`; intermediate `log`, `heck`, `unicode-xid`, `bumpalo`, and `clap_lex` stages appeared in Cargo output. Disk remains at 13 GiB free and no OOM events occurred.
At 2026-10-27 10:36 UTC, Guix ARM64 progressed from low-level CLI dependencies to compiling `wast` v235.0.0 for the stage1 tool; active rustc has about 189 s CPU and 445 MiB RSS. Disk remains stable at 13 GiB free; OOM counters are zero.
At 2026-10-27 10:36 UTC, Guix ARM64 `wast` v235 remains in active code generation; cumulative rustc CPU reached about 522.2 s and RSS about 675 MiB. The build remains live with zero cgroup OOM events and 13 GiB free disk.
At 2026-10-27 10:37 UTC, Guix ARM64 `wast` v235 remains CPU-active with seven rustc threads; cumulative CPU reached about 913.4 s and RSS about 684 MiB. No exit marker or cgroup OOM event; disk remains about 13 GiB free.
At 2026-10-27 10:37 UTC, the same Guix ARM64 `wast` compilation continued; rustc cumulative CPU rose to about 1,183.4 s and RSS is about 622 MiB across eight threads. The build remains live, disk/OOM status unchanged.
At 2026-10-27 10:38 UTC, Guix ARM64 `wast` continues active compilation; rustc CPU reached about 1,482.6 s, RSS about 670 MiB, eight threads. No OOM events and 13 GiB disk free.
At 2026-10-27 10:38 UTC, Guix ARM64 `wast` v235 compilation remains active; cumulative rustc CPU reached about 1,826.6 s and RSS about 655 MiB. Container stays live with 13 GiB disk free and zero OOM events.
At 2026-10-27 10:39 UTC, the same `wast` compile advanced to about 2,090.7 s cumulative rustc CPU while retaining eight active threads and about 656 MiB RSS. The build remains live, with zero OOM events and 13 GiB free disk.
At 2026-10-27 10:39 UTC, Guix ARM64 `wast` v235 remains CPU-active; cumulative rustc CPU reached about 2,432.3 s, RSS about 656 MiB, eight threads. Disk and cgroup memory/OOM status remain stable.
At 2026-10-27 10:40 UTC, Guix ARM64 moved past the long `wast` compile and is compiling `rustix`; active rustc has about 83.6 s CPU and 362 MiB RSS. Build remains live with zero OOM events and 13 GiB free disk.
At 2026-10-27 10:40 UTC, Guix ARM64 advanced from `rustix` to `clap_builder`; the active stage1 rustc worker is live at about 75 s CPU and 356 MiB RSS. Disk and OOM counters remain stable.
At 2026-10-27 10:41 UTC, Guix ARM64 `clap_builder` remains CPU-active; cumulative rustc CPU reached about 424.2 s and RSS about 479 MiB. Guix is live, with zero OOM events and 13 GiB free disk.
At 2026-10-27 10:41 UTC, the same `clap_builder` compile advanced to about 711.5 s cumulative rustc CPU across eight threads; RSS is about 410 MiB. No build exit, OOM event, or disk change.
At 2026-10-27 10:42 UTC, Guix ARM64 moved past `clap_builder` and is compiling `wit_parser` v0.229.0; stage1 rustc is CPU-active at about 92.6 s and 387 MiB RSS. Disk remains at 13 GiB free and OOM counters remain zero.
At 2026-10-27 10:43 UTC, the Guix ARM64 `wit_parser` compile remains CPU-active and reached about 379 s cumulative CPU with eight threads and RSS about 544 MiB. Build, free disk, and cgroup OOM status remain healthy.
At 2026-10-27 10:43 UTC, Guix ARM64 `wit_parser` compilation remains active; rustc cumulative CPU increased to about 712.4 s with eight threads and about 545 MiB RSS. No OOM events; disk remains at 13 GiB free.
At 2026-10-27 10:44 UTC, the same Guix ARM64 `wit_parser` worker reached about 987.2 s cumulative CPU across eight threads; RSS about 451 MiB. The process remains live; cgroup OOM counters are zero and disk remains stable.
At 2026-10-27 10:44 UTC, Guix ARM64 `wit_parser` rustc remains active; cumulative CPU rose to about 1,383.3 s across eight threads and RSS is about 479 MiB. Build and disk remain healthy with no OOM events.
At 2026-10-27 10:45 UTC, the same Guix ARM64 `wit_parser` compilation reached about 1,681.9 s cumulative rustc CPU with eight threads; RSS remains about 475 MiB. No OOM events and 13 GiB free disk.
At 2026-10-27 10:45 UTC, Guix ARM64 `wit_parser` remains active; rustc cumulative CPU reached about 2,010.1 s with eight threads and about 472 MiB RSS. Cgroup OOM counters remain zero and 13 GiB disk remains free.
At 2026-10-27 10:46 UTC, Guix ARM64 advanced beyond `wit_parser` to compile `clap_derive`; rustc is active at about 127 s and 401 MiB RSS. Disk remains stable at 13 GiB free and OOM counters remain zero.
At 2026-10-27 10:46 UTC, Guix ARM64 advanced past `clap_derive` and `wasm_metadata`; current dependency is `tempfile` v3.20.0, CPU-active at about 106.7 s and 303 MiB RSS. Disk and OOM status remain stable.
At 2026-10-27 10:47 UTC, Guix ARM64 advanced past `tempfile` and is compiling `wit_component` v0.229.0; active rustc reached about 264.6 s CPU and 524 MiB RSS. No OOM events; disk remains at 13 GiB free.
At 2026-10-27 10:48 UTC, Guix ARM64 `wit_component` remains CPU-active; cumulative rustc CPU reached about 611.4 s with eight threads and RSS about 531 MiB. Build, disk, and OOM state remain healthy.
At 2026-10-27 10:48 UTC, Guix ARM64 `wit_component` continued and reached about 902.8 s cumulative rustc CPU with eight threads; RSS about 435 MiB. No OOM events and disk remains at 13 GiB free.
At 2026-10-27 10:49 UTC, Guix ARM64 `wit_component` remains actively compiling; cumulative rustc CPU reached about 1,262.8 s with eight threads and RSS about 467 MiB. Build/disk/OOM state remains stable.
At 2026-10-27 10:49 UTC, Guix ARM64 `wit_component` advanced to about 1,570.4 s cumulative rustc CPU across eight threads; RSS about 468 MiB. No OOM events and 13 GiB disk free.
At 2026-10-27 10:50 UTC, Guix ARM64 `wit_component` remains CPU-active; cumulative rustc CPU reached about 1,997.0 s with eight threads and 470 MiB RSS. Build is live; disk free and OOM counters unchanged.
At 2026-10-27 10:50 UTC, Guix ARM64 completed `wit_component` and its related dependencies (`clap`, `wat`, WASI adapter provider) and is compiling the target tool `wasm-component-ld` v0.5.13; rustc is active at about 52.6 s CPU and 402 MiB RSS. Disk and OOM status remain healthy.
At 2026-10-27 10:51 UTC, Guix ARM64 `wasm-component-ld` v0.5.13 remains CPU-active; cumulative rustc CPU reached about 395.7 s with eight threads and RSS about 336 MiB. No OOM events and 13 GiB disk free.
At 2026-10-27 10:51 UTC, Guix ARM64 finished the optimized `wasm-component-ld` tool build after 26m31s and advanced to tool `llvm-bitcode-linker` (stage1 -> stage2); Cargo is compiling `syn`. No OOM events; 13 GiB disk free.
At 2026-10-27 10:52 UTC, Guix ARM64 stage1 `llvm-bitcode-linker` dependency compilation advanced through `syn`, `utf8parse`, and `tracing-core` to `anstyle_parse`; active rustc is running. Disk remains at 13 GiB free and OOM counters are zero.
At 2026-10-27 10:53 UTC, Guix ARM64 `llvm-bitcode-linker` dependency build advanced to `strsim` after its CLI formatting/logging crates; rustc remains live. Disk stays at 13 GiB free and OOM counters remain zero.
At 2026-10-27 10:54 UTC, Guix ARM64 `llvm-bitcode-linker` dependency build moved from tracing/CLI support crates to `clap_builder`; rustc is active at about 216 s CPU and 476 MiB RSS. Disk and OOM counters remain stable.
At 2026-10-27 10:54 UTC, `clap_builder` in the Guix ARM64 `llvm-bitcode-linker` dependency build remained active and reached about 540 s cumulative CPU across eight threads; RSS about 398 MiB. No OOM events; disk remains at 13 GiB free.
At 2026-10-27 10:55 UTC, `clap_builder` in the Guix ARM64 `llvm-bitcode-linker` dependency graph remains active; cumulative rustc CPU reached about 1,013.9 s across eight threads and RSS about 425 MiB. Disk and OOM counters remain stable.
At 2026-10-27 10:55 UTC, Guix ARM64 advanced from `clap_builder` to `clap_derive` after compiling tracing output crates; active rustc is live. Disk remains at 13 GiB free and OOM counters are zero.
At 2026-10-27 10:56 UTC, Guix ARM64 stage1 `llvm-bitcode-linker` dependencies advanced from `clap_derive` to `tracing`; rustc is active at about 30 s CPU and 328 MiB RSS. Disk remains at 13 GiB free and OOM counters are zero.
At 2026-10-27 10:57 UTC, the Guix ARM64 dependency build advanced from `tracing` to `tracing_subscriber`; rustc is active at about 303 s CPU and 359 MiB RSS. Disk/OOM status unchanged.
At 2026-10-27 10:57 UTC, Guix ARM64 finished the dependency graph (`tracing_subscriber`, `clap`) and is compiling the actual `llvm-bitcode-linker` v0.0.1 tool; rustc is active at about 100 s CPU and 377 MiB RSS. No OOM; 13 GiB disk free.
At 2026-10-27 10:58 UTC, Guix ARM64 finished optimized `llvm-bitcode-linker` after 6m48s, began uplifting the library stage1 -> stage2, and started building stage2 `cargo` (currently compiling libc build script). No OOM; 13 GiB disk free.
At 2026-10-27 10:59 UTC, stage2 `cargo` build is compiling `syn` v2.0.101 after `libc`; active rustc reached about 404.9 s CPU across eight threads and 555 MiB RSS. Disk remains at 13 GiB free and OOM counters are zero.
At 2026-10-27 10:59 UTC, stage2 `cargo` dependency compilation progressed beyond `syn` to `aho_corasick` after `memchr`; active rustc reached about 169.7 s CPU and 416 MiB RSS. OOM counters remain zero; 13 GiB disk free.
At 2026-10-27 11:00 UTC, stage2 `cargo` compilation advanced beyond `aho_corasick` to `regex_syntax` v0.8.5; active rustc is CPU-active at about 125.5 s and 428 MiB RSS. No OOM events and 13 GiB disk free.
At 2026-10-27 11:00 UTC, `regex_syntax` remains in active stage2 compilation; rustc CPU reached about 472.7 s across eight threads and RSS about 446 MiB. Build and disk remain healthy with zero OOM events.
At 2026-10-27 11:01 UTC, stage2 `cargo` build progressed beyond `regex_syntax` to `regex_automata` v0.4.9; active rustc is live at about 104.9 s CPU and 386 MiB RSS. No OOM; disk remains at 13 GiB free.
At 2026-10-27 11:02 UTC, `regex_automata` remains in active stage2 compilation; rustc reached about 391.9 s CPU across eight threads and 530 MiB RSS. Disk and OOM status remain stable.
At 2026-10-27 11:02 UTC, stage2 `regex_automata` remains active; rustc cumulative CPU advanced to about 768.6 s across eight threads and RSS about 474 MiB. No OOM events and 13 GiB disk free.
At 2026-10-27 11:03 UTC, `regex_automata` remains CPU-active in the Guix ARM64 stage2 Cargo build; rustc reached about 1,031.6 s cumulative CPU across eight threads and RSS about 479 MiB. Disk/OOM status remains stable.
At 2026-10-27 11:03 UTC, stage2 Cargo dependency compilation advanced past `regex_automata` to `thiserror`/`thiserror-impl` v2.0.12; active rustc is compiling the derive crate at about 72.7 s CPU and 380 MiB RSS. Disk remains at 13 GiB free; OOM counters zero.
At 2026-10-27 11:04 UTC, stage2 Cargo dependencies progressed to `bstr` v1.12.0 after `version_check` and `smallvec`; active rustc is live at about 137 s CPU and 326 MiB RSS. No OOM and 13 GiB disk free.
At 2026-10-27 11:04 UTC, stage2 `cargo` compilation advanced beyond `bstr` to `serde` v1.0.219; the active rustc process is live at about 58.8 s CPU and 307 MiB RSS. Disk/OOM counters remain stable.
At 2026-10-27 11:05 UTC, stage2 `cargo` dependency build advanced past `serde` to `stable_deref_trait`, `typenum`, and `autocfg`; active rustc is compiling `autocfg` at about 22.7 s CPU and 301 MiB RSS. No OOM; disk free remains 13 GiB.
At 2026-10-27 11:06 UTC, stage2 Cargo dependency build advanced through `zeroize`, `generic-array`, and `subtle` to `tinyvec`; active rustc is live at about 77 s CPU and 352 MiB RSS. Disk/OOM status remains stable.
At 2026-10-27 11:06 UTC, stage2 Cargo dependency compilation advanced beyond `tinyvec` to `crossbeam_utils` after `gix-trace`/Unicode normalization; rustc is active at about 91.6 s CPU and 306 MiB RSS. OOM counters remain zero; 13 GiB disk free.
At 2026-10-27 11:06 UTC, stage2 Cargo dependencies advanced through `crossbeam-utils`, `tinyvec`, `unicode-normalization`, and locking support to `gix-utils`; active rustc is live at about 52 s CPU and 349 MiB RSS. No OOM; disk remains at 13 GiB free.
At 2026-10-27 11:07 UTC, the stage2 Cargo dependency graph advanced past `gix-utils` through `gix-validate`, `home`, and `gix-path`; current rustc is compiling `parking_lot_core`, CPU-active. Disk remains at 13 GiB free and OOM counters zero.
At 2026-10-27 11:07 UTC, stage2 Cargo dependencies progressed through crypto/digest and filesystem helpers to `parking_lot`; its rustc worker is running. Disk and OOM status remain stable.
At 2026-10-27 11:08 UTC, stage2 Cargo dependencies advanced from `parking_lot` through compression/digest helpers to `zlib_rs` v0.5.0; active rustc reached about 221 s CPU and 361 MiB RSS. No OOM; disk remains at 13 GiB free.
At 2026-10-27 11:08 UTC, Cargo stage2 advanced from `zlib_rs` to its native FFI companion `libz_rs_sys` v0.5.0; active rustc is live at about 8.3 s CPU and 176 MiB RSS. Disk/OOM status unchanged.
At 2026-10-27 11:08 UTC, Cargo stage2 dependency resolution advanced beyond `libz-rs-sys` through `jobserver` and started `crc32fast`; current rustc is building the `cc` crate's build script. CPU-active, with no OOM events and 13 GiB disk free.
At 2026-10-27 11:09 UTC, stage2 Cargo dependencies advanced through `cc`, `flate2`, and into `prodash` v29.0.2; rustc is active at about 60.7 s CPU and 366 MiB RSS. Disk remains at 13 GiB free; OOM counters zero.
At 2026-10-27 11:09 UTC, stage2 Cargo dependencies progressed from `prodash` to `crossbeam-channel` and `bytes`; active rustc is compiling `bytes` at about 30 s CPU and 278 MiB RSS. Disk/OOM status unchanged.
At 2026-10-27 11:10 UTC, stage2 Cargo dependencies advanced beyond `bytes` to `gix-features` v0.42.1; active rustc is live at about 20.6 s CPU and 289 MiB RSS. No OOM, 13 GiB disk free.
At 2026-10-27 11:10 UTC, Cargo stage2 progressed through CPU-feature/heapless/hash crates and is compiling `pkg-config` v0.3.32; rustc is active at about 16 s CPU and 246 MiB RSS. Disk/OOM status unchanged.
At 2026-10-27 11:11 UTC, Cargo stage2 advanced beyond `pkg-config` to `zerocopy` v0.8.25 after `faster-hex`/`synstructure`; rustc is active at about 66 s CPU and 328 MiB RSS. No OOM; disk free remains 13 GiB.
At 2026-10-27 11:11 UTC, Cargo stage2 progressed beyond `zerocopy` through `faster-hex`/`synstructure` to `vcpkg` v0.2.15; rustc is live at about 9.4 s CPU and 191 MiB RSS. OOM counters are zero and disk remains at 13 GiB free.
At 2026-10-27 11:11 UTC, Cargo stage2 progressed through `rustix`, `zerofrom-derive`, and `sha1` to `errno`; active rustc reached about 21.9 s CPU and 313 MiB RSS. No OOM and disk remains at 13 GiB free.
At 2026-10-27 11:12 UTC, stage2 Cargo dependency build advanced from `errno` to `linux-raw-sys` and `rustix`; current rustc is compiling `rustix` at about 318 s CPU and 428 MiB RSS. OOM counters remain zero; disk has 13 GiB free.
At 2026-10-27 11:12 UTC, stage2 Cargo dependencies advanced beyond `rustix` to `sha1-checked` v0.10.0; the active rustc worker is live at about 67 s CPU and 294 MiB RSS. No OOM events; disk remains at 13 GiB free.
At 2026-10-27 11:12 UTC, stage2 Cargo dependency build advanced through `zerofrom`, `yoke-derive`, and `ahash` to `winnow` v0.7.10; active rustc reached about 123.5 s CPU and 384 MiB RSS. OOM counters are zero and disk free remains 13 GiB.
At 2026-10-27 11:13 UTC, Cargo stage2 advanced beyond `winnow` through `yoke` and `gix-hash`; it is compiling `zerovec-derive` v0.11.1 with an active rustc process. Disk/OOM status unchanged.
At 2026-10-27 11:13 UTC, Cargo stage2 dependencies advanced beyond `zerovec-derive` through `allocator-api2` to `jiff` v0.2.14; the `jiff` rustc workers are live. No OOM, with 13 GiB disk free.
At 2026-10-27 11:14 UTC, Cargo stage2 `jiff` compilation remains CPU-active; rustc reached about 363.7 s cumulative CPU across eight threads and 579 MiB RSS. No OOM; 13 GiB disk free.
At 2026-10-27 11:14 UTC, the same stage2 `jiff` compile continued to about 637.9 s cumulative rustc CPU across eight threads and 591 MiB RSS. Build is live; disk and OOM status remain stable.
At 2026-10-27 11:15 UTC, stage2 `jiff` remains active; rustc reached about 975.7 s CPU across eight threads and 535 MiB RSS. Available overlay disk is now about 12 GiB (98% used), `/src` remains 13 GiB free, and cgroup OOM counters remain zero.
At 2026-10-27 11:15 UTC, Cargo stage2 advanced beyond the long `jiff` compile to `gix-date` v0.10.2; rustc is active at about 114 s CPU and 377 MiB RSS. Overlay free space is 12 GiB, `/src` free space 13 GiB, and OOM counters zero.
At 2026-10-27 11:16 UTC, Cargo stage2 advanced past `gix-date` through `hashbrown` v0.14.5 and `zerovec` to `getrandom` v0.3.3; active rustc is live at about 27.5 s CPU and 328 MiB RSS. Overlay has 12 GiB free, `/src` 13 GiB, and OOM counters zero.
At 2026-10-27 11:16 UTC, stage2 Cargo progressed through `displaydoc`, `gix-hashtable`, and `gix-actor` to `gix-object` v0.49.1; active rustc reached about 123 s CPU and 447 MiB RSS. No OOM; overlay free space is 12 GiB and `/src` has 13 GiB.
At 2026-10-27 11:17 UTC, Cargo stage2 progressed beyond `gix-object` to native build scripts for `openssl-sys` v0.9.109 and `libz-sys` v1.1.22; active rustc is compiling a build script at about 22.8 s CPU and 267 MiB RSS. No OOM; overlay free space 12 GiB, `/src` 13 GiB.
At 2026-10-27 11:17 UTC, Cargo stage2 passed the OpenSSL/zlib build-script steps and is compiling ICU locale dependencies (`icu_locale_core` v2.0.0); active rustc reached about 126.5 s CPU and 365 MiB RSS. OOM remains zero; 12 GiB overlay and 13 GiB `/src` space free.
At 2026-10-27 11:18 UTC, stage2 Cargo progressed beyond `icu_locale_core` through `zerotrie`, `potential_utf`, and ICU data crates to `icu_collections`; active rustc is live at about 80.5 s CPU and 299 MiB RSS. Overlay space remains 12 GiB free, `/src` 13 GiB, OOM counters zero.
At 2026-10-27 11:19 UTC, Cargo stage2 advanced through `icu_provider` and `tempfile` to `gix-fs` v0.15.0; active rustc reached about 67.1 s CPU and 308 MiB RSS. Overlay free remains 12 GiB, `/src` 13 GiB, with no OOM events.
At 2026-10-27 11:19 UTC, stage2 Cargo advanced from `gix-fs` through `gix-chunk` to `gix-tempfile` v17.1.0; active rustc reached about 33.3 s CPU and 356 MiB RSS. Overlay has 12 GiB free, `/src` 13 GiB, and OOM counters zero.
At 2026-10-27 11:19 UTC, stage2 Cargo advanced through `gix-tempfile` and `icu_normalizer` to `icu_properties` v2.0.1; active rustc reached about 110.8 s CPU and 383 MiB RSS. OOM counters remain zero; overlay space remains 12 GiB.
At 2026-10-27 11:20 UTC, stage2 Cargo advanced through `gix-quote`, `getrandom` v0.2.16, `idna_adapter`, and `libnghttp2-sys` to `utf8_iter`; active rustc is running. Disk and OOM status remain stable.
At 2026-10-27 11:20 UTC, Cargo stage2 progressed past `utf8_iter` to `idna` v1.0.3; active rustc reached about 86.6 s CPU and 372 MiB RSS. Overlay has 12 GiB free, `/src` 13 GiB, and cgroup OOM counters zero.
At 2026-10-27 11:20 UTC, Cargo stage2 advanced beyond URL/IDNA and random-core dependencies to `gix-commitgraph` v0.28.0; active rustc reached about 71.8 s CPU and 386 MiB RSS. No OOM; overlay free space remains 12 GiB.
At 2026-10-27 11:21 UTC, stage2 Cargo advanced past `gix-commitgraph`/`gix-revwalk` to `url` v2.5.4; active rustc reached about 184.4 s CPU and 332 MiB RSS. Overlay has 12 GiB free, `/src` 13 GiB; OOM counters remain zero.
At 2026-10-27 11:21 UTC, Cargo stage2 advanced beyond `url` to `gix-lock` v17.1.0; active rustc reached about 27 s CPU and 354 MiB RSS. Overlay has 12 GiB free, `/src` 13 GiB, with zero OOM events.
At 2026-10-27 11:22 UTC, Guix ARM64 stage2 Cargo advanced beyond `gix-lock` to `curl-sys`, `base64ct`, `pem-rfc7468`, `gix-glob`, and `gix-config-value`; rustc workers remain live. Overlay has 12 GiB free, `/src` 13 GiB, and cgroup OOM counters remain zero.
At 2026-10-27 11:22 UTC, the live Guix ARM64 stage2 Cargo build advanced beyond `gix-config-value` to `unicode-bom` and `der`; rustc reached about 145 s CPU and 405 MiB RSS. Overlay has 12 GiB free, `/src` 13 GiB, and cgroup OOM counters remain zero.
At 2026-10-27 11:24 UTC, the Guix ARM64 stage2 dependency build advanced to `gix-command` v0.6.1 after compiling `serde_json`, `libssh2-sys`, and related dependencies. Active rustc reached about 2,650 CPU ticks and 344 MiB RSS; OOM counters remain zero and 12 GiB overlay/13 GiB `/src` space remains free.
At 2026-10-27 11:26 UTC, stage2 Cargo advanced beyond the stalled-looking crypto dependency batch to `pkcs8` and `gix-attributes`; active AArch64 rustc has about 1,060 CPU ticks and 393 MiB RSS. The cargo process is still live, the build has no exit marker, and cgroup OOM counters remain zero.
At 2026-10-27 11:26 UTC, Guix ARM64 stage2 Cargo advanced to `gix-ref` v0.52.1 after `gix-attributes`; its rustc worker reached about 194 s CPU and 458 MiB RSS. Cargo remains live, no exit marker is present, and OOM counters remain zero.
At 2026-10-27 11:27 UTC, stage2 Cargo advanced from `gix-ref`/`ff` to `tracing-core` v0.1.33; rustc worker is live at roughly 30 CPU ticks and 80 MiB RSS. Guix and Cargo remain active, OOM counters are zero, and disk availability is unchanged.
At 2026-10-27 11:28 UTC, Guix ARM64 Cargo advanced beyond `tracing-core` to file/time, socket, and elliptic-curve crates (`filetime`, `socket2`, `base16ct`, `sec1`). Active rustc reached about 66 s CPU and 293 MiB RSS. No exit marker or OOM event; free disk remains 12 GiB on overlay and 13 GiB on `/src`.
At 2026-10-27 11:28 UTC, the Guix ARM64 stage2 graph advanced through `group`, `hkdf`, and `gix-url` v0.31.0; current rustc worker is live at about 36 s CPU and 348 MiB RSS. Build remains active with zero OOM events.
At 2026-10-27 11:29 UTC, stage2 Cargo advanced from `gix-url` to `crypto-bigint` v0.5.5; AArch64 rustc is active at about 226 s CPU and 369 MiB RSS. Cargo/Guix remain live; no OOM events.
At 2026-10-27 11:29 UTC, the Guix ARM64 dependency graph progressed through `crypto-bigint` to native `libgit2-sys` v0.18.1, `num-traits`, and tracing/format support crates. Current rustc is active at about 44 s CPU and 299 MiB RSS; memory and disk health remain stable.
At 2026-10-27 11:31 UTC, while Cargo's log remained on `libgit2-sys`, process inspection found its live `libgit2-sys` build script compiling bundled C with AArch64 `gcc`/`cc1` under QEMU (about 28 CPU ticks, 50 MiB RSS). The stage is active despite no new Cargo progress line; no OOM event.
At 2026-10-27 11:31 UTC, `libgit2-sys` remains in its C build phase; a fresh `cc1` process is actively compiling under QEMU. The parent Cargo job remains live; OOM counters are zero.
At 2026-10-27 11:32 UTC, the `libgit2-sys` build script is still compiling C sources; a live `cc1` worker accumulated CPU time under QEMU, with no OOM events. Cargo has not emitted the next crate completion yet.
At 2026-10-27 11:33 UTC, the live AArch64 `cc1` worker for `libgit2-sys` has advanced to about 84 CPU ticks and 93 MiB RSS; its C build script and Cargo parent remain active. OOM counters remain zero and free space is unchanged.
At 2026-10-27 11:34 UTC, the `libgit2-sys` C build under QEMU started another substantial `cc1` compile, now about 420 CPU ticks and 166 MiB RSS. Build script and Cargo are alive; no OOM events.
At 2026-10-27 11:34 UTC, `libgit2-sys` is still in bundled C compilation; the current AArch64 `cc1` worker has about 313 CPU ticks and 163 MiB RSS. Cargo and the crate build script remain active. OOM counters are zero.
At 2026-10-27 11:35 UTC, the live `libgit2-sys` AArch64 C compile continues under QEMU; current `cc1` is at about 234 CPU ticks and 147 MiB RSS. No failure/exit marker or OOM event.
At 2026-10-27 11:36 UTC, the `libgit2-sys` bundled C build had produced 136 object files in its AArch64 output directory (up from 120 at the prior poll); `cc1` remains active. This confirms ongoing compile progress. No OOM events; Cargo remains live.
At 2026-10-27 11:36 UTC, the `libgit2-sys` AArch64 output advanced from 136 to 151 object files; `cc1` is still compiling. Cargo remains active, with zero OOM events.
At 2026-10-27 11:37 UTC, the bundled `libgit2-sys` AArch64 build reached 163 object files, up from 151; the current `cc1` worker is active at about 75 CPU ticks/90 MiB RSS. OOM counters remain zero.
At 2026-10-27 11:37 UTC, the same live Guix `libgit2-sys` build advanced from 163 to 168 AArch64 object files; active `cc1` is at about 181 CPU ticks and 117 MiB RSS. No OOM events; overlay and `/src` free space remain 12 GiB and 13 GiB respectively.
At 2026-10-27 11:37 UTC, Guix ARM64 `libgit2-sys` reached 176 generated objects, up from 168; its active `cc1` worker is at about 82 CPU ticks and 94 MiB RSS. Build remains live and OOM-free.
At 2026-10-27 11:38 UTC, `libgit2-sys` advanced from 176 to 198 AArch64 objects and Cargo resumed Rust dependency compilation (`elliptic-curve` v0.13.8); active rustc reached about 308 CPU ticks/299 MiB RSS. Cargo remains live; no OOM events.
At 2026-10-27 11:38 UTC, after producing 198 bundled libgit2 objects, stage2 Cargo moved on through `elliptic-curve`, `gix-prompt`, `gix-revision`, `gix-traverse`, and `gix-bitmap`; active AArch64 rustc is at about 252 CPU ticks/325 MiB RSS. OOM counters remain zero.
At 2026-10-27 11:39 UTC, Guix ARM64 stage2 Cargo progressed beyond the `gix-*` crates to `num-conv`, `fnv`, `time-core`, and `equivalent`; current rustc reached about 2,349 CPU ticks and 382 MiB RSS. No OOM; build remains active.
At 2026-10-27 11:39 UTC, stage2 Cargo advanced to `regex-syntax` v0.6.29; active AArch64 rustc reached about 3,209 CPU ticks and 482 MiB RSS. Cargo remains live, OOM counters zero, with 12 GiB overlay and 13 GiB `/src` space free.
At 2026-10-27 11:40 UTC, the long `regex-syntax` stage completed and Cargo advanced to `regex-automata` v0.1.10; active rustc is live at about 187 CPU ticks and 246 MiB RSS. Guix build remains active with no OOM events.
At 2026-10-27 11:41 UTC, the active `regex-automata` AArch64 rustc worker accumulated about 3,248 CPU ticks and 348 MiB RSS while Cargo continued the stage2 build. No OOM events; the compile is CPU-active.
At 2026-10-27 11:41 UTC, Cargo advanced beyond `regex-automata` to `indexmap` v2.9.0 and `time` v0.3.41; active AArch64 rustc is at about 1,955 CPU ticks and 459 MiB RSS. No OOM events; stage2 build remains live.
At 2026-10-27 11:42 UTC, the current AArch64 rustc worker for the stage2 dependency batch continued CPU-active to about 5,124 CPU ticks and 389 MiB RSS; Cargo still reports `indexmap`/`time` compiling. The process is live and OOM counters remain zero.
At 2026-10-27 11:42 UTC, stage2 Cargo progressed to `gix-index` v0.40.1 after the `indexmap`/`time` batch; active AArch64 rustc is at about 2,397 CPU ticks and 458 MiB RSS. OOM counters remain zero.
At 2026-10-27 11:43 UTC, Guix ARM64 stage2 Cargo advanced beyond `gix-index` to `gix-refspec` v0.30.1; active rustc is at about 252 CPU ticks and 315 MiB RSS. Build is live, OOM counters zero.
At 2026-10-27 11:43 UTC, stage2 Cargo moved from `gix-refspec` to `gix-credentials` v0.29.0; its AArch64 rustc worker is live at about 60 CPU ticks and 110 MiB RSS. OOM counters remain zero.
At 2026-10-27 11:44 UTC, Guix ARM64 Cargo remains on `gix-credentials` v0.29.0; its active rustc worker advanced to about 95 CPU ticks and 189 MiB RSS. Build remains live, with zero OOM events and 12 GiB/13 GiB free on overlay/`/src`.
At 2026-10-27 11:44 UTC, Cargo moved beyond `gix-credentials` to `gix-pathspec` v0.11.0 and `rfc6979` v0.4.0; active rustc is at about 177 CPU ticks and 247 MiB RSS. No OOM events.
At 2026-10-27 11:45 UTC, Cargo advanced through `gix-ignore`, `signature`, `terminal_size`, and into native `libsqlite3-sys` v0.32.0, alongside `gix-packetline`/`sha2`; active rustc reached about 834 CPU ticks and 297 MiB RSS. No OOM events.
At 2026-10-27 11:45 UTC, the stage2 graph advanced from `sha2` to `crossbeam-epoch`, TOML, and `regex` crates; `libsqlite3-sys` remains in the active set. Current rustc reached about 1,622 CPU ticks/322 MiB RSS, with zero OOM events.
At 2026-10-27 11:46 UTC, the Guix ARM64 stage2 build advanced through `base64`, `clru`, `toml_write`, `minimal-lexical`, and `semver` to `clap_builder` v4.5.39; active rustc is at about 225 CPU ticks/247 MiB RSS. No OOM events.
At 2026-10-27 11:46 UTC, `clap_builder` is CPU-active under AArch64 rustc at about 3,536 CPU ticks and 483 MiB RSS; Cargo has not emitted its completion yet. The build remains live without OOM events.
At 2026-10-27 11:47 UTC, the `clap_builder` compile continued CPU-active to about 6,826 rustc CPU ticks and 432 MiB RSS. Cargo remains alive and no OOM events have occurred.
At 2026-10-27 11:47 UTC, `clap_builder` remained the active Rust compile and reached about 10,191 CPU ticks across eight threads, RSS about 428 MiB. No OOM events; process remains live.
At 2026-10-27 11:48 UTC, Cargo completed the long `clap_builder` stage and advanced through `nom` to `toml_edit` v0.22.26; the active AArch64 rustc worker is at about 685 CPU ticks/343 MiB RSS. Build remains live, OOM counters zero.
At 2026-10-27 11:49 UTC, the active `toml_edit` AArch64 rustc compile continued to about 4,646 CPU ticks and 460 MiB RSS; Cargo has not yet emitted the next completion. No OOM events.
At 2026-10-27 11:49 UTC, `toml_edit` remains CPU-active and its rustc worker has reached about 7,867 CPU ticks; RSS is about 392 MiB. No exit marker or OOM event.
At 2026-10-27 11:50 UTC, Cargo completed `toml_edit` and advanced to `gix-pack` v0.59.1; active AArch64 rustc reached about 1,852 CPU ticks/477 MiB RSS. OOM counters remain zero.
At 2026-10-27 11:50 UTC, `gix-pack` remains the active Rust compile; its AArch64 rustc worker advanced to about 5,072 CPU ticks/396 MiB RSS. Cargo and Guix remain live, OOM counters zero.
At 2026-10-27 11:51 UTC, `gix-pack` compilation continued CPU-active to about 8,314 AArch64 rustc CPU ticks and 405 MiB RSS. No OOM events; the build is still live.
At 2026-10-27 11:51 UTC, Cargo advanced from `gix-pack` to `gix-transport` v0.47.0; active AArch64 rustc is at about 3,126 CPU ticks and 346 MiB RSS. OOM counters remain zero.
At 2026-10-27 11:51 UTC, the active `gix-transport` AArch64 rustc worker continued compiling to about 4,172 CPU ticks and 347 MiB RSS. Cargo and Guix remain live; OOM counters zero.
At 2026-10-27 11:52 UTC, process inspection identified the long native compile as bundled SQLite (`sqlite3/sqlite3.c`) for `libsqlite3-sys`; AArch64 `cc1` is active at about 1,466 CPU ticks and 322 MiB RSS. Cargo also advanced to `crossbeam-deque`; OOM counters remain zero.
At 2026-10-27 11:53 UTC, the SQLite amalgamation compile (`sqlite3.c`) continued to about 5,534 CPU ticks and 512 MiB RSS under QEMU; Cargo's log shows `crossbeam-deque` next. No OOM events.
At 2026-10-27 11:53 UTC, `sqlite3.c` remains actively compiling and its AArch64 `cc1` worker reached about 8,806 CPU ticks/531 MiB RSS. The cgroup still reports zero OOM events; build stays live.
At 2026-10-27 11:54 UTC, the SQLite amalgamation compile reached about 12,074 CPU ticks and 547 MiB RSS. It remains CPU-active; cgroup OOM counters remain zero and Cargo has not exited.
At 2026-10-27 11:54 UTC, `sqlite3.c` AArch64 compilation advanced to about 13,077 CPU ticks and 529 MiB RSS under QEMU. The compile remains active, with no OOM or exit marker; free disk is unchanged.
At 2026-10-27 11:54 UTC, the SQLite amalgamation compiler reached about 16,322 CPU ticks and 532 MiB RSS. The same `cc1` process is CPU-active; no OOM events.
At 2026-10-27 11:55 UTC, SQLite's single amalgamation compile reached about 19,630 CPU ticks and 521 MiB RSS, still CPU-active. The Guix job remains live and OOM counters are zero.
At 2026-10-27 11:56 UTC, bundled `sqlite3.c` compilation remains active and reached about 22,920 CPU ticks/530 MiB RSS. The same Guix/Cargo job persists; OOM counters are zero.
At 2026-10-27 11:56 UTC, the SQLite C translation unit reached about 26,051 CPU ticks and 534 MiB RSS. It remains CPU-active; no OOM events.
At 2026-10-27 11:57 UTC, the long SQLite native compile completed and stage2 Cargo advanced to Rust crates `ecdsa` v0.16.9 and `gix-worktree` v0.41.0; active AArch64 rustc is at about 527 CPU ticks/385 MiB RSS. No OOM events.
At 2026-10-27 11:57 UTC, after SQLite, stage2 Cargo advanced through `tar` v0.4.44 and `erased-serde` v0.4.6; active rustc reached about 717 CPU ticks/349 MiB RSS. Build remains live and OOM-free.
At 2026-10-27 11:58 UTC, Cargo advanced through `ordered-float`, `matchers`, `primeorder`, and `tracing-log` to `gix-config` v0.45.1; active AArch64 rustc is at about 1,453 CPU ticks and 469 MiB RSS. No OOM events.
At 2026-10-27 11:58 UTC, the active `gix-config` compile continued to about 4,775 AArch64 rustc CPU ticks and 358 MiB RSS. Cargo/Guix remain live; no OOM events.
At 2026-10-27 11:59 UTC, stage2 Cargo advanced beyond `gix-config` to `gix-discover` v0.40.1 and `gix-shallow` v0.4.0; active rustc is at about 254 CPU ticks/369 MiB RSS. No OOM events.
At 2026-10-27 11:59 UTC, Cargo continued through `gix-negotiate`, `rand_core`, and `ppv-lite86` to `gix-packetline-blocking` v0.19.0; active AArch64 rustc is at about 522 CPU ticks/302 MiB RSS. OOM counters remain zero.
At 2026-10-27 12:00 UTC, stage2 Cargo advanced beyond `gix-packetline-blocking` to `blake3` v1.8.2 and `globset` v0.4.16; active AArch64 rustc is at about 771 CPU ticks/381 MiB RSS. OOM counters remain zero and disk availability is unchanged.
At 2026-10-27 12:00 UTC, Cargo advanced to `bitmaps` v2.1.0 after `blake3`/`globset`; active rustc is at about 725 CPU ticks/286 MiB RSS. The Guix job remains live and OOM-free.
At 2026-10-27 12:01 UTC, stage2 Cargo advanced through `thread_local`, `im-rc`, and `encoding_rs` v0.8.35; active AArch64 rustc reached about 2,215 CPU ticks/367 MiB RSS. No OOM events.
At 2026-10-27 12:01 UTC, Cargo progressed beyond `encoding_rs` to `maybe-async` and `arc-swap` v1.7.1; active rustc is at about 398 CPU ticks/337 MiB RSS. Build remains active without OOM events.
At 2026-10-27 12:01 UTC, Guix ARM64 Cargo advanced beyond `arc-swap` to `fiat-crypto` v0.2.9; active AArch64 rustc is at about 1,088 CPU ticks/353 MiB RSS. No OOM events; container resources remain stable.
At 2026-10-27 12:02 UTC, stage2 Cargo advanced to `orion` v0.17.10 after `fiat-crypto`; the active AArch64 rustc worker is at about 570 CPU ticks/296 MiB RSS. Build remains live, OOM counters zero.
At 2026-10-27 12:03 UTC, `orion` v0.17.10 remains CPU-active under AArch64 rustc at about 3,752 CPU ticks/375 MiB RSS. No OOM events; Cargo remains live.
At 2026-10-27 12:03 UTC, Cargo advanced beyond `orion` to `gix-odb` v0.69.1; its active rustc worker is at about 1,916 CPU ticks/456 MiB RSS. Build remains alive and OOM-free.
At 2026-10-27 12:03 UTC, `gix-odb` v0.69.1 AArch64 rustc remains active and reached about 3,214 CPU ticks/361 MiB RSS. Cargo/Guix are still live; cgroup OOM counters are zero.
At 2026-10-27 12:04 UTC, stage2 Cargo advanced from `gix-odb` to `gix-protocol` v0.50.1; active AArch64 rustc is at about 1,047 CPU ticks/445 MiB RSS. No OOM events; build is live.
At 2026-10-27 12:05 UTC, Cargo moved beyond `gix-protocol` to `gix-filter` v0.19.2; active AArch64 rustc is at about 1,267 CPU ticks/416 MiB RSS. The bootstrap remains active and OOM-free.
At 2026-10-27 12:05 UTC, Cargo advanced beyond `gix-filter` to `tracing-subscriber` v0.3.19; the active AArch64 rustc worker is at about 772 CPU ticks/368 MiB RSS. OOM counters remain zero.
At 2026-10-27 12:06 UTC, `tracing-subscriber` remains CPU-active under AArch64 rustc at about 3,949 CPU ticks/394 MiB RSS. Cargo and Guix remain live; OOM counters zero.
At 2026-10-27 12:06 UTC, Cargo advanced past `tracing-subscriber` to `sized-chunks` v0.6.5 and `ignore` v0.4.23; active AArch64 rustc is at about 464 CPU ticks/350 MiB RSS. OOM remains zero.
At 2026-10-27 12:07 UTC, the `ignore` v0.4.23 dependency remains CPU-active under AArch64 rustc at about 3,846 CPU ticks and 348 MiB RSS; the Cargo process remains live and OOM counters are zero.
At 2026-10-27 12:07 UTC, the active `ignore` v0.4.23 AArch64 rustc worker accumulated to about 5,038 CPU ticks and 349 MiB RSS. The same Guix/Cargo processes remain live; OOM counters are zero.
At 2026-10-27 12:08 UTC, Cargo advanced beyond `ignore` to `rand_chacha` v0.9.0 and `gix-dir` v0.14.1; active AArch64 rustc is at about 675 CPU ticks/398 MiB RSS. No OOM events.
At 2026-10-27 12:08 UTC, stage2 Cargo advanced to `gix-submodule` v0.19.1 and `p384` v0.13.1; the current AArch64 rustc worker is at about 288 CPU ticks/277 MiB RSS. Build remains live and OOM-free.
At 2026-10-27 12:09 UTC, the active `p384` v0.13.1 AArch64 compile reached about 3,549 CPU ticks/337 MiB RSS. No OOM events; Cargo remains live.
At 2026-10-27 12:09 UTC, Cargo's AArch64 bootstrap reached the `cargo` v0.90.0 crate itself and `git2` v0.20.2 after `p384`/serde support; active rustc is at about 867 CPU ticks/374 MiB RSS. This is the Cargo tool build phase; no OOM events.
At 2026-10-27 12:10 UTC, the `cargo` v0.90.0 AArch64 crate compile is CPU-active at about 4,280 rustc CPU ticks and 524 MiB RSS; `git2` remains in the build graph. No OOM events.
At 2026-10-27 12:10 UTC, the `cargo` v0.90.0 compile continued to about 7,576 AArch64 rustc CPU ticks/462 MiB RSS. The build remains CPU-active with zero OOM events.
At 2026-10-27 12:11 UTC, Cargo's dependency build advanced to `toml` v0.8.22 while building Cargo v0.90.0; active AArch64 rustc is at about 104 CPU ticks/201 MiB RSS. No OOM events.
At 2026-10-27 12:11 UTC, the Rust tool bootstrap advanced through `toml`/`clap` and started `cargo-credential` v0.4.8 as part of Cargo v0.90.0; active AArch64 rustc is at about 1,473 CPU ticks/322 MiB RSS. No OOM events.
At 2026-10-27 12:12 UTC, Cargo's dependency graph advanced beyond `cargo-credential` to `hashlink`, `rand_xoshiro`, and `ed25519-compact`; active AArch64 rustc is at about 891 CPU ticks/297 MiB RSS. No OOM events.
At 2026-10-27 12:12 UTC, the Cargo v0.90.0 graph advanced to `gix-diff` v0.52.1, `libloading` v0.8.8, and `hex` v0.4.3; active AArch64 rustc is at about 159 CPU ticks/252 MiB RSS. OOM counters remain zero.
At 2026-10-27 12:13 UTC, Cargo advanced through Unicode, streaming iterator, shell-escape, `either`, and `ct-codecs` dependencies; active AArch64 rustc is at about 280 CPU ticks/304 MiB RSS. Bootstrap remains live and OOM-free.
At 2026-10-27 12:14 UTC, stage2 Cargo advanced through `arrayvec` to `clap_complete` v4.5.52; active AArch64 rustc is at about 2,466 CPU ticks/407 MiB RSS. No OOM events.
At 2026-10-27 12:14 UTC, the `clap_complete` v4.5.52 compile remained CPU-active and reached about 5,577 AArch64 rustc CPU ticks/345 MiB RSS. Cargo is live; OOM counters remain zero.
At 2026-10-27 12:15 UTC, Cargo advanced from `clap_complete` to `pasetors` v0.7.4; active AArch64 rustc is at about 1,597 CPU ticks/426 MiB RSS. No OOM events.
At 2026-10-27 12:15 UTC, the `pasetors` v0.7.4 AArch64 compile continued CPU-active to about 4,829 rustc CPU ticks and 340 MiB RSS. The Guix Cargo build remains live, with zero OOM events.
At 2026-10-27 12:16 UTC, Cargo advanced to `rusqlite` v0.34.0 after `pasetors`; active AArch64 rustc is at about 2,448 CPU ticks/351 MiB RSS. The native SQLite dependency was built earlier in this graph; current stage remains OOM-free.
At 2026-10-27 12:16 UTC, stage2 Cargo reached `cargo-util` v0.2.22 after `itertools`, while compiling Cargo v0.90.0; active AArch64 rustc is at about 1,103 CPU ticks/404 MiB RSS. No OOM events.
At 2026-10-27 12:17 UTC, the Cargo bootstrap advanced beyond `cargo-util` to `cargo-util-schemas` v0.9.0; active AArch64 rustc is at about 1,311 CPU ticks/434 MiB RSS. Build remains live with no OOM events.
At 2026-10-27 12:17 UTC, Cargo's tool graph advanced to `annotate-snippets` v0.11.5; active AArch64 rustc is at about 1,996 CPU ticks/311 MiB RSS. The bootstrap remains live with zero OOM events.
At 2026-10-27 12:18 UTC, the Cargo tool graph advanced through `cargo-credential-libsecret` v0.5.0 to `gix` v0.72.1; active AArch64 rustc is at about 1,500 CPU ticks/461 MiB RSS. No OOM events.
At 2026-10-27 12:18 UTC, the `gix` v0.72.1 Rust compile for Cargo reached about 5,018 CPU ticks and 642 MiB RSS; the worker remains CPU-active. Cgroup OOM counters remain zero.
At 2026-10-27 12:19 UTC, `gix` v0.72.1 remains the long active crate compile and reached about 8,130 CPU ticks/647 MiB RSS. No OOM events; bootstrap process remains live.
At 2026-10-27 12:20 UTC, the `gix` AArch64 rustc worker advanced to about 11,382 CPU ticks; RSS is about 537 MiB. Cargo remains active and OOM counters are zero.
At 2026-10-27 12:20 UTC, `gix` compilation continued to about 14,485 AArch64 rustc CPU ticks/558 MiB RSS. No OOM events; no Cargo exit marker.
At 2026-10-27 12:21 UTC, the same `gix` crate compile reached about 17,639 CPU ticks and 561 MiB RSS. It remains active under QEMU with zero OOM events.
At 2026-10-27 12:21 UTC, the `gix` v0.72.1 compile remains CPU-active and reached about 18,541 AArch64 rustc CPU ticks/549 MiB RSS. No OOM events; Cargo remains live.
At 2026-10-27 12:21 UTC, `gix` v0.72.1 reached about 21,641 rustc CPU ticks/560 MiB RSS and remains CPU-active. No OOM events or Cargo exit.
At 2026-10-27 12:22 UTC, process inspection showed the active AArch64 rustc worker compiling `im_rc` (CPU about 256 ticks/244 MiB RSS), following the long `gix` worker; the log has not yet emitted its next completion line. Cargo remains live and OOM counters are zero.
At 2026-10-27 12:22 UTC, Cargo emitted completion beyond `gix` and advanced through `color-print`, `git2-curl`, and `rand` to `tracing-chrome` v0.7.2; active AArch64 rustc is at about 167 CPU ticks/276 MiB RSS. No OOM events.
At 2026-10-27 12:23 UTC, the Cargo v0.90.0 build advanced through `rustfix` v0.9.1 to its `crates-io` v0.40.12 component; active AArch64 rustc is at about 1,265 CPU ticks/400 MiB RSS. No OOM events.
At 2026-10-27 12:23 UTC, `crates-io` v0.40.12 remains in the Cargo v0.90.0 graph; active AArch64 rustc reached about 2,313 CPU ticks and 336 MiB RSS. Cargo remains live and OOM counters are zero.
At 2026-10-27 12:24 UTC, Cargo advanced to `os_info` v3.11.0 after the `crates-io` crate; active AArch64 rustc is at about 219 CPU ticks/280 MiB RSS. No OOM events; bootstrap remains live.
At 2026-10-27 12:24 UTC, the Cargo build advanced through `cargo-platform`, `serde_ignored`, `opener`, and `http-auth`; active AArch64 rustc is at about 312 CPU ticks/336 MiB RSS. No OOM events.
At 2026-10-27 12:25 UTC, Cargo advanced through `supports-hyperlinks`, `glob`, and Rust hash/path helper crates; active AArch64 rustc is at about 274 CPU ticks/306 MiB RSS. OOM counters remain zero.
At 2026-10-27 12:25 UTC, Cargo advanced to `supports-unicode` v3.0.0; the active AArch64 rustc worker is at about 2,667 CPU ticks and 684 MiB RSS. OOM counters remain zero.
At 2026-10-27 12:26 UTC, `supports-unicode` remains CPU-active and has reached about 5,809 AArch64 rustc CPU ticks/855 MiB RSS. Memory cgroup OOM counters remain zero; build is live.
At 2026-10-27 12:27 UTC, `supports-unicode` reached about 12,250 AArch64 rustc CPU ticks and 1.26 GiB RSS; it remains CPU-active. Container memory cgroup has no configured hard limit, current group use is about 4.3 GiB, and OOM counters are zero.
At 2026-10-27 12:27 UTC, the `supports-unicode` AArch64 compile continued to about 15,418 CPU ticks and 1.55 GiB RSS; it remains CPU-active with no OOM events.
At 2026-10-27 12:28 UTC, `supports-unicode` remains CPU-active at about 18,712 AArch64 rustc CPU ticks and 1.55 GiB RSS; no cgroup OOM events.
At 2026-10-27 12:28 UTC, the `supports-unicode` AArch64 compile continued to about 21,972 CPU ticks/1.56 GiB RSS. It remains active, and cgroup OOM counters are still zero.
At 2026-10-27 12:29 UTC, the `supports-unicode` compile reached about 25,142 CPU ticks and 1.57 GiB RSS; still CPU-active, with no OOM events.
At 2026-10-27 12:30 UTC, the `supports-unicode` Rust compile reached about 28,263 CPU ticks and 1.59 GiB RSS, remaining CPU-active. No OOM events; Cargo is still alive.
At 2026-10-27 12:30 UTC, `supports-unicode` reached about 31,680 AArch64 rustc CPU ticks and 1.61 GiB RSS, with the worker still CPU-active. OOM counters remain zero.
At 2026-10-27 12:30 UTC, `supports-unicode` remained active at about 32,719 AArch64 rustc CPU ticks and 1.61 GiB RSS. Guix/Cargo are live; OOM counters are zero and disk availability unchanged.
At 2026-10-27 12:31 UTC, `supports-unicode` advanced to about 36,111 rustc CPU ticks and 1.61 GiB RSS, still CPU-active. No OOM events.
At 2026-10-27 12:31 UTC, `supports-unicode` continued compiling to about 39,273 AArch64 rustc CPU ticks and 1.61 GiB RSS; process remains active, no OOM events.
At 2026-10-27 12:32 UTC, `supports-unicode` reached about 42,408 AArch64 rustc CPU ticks/1.61 GiB RSS and remains CPU-active. No OOM events.
At 2026-10-27 12:32 UTC, `supports-unicode` continued to about 45,835 AArch64 rustc CPU ticks and 1.61 GiB RSS. It remains active, with no cgroup OOM events.
At 2026-10-27 12:33 UTC, `supports-unicode` continued to about 49,172 AArch64 rustc CPU ticks and 1.62 GiB RSS, still CPU-active. OOM counters remain zero.
At 2026-10-27 12:34 UTC, `supports-unicode` reached about 52,518 AArch64 rustc CPU ticks/1.62 GiB RSS and remains CPU-active; no OOM events.
At 2026-10-27 12:34 UTC, `supports-unicode` reached about 55,848 AArch64 rustc CPU ticks/1.63 GiB RSS; it remains active and OOM counters remain zero.
At 2026-10-27 12:35 UTC, the `supports-unicode` compile reached about 59,026 AArch64 rustc CPU ticks and 1.65 GiB RSS; it remains CPU-active with no OOM events.
At 2026-10-27 12:35 UTC, `supports-unicode` reached about 62,293 AArch64 rustc CPU ticks/1.66 GiB RSS, remaining CPU-active. No OOM events.
At 2026-10-27 12:36 UTC, `supports-unicode` remained CPU-active and reached about 65,361 AArch64 rustc CPU ticks/1.71 GiB RSS. OOM counters remain zero.
At 2026-10-27 12:36 UTC, the `supports-unicode` AArch64 compile advanced to about 68,562 CPU ticks/1.71 GiB RSS; still CPU-active with no OOM events.
At 2026-10-27 12:37 UTC, `supports-unicode` reached about 71,774 AArch64 rustc CPU ticks and 1.71 GiB RSS. The worker remains CPU-active; cgroup OOM counters remain zero.
At 2026-10-27 12:37 UTC, the `supports-unicode` compile advanced to about 75,067 AArch64 rustc CPU ticks/1.71 GiB RSS and remains CPU-active. OOM counters remain zero.
At 2026-10-27 12:38 UTC, `supports-unicode` reached about 76,185 AArch64 rustc CPU ticks and 1.71 GiB RSS; the same worker remains active. No OOM events and disk availability is unchanged.
At 2026-10-27 12:38 UTC, the `supports-unicode` AArch64 compile advanced to about 79,412 rustc CPU ticks/1.72 GiB RSS; still CPU-active, with OOM counters zero.
At 2026-10-27 12:39 UTC, `supports-unicode` remained active and reached about 82,762 AArch64 rustc CPU ticks/1.72 GiB RSS. OOM counters remain zero.
At 2026-10-27 12:39 UTC, `supports-unicode` advanced to about 86,060 AArch64 rustc CPU ticks; RSS fluctuated down to 1.56 GiB while the worker remained active. No OOM events.
At 2026-10-27 12:40 UTC, the same `supports-unicode` compile reached about 89,338 AArch64 rustc CPU ticks/1.52 GiB RSS and remains active. No OOM events.
At 2026-10-27 12:40 UTC, `supports-unicode` reached about 92,451 AArch64 rustc CPU ticks and 1.66 GiB RSS; the worker remains CPU-active and OOM counters are zero.
At 2026-10-27 12:41 UTC, `supports-unicode` reached about 95,617 AArch64 rustc CPU ticks; RSS fluctuated down to 1.57 GiB. The compile remains active, no OOM events.
At 2026-10-27 12:41 UTC, `supports-unicode` reached about 96,504 AArch64 rustc CPU ticks and 1.57 GiB RSS; worker remains active, with zero OOM events.
At 2026-10-27 12:43 UTC, the live Guix ARM64 Rust 1.89 bootstrap (`jarvis-guix-rust190-resumed4`) remains in the Cargo tools stage. `supports-unicode` rustc advanced from about 101,317 to 107,862 CPU ticks in roughly one minute, with about 1.57 GiB RSS; cgroup OOM counters remain zero and `/src` has 13 GiB free.
At 2026-10-27 12:44 UTC, the same live Guix ARM64 bootstrap advanced to about 114,701 rustc CPU ticks (roughly +6,800 since 12:43); `supports-unicode` is still compiling at about 1.62 GiB RSS. No OOM events; `/src` retains 13 GiB free.
At 2026-10-27 12:45 UTC, the Guix ARM64 bootstrap remains active in `supports-unicode`, at about 121,760 rustc CPU ticks and 1.58 GiB RSS; OOM counters remain zero and `/src` has 13 GiB free.
At 2026-10-27 12:47 UTC, the same Guix Rust bootstrap remains CPU-active in `supports-unicode` at about 135,227 rustc CPU ticks/1.58 GiB RSS. No exit marker or OOM events; `/src` has 13 GiB available.
At 2026-10-27 12:49 UTC, the live Guix ARM64 bootstrap remains active in the Cargo tools compilation, with `supports-unicode` at about 141,919 rustc CPU ticks and 1.57 GiB RSS. It advanced ~6,700 ticks since 12:47; there is still no exit marker or OOM event, and `/src` has 13 GiB free.
At 2026-10-27 12:50 UTC, the Guix ARM64 Rust bootstrap remains active; `supports-unicode` reached about 149,582 rustc CPU ticks and 1.57 GiB RSS. It advanced ~6,500 ticks since 12:49; no exit marker or OOM events, with 13 GiB free in `/src`.
At 2026-10-27 12:52 UTC, `supports-unicode` in the active Guix ARM64 bootstrap reached about 162,801 rustc CPU ticks/1.57 GiB RSS. CPU time continues to advance; build has no exit marker and cgroup OOM counters remain zero.
At 2026-10-27 12:52 UTC, the Guix ARM64 Rust bootstrap is still live in `supports-unicode` (~164,945 rustc CPU ticks, 1.57 GiB RSS); OOM counters remain zero. The host session was also read-only inspected: KDE Wayland, PipeWire 1.6.10 with ALSA capture devices available; no capture or playback was started.
At 2026-10-27 12:55 UTC, the live Guix ARM64 Rust bootstrap remains in `supports-unicode` at about 178,564 rustc CPU ticks/1.58 GiB RSS, roughly +6,600 since 12:54. No exit marker or OOM event; `/src` remains 13 GiB free.
At 2026-10-27 12:57 UTC, Cargo replaced the long-running `supports-unicode` rustc worker with a new AArch64 rustc process (PID 287250), indicating that crate completed; the new worker advanced from about 4,334 to 10,947 CPU ticks by 12:58 and RSS is 433 MiB. Guix bootstrap remains active and OOM counters are zero.
At 2026-10-27 12:59 UTC, the new AArch64 rustc worker reached about 17,726 CPU ticks/450 MiB RSS, up from ~10,947 at 12:58. Cargo/Guix remain live, no OOM events, and `/src` retains 13 GiB.
At 2026-10-27 13:02 UTC, the previous Cargo stage2 bootstrap completed and Guix entered the `rust-1.90.0-src` derivation. It extracted the Rust source archive and completed `patch-source-shebangs`, `configure`, `use-system-llvm`, and `disable-lld-wrapper`; current phase is patching generated shebangs. The build remains live with zero OOM events and 13 GiB free on `/src`.
At 2026-10-27 13:03 UTC, the Guix Rust source derivation advanced from shebang patching into `patch-cargo-checksums`, generating vendor checksums across the Rust 1.90.0 source tree. Guile worker remains active; no OOM events, `/src` has 13 GiB free.
At 2026-10-27 13:04 UTC, Guix continues `patch-cargo-checksums` in Rust 1.90.0, advancing from `bitflags` through `chrono`, `ciborium`, and `clap` vendor crates. Guile remains active, OOM counters zero, `/src` has 13 GiB free.
At 2026-10-27 13:05 UTC, the Rust 1.90.0 checksum phase advanced through the `darling`, `dashmap`, `dbus`, `der`, and `derive_*` vendor crates. Guile remains live; no OOM events and `/src` has 13 GiB available.
At 2026-10-27 13:06 UTC, Rust 1.90.0 `patch-cargo-checksums` advanced through `diesel*`, `dirs*`, `getrandom`, `gimli`, `git2`, and `gix` vendor crates. Guile remains active, OOM counters zero, `/src` has 13 GiB free.
At 2026-10-27 13:08 UTC, Rust source checksum generation advanced through `hermit-abi`, `hkdf`, `home`, `html5ever`, and HTTP vendor crates. Guix remains active and OOM-free; `/src` has 13 GiB available.
At 2026-10-27 13:09 UTC, `patch-cargo-checksums` advanced into Rust vendor crates `intrusive-collections`, `io-uring`, `ipc-channel`, `ipnet`, and `itertools`. Guile remains active, with zero OOM events and 13 GiB free on `/src`.
At 2026-10-27 13:10 UTC, Rust 1.90.0 checksum generation advanced through `lazycell`, `libc`, `libdbus-sys`, `libffi`, and `libgit2-sys` vendor crates. Guile remains active with no OOM events; `/src` has 13 GiB free.
At 2026-10-27 13:11 UTC, Rust 1.90.0 `patch-cargo-checksums` advanced through `kqueue-sys`, `libgit2-sys`, `link-cplusplus`, `linux-raw-sys`, and `lsp-*` vendor crates. Active `sha256sum` workers confirm checksumming continues; no OOM events, `/src` has 13 GiB free.
At 2026-10-27 13:12 UTC, the Rust source checksum phase progressed through the remaining `lsp-*` entries into `num-*` and `objc2-core-foundation`; a live `sha256sum` worker is present. Guix remains active with zero OOM events and 13 GiB free on `/src`.
At 2026-10-27 13:14 UTC, Rust 1.90.0 checksum generation has reached `openssl-*` after processing `num-*`, `oorandom`, and `opener`; two live `sha256sum` workers are visible. Guix remains active, OOM counters zero, `/src` has 13 GiB free.
At 2026-10-27 13:14 UTC, the Rust 1.90.0 checksum phase continued beyond `openssl-*` through `phf_*` and `pin-project*` vendor crates. A live `sha256sum` worker was present, with no OOM events; the Guix ARM64 package build has not reached its terminal result.
At 2026-10-27 13:16 UTC, Rust 1.90.0 checksum generation progressed through `pq-*`, `proc-macro*`, `proptest`, and into `redox_*`/`regex-*` vendor crates. Two sha256sum workers remain active; no OOM events, 13 GiB free in `/src`.
At 2026-10-27 13:17 UTC, the checksum phase advanced through the rest of `regex-*` and into `rustc_version`, `rustfix`, `rustix`, and `rustls*`. Guix remains active, OOM counters zero, `/src` has 13 GiB free.
At 2026-10-27 13:19 UTC, Rust 1.90.0 checksum generation advanced beyond `rustls-*` into `signal-hook-*`, `similar`, and `slab`/`smallvec` vendor crates. The Guix worker remains live, OOM counters zero, and `/src` has 13 GiB free.
At 2026-10-27 13:20 UTC, the Rust 1.90.0 checksum phase advanced through `signal-hook`, `slab`, and `smallvec`, into `tendril`, terminal utilities, and `thiserror` crates. Two sha256sum workers are active; no OOM events, 13 GiB free on `/src`.
At 2026-10-27 13:21 UTC, Rust 1.90.0 checksum generation advanced from `thiserror`/`time` through `tinyvec`, TLS helpers, and into `tokio-*` vendor crates. Two sha256sum workers remain active; no OOM events, `/src` has 13 GiB free.
At 2026-10-27 13:22 UTC, Rust 1.90.0 checksum generation advanced from `tokio-*` into the `toml-*` and `toml_edit` vendor crates. Two sha256sum workers are active; no OOM events, `/src` retains 13 GiB free.
At 2026-10-27 13:29 UTC, Rust 1.90.0 `patch-cargo-checksums` has advanced from `tokio`/`toml` through `wasmparser`, `wasmtime`, web crates, and Windows vendor crates. Guile's RSS fell from ~194 MiB to ~77 MiB while remaining active; no OOM events, `/src` has 13 GiB free.
At 2026-10-27 13:30 UTC, the checksum pass is progressing through the large `windows-*` vendored family in Rust 1.90.0 (Windows system/target bindings). Two sha256sum workers are live, no OOM events, `/src` has 13 GiB free.
At 2026-10-27 13:31 UTC, the Rust 1.90.0 checksum pass has advanced past the `windows-*` family into `wit-bindgen`, `xattr`, `xz2`, `yoke`, and `zerocopy` crates near the end of the vendor list. Guile and sha256sum remain live; no OOM events, `/src` has 13 GiB free.
At 2026-10-27 13:32 UTC, Rust 1.90.0 `patch-cargo-checksums` completed successfully after 1,790.2 seconds and Guix entered the `build` phase (`Building bootstrap`). Cargo is compiling bootstrap dependencies including `proc-macro2`, `libc`, `serde`, `regex-syntax`, and `cc`; no OOM events and `/src` has 13 GiB free.
At 2026-10-27 13:35 UTC, Guix Rust 1.90.0 `Building bootstrap` has advanced through archive/compression, hashing, serialization, and CLI crates including `tar`, `xz2`, `sha2`, `clap`, and `clap_complete`. Cargo remains active; no OOM events, `/src` has 13 GiB free.
At 2026-10-27 13:36 UTC, the build was actively compiling the Rust bootstrap crate itself: AArch64 `.rustc-real` PID 527442, 8 threads, about 8,356 CPU ticks and 858 MiB RSS. Cargo's parent is sleeping while the child compiles; cgroup OOM counters remain zero.
At 2026-10-27 13:37 UTC, Cargo finished compiling the Rust bootstrap crate (`Finished dev profile` in 5m37s), and `x.py` advanced to building compiler artifacts stage0→stage1 for `aarch64-unknown-linux-gnu`. The stage1 Rust compiler is active; no OOM events, `/src` has 13 GiB free.
At 2026-10-27 13:40 UTC, stage0→stage1 AArch64 compiler build progressed past the initial `proc-macro2`/`syn` group to `cfg-if`, `libc`, `synstructure`, `memchr`, `displaydoc`, and `cc`. Rustc workers are active; OOM counters remain zero, `/src` has 13 GiB free.
At 2026-10-27 13:41 UTC, stage1 compilation advanced from `cc` into `stable_deref_trait`, `smallvec`, `hashbrown`, `getrandom`, and `lock_api`; current rustc worker has about 165 MiB RSS and continues. No OOM events, `/src` has 13 GiB free.
At 2026-10-27 13:42 UTC, stage1 AArch64 build advanced beyond `generic-array`/`indexmap` into `parking_lot_core`, `tracing-core`, `log`, and tracing attributes. Current `.rustc-real` worker has 8 threads, ~361 MiB RSS and is CPU-active; no OOM events.
At 2026-10-27 13:44 UTC, stage1 Cargo advanced through `crossbeam-utils`, `tracing`, `parking_lot`, `zerocopy`, `rustix`, and `linux-raw-sys`; it is progressing through the dependency graph with no OOM events. `/src` retains 13 GiB free.
At 2026-10-27 13:45 UTC, stage1 compilation has reached compiler-internal crates `rustc_macros`, `rustc_hashes`, and `rustc-stable-hash`, alongside `crossbeam-epoch` and `digest`. A new AArch64 rustc worker is active (~260 MiB RSS); no OOM events.
At 2026-10-27 13:46 UTC, stage1 Cargo advanced into compiler internals and dependencies: `stacker`, `thin-vec`, `rustc_serialize`, `rustc_index_macros`, `blake3`, and crossbeam crates. Active `.rustc-real` worker has 3 threads and ~63 MiB RSS; OOM counters remain zero.
At 2026-10-27 13:47 UTC, stage1 compilation advanced into compiler crates `rustc_index`, `rustc_thread_pool`, and `rustc_arena`, with `measureme` and `ena` dependencies. AArch64 `.rustc-real` is active (~279 MiB RSS); OOM counters zero and `/src` has 13 GiB free.
At 2026-10-27 13:49 UTC, stage1 Cargo advanced into `rustc_graphviz` and `rustc_data_structures` after `rustc_arena`/`rustc_index`; the active `.rustc-real` worker reached ~3,509 CPU ticks and 407 MiB RSS. Build remains live, OOM counters zero.
At 2026-10-27 13:50 UTC, stage1 compiler build advanced to `rustc_span` after `rustc_data_structures`, with `sha1`, `sha2`, and `md-5` dependencies compiled. Active AArch64 `.rustc-real` is ~411 MiB RSS; no OOM events and `/src` has 13 GiB free.
At 2026-10-27 13:52 UTC, stage1 Cargo has advanced past `rustc_span` into serde and derive dependencies (`zerofrom`, `yoke`, `zerovec`, `thiserror`). A new AArch64 `.rustc-real` worker is active at ~294 MiB RSS; no OOM events.
At 2026-10-27 13:53 UTC, stage1 progressed through `zerovec` and is compiling `serde_derive`/`thiserror-impl` after Rust compiler-internal and Unicode crates. Current `.rustc-real` worker has ~341 MiB RSS; no OOM events and 13 GiB remain free on `/src`.
At 2026-10-27 13:54 UTC, stage1 Cargo has advanced into `rustc_ast_ir`, `rustc-literal-escaper`, and ICU localization crates, alongside `wasmparser`. Active AArch64 `.rustc-real` is ~334 MiB RSS; no OOM events and `/src` retains 13 GiB free.
At 2026-10-27 13:56 UTC, stage1 advanced to `rustc_lexer` and ICU provider crates, with `object`, `serde_json`, and Unicode parser dependencies compiling. Current AArch64 `.rustc-real` uses ~322 MiB RSS; build remains OOM-free.
At 2026-10-27 13:57 UTC, stage1 progressed beyond ICU provider/lexer into `rand`, `unic-langid`, and `rand_xoshiro`; the active compiler worker has ~260 MiB RSS. Build remains live with no OOM events and 13 GiB free on `/src`.
At 2026-10-27 13:58 UTC, the AArch64 stage1 dependency graph advanced into `rustc_abi` and ICU locale transforms; active `.rustc-real` reached ~378 MiB RSS. Guix remains active with zero OOM events and 13 GiB free on `/src`.
At 2026-10-27 14:05 UTC, stage1 compilation advanced to core compiler crates `rustc_ast`, `rustc_fs_util`, and `rustc_target` after `rustc_abi`; `.rustc-real` reached ~12,537 CPU ticks and 647 MiB RSS. Guix remains active, OOM counters zero, `/src` has 13 GiB free.
At 2026-10-27 14:06 UTC, the active AArch64 `.rustc-real` continued compiling `rustc_target`/compiler artifacts, advancing from ~12,537 to 20,426 CPU ticks with ~594 MiB RSS. Cargo and x.py remain live; no OOM events, `/src` has 13 GiB free.
At 2026-10-27 14:08 UTC, the same stage1 `.rustc-real` compile advanced to ~29,918 CPU ticks (~+9,500 since 14:06) while compiling `rustc_target`; RSS remained ~594 MiB. No exit marker or OOM event; `/src` has 13 GiB free.
At 2026-10-27 14:10 UTC, stage1 advanced beyond `rustc_target` into `rustc_ast_pretty`, `regex-automata`, and `odht`. New AArch64 rustc worker is active (~279 MiB RSS); no OOM events and 13 GiB remain free on `/src`.
At 2026-10-27 14:13 UTC, stage1 Cargo advanced into `rustc_hir` and compiler localization (`fluent-syntax`, `fluent-langneg`, `intl_pluralrules`), with `darling_core` and ICU list crates. AArch64 rustc worker is active (~316 MiB RSS); no OOM events, 13 GiB free.
At 2026-10-27 14:14 UTC, stage1 advanced into `fluent-bundle`, compiler `rustc_baked_icu_data`, `darling_macro`, and ICU provider adapters after `rustc_hir`. Active AArch64 rustc worker has ~234 MiB RSS; no OOM events, `/src` has 13 GiB free.
At 2026-10-27 14:15 UTC, stage1 advanced into `rustc_type_ir_macros` and `rustc_type_ir` after localization/ICU compiler dependencies; `rustc_target` and `rustc_hir` are in the graph. `/src` usage grew to 3.2 GiB of 16 GiB, still 13 GiB free; no OOM events.
At 2026-10-27 14:17 UTC, stage1 advanced through `rustc_type_ir` into compiler `rustc_error_messages`, with `darling` completing its dependency chain. Active AArch64 `.rustc-real` is ~314 MiB RSS; no OOM events, `/src` has 13 GiB free.
At 2026-10-27 14:18 UTC, stage1 compilation advanced through `rustc_lint_defs`, `rustc_fluent_macro`, `rustc_error_codes`, and `rustc_errors`; active `.rustc-real` is ~539 MiB RSS. Guix remains OOM-free with 13 GiB free on `/src`.
At 2026-10-27 14:20 UTC, the active stage1 rustc compile continued through `rustc_errors`, advancing from ~3,078 to 12,358 CPU ticks; RSS is ~463 MiB. No terminal result or OOM events; `/src` has 13 GiB free.
At 2026-10-27 14:22 UTC, stage1 Cargo advanced from `rustc_errors` to `rustc_feature` and `getopts`; a new AArch64 rustc worker is active (~292 MiB RSS). No OOM events, `/src` retains 13 GiB free.
At 2026-10-27 14:23 UTC, stage1 advanced to `rustc_session` after `rustc_feature`; `.rustc-real` reached ~6,872 CPU ticks and 567 MiB RSS. Build remains active without OOM, `/src` has 13 GiB available.
At 2026-10-27 14:25 UTC, the active stage1 rustc compile continued through `rustc_session`, reaching ~15,141 CPU ticks with ~460 MiB RSS. No exit marker or OOM events; `/src` has 13 GiB free.
At 2026-10-27 14:26 UTC, stage1 advanced through `rustc_apfloat`, `polonius-engine`, and compiler `rustc_query_system` after `rustc_session`. A new AArch64 rustc worker is active (~402 MiB RSS); no OOM events, `/src` has 13 GiB free.
At 2026-10-27 14:28 UTC, stage1 advanced into `rustc_hir_pretty` and core compiler crate `rustc_middle`, after `rustc_query_system`. Active AArch64 rustc worker is ~463 MiB RSS; no OOM events and 13 GiB remain free on `/src`.
At 2026-10-27 14:29 UTC, the stage1 `.rustc-real` worker remains compiling `rustc_middle`, advancing from ~3,162 to 11,312 CPU ticks and growing to ~896 MiB RSS. No OOM events; `/src` has 13 GiB available.
At 2026-10-27 14:30 UTC, the active `rustc_middle` compilation advanced to ~18,752 CPU ticks and ~1.0 GiB RSS. Cgroup OOM counters remain zero; `/src` has 13 GiB free.
At 2026-10-27 14:32 UTC, `rustc_middle` remains the active stage1 compile, advancing to ~26,821 CPU ticks and ~1.16 GiB RSS. No OOM events; `/src` has 13 GiB free.
At 2026-10-27 14:33 UTC, `rustc_middle` compilation remains active and advanced to ~36,058 CPU ticks; RSS fluctuated down to ~1.05 GiB. OOM counters remain zero, `/src` has 13 GiB free.
At 2026-10-27 14:35 UTC, the active `rustc_middle` compilation reached ~43,109 CPU ticks with RSS down to ~884 MiB; the same worker is still advancing. OOM counters remain zero and `/src` has 13 GiB free.
At 2026-10-27 14:36 UTC, `rustc_middle` advanced to ~51,257 CPU ticks while RSS fell to ~827 MiB. The same stage1 worker remains active; no OOM events, `/src` has 13 GiB free.
At 2026-10-27 14:37 UTC, the same `rustc_middle` stage1 compile reached ~59,976 CPU ticks and ~920 MiB RSS. It remains CPU-active; no OOM events and 13 GiB remain available on `/src`.
At 2026-10-27 14:39 UTC, `rustc_middle` remained the active stage1 crate, advancing to ~69,611 CPU ticks; RSS fluctuated down to ~815 MiB. No OOM events and `/src` has 13 GiB free.
At 2026-10-27 14:40 UTC, the active `rustc_middle` compile advanced to ~77,047 CPU ticks at ~815 MiB RSS. The worker remains live, with zero OOM events and 13 GiB free on `/src`.
At 2026-10-27 14:42 UTC, `rustc_middle` completed and stage1 Cargo advanced to `rustc_parse_format`; the active AArch64 rustc worker changed and has ~328 MiB RSS. No OOM events; `/src` has 13 GiB free.
At 2026-10-27 14:43 UTC, stage1 advanced beyond `rustc_parse_format` into `rustc_infer`, with `tinyvec` dependencies; the active AArch64 rustc worker reached ~7,016 CPU ticks and ~633 MiB RSS. No OOM events, `/src` has 13 GiB free.
At 2026-10-27 14:45 UTC, `rustc_infer` remains active and advanced to ~14,692 CPU ticks; RSS fluctuated down to ~504 MiB. No OOM events, `/src` has 13 GiB free.
At 2026-10-27 14:46 UTC, `rustc_infer` completed and stage1 advanced to `rustc_transmute`; a new AArch64 rustc worker is active (~487 MiB RSS). No OOM events and `/src` has 13 GiB free.
At 2026-10-27 14:50 UTC, stage1 advanced beyond `rustc_transmute` into `rustc_attr_parsing` and `rustc_next_trait_solver`; active AArch64 rustc worker is ~369 MiB RSS. No OOM events; `/src` has 13 GiB free.
At 2026-10-27 14:51 UTC, stage1 advanced into `rustc_trait_selection` after `rustc_next_trait_solver`; active AArch64 rustc worker reached ~7,400 CPU ticks and ~791 MiB RSS. No OOM events, `/src` has 13 GiB free.
At 2026-10-27 14:53 UTC, `rustc_trait_selection` remains active and advanced to ~18,742 CPU ticks with ~1.11 GiB RSS. No OOM events; `/src` has 13 GiB free.
At 2026-10-27 14:55 UTC, the active `rustc_trait_selection` compile advanced to ~26,970 CPU ticks, with ~1.10 GiB RSS. It remains live; OOM counters zero and `/src` has 13 GiB free.
At 2026-10-27 14:56 UTC, `rustc_trait_selection` continued to ~34,234 CPU ticks with ~1.11 GiB RSS. Stage1 remains active and OOM-free; `/src` has 13 GiB free.
At 2026-10-27 14:57 UTC, `rustc_trait_selection` remained active, advancing to ~43,059 CPU ticks with ~1.05 GiB RSS. No OOM events; `/src` has 13 GiB free.
At 2026-10-27 14:59 UTC, the same `rustc_trait_selection` compile reached ~50,593 CPU ticks, RSS ~886 MiB. It remains active with no OOM events; `/src` has 13 GiB free.
At 2026-10-27 15:10 UTC, stage1 completed the long `rustc_trait_selection` build and moved on to regex dependencies (`unicode-normalization`, `aho-corasick`, `regex-syntax`, `regex-automata`). The new active AArch64 rustc worker is at ~3,419 CPU ticks/~514 MiB RSS; Guix is still running and all cgroup OOM counters remain zero.
At 2026-10-27 15:13 UTC, stage1 progressed beyond the regex crates into `getrandom`, `rand_core`, `rand_chacha`, `regex`, and `rand`; the active AArch64 rustc worker was compiling with ~386 MiB RSS and increasing CPU time. Guix remains running with zero OOM events. The local `scripts/verify-linux.sh` also passed after syncing the Gentoo AArch64 catalog and matrix capability allowlist: voice 531/1 skipped, MCP 33, GUI 5, OpenCode 120, Rust 7, plus Tauri release build.
At 2026-10-27 15:16 UTC, the Guix AArch64 stage1 compiler is still compiling `rustc_parse`; `.rustc-real` advanced to ~20,328 CPU ticks and ~681 MiB RSS since the prior checkpoint. No OOM events. Separately, the opt-in KDE Wayland AT-SPI test now passes both cases (2 passed, 0 skipped) in the 15:15 session; matrix and verification notes record this run while retaining broader GNOME/X11/portal gates.
At 2026-10-27 15:19 UTC, Guix AArch64 remains in `rustc_parse`; the same worker's CPU ticks rose to ~34,363 and RSS to ~753 MiB since 15:16. No OOM events and `/src` has ample space. The interactive KDE Wayland AT-SPI rerun passed 2/2 at 15:15 UTC and is now recorded as a separate passed matrix row; the earlier skipped run remains historical evidence.
At 2026-10-27 15:20 UTC, stage1 moved past `rustc_parse` into `rustc_ast_passes`, alongside `static_assertions` and `twox-hash`. The active AArch64 rustc worker changed (new process, ~3,382 CPU ticks/~366 MiB RSS); Guix remains active with zero OOM events and 13 GiB free on `/src`.
At 2026-10-27 15:22 UTC, Guix stage1 advanced from `rustc_ast_passes` into `rustc_proc_macro`. A new AArch64 rustc process is active (~4,628 CPU ticks/~370 MiB RSS); the build has no OOM events. Disk/memory checks remain healthy for the isolated build container.
At 2026-10-27 15:24 UTC, Guix stage1 advanced into compiler crate `rustc_expand` after `rustc_proc_macro`; the active AArch64 rustc worker reached ~8,059 CPU ticks/~594 MiB RSS. Build remains alive and all cgroup OOM counters are zero.
At 2026-10-27 15:25 UTC, `rustc_expand` remains active and advanced from ~8,059 to ~16,661 CPU ticks; RSS is ~520 MiB. No terminal marker or OOM event; the build has not stalled.
At 2026-10-27 15:28 UTC, `rustc_expand` dependencies progressed through `object` and `flate2`; the AArch64 rustc process changed to a new worker (~234 CPU ticks/~251 MiB RSS), showing Cargo advanced to another compile unit. Guix is running and OOM counters remain zero.
At 2026-10-27 15:28 UTC, the Guix Rust bootstrap advanced through `object` and `flate2` into `ruzstd`; a new AArch64 rustc worker is active (~1,605 CPU ticks/~324 MiB RSS), with all OOM counters at zero. The desktop pending-gate summary was also reconciled with the evidence: focus, portal authorization/screenshot and keyboard input passed on KDE Wayland; pointer click, portal denial/revocation, clipboard, GNOME and X11 remain open. Matrix consistency check passed.
At 2026-10-27 15:30 UTC, the Guix AArch64 stage1 graph advanced through `ruzstd` and Unicode helper crates (`unicode-script`, `unicode-security`). The active compiler worker reached ~6,192 CPU ticks/~569 MiB RSS; no OOM or terminal marker.
At 2026-10-27 15:31 UTC, Cargo advanced from the `rustc_expand` dependency group into `rustc_incremental`; a new stage1 AArch64 compiler worker reached ~6,822 CPU ticks/~403 MiB RSS. Guix remains running with zero OOM events.
At 2026-10-27 15:32 UTC, Guix stage1 advanced beyond `rustc_incremental` into `libloading`, `rustc-demangle`, and `fallible-iterator`; a new AArch64 rustc worker started (~467 CPU ticks/~304 MiB RSS). No OOM or terminal status.
At 2026-10-27 15:34 UTC, the active AArch64 Rust worker advanced from ~467 to ~7,312 CPU ticks (~440 MiB RSS) while Cargo compiled `regex-syntax` and Rust compiler dependencies. Still running, with no OOM events.
At 2026-10-27 15:34 UTC, the stage1 graph advanced through `rustc_incremental` to `rustc_symbol_mangling`; AArch64 rustc started a new worker (~339 CPU ticks/~363 MiB RSS). The compile remains active and OOM-free; matrix evidence still records 171 passed, 2 partial, 1 unverified.
At 2026-10-27 15:35 UTC, stage1 advanced to `regex-automata` alongside `rustc_symbol_mangling`; a new AArch64 compiler worker is active (~687 CPU ticks/~346 MiB RSS). No OOM events.
At 2026-10-27 15:37 UTC, Cargo advanced into `gimli` after `regex-automata`; a new AArch64 rustc worker reached ~5,117 CPU ticks/~492 MiB RSS. Guix remains alive with zero OOM events. The matrix's six overlapping pending statements were consolidated into four distinct gates; the package/matrix consistency test passed afterward.
At 2026-10-27 15:37 UTC, stage1 advanced to `rustc_metadata`; the active AArch64 rustc worker reached ~2,553 CPU ticks/~545 MiB RSS, with zero OOM events. The current-worktree overlay also passed an Xvfb/AT-SPI relaunch/cleanup smoke at 15:37 UTC; this was added as isolated X11 evidence and did not replace the real GNOME/X11 session gate. Matrix status is now 172 passed, 2 partial, 1 unverified; metadata consistency test passed.
At 2026-10-27 15:39 UTC, `rustc_metadata` remains active and its worker advanced from ~2,553 to ~10,252 CPU ticks (~723 MiB RSS). No OOM events. The Xvfb overlay smoke has been added to the matrix, and the public Linux status docs now show 175 checks (172 passed, 2 partial, 1 unverified).
At 2026-10-27 15:45 UTC, `rustc_lint` remains the active stage1 compiler crate; its AArch64 worker advanced from ~2,025 to ~8,875 CPU ticks and ~803 MiB RSS over the latest interval. Cgroup OOM counters remain zero and `/src` has ~13 GiB free.
At 2026-10-27 15:51 UTC, the same `rustc_lint` stage1 worker continued advancing to ~46,282 CPU ticks (~684 MiB RSS). It has not emitted a new crate line yet, but CPU use confirms active compilation; OOM counters remain zero and the build stays live.
At 2026-10-27 16:00 UTC, `rustc_lint` completed and stage1 advanced to `rustc_mir_dataflow`, `rustc_llvm`, and `rustc_ty_utils`, with runtime dependencies compiling in parallel. The active worker changed (~2,848 CPU ticks/~593 MiB RSS); OOM counters remain zero.
At 2026-10-27 16:01 UTC, stage1 remains in `rustc_llvm`/`rustc_ty_utils`; the active AArch64 rustc worker advanced from ~4,829 to ~12,103 CPU ticks. RSS is ~457 MiB and OOM counters remain zero, so this long compiler group is still making progress.
At 2026-10-27 16:02 UTC, the `rustc_llvm`/`rustc_ty_utils` group is still compiling; the worker reached ~20,055 CPU ticks (~441 MiB RSS), up ~7,952 ticks since 16:01. No OOM events or failure output.
At 2026-10-27 16:03 UTC, stage1 advanced beyond `rustc_llvm`/`rustc_ty_utils` into `rustc_pattern_analysis`; a new AArch64 compiler worker is active (~603 CPU ticks/~406 MiB RSS). Guix is still building the toolchain, not yet the Jarvis crate; no OOM events.
At 2026-10-27 16:04 UTC, Cargo advanced to dependency `thread_local` while the `rustc_pattern_analysis` group remains in flight; a new worker started (~41 CPU ticks/~85 MiB RSS). This confirms scheduling progress; no OOM events.
At 2026-10-27 16:05 UTC, the bootstrap advanced to compiler crate `rustc_codegen_ssa` after `thread_local` and documentation/parser dependencies. The active AArch64 rustc worker reached ~6,818 CPU ticks/~867 MiB RSS; cgroup OOM counters remain zero.
At 2026-10-27 16:06 UTC, `rustc_codegen_ssa` remains active and advanced from ~6,818 to ~8,701 CPU ticks (~869 MiB RSS); Cargo also reports the same compiler crate. No OOM events. Matrix count (175: 172 passed, 2 partial, 1 unverified) matches the Linux status docs after whitespace-normalized check.
At 2026-10-27 16:07 UTC, the `rustc_codegen_ssa` AArch64 compile advanced to ~16,658 CPU ticks and ~898 MiB RSS (~7,957 additional ticks since 16:06). No OOM events; this heavy compiler crate remains active.
At 2026-10-27 16:09 UTC, the `rustc_codegen_ssa` worker advanced to ~26,202 CPU ticks (~715 MiB RSS), up ~7,267 ticks since 16:08. Cargo still reports this crate as the active long compile; no OOM events or errors.
At 2026-10-27 16:10 UTC, `rustc_codegen_ssa` advanced to ~36,377 CPU ticks (~715 MiB RSS), about +10,175 ticks since 16:09. The process is actively compiling despite no new Cargo line; all OOM counters remain zero.
At 2026-10-27 16:12 UTC, Cargo advanced to `tracing-subscriber` while `rustc_codegen_ssa` remains in the dependency graph; the active AArch64 worker changed (~1,304 CPU ticks/~372 MiB RSS). No OOM events; scheduling has progressed.
At 2026-10-27 16:12 UTC, the Rust bootstrap graph advanced to `tracing-subscriber`; a new AArch64 rustc worker is active (~3,307 CPU ticks/~446 MiB RSS). All cgroup OOM counters remain zero. The 175-row matrix still distinguishes passed Xvfb/AT-SPI and real KDE Wayland evidence from four open gates.
At 2026-10-27 16:14 UTC, stage1 advanced into `rustc_mir_build` after scheduling `tracing-subscriber`; a new AArch64 rustc worker reached ~2,228 CPU ticks/~493 MiB RSS. The bootstrap remains active with zero OOM events.
At 2026-10-27 16:15 UTC, `rustc_mir_build` advanced to ~11,078 CPU ticks (~729 MiB RSS), up ~7,017 ticks since 16:14. It remains active and cgroup OOM counters are zero.
At 2026-10-27 16:16 UTC, `rustc_mir_build` remained the active crate and advanced to ~19,610 CPU ticks (~559 MiB RSS), about +8,532 ticks since 16:15. No OOM events or failure output.
At 2026-10-27 16:19 UTC, `rustc_mir_build` advanced to ~32,133 CPU ticks (~495 MiB RSS), about +10,093 ticks since 16:17. The build remains active, with zero OOM counters and no compile errors.
At 2026-10-27 16:20 UTC, Cargo advanced to `rustc_privacy` alongside `rustc_mir_build`; a new AArch64 worker started (~1,632 CPU ticks/~495 MiB RSS). The Guix build remains healthy and OOM-free.
At 2026-10-27 16:22 UTC, stage1 advanced to `rustc_const_eval` after `rustc_privacy`; new AArch64 compiler worker is at ~2,728 CPU ticks/~566 MiB RSS. The build remains active without OOM events.
At 2026-10-27 16:23 UTC, `rustc_const_eval` advanced to ~11,856 CPU ticks (~821 MiB RSS), about +7,191 ticks since 16:22. It remains active, with all OOM counters at zero.
At 2026-10-27 16:25 UTC, `rustc_const_eval` advanced to ~20,515 CPU ticks (~655 MiB RSS), about +7,007 ticks since 16:23. The compile remains active with zero OOM events.
At 2026-10-27 16:26 UTC, `rustc_const_eval` advanced to ~29,833 CPU ticks (~686 MiB RSS), up ~7,092 ticks since 16:25. The active stage1 Rust compile remains OOM-free.
At 2026-10-27 16:28 UTC, Cargo advanced from the long `rustc_const_eval` group into `rustc_sanitizers`; a new AArch64 rustc worker started (~1,151 CPU ticks/~492 MiB RSS). The build is alive and OOM counters are zero.
At 2026-10-27 16:29 UTC, stage1 advanced from `rustc_sanitizers` to `rustc_traits`; a new AArch64 rustc worker reached ~3,350 CPU ticks/~541 MiB RSS. The build is still active with zero OOM events.
At 2026-10-27 16:31 UTC, the `rustc_traits` worker advanced to ~12,647 CPU ticks (~419 MiB RSS), about +7,091 ticks since 16:30. No new crate line yet; CPU progress and zero OOM indicate ongoing compilation.
At 2026-10-27 16:32 UTC, the `rustc_traits` worker advanced from ~15,038 to ~22,454 CPU ticks (~419 MiB RSS). Cargo still reports the compiler crate active; no OOM events.
At 2026-10-27 16:34 UTC, the stage1 graph advanced into `rustc_hir_analysis` after `rustc_traits`; a new AArch64 worker reached ~3,372 CPU ticks/~580 MiB RSS. Guix remains active and OOM-free.
At 2026-10-27 16:36 UTC, the `rustc_hir_analysis` worker advanced to ~12,707 CPU ticks (~932 MiB RSS), up ~7,426 ticks since 16:34. The compile is active and cgroup OOM counters remain zero.

At 2026-10-27 17:51 UTC, the resumed Guix AArch64 build remains active in Rust
stage1. The `rustc_mir_transform` compilation is still reported; the active
`.rustc-real` worker advanced from about 19,946 to 30,521 CPU ticks since
17:49 UTC (RSS about 688 MiB). The terminal marker is absent and cgroup OOM
counters remain zero. Guix package install/runtime validation is still pending.

At 2026-10-27 18:07 UTC, Guix AArch64 stage1 advanced through
`rustc_monomorphize` into `rustc_query_impl`; the active `.rustc-real` worker
reached about 27,703 CPU ticks and 1.2 GiB RSS. The process remains live, no
terminal marker is present, and cgroup OOM counters remain zero. The package
build and lifecycle smoke have not completed.

At 2026-10-27 18:15 UTC, `.rustc-real` is still compiling
`rustc_query_impl`; its QEMU worker is consuming about 99% CPU at 1.14 GiB RSS.
Container CPU is about 99%, `/src` has 13 GiB free, and cgroup OOM counters
remain zero. The build is active, but has not yet advanced to the Jarvis crate.

At 2026-10-27 19:21 UTC, Guix AArch64 completed Rust stage1 after the extended
`rustc_query_impl` compile and began building the stage1 `llvm-bitcode-linker`;
`syn` is compiling in parallel. Container CPU remains about 98%, and cgroup
OOM counters are zero. Jarvis package build and lifecycle smoke are still
pending.

At 2026-10-27 19:39 UTC, Guix completed the stage1 library artifacts (12m 23s)
and entered compiler artifacts (stage1 → stage2) for AArch64. `proc-macro2`,
`quote`, and `syn` are compiling; container CPU remains about 98%, with zero
cgroup OOM events. The Jarvis package derivation and lifecycle smoke remain
pending.

At 2026-10-27 20:47 UTC, the resumed Guix AArch64 Rust bootstrap remains in
stage2, compiling `rustc_next_trait_solver` and `rustc_trait_selection`. Docker
reported 99.01% CPU and 913 MiB memory; the worker is active and cgroup OOM
counters remain zero. The Jarvis package derivation and installed lifecycle
smoke are still pending.

At 2026-10-27 20:58 UTC, stage2 `rustc_trait_selection` is actively compiling
under QEMU: the rustc worker reached 99.6% CPU for 11m25s with ~957 MiB RSS.
The build marker is still `running`; all cgroup OOM counters remain zero. The
Jarvis Guix package and lifecycle smoke are not yet available.

At 2026-10-27 21:02 UTC, Guix moved past the prolonged `rustc_trait_selection`
compile and started `aho_corasick` in stage2. The active AArch64 rustc worker is
at 99.5% CPU, ~407 MiB RSS, with zero cgroup OOM events; package output and
profile lifecycle remain pending.

At 2026-10-27 21:03 UTC, stage2 finished `aho_corasick` and advanced into
`regex_syntax`. The live AArch64 rustc worker was at 99.6% CPU, ~483 MiB RSS;
cgroup OOM counters remain zero. The Guix Jarvis derivation and lifecycle smoke
are still pending.

At 2026-10-27 21:10 UTC, the resumed Guix AArch64 stage2 Rust build remains
active in `rustc_parse`; the AArch64 rustc worker was at 99.6% CPU. The build
log advanced through dependency compilation and cgroup OOM counters remain zero.
The new recipe's libei dependency and full AArch64 derivation were evaluated
separately; this running build still uses its earlier source snapshot. Jarvis
package installation and runtime lifecycle remain pending.

At 2026-10-27 21:24 UTC, the same Guix AArch64 stage2 build advanced past
`rustc_parse` into `rustc_proc_macro`/`rustc_expand` and began compiling the
`object` crate. Its QEMU rustc worker remains at about 99.5% CPU; `/src` has
12 GiB free and all cgroup OOM counters are zero. The Nix x86_64 current-worktree
profile lifecycle passed separately at 21:23 UTC. Guix package lifecycle remains
pending.
At 2026-10-27 22:15 UTC, the active Guix ARM64 Rust stage advanced from `rustc_mir_build` into `rustc_privacy`; the container is still running at ~99% CPU with 714 MiB reported memory, 35 GiB host overlay space free, and no failure output. This is the pre-EIS source snapshot; the refreshed derivation containing `Region.convert_point()` remains queued behind this build.
At 2026-10-27 22:16 UTC, the active AArch64 `rustc_privacy` codegen worker is still at ~99.7% CPU. Its stage1 Rust build has emitted 10 CGU object files (about 815 KiB total; largest currently 276,704 bytes), confirming active compiler output; disk remains 35 GiB free and no error or OOM is reported. The current build still uses the earlier source snapshot, with the refreshed EIS build queued afterward.
At 2026-10-27 22:16 UTC, Guix advanced from `rustc_privacy` to `rustc_const_eval`; the prior Rust crate is no longer the active Cargo item and the current AArch64 rustc worker is CPU-active. The build container remains up, reports 35 GiB free on the overlay, and has not logged a compiler failure. The output is still from the pre-EIS source snapshot; current EIS derivation build and lifecycle remain queued.
At 2026-10-27 22:19 UTC, the resumed pre-EIS Guix ARM64 bootstrap was interrupted after re-reading the explicit 2026-10-22 scope amendment excluding GNU Guix and Gentoo from the current delivery. The build wrapper wrote exit marker `1`; no Jarvis package was produced. Keep this attempt as historical evidence only and do not resume the Guix build or run Guix validation for the current delivery.
