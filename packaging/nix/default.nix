{
  lib,
  stdenvNoCC,
  stdenv,
  python314,
  autoPatchelfHook,
  buildNpmPackage,
  fetchurl,
  makeWrapper,
  rustPlatform,
  pkg-config,
  wrapGAppsHook3,
  gtk3,
  webkitgtk_4_1,
  libsoup_3,
  glib,
  ffmpeg,
  pulseaudio,
  alsa-utils,
  xdotool,
  wl-clipboard,
  xclip,
  at-spi2-core,
  espeak-ng,
  zlib,
  openssl,
  src,
}:
let
  opencodeSources = builtins.fromJSON (builtins.readFile "${src}/packaging/opencode-sources.json");
  target = if stdenv.hostPlatform.isAarch64 then "aarch64-glibc" else "x86_64-glibc";
  opencodeSource = opencodeSources.${target};
  opencodeArchive = fetchurl {
    url = opencodeSource.url;
    hash = opencodeSource.integrity;
  };

  opencode = stdenvNoCC.mkDerivation {
    pname = "jarvis-opencode";
    version = opencodeSource.version;
    dontUnpack = true;
    nativeBuildInputs = [ autoPatchelfHook ];
    buildInputs = [ stdenv.cc.cc.lib zlib openssl ];
    installPhase = ''
      mkdir -p "$out/bin"
      tar -xOzf "${opencodeArchive}" opencode > "$out/bin/opencode"
      chmod 0555 "$out/bin/opencode"
    '';
    meta.license = lib.licenses.mit;
  };

  python = python314;
  piperWheel = if stdenv.hostPlatform.isAarch64 then {
    url = "https://files.pythonhosted.org/packages/5e/90/de832b09736db8c26c9b5dd25cb408ed065b1d9535e05c78947aec056e36/piper_tts-1.8.0-cp39-abi3-manylinux_2_17_aarch64.manylinux2014_aarch64.manylinux_2_28_aarch64.whl";
    sha256 = "3f60c1917de6d8e8033f395878ad3f88f6dfee88a8b05f98971a275f76a38484";
  } else {
    url = "https://files.pythonhosted.org/packages/84/81/0112a7d510911f33018dc24023d1655bb772f84a4e95fe7f0180f66bbd17/piper_tts-1.8.0-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.manylinux_2_28_x86_64.whl";
    sha256 = "25b4d3f31ff70c8fa7151908e00aaa5650cbdf16bca8fcf21299f3941b89a7d3";
  };

  piperTts = python.pkgs.buildPythonPackage {
    pname = "piper-tts";
    version = "1.8.0";
    format = "wheel";
    src = fetchurl piperWheel;
    nativeBuildInputs = [ autoPatchelfHook ];
    buildInputs = [ stdenv.cc.cc.lib espeak-ng ];
    dependencies = with python.pkgs; [ onnxruntime pathvalidate ];
    pythonImportsCheck = [ "piper" ];
  };

  pythonEnv = python.withPackages (ps: with ps; [
    av
    ctranslate2
    dbus-next
    faster-whisper
    httpx
    jsonschema
    mcp
    onnxruntime
    pygobject3
    piperTts
  ]);

  overlay = rustPlatform.buildRustPackage {
    pname = "jarvis-overlay";
    version = "0.1.0";
    inherit src;
    cargoRoot = "gui/src-tauri";
    buildAndTestSubdir = "gui/src-tauri";
    cargoLock.lockFile = "${src}/gui/src-tauri/Cargo.lock";
    cargoBuildFlags = [ "--locked" ];
    doCheck = false;
    dontUseCargoInstallHook = true;
    nativeBuildInputs = [ pkg-config wrapGAppsHook3 ];
    buildInputs = [ gtk3 webkitgtk_4_1 libsoup_3 glib ];
    installPhase = ''
      runHook preInstall
      mkdir -p "$out/bin"
      cp "target/${stdenv.hostPlatform.rust.rustcTarget}/release/jarvis-overlay" "$out/bin/jarvis-overlay"
      runHook postInstall
    '';
  };

  plugin = buildNpmPackage {
    pname = "jarvis-opencode-plugin";
    version = "0.1.0";
    src = "${src}/.opencode";
    sourceRoot = ".";
    postPatch = ''
      cp -a "${src}/.opencode/." .
      chmod -R u+w .
    '';
    npmDepsHash = "sha256-lnyoIScrNdPeu9J7XUpbteOUQVENF7tzJqrII0fwTbY=";
    dontNpmBuild = true;
    installPhase = ''
      mkdir -p "$out"
      cp -a node_modules "$out/node_modules"
    '';
  };

  runtimeTools = [
    ffmpeg
    pulseaudio
    alsa-utils
    xdotool
    wl-clipboard
    xclip
    espeak-ng
    at-spi2-core
  ];
  runtimePath = lib.makeBinPath runtimeTools + ":${pythonEnv}/bin";
in
stdenvNoCC.mkDerivation {
  pname = "jarvis-assistant";
  version = "0.1.0";
  dontUnpack = true;
  nativeBuildInputs = [ python makeWrapper autoPatchelfHook ];
  buildInputs = [ stdenv.cc.cc.lib zlib openssl ] ++ runtimeTools;
  installPhase = ''
    runHook preInstall
    python "${src}/scripts/prepare-package.py" \
      --prefix "$out" --destdir "" \
      --overlay "${overlay}/bin/jarvis-overlay" \
      --python "${pythonEnv}/bin/python3" \
      --external-python-runtime "${pythonEnv}/bin/python3" \
      --without-node-modules \
      --opencode "${opencode}/bin/opencode" \
      --expected-opencode-version "1.18.23"
    ln -s "${plugin}/node_modules" "$out/lib/jarvis/.opencode/node_modules"
    rm "$out/bin/jarvis"
    makeWrapper "$out/lib/jarvis/jarvis" "$out/bin/jarvis" \
      --prefix PATH : "${runtimePath}"
    runHook postInstall
  '';
  meta = {
    description = "Voice assistant with native desktop overlay";
    homepage = "https://github.com/GuilhermeBn/jarvis";
    license = with lib.licenses; [ asl20 mit gpl3Plus ];
    platforms = [ "x86_64-linux" "aarch64-linux" ];
    mainProgram = "jarvis";
  };
}
