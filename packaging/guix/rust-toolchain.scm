;;; Rust 1.90 bootstrap packages for the Jarvis Guix recipe.
;;; Adapted from GNU Guix gnu/packages/rust.scm (rust-1.89 and rust-1.90).
;;; Copyright © GNU Guix contributors.
;;; SPDX-License-Identifier: GPL-3.0-or-later

(define rust-1.89-jarvis
  (let ((base-rust
         ((@@ (gnu packages rust) rust-bootstrapped-package)
          rust-1.88 "1.89.0"
          "0395ax8d138ch65fzm1y9xf2s4661am5k3yj3cav16fx83sgjxi5")))
    (package
      (inherit base-rust)
      ;; Rust's bootstrap builder otherwise inherits Guix's host-wide default
      ;; job count (four here), which OOM-kills rustc on emulated AArch64.
      (arguments
       (substitute-keyword-arguments (package-arguments base-rust)
         ((#:parallel-build? parallel-build? #t) #f)))
      (source
       (origin
         (inherit (package-source base-rust))
         (snippet
          '(begin
             (for-each delete-file-recursively
                       '("src/llvm-project"
                         "vendor/curl-sys-0.4.79+curl-8.12.0/curl"
                         "vendor/curl-sys-0.4.80+curl-8.12.1/curl"
                         "vendor/curl-sys-0.4.82+curl-8.14.1/curl"
                         "vendor/jemalloc-sys-0.5.3+5.3.0-patched/jemalloc"
                         "vendor/jemalloc-sys-0.5.4+5.3.0-patched/jemalloc"
                         "vendor/libffi-sys-3.3.1/libffi"
                         "vendor/libz-sys-1.1.21/src/zlib"
                         "vendor/libz-sys-1.1.22/src/zlib"
                         "vendor/libmimalloc-sys-0.1.42/c_src/mimalloc"
                         "vendor/openssl-src-111.28.2+1.1.1w/openssl"
                         "vendor/openssl-src-300.5.0+3.5.0/openssl"
                         "vendor/tikv-jemalloc-sys-0.5.4+5.3.0-patched/jemalloc"
                         "vendor/tikv-jemalloc-sys-0.6.0+5.3.0-1-\
ge13ca993e8ccb9ba9847cc330696e02839f328f7/jemalloc"))
             ;; Remove vendored dynamically linked libraries.
             ;; find . -not -type d -executable -exec file {} \+ | grep ELF
             ;; Also remove the bundled (mostly Windows) libraries.
             (for-each delete-file
                       (find-files "vendor" "\\.(a|dll|exe|lib)$"))
             ;; Use the packaged nghttp2.
             (for-each
              (lambda (ver)
                (let ((vendored-dir
                       (format #f "vendor/libnghttp2-sys-~a/nghttp2" ver))
                      (build-rs
                       (format #f "vendor/libnghttp2-sys-~a/build.rs" ver)))
                  (delete-file-recursively vendored-dir)
                  (delete-file build-rs)
                  (call-with-output-file build-rs
                    (lambda (port)
                      (format port "fn main() {~@
                         println!(\"cargo:rustc-link-lib=nghttp2\");~@
                         }~%")))))
              '("0.1.11+1.64.0"))
             ;; Adjust vendored dependency to explicitly use rustix with libc
             ;; backend.
             (substitute* '("vendor/tempfile-3.14.0/Cargo.toml"
                            "vendor/tempfile-3.16.0/Cargo.toml"
                            "vendor/tempfile-3.19.0/Cargo.toml"
                            "vendor/tempfile-3.19.1/Cargo.toml"
                            "vendor/tempfile-3.20.0/Cargo.toml")
               (("features = \\[\"fs\"" all)
                (string-append all ", \"use-libc\"")))))))
      (inputs
       (modify-inputs (package-inputs base-rust)
         (prepend curl `(,nghttp2 "lib") libffi))))))

(define rust-1.90-jarvis
  (let ((base-rust
         ((@@ (gnu packages rust) rust-bootstrapped-package)
          rust-1.89-jarvis "1.90.0"
          "0zlv3ybd8za07brxwj4n03cma1snnpvbqj0h0wg3bmafpaf9z6kr")))
    (package
      (inherit base-rust)
      (source
       (origin
         (inherit (package-source base-rust))
         (snippet
          '(begin
             (for-each delete-file-recursively
                       '("src/llvm-project"
                         "vendor/curl-sys-0.4.79+curl-8.12.0/curl"
                         "vendor/curl-sys-0.4.82+curl-8.14.1/curl"
                         "vendor/jemalloc-sys-0.5.3+5.3.0-patched/jemalloc"
                         "vendor/jemalloc-sys-0.5.4+5.3.0-patched/jemalloc"
                         "vendor/libffi-sys-3.3.2/libffi"
                         "vendor/libz-sys-1.1.21/src/zlib"
                         "vendor/libz-sys-1.1.22/src/zlib"
                         "vendor/libmimalloc-sys-0.1.42/c_src/mimalloc"
                         "vendor/openssl-src-111.28.2+1.1.1w/openssl"
                         "vendor/openssl-src-300.5.0+3.5.0/openssl"
                         "vendor/tikv-jemalloc-sys-0.5.4+5.3.0-patched/jemalloc"
                         "vendor/tikv-jemalloc-sys-0.6.0+5.3.0-1-\
ge13ca993e8ccb9ba9847cc330696e02839f328f7/jemalloc"))
             ;; Remove vendored dynamically linked libraries.
             ;; find . -not -type d -executable -exec file {} \+ | grep ELF
             ;; Also remove the bundled (mostly Windows) libraries.
             (for-each delete-file
                       (find-files "vendor" "\\.(a|dll|exe|lib)$"))
             ;; Use the packaged nghttp2.
             (for-each
              (lambda (ver)
                (let ((vendored-dir
                       (format #f "vendor/libnghttp2-sys-~a/nghttp2" ver))
                      (build-rs
                       (format #f "vendor/libnghttp2-sys-~a/build.rs" ver)))
                  (delete-file-recursively vendored-dir)
                  (delete-file build-rs)
                  (call-with-output-file build-rs
                    (lambda (port)
                      (format port "fn main() {~@
                         println!(\"cargo:rustc-link-lib=nghttp2\");~@
                         }~%")))))
              '("0.1.11+1.64.0"))
             ;; Adjust vendored dependency to explicitly use rustix with libc
             ;; backend.
             (substitute* '("vendor/tempfile-3.14.0/Cargo.toml"
                            "vendor/tempfile-3.16.0/Cargo.toml"
                            "vendor/tempfile-3.19.0/Cargo.toml"
                            "vendor/tempfile-3.19.1/Cargo.toml"
                            "vendor/tempfile-3.20.0/Cargo.toml")
               (("features = \\[\"fs\"" all)
                (string-append all ", \"use-libc\"")))))))
      (inputs
       (modify-inputs (package-inputs base-rust)
         (replace "llvm" llvm-21))))))

