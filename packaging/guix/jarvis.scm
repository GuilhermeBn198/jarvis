(use-modules (guix packages)
             (guix download)
             (guix git-download)
             (guix build-system cargo)
             (guix build-system pyproject)
             (guix build-system python)
             ((guix licenses) #:prefix license:)
             (guix gexp)
             (guix utils)
             (gnu packages audio)
             (gnu packages base)
             (gnu packages check)
             (gnu packages cmake)
             (gnu packages commencement)
             (gnu packages compression)
             (gnu packages elf)
             (gnu packages freedesktop)
             (gnu packages gcc)
             (gnu packages gnome)
             (gnu packages glib)
             (gnu packages gtk)
             (gnu packages linux)
             (gnu packages machine-learning)
             (gnu packages node)
             (gnu packages ninja)
             (gnu packages oneapi)
             (gnu packages pulseaudio)
             (gnu packages pkg-config)
             (gnu packages python)
             (gnu packages python-build)
             (gnu packages python-check)
             (gnu packages python-xyz)
             (gnu packages python-web)
             (gnu packages rust)
             (gnu packages speech)
             (gnu packages tls)
             (gnu packages video)
             (gnu packages web)
             (gnu packages webkit)
             (gnu packages xdisorg)
             (gnu packages xorg)
             (gnu packages rust-crates)
             (guix build utils))

(load "cargo-crate-sources.scm")

(define onednn-aarch64-jarvis
  ;; The Guix oneDNN 3.10.2 benchdnn sources do not compile on AArch64 with
  ;; DNNL_EXPERIMENTAL_UKERNEL enabled. Tests and benchmarks are not needed
  ;; when oneDNN is a runtime dependency of PyTorch.
  (package/inherit onednn
    (name "onednn-aarch64-jarvis")
    (arguments
     (substitute-keyword-arguments (package-arguments onednn)
       ((#:configure-flags flags)
        #~(append #$flags '("-DONEDNN_BUILD_TESTS=OFF")))))))

(define ctranslate2-aarch64-jarvis
  (package/inherit ctranslate2
    (name "ctranslate2-aarch64-jarvis")
    (native-inputs
     (modify-inputs (package-native-inputs ctranslate2)
       (replace "onednn" onednn-aarch64-jarvis)))))

(define python-ctranslate2-aarch64-jarvis
  (package/inherit python-ctranslate2
    (name "python-ctranslate2-aarch64-jarvis")
    (native-inputs
     (modify-inputs (package-native-inputs python-ctranslate2)
       (replace "ctranslate2" ctranslate2-aarch64-jarvis)))))

(define python-faster-whisper-aarch64-jarvis
  (package/inherit python-faster-whisper
    (name "python-faster-whisper-aarch64-jarvis")
    (propagated-inputs
     (modify-inputs (package-propagated-inputs python-faster-whisper)
       (replace "onnxruntime" (list onnxruntime-aarch64-jarvis "python"))
       (replace "python-ctranslate2" python-ctranslate2-aarch64-jarvis)))))

(define onnxruntime-aarch64-jarvis
  (package/inherit onnxruntime
    (name "onnxruntime-aarch64-jarvis")
    ;; PyTorch and SentencePiece are only used by ONNX Runtime's upstream
    ;; Python tests.  Jarvis exercises the installed runtime separately; these
    ;; test-only inputs pull in very large, broken-on-QEMU AArch64 builds.
    (arguments
     (substitute-keyword-arguments (package-arguments onnxruntime)
       ((#:tests? tests? #t) #f)))
    (native-inputs
     (modify-inputs (package-native-inputs onnxruntime)
       (delete "python-pytorch")
       (delete "python-sentencepiece")))))

(define python-dunamai-jarvis
  (package/inherit python-dunamai
    (name "python-dunamai-jarvis")
    (version "1.26.1")
    (source (origin
              (method url-fetch)
              (uri (pypi-uri "dunamai" version))
              (sha256
               (base32 "12qchr98zm2ggm4ikhmrq872vljz6vp1l2md9s1b802vsrxh0iiv"))))))

(define python-pathvalidate-jarvis
  (package/inherit python-pathvalidate
    (name "python-pathvalidate-jarvis")
    (version "3.3.1")
    (source (origin
              (method url-fetch)
              (uri (pypi-uri "pathvalidate" version))
              (sha256
               (base32 "0xx13cmssda0p6h4x69njyiibkyd85hiv3mv8m1n5bgy5chhg35i"))))))

(define opencode-binary
  (local-file "opencode-package" "jarvis-opencode-1.18.23"))

(define-public python-uv-dynamic-versioning-jarvis
  (package
    (name "python-uv-dynamic-versioning-jarvis")
    (version "0.14.1")
    (source (origin
              (method git-fetch)
              (uri (git-reference
                    (url "https://github.com/ninoseki/uv-dynamic-versioning/")
                    (commit (string-append "v" version))))
              (file-name (git-file-name name version))
              (sha256 (base32 "0j3hwab4ywgiydir1rdrc9hl9akzz47wqdb2cb3pjmxapki6zlcg"))))
    (build-system pyproject-build-system)
    (arguments (list #:tests? #f))
    (propagated-inputs (list python-dunamai-jarvis python-jinja2 python-tomlkit))
    (native-inputs (list python-hatchling))
    (home-page "https://github.com/ninoseki/uv-dynamic-versioning/")
    (synopsis "Dynamic versioning plugin for Hatch")
    (description "Dynamic versioning plugin for projects built with Hatch.")
    (license license:expat)))

(define-public python-mcp-types
  (package
    (name "python-mcp-types")
    (version "2.3.0")
    (source (origin
              (method url-fetch)
              (uri (pypi-uri "mcp_types" version))
              (sha256 (base32 "0qn33xw88p9zm3fr5smpk9c7xpdds7kcw3wljjdf2pmkxm4nbr6i"))))
    (build-system pyproject-build-system)
    (arguments (list #:tests? #f))
    (propagated-inputs (list python-pydantic python-typing-extensions))
    (native-inputs (list python-hatchling python-uv-dynamic-versioning-jarvis))
    (home-page "https://modelcontextprotocol.io")
    (synopsis "Model Context Protocol wire types")
    (description "Python wire types for the Model Context Protocol.")
    (license license:expat)))

(define-public python-httpcore2-jarvis
  (package
    (name "python-httpcore2-jarvis")
    (version "2.13.1")
    (source (origin
              (method git-fetch)
              (uri (git-reference
                    (url "https://github.com/pydantic/httpx2")
                    (commit (string-append "v" version))))
              (file-name (git-file-name name version))
              (sha256 (base32 "178byk7fwnmq8q4kvcca8dyzrkc767qhf4wp7jr11qqw5j4wa22y"))))
    (build-system pyproject-build-system)
    (arguments
     (list #:tests? #f
           #:phases
           #~(modify-phases %standard-phases
               (add-after 'unpack 'enter-httpcore2-subdirectory
                 (lambda _ (chdir "src/httpcore2"))))))
    (propagated-inputs (list python-h11 python-truststore))
    (native-inputs (list python-hatchling python-hatch-fancy-pypi-readme
                         python-uv-dynamic-versioning-jarvis))
    (home-page "https://github.com/pydantic/httpx2")
    (synopsis "Low-level HTTP transport for HTTPX2")
    (description "Low-level HTTP transport for the HTTPX2 Python client.")
    (license license:bsd-3)))

(define-public python-httpx2-jarvis
  (package
    (name "python-httpx2-jarvis")
    (version "2.13.1")
    (source (origin
              (method git-fetch)
              (uri (git-reference
                    (url "https://github.com/pydantic/httpx2")
                    (commit (string-append "v" version))))
              (file-name (git-file-name name version))
              (sha256 (base32 "178byk7fwnmq8q4kvcca8dyzrkc767qhf4wp7jr11qqw5j4wa22y"))))
    (build-system pyproject-build-system)
    (arguments
     (list #:tests? #f
           #:phases
           #~(modify-phases %standard-phases
               (add-after 'unpack 'enter-httpx2-subdirectory
                 (lambda _ (chdir "src/httpx2"))))))
    (propagated-inputs (list python-anyio python-httpcore2-jarvis python-idna
                             python-truststore python-typing-extensions))
    (native-inputs (list python-hatchling python-hatch-fancy-pypi-readme
                         python-uv-dynamic-versioning-jarvis))
    (home-page "https://github.com/pydantic/httpx2")
    (synopsis "Async-capable HTTP client")
    (description "HTTPX2 Python client required by the MCP SDK.")
    (license license:bsd-3)))

(define-public python-dbus-next-jarvis
  (package
    (name "python-dbus-next-jarvis")
    (version "0.2.3")
    (source (origin
              (method git-fetch)
              (uri (git-reference
                    (url "https://github.com/altdesktop/python-dbus-next")
                    (commit (string-append "v" version))))
              (file-name (git-file-name name version))
              (sha256 (base32 "1ahaz52kny1p9xxv6phvk4iq56rg8li390wywlxf2yslaij1188h"))))
    (build-system pyproject-build-system)
    ;; The upstream release has no setuptools `test` command; Guix's default
    ;; Python check phase still invokes it for this project.
    (arguments (list #:tests? #f))
    (native-inputs (list python-setuptools))
    (home-page "https://github.com/altdesktop/python-dbus-next")
    (synopsis "Async DBus library")
    (description "Zero-dependency DBus library with asyncio support.")
    (license license:expat)))

(define-public python-mcp-jarvis
  (package
    (name "python-mcp-jarvis")
    (version "2.3.0")
    (source (origin
              (method url-fetch)
              (uri (pypi-uri "mcp" version))
              (sha256 (base32 "1n1l5gyyyc03p7kwviir1ymg11rnxnpf1166i3f5kw0w8i87l54b"))))
    (build-system pyproject-build-system)
    (arguments (list #:tests? #f))
    (propagated-inputs (list python-anyio python-click python-httpx2-jarvis
                             python-jsonschema python-mcp-types
                             python-opentelemetry-api python-pydantic
                             python-pyjwt python-multipart python-sse-starlette
                             python-starlette python-typing-extensions
                             python-typing-inspection python-uvicorn))
    (native-inputs (list python-hatchling python-uv-dynamic-versioning-jarvis))
    (home-page "https://modelcontextprotocol.io")
    (synopsis "Model Context Protocol SDK")
    (description "Python SDK for the Model Context Protocol, version 2.3.0.")
    (license license:expat)))

(define-public python-piper-tts-jarvis
  (package
    (name "python-piper-tts-jarvis")
    (version "1.8.0")
    (source (origin
              (method git-fetch)
              (uri (git-reference
                    (url "https://github.com/OHF-Voice/piper1-gpl")
                    (commit (string-append "v" version))))
              (file-name (git-file-name name version))
              (sha256 (base32 "1gxwrg3fvsp6hq879nb89h994jccy15gy2xfwgzrfn44gzk32nmf"))))
    (build-system pyproject-build-system)
    (arguments
     (list
      #:phases
      #~(modify-phases %standard-phases
          (add-after 'unpack 'no-embedded-git-fetch
            (lambda* (#:key inputs #:allow-other-keys)
              (use-modules (ice-9 regex)
                           (ice-9 rdelim))
              (let ((pattern (make-regexp
                              "ExternalProject_Add\\(espeak_ng_external[^)]+\\)"
                              regexp/extended))
                    (replacement "add_library(espeak_ng_external INTERFACE)"))
                (with-atomic-file-replacement "CMakeLists.txt"
                  (lambda (in out)
                    (display (regexp-substitute/global
                              #f pattern (read-string in) 'pre replacement 'post)
                             out))))
              (let ((espeak (assoc-ref inputs "espeak-ng"))
                    (espeak-lib (search-input-file inputs "lib/libespeak-ng.so.1"))
                    (espeak-data (search-input-directory inputs
                                  "share/espeak-ng-data"))
                    (cmake-setter (lambda (key value)
                                    (string-append "set(" key " \"" value "\")\n"))))
                (substitute* "CMakeLists.txt"
                  (("set\\(ESPEAKNG_INSTALL_DIR .*")
                   (cmake-setter "ESPEAKNG_INSTALL_DIR" espeak))
                  (("set\\(ESPEAKNG_STATIC_LIB .*")
                   (cmake-setter "ESPEAKNG_STATIC_LIB" espeak-lib))
                  (("set\\(UCD_STATIC_LIB .*")
                   (cmake-setter "UCD_STATIC_LIB" ""))
                  (("set\\(DATA_SRC .*")
                   (cmake-setter "DATA_SRC" espeak-data)))))))))
    (native-inputs (list ninja python-scikit-build python-setuptools
                         python-pytest))
    (propagated-inputs (list espeak-ng python-pathvalidate-jarvis python-numpy
                             (list (if (target-aarch64?)
                                       onnxruntime-aarch64-jarvis
                                       onnxruntime)
                                   "python")))
    (home-page "https://github.com/OHF-Voice/piper1-gpl")
    (synopsis "Fast and local neural TTS engine")
    (description "Piper is a fast and local neural text-to-speech engine
that embeds espeak-ng for phonemization.")
    (license license:gpl3+)))

(define rust-lock-inputs
  (map (lambda (source index)
         (list (string-append "rust-lock-" (number->string index)) source))
       jarvis-cargo-lock-inputs
       (iota (length jarvis-cargo-lock-inputs))))

(define-public jarvis-assistant
  (package
    (name "jarvis-assistant")
    (version "0.1.0")
    (source (local-file "jarvis-guix-source.tar.gz"))
    (build-system cargo-build-system)
    (arguments
     (list
      #:cargo-inputs rust-lock-inputs
      #:install-source? #f
      #:parallel-build? #f
      #:cargo-build-flags ''("--release")
      #:phases
      #~(modify-phases %standard-phases
          ;; OpenCode ships optional ELF modules for both glibc and musl, so
          ;; Guix's blanket single-target RUNPATH audit cannot classify them.
          (delete 'validate-runpath)
          (add-after 'unpack 'enter-tauri-project
            (lambda _ (chdir "gui/src-tauri")))
          ;; Stripping OpenCode drops version metadata used by --version.
          (add-before 'strip 'save-opencode-unstripped
            (lambda* (#:key outputs #:allow-other-keys)
              (copy-file
               (string-append (assoc-ref outputs "out")
                              "/lib/jarvis/bin/opencode")
               (string-append (getenv "TMPDIR")
                              "/jarvis-opencode-unstripped"))))
          (add-after 'strip 'restore-opencode-unstripped
            (lambda* (#:key outputs #:allow-other-keys)
              (let ((opencode (string-append (assoc-ref outputs "out")
                                             "/lib/jarvis/bin/opencode")))
                (copy-file (string-append (getenv "TMPDIR")
                                          "/jarvis-opencode-unstripped")
                             opencode)
                (chmod opencode #o755))))
          (replace 'install
            (lambda* (#:key outputs inputs #:allow-other-keys)
              (let* ((out (assoc-ref outputs "out"))
                     (opencode (string-append (getenv "TMPDIR") "/jarvis-opencode"))
                     (loader (search-input-file inputs "/lib/ld-linux-x86-64.so.2")))
                (copy-file #$opencode-binary opencode)
                (chmod opencode #o755)
                (invoke "patchelf" "--set-interpreter" loader opencode)
                (setenv "HOME" (getenv "TMPDIR"))
                (setenv "XDG_CACHE_HOME"
                        (string-append (getenv "TMPDIR") "/.cache"))
                (invoke "python3" "../../scripts/prepare-package.py"
                        "--prefix" out "--destdir" ""
                        "--overlay" "target/release/jarvis-overlay"
                        "--external-python-runtime"
                        (search-input-file inputs "/bin/python3")
                        "--opencode" opencode)
                (let* ((launcher (string-append out "/bin/jarvis"))
                       (path (string-append
                              (assoc-ref inputs "python-wrapper") "/bin:"
                              (assoc-ref inputs "python-piper-tts-jarvis") "/bin:"
                              (assoc-ref inputs "ffmpeg") "/bin:"
                              (assoc-ref inputs "pulseaudio") "/bin:"
                              (assoc-ref inputs "alsa-utils") "/bin:"
                              (assoc-ref inputs "xdotool") "/bin:"
                              (assoc-ref inputs "wl-clipboard") "/bin:"
                              (assoc-ref inputs "xclip") "/bin:"
                              (assoc-ref inputs "dbus") "/bin:"
                              (assoc-ref inputs "espeak-ng") "/bin:"
                              (assoc-ref inputs "at-spi2-core") "/bin:"
                              (assoc-ref inputs "glib") "/bin"))
                       (python-path (or (getenv "GUIX_PYTHONPATH")
                                        (getenv "PYTHONPATH") "")))
                  (wrap-program launcher
                    `("PATH" ":" prefix (,path))
                    `("PYTHONPATH" ":" prefix (,python-path))
                    `("LD_LIBRARY_PATH" ":" prefix
                      (,(string-append (assoc-ref inputs "gtk+") "/lib")
                       ,(string-append (assoc-ref inputs "webkitgtk-for-gtk3") "/lib")
                       ,(string-append (assoc-ref inputs "libsoup") "/lib")
                       ,(string-append (assoc-ref inputs "glib") "/lib")
                       ,(dirname (search-input-file inputs "/lib/libstdc++.so.6"))
                       ,(string-append (assoc-ref inputs "glibc") "/lib")))))))))))
    (inputs
     (list python-wrapper
                   (if (target-aarch64?)
                       python-faster-whisper-aarch64-jarvis
                       python-faster-whisper)
                   (if (target-aarch64?)
                       python-ctranslate2-aarch64-jarvis
                       python-ctranslate2)
                   python-av
                   (list (if (target-aarch64?)
                             onnxruntime-aarch64-jarvis
                             onnxruntime)
                         "python") python-httpx python-jsonschema
                   python-mcp-jarvis python-pygobject python-dbus-next-jarvis
                   python-piper-tts-jarvis ffmpeg pulseaudio alsa-utils
                   gtk+ webkitgtk-for-gtk3 libsoup glib at-spi2-core espeak-ng dbus
                   xdotool wl-clipboard xclip zlib openssl glibc
                   (list gcc-14 "lib")))
    (native-inputs (list pkg-config node rust patchelf))
    (home-page "https://github.com/V1nic1us/jarvis")
    (synopsis "Voice assistant with a native Linux overlay")
    (description
     "Jarvis is a local voice assistant with speech recognition and a native desktop overlay.")
    (license (list license:asl2.0 license:expat license:gpl3+))
    (supported-systems '("x86_64-linux" "aarch64-linux"))))

jarvis-assistant
