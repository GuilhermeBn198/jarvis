"""Verify integrity and extraction boundaries of release dependency archives."""
import hashlib
import importlib.util
import io
import tarfile
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]


def test_completed_native_package_recipes_provide_xdg_open():
    recipes={
        'Arch': (ROOT/'packaging/arch/PKGBUILD', "'xdg-utils'"),
        'Alpine': (ROOT/'packaging/alpine/APKBUILD', 'xdg-utils'),
        'Debian/Ubuntu': (ROOT/'packaging/debian/control', 'xdg-utils'),
        'Fedora': (ROOT/'packaging/rpm/fedora/jarvis-assistant.spec', 'xdg-utils'),
        'RHEL/AlmaLinux': (ROOT/'packaging/rpm/rhel/jarvis-assistant.spec', 'xdg-utils'),
        'openSUSE': (ROOT/'packaging/rpm/suse/jarvis-assistant.spec', 'xdg-utils'),
        'Void glibc': (ROOT/'packaging/void/template', 'xdg-utils'),
        'Void musl': (ROOT/'packaging/void-musl/template', 'xdg-utils'),
        'Solus': (ROOT/'packaging/solus/package.yml', 'xdg-utils'),
        'Nix': (ROOT/'packaging/nix/default.nix', 'xdg-utils'),
    }
    missing=[name for name,(path,provider) in recipes.items() if provider not in path.read_text()]
    assert not missing, f'missing xdg-open provider in completed recipes: {missing}'
    lifecycle=(ROOT/'scripts/test-native-package.sh').read_text()
    assert 'task_runtime_tools="$task_runtime_tools xdg-open"' in lifecycle


def test_installed_package_smokes_verify_opencode_mit_notice():
    native=(ROOT/'scripts/test-native-package.sh').read_text()
    nix=(ROOT/'scripts/test-nix-package.sh').read_text()
    flatpak=(ROOT/'scripts/build-flatpak.sh').read_text()
    for content in (native,nix,flatpak):
        assert 'opencode-MIT.txt' in content
        assert 'Copyright (c) 2025 opencode' in content


spec=importlib.util.spec_from_file_location('fetch_opencode',ROOT/'scripts/fetch-opencode.py')
fetch=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)
overlay_spec=importlib.util.spec_from_file_location('overlay_instance',ROOT/'scripts/test-overlay-instance.py')
overlay=importlib.util.module_from_spec(overlay_spec)
overlay_spec.loader.exec_module(overlay)


def test_overlay_x11_environment_ignores_host_desktop_choice(monkeypatch):
    monkeypatch.setenv('XDG_CURRENT_DESKTOP','KDE')
    monkeypatch.setenv('XDG_SESSION_DESKTOP','KDE')
    env=overlay.x11_environment(':42')
    assert env['DISPLAY']==':42'
    assert 'XDG_CURRENT_DESKTOP' not in env
    assert 'XDG_SESSION_DESKTOP' not in env


def test_void_builds_are_not_cancelled_by_new_commits():
    for name in ('linux-void.yml','linux-nix.yml','linux-packages.yml'):
        workflow=(ROOT/'.github/workflows'/name).read_text()
        assert 'cancel-in-progress: false' in workflow, name


def test_suse_rolling_container_synchronizes_snapshot_before_installing_build_deps():
    dockerfile=(ROOT/'packaging/rpm/suse/Dockerfile').read_text()
    refresh=dockerfile.index('zypper --non-interactive refresh --force')
    dup=dockerfile.index('zypper --non-interactive dup --no-recommends')
    install=dockerfile.index('zypper --non-interactive install --no-recommends')
    assert refresh < dup < install


def archive(binary=b'\x7fELFtest',kind=tarfile.REGTYPE,extra=None):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as tar:
        member=tarfile.TarInfo('opencode')
        member.type=kind
        member.linkname='../../outside'
        member.size=len(binary) if kind==tarfile.REGTYPE else 0
        tar.addfile(member,io.BytesIO(binary) if member.size else None)
        if extra:
            member=tarfile.TarInfo(extra);member.size=4
            tar.addfile(member,io.BytesIO(b'evil'))
    data=stream.getvalue()
    integrity='sha256:'+hashlib.sha256(data).hexdigest()
    return data,integrity


def test_verified_archive_installs_only_agent(tmp_path):
    data,integrity=archive(extra='../outside')
    output=tmp_path/'private/bin/opencode'
    fetch.extract_verified(data,integrity,output)
    assert output.read_bytes()==b'\x7fELFtest'
    assert output.stat().st_mode & 0o777==0o755
    assert not (tmp_path/'outside').exists()
    assert not output.with_name('opencode.partial').exists()


@pytest.mark.parametrize('kind',[tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.DIRTYPE])
def test_archive_refuses_non_regular_agent(tmp_path,kind):
    data,integrity=archive(kind=kind)
    with pytest.raises(ValueError,match='regular'):
        fetch.extract_verified(data,integrity,tmp_path/'opencode')
    assert not (tmp_path/'opencode').exists()


def test_corrupt_archive_preserves_installed_binary(tmp_path):
    data,integrity=archive()
    output=tmp_path/'opencode';output.write_bytes(b'existing')
    with pytest.raises(ValueError,match='SHA256'):
        fetch.extract_verified(data+b'corruption',integrity,output)
    assert output.read_bytes()==b'existing'


def test_non_elf_payload_is_rejected(tmp_path):
    data,integrity=archive(binary=b'#!/bin/sh\n')
    with pytest.raises(ValueError,match='ELF'):
        fetch.extract_verified(data,integrity,tmp_path/'opencode')


def test_source_archive_contains_build_inputs_without_user_state(tmp_path):
    script=ROOT/'scripts/source-archive.py'
    assert script.is_file()
    import subprocess
    output=tmp_path/'source.tar.gz'
    subprocess.run(['python3',str(script),'--output',str(output)],check=True,capture_output=True,text=True)
    with tarfile.open(output) as tar:
        names=set(tar.getnames())
    for required in ('gui/src-tauri/Cargo.lock','scripts/prepare-package.py',
                     'packaging/rpm/fedora/jarvis-assistant.spec','voice/linux_input.py',
                     'voice/model_selection.py','voice/linux_eis.py',
                     'packaging/opencode/LICENSE',
                     '.opencode/package-lock.json','flake.nix','flake.lock'):
        assert 'jarvis-0.1.0/'+required in names
    assert not any('/.venv/' in name or '/node_modules/' in name or '/.superpowers/' in name or '/target/' in name for name in names)
    assert all(name.startswith('jarvis-0.1.0/') for name in names)


def test_arch_native_builder_is_x86_64_only():
    driver=(ROOT/'scripts/build-package.sh').read_text()
    arch_branch=driver.split('    arch)\n',1)[1].split('    slackware)',1)[0]
    assert 'archarm' not in arch_branch
    assert 'Arch Linux ARM' not in arch_branch
    assert '[ "$task_arch" != x86_64 ]' in driver


def test_arch_native_package_lifecycle_is_x86_64_only():
    lifecycle=(ROOT/'scripts/test-native-package.sh').read_text()
    assert 'arch:arch|arch:archarm)' not in lifecycle
    assert "expected={'x86_64':62,'aarch64':183}" not in lifecycle
    upgrade=(ROOT/'scripts/test-native-arch-upgrade.sh').read_text()
    assert 'arch|archarm)' not in upgrade
    assert 'aarch64' not in upgrade


def test_arch_arm64_is_not_in_active_package_ci():
    workflow=(ROOT/'.github/workflows/linux-packages.yml').read_text()
    assert "family: arch, arch: aarch64" not in workflow
    assert 'ubuntu-24.04-arm' not in workflow
    assert 'test-native-arch-upgrade.sh' in workflow


def test_arch_docker_export_accepts_makepkg_compression_extensions():
    dockerfile=(ROOT/'packaging/arch/Dockerfile').read_text()
    assert 'cp /build/packages/*.pkg.tar.* /out/' in dockerfile


@pytest.mark.parametrize(('arch','repo','bootstrap'),[
    ('x86_64','https://repo-default.voidlinux.org/current','https://repo-default.voidlinux.org/current/bootstrap'),
    ('x86_64-musl','https://repo-default.voidlinux.org/current/musl','https://repo-default.voidlinux.org/current/musl/bootstrap'),
])
def test_void_repository_url_resolves_architecture_layout(arch,repo,bootstrap):
    import subprocess
    import os
    resolver=ROOT/'packaging/void/repository-url.sh'
    env={**os.environ,'JARVIS_VOID_REPOSITORY_BASE':'https://mirror.example/void/current'}
    main=subprocess.run([str(resolver),arch,'main'],capture_output=True,text=True,env=env)
    boot=subprocess.run([str(resolver),arch,'bootstrap'],capture_output=True,text=True,env=env)
    assert main.returncode==0,main.stderr
    assert boot.returncode==0,boot.stderr
    expected_suffix=repo.removeprefix('https://repo-default.voidlinux.org/current')
    expected_bootstrap_suffix=bootstrap.removeprefix('https://repo-default.voidlinux.org/current')
    assert main.stdout.strip()=='https://mirror.example/void/current'+expected_suffix
    assert boot.stdout.strip()=='https://mirror.example/void/current'+expected_bootstrap_suffix


def test_void_bootstrap_creates_host_xbps_cache_before_copying_it():
    dockerfile=(ROOT/'packaging/void/Dockerfile').read_text()
    assert 'mkdir -p /var/cache/xbps' in dockerfile
    assert dockerfile.index('mkdir -p /var/cache/xbps') < dockerfile.index('cp -a /var/cache/xbps/.')


def test_overlay_accessibility_reader_retries_stale_nodes():
    class StaleNodeError(Exception):pass
    def stale_read():raise StaleNodeError('application no longer exists')
    assert overlay.read_atspi(stale_read,StaleNodeError,fallback=[])==[]


def test_overlay_accessibility_reader_preserves_unrelated_errors():
    class StaleNodeError(Exception):pass
    def broken_read():raise RuntimeError('unexpected failure')
    with pytest.raises(RuntimeError,match='unexpected failure'):
        overlay.read_atspi(broken_read,StaleNodeError)


def test_native_driver_rejects_fedora_target_on_arch(tmp_path):
    import subprocess
    if 'ID=arch' not in Path('/etc/os-release').read_text():pytest.skip('requires Arch host')
    result=subprocess.run([str(ROOT/'scripts/build-package.sh'),'--target','fedora','--output',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==2
    assert 'exige ambiente Fedora' in result.stderr


def test_native_driver_rejects_debian_target_on_arch(tmp_path):
    import subprocess
    if 'ID=arch' not in Path('/etc/os-release').read_text():pytest.skip('requires Arch host')
    result=subprocess.run([str(ROOT/'scripts/build-package.sh'),'--target','debian','--output',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==2
    assert 'exige ambiente Debian' in result.stderr


def test_native_driver_rejects_ubuntu_target_on_arch(tmp_path):
    import subprocess
    if 'ID=arch' not in Path('/etc/os-release').read_text():pytest.skip('requires Arch host')
    result=subprocess.run([str(ROOT/'scripts/build-package.sh'),'--target','ubuntu','--output',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==2
    assert 'exige ambiente Ubuntu' in result.stderr


def test_native_driver_rejects_suse_target_on_arch(tmp_path):
    import subprocess
    if 'ID=arch' not in Path('/etc/os-release').read_text():pytest.skip('requires Arch host')
    result=subprocess.run([str(ROOT/'scripts/build-package.sh'),'--target','suse','--output',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==2
    assert 'exige openSUSE Tumbleweed' in result.stderr


def test_native_driver_rejects_slackware_target_on_arch(tmp_path):
    import subprocess
    if 'ID=arch' not in Path('/etc/os-release').read_text():pytest.skip('requires Arch host')
    result=subprocess.run([str(ROOT/'scripts/build-package.sh'),'--target','slackware','--output',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==2
    assert 'fora do escopo de build' in result.stderr


def test_target_catalog_records_recipe_and_validation_separately():
    import json
    catalog=json.loads((ROOT/'packaging/targets.json').read_text())
    assert {'arch','debian','fedora','suse','alpine','flatpak','void-glibc','void-musl',
            'gentoo','nix','guix','slackware','solus'} <= set(catalog)
    for target,item in catalog.items():
        assert item['libc'] in ('glibc','musl')
        assert item['architectures']==['x86_64']
        assert item['validation'] in ('unverified','extracted-smoke','installed-smoke','bundle-smoke')
        if item['recipe'] is not None:
            assert (ROOT/item['recipe']).is_file(),target
        else:
            assert item['implementation']=='pending'
    assert catalog['void-musl']['libc']=='musl'
    assert catalog['void-musl']['implementation']=='recipe'
    assert catalog['void-musl']['recipe']=='packaging/void-musl/template'
    assert catalog['void-musl']['validation']=='installed-smoke'
    assert catalog['void-musl']['validated_architectures']==['x86_64']
    for target in ('void-musl','nix','slackware','solus'):
        assert catalog[target]['delivery_scope']=='excluded'
    assert catalog['flatpak']['validated_architectures']==['x86_64']
    for item in catalog.values():
        assert set(item['validated_architectures']) <= set(item['architectures'])
        if item['validation']=='unverified':assert not item['validated_architectures']
        elif item['validation']=='bundle-smoke':assert item['validated_architectures']
        else:assert item['validated_architectures']


def test_target_catalog_validation_matches_passed_package_lifecycle_evidence():
    import json
    catalog=json.loads((ROOT/'packaging/targets.json').read_text())
    matrix=json.loads((ROOT/'docs/notes/linux-matrix.json').read_text())
    for target,item in catalog.items():
        capabilities=({'flatpak_native_bundle_lifecycle','flatpak_installed_runtime_smoke'}
                      if item['validation']=='bundle-smoke' else {'native_package_lifecycle'})
        lifecycle=[row for row in matrix['results']
                   if row.get('target')==target
                   and row.get('capability') in capabilities]
        passed={row['arch'] for row in lifecycle
                if row['status']=='passed' and row['arch'] in item['architectures']}
        assert passed==set(item['validated_architectures']),target


def test_guix_aarch64_onednn_disables_upstream_tests():
    recipe=(ROOT/'packaging/guix/jarvis.scm').read_text()
    onednn=recipe.split('(define onednn-aarch64-jarvis',1)[1].split('(define ctranslate2-aarch64-jarvis',1)[0]
    assert '"-DDNNL_BUILD_TESTS=OFF"' in onednn
    assert '"-DDNNL_BUILD_EXAMPLES=OFF"' in onednn
    assert '((#:tests? tests? #t) #f)' in onednn


def test_guix_removes_unused_windows_binaries_before_binary_scan():
    recipe=(ROOT/"packaging/guix/jarvis.scm").read_text()
    assistant=recipe.split("(define-public jarvis-assistant",1)[1]
    phase=assistant.split("(replace 'install",1)[0]
    assert "add-after 'configure 'remove-unused-windows-binaries" in phase
    assert '(delete-file-recursively path)' in phase
    assert '"guix-vendor/rust-libloading-0.7.4.tar.gz/tests/nagisa32.dll"' in phase
    assert '"guix-vendor/rust-libloading-0.7.4.tar.gz/tests/nagisa64.dll"' in phase
    assert '"guix-vendor/rust-winapi-i686-pc-windows-gnu-0.4.0.tar.gz/lib"' in phase
    assert '"guix-vendor/rust-winapi-x86-64-pc-windows-gnu-0.4.0.tar.gz/lib"' in phase
    for target in ('aarch64-gnullvm','aarch64-msvc','i686-gnu','i686-msvc',
                   'x86-64-gnu','x86-64-gnullvm','x86-64-msvc'):
        assert f'"guix-vendor/rust-windows-{target}-0.42.2.tar.gz/lib"' in phase
    for path in ('arm64','x64','x86'):
        assert f'"guix-vendor/rust-webview2-com-sys-0.39.1.tar.gz/{path}"' in phase
    for path in ('src/rt/libwit_bindgen_cabi.a',
                 'src/rt/wit_bindgen_cabi_realloc.o',
                 'src/rt/wit_bindgen_cabi_wasip3.o',
                 'wasi-cli@0.2.0.wasm'):
        assert f'"guix-vendor/rust-wit-bindgen-0.57.1.tar.gz/{path}"' in phase


def test_guix_profile_smoke_checks_optional_libei_fallback():
    smoke=(ROOT/'scripts/test-guix-package.sh').read_text()
    assert "'libei'" in smoke
    assert 'EISPointer' in smoke
    assert "'unsupported'" in smoke


def test_guix_pins_rust_190_for_current_cargo_lockfile():
    recipe=(ROOT/'packaging/guix/jarvis.scm').read_text()
    toolchain=(ROOT/'packaging/guix/rust-toolchain.scm').read_text()
    assert '(define rust-1.90-jarvis' in toolchain
    assert '"1.90.0"' in toolchain
    assistant=recipe.split('(define-public jarvis-assistant',1)[1]
    assert '(list pkg-config node rust-1.90-jarvis' in assistant
    assert '(list rust-1.90-jarvis "cargo")' in assistant
    assert '(load "rust-toolchain.scm")' in recipe


def test_guix_uv_dynamic_versioning_uses_compatible_dunamai():
    recipe=(ROOT/'packaging/guix/jarvis.scm').read_text()
    dunamai=recipe.split('(define python-dunamai-jarvis',1)[1].split('(define-public python-uv-dynamic-versioning-jarvis',1)[0]
    assert '(version "1.26.1")' in dunamai
    plugin=recipe.split('(define-public python-uv-dynamic-versioning-jarvis',1)[1].split('(define-public python-mcp-types',1)[0]
    assert 'python-dunamai-jarvis' in plugin


def test_guix_piper_uses_compatible_pathvalidate():
    recipe=(ROOT/'packaging/guix/jarvis.scm').read_text()
    pathvalidate=recipe.split('(define python-pathvalidate-jarvis',1)[1].split('(define opencode-binary',1)[0]
    assert '(version "3.3.1")' in pathvalidate
    assert '#:tests? #f' in pathvalidate
    assert '("Version: 0.0.0") "Version: 3.3.1"' in pathvalidate
    assert 'find-files (assoc-ref outputs "out") "METADATA"' in pathvalidate
    assert 'pathvalidate-3.3.1.dist-info' in pathvalidate
    assert 'pathvalidate-0\\\\.0\\\\.0.dist-info' in pathvalidate
    piper=recipe.split('(define-public python-piper-tts-jarvis',1)[1].split('(define rust-lock-inputs',1)[0]
    assert 'python-pathvalidate-jarvis' in piper


def test_guix_target_has_local_package_recipe_and_native_driver(tmp_path):
    import json
    catalog=json.loads((ROOT/'packaging/targets.json').read_text())
    item=catalog['guix']
    assert item['implementation']=='recipe'
    assert item['recipe']=='packaging/guix/jarvis.scm'
    assert item['validation']=='installed-smoke'
    assert item['architectures']==['x86_64']
    assert item['validated_architectures']==['x86_64']
    assert "#:cargo-build-flags ''(\"--release\")" in (ROOT/item['recipe']).read_text()
    assert '"../../scripts/prepare-package.py"' in (ROOT/item['recipe']).read_text()
    recipe=ROOT/item['recipe']
    assert recipe.is_file()
    crate_sources=(ROOT/'packaging/guix/cargo-crate-sources.scm').read_text()
    cargo_inputs=crate_sources.split('(define jarvis-cargo-lock-inputs',1)[1]
    import re
    defined=set(re.findall(r'^\(define (rust-[^\s)]+)',crate_sources,re.M))
    listed=set(re.findall(r'^\s+(rust-[^\s)]+)',cargo_inputs,re.M))
    assert defined <= listed
    recipe_text=recipe.read_text()
    build_driver=(ROOT/'scripts/build-package.sh').read_text()
    assert '"$task_root/packaging/guix/rust-toolchain.scm"' in build_driver
    assert '(supported-systems \'("x86_64-linux"))' in recipe_text
    assert '(guix build-system python)' in recipe_text
    assert '(inherit python-piper-tts)' not in recipe_text
    assert "add-after 'unpack 'no-embedded-git-fetch" in recipe_text
    assert '(gnu packages cmake)' in recipe_text and '(gnu packages ninja)' in recipe_text
    assert '(gnu packages check)' in recipe_text
    assert '(gnu packages python-check)' in recipe_text
    piper_recipe=recipe_text.split('(define-public python-piper-tts-jarvis',1)[1].split('(define rust-lock-inputs',1)[0]
    assert '(home-page "https://github.com/OHF-Voice/piper1-gpl")' in piper_recipe
    assert '(synopsis "Fast and local neural TTS engine")' in piper_recipe
    assert '(license license:gpl3+)' in piper_recipe
    assert '(gnu packages elf)' in recipe_text
    assert 'jarvis-opencode-1.18.23' in recipe_text
    assert 'copy-file\n               (string-append (assoc-ref outputs "out")' in recipe_text
    assert 'copy-file (string-append (getenv "TMPDIR")' in recipe_text
    assert '(getenv "GUIX_PYTHONPATH")' in recipe_text
    assert "add-before 'strip 'save-opencode-unstripped" in recipe_text
    assert "add-after 'strip 'restore-opencode-unstripped" in recipe_text
    assert 'webkitgtk-for-gtk3' in recipe_text
    assert 'assoc-ref inputs "webkitgtk-for-gtk3"' in recipe_text
    assert '(invoke "patchelf" "--set-interpreter" loader opencode)' in recipe_text
    assert '"--set-rpath"' not in recipe_text
    assert '(chmod opencode #o755)' in recipe_text
    assert 'pkg-config node' in recipe_text
    assert '(list pkg-config node rust-1.90-jarvis' in recipe_text
    assert '(list rust-1.90-jarvis "cargo")' in recipe_text
    assert 'patchelf))' in recipe_text
    assert 'xclip zlib openssl glibc' in recipe_text and '(list gcc-14 "lib"))' in recipe_text
    assert "(delete 'validate-runpath)" in recipe_text
    assert 'dirname (search-input-file inputs "/lib/libstdc++.so.6")' in recipe_text
    dbus=recipe_text.split('(define-public python-dbus-next-jarvis',1)[1].split('(define-public python-mcp-jarvis',1)[0]
    assert '(arguments (list #:tests? #f))' in dbus
    uv_versioning=recipe_text.split('(define-public python-uv-dynamic-versioning-jarvis',1)[1].split('(define-public python-mcp-types',1)[0]
    assert '(arguments (list #:tests? #f))' in uv_versioning
    httpcore=recipe_text.split('(define-public python-httpcore2-jarvis',1)[1].split('(define-public python-httpx2-jarvis',1)[0]
    httpx=recipe_text.split('(define-public python-httpx2-jarvis',1)[1].split('(define-public python-dbus-next-jarvis',1)[0]
    for package, subdir in ((httpcore,'httpcore2'),(httpx,'httpx2')):
        assert f'(chdir "src/{subdir}")' in package
        assert 'python-hatch-fancy-pypi-readme' in package
    mcp_types=recipe_text.split('(define-public python-mcp-types',1)[1].split('(define-public python-httpcore2-jarvis',1)[0]
    mcp=recipe_text.split('(define-public python-mcp-jarvis',1)[1].split('(define-public python-piper-tts-jarvis',1)[0]
    assert '(arguments (list #:tests? #f))' in mcp_types
    assert '(arguments (list #:tests? #f))' in mcp
    driver=(ROOT/'scripts/build-package.sh').read_text()
    assert 'guix)' in driver and 'guix build' in driver
    assert (ROOT/'scripts/test-guix-package.sh').is_file()


def test_guix_native_builder_rejects_aarch64_outside_active_scope(tmp_path):
    import os
    import subprocess
    bindir=tmp_path/'bin'; bindir.mkdir()
    uname=bindir/'uname'
    uname.write_text('#!/bin/sh\nprintf "aarch64\\n"\n'); uname.chmod(0o755)
    python=bindir/'python3'
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$PYTHON_TEST_LOG"\nwhile [ "$#" -gt 0 ]; do if [ "$1" = --output ]; then shift; : > "$1"; exit 0; fi; shift; done\nexit 2\n')
    python.chmod(0o755)
    guix=bindir/'guix'
    guix.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$GUIX_TEST_LOG"\n')
    guix.chmod(0o755)
    log=tmp_path/'guix-args.log'
    python_log=tmp_path/'python-args.log'
    env=os.environ|{'PATH':f'{bindir}:{os.environ["PATH"]}','GUIX_TEST_LOG':str(log),'PYTHON_TEST_LOG':str(python_log)}
    result=subprocess.run(['sh',str(ROOT/'scripts/build-package.sh'),'--target','guix','--arch','aarch64','--output',str(tmp_path/'out')],env=env,capture_output=True,text=True)
    assert result.returncode==2
    assert 'suporta somente x86_64' in result.stderr
    assert not python_log.exists()
    assert not log.exists()


def test_guix_package_avoids_onednn_aarch64_benchdnn_compile_failure():
    recipe=(ROOT/'packaging/guix/jarvis.scm').read_text()
    assert '(define onednn-aarch64-jarvis' in recipe
    assert '"-DDNNL_BUILD_TESTS=OFF"' in recipe
    assert '(define onnxruntime-aarch64-jarvis' in recipe
    onnxruntime_section=recipe.split('(define onnxruntime-aarch64-jarvis',1)[1].split('(define opencode-binary',1)[0]
    assert '((#:tests? tests? #t) #f)' in onnxruntime_section
    assert '(delete "python-pytorch")' in onnxruntime_section
    assert '(delete "python-sentencepiece")' in onnxruntime_section
    assert recipe.count('(replace "onednn" onednn-aarch64-jarvis)') == 1
    assert '(define ctranslate2-aarch64-jarvis' in recipe
    assert '(define python-ctranslate2-aarch64-jarvis' in recipe
    assert '(replace "ctranslate2" ctranslate2-aarch64-jarvis)' in recipe
    assert '(define python-faster-whisper-aarch64-jarvis' in recipe
    assert '(replace "python-ctranslate2" python-ctranslate2-aarch64-jarvis)' in recipe
    assert '(replace "onnxruntime" (list onnxruntime-aarch64-jarvis "python"))' in recipe
    assert '(if (target-aarch64?)\n                       python-faster-whisper-aarch64-jarvis\n                       python-faster-whisper)' in recipe
    assert '(if (target-aarch64?)\n                       python-ctranslate2-aarch64-jarvis\n                       python-ctranslate2)' in recipe
    assert 'onnxruntime-aarch64-jarvis' in recipe
    assert recipe.count('(target-aarch64?)') == 5
    assert 'DNNL_EXPERIMENTAL_UKERNEL=OFF' not in recipe


def test_guix_aarch64_sentencepiece_disables_tcmalloc_static_tls_failure():
    recipe=(ROOT/'packaging/guix/jarvis.scm').read_text()
    onnxruntime_section=recipe.split('(define onnxruntime-aarch64-jarvis',1)[1].split('(define opencode-binary',1)[0]
    assert '(delete "python-sentencepiece")' in onnxruntime_section


def test_nix_target_is_a_profile_installable_package():
    import json
    catalog=json.loads((ROOT/'packaging/targets.json').read_text())
    item=catalog['nix']
    assert item['implementation']=='recipe'
    assert item['recipe']=='packaging/nix/default.nix'
    assert item['validation']=='installed-smoke'
    assert item['validated_architectures']==['x86_64']
    flake=(ROOT/'flake.nix').read_text()
    assert 'jarvis-assistant' in flake
    assert 'x86_64-linux' in flake
    lock=json.loads((ROOT/'flake.lock').read_text())
    assert lock['nodes']['nixpkgs']['locked']['rev'] in flake
    assert lock['nodes']['nixpkgs']['locked']['narHash'].startswith('sha256-')
    recipe=(ROOT/'packaging/nix/default.nix').read_text()
    nix_lifecycle=(ROOT/'scripts/test-nix-package.sh').read_text()
    assert 'nix-store -qR "$task_store"' in nix_lifecycle
    assert "grep -- '-xdg-utils-'" in nix_lifecycle
    assert 'grep -F "$task_xdg_store/bin" "$task_store/bin/jarvis"' in nix_lifecycle
    assert 'test -x "$task_xdg_store/bin/xdg-open"' in nix_lifecycle
    assert 'export HOME="$TMPDIR"' in recipe
    assert 'chmod -R u+w .' in recipe
    assert 'npmDepsHash = "sha256-DqqV4xwHMWfevxHxgje2F4owhCTKVFux0AqMdrGBkmM=";' in recipe
    assert 'cargoBuildFlags = [ "--locked" ];' in recipe
    assert 'target/${stdenv.hostPlatform.rust.rustcTarget}/release/jarvis-overlay' in recipe
    assistant_derivation=recipe.split('pname = "jarvis-assistant";',1)[1]
    for dependency in ('gtk3', 'webkitgtk_4_1', 'libsoup_3', 'glib'):
        assert dependency in assistant_derivation
    assert 'tar -xOzf "${opencodeArchive}" opencode > "$out/bin/opencode"' in recipe
    assert 'package/bin/opencode' not in recipe
    assert '--expected-opencode-version "1.18.23"' in recipe
    assert 'profile install .#jarvis-assistant' in (ROOT/'docs/linux-packages.md').read_text()
    lifecycle=ROOT/'scripts/test-nix-package.sh'
    assert lifecycle.is_file()
    lifecycle_text=lifecycle.read_text()
    for command in ('profile install', 'bin/jarvis" --doctor', 'profile remove',
                    'faster_whisper', 'piper', 'mcp', 'httpx', 'dbus_next', 'libei'):
        assert command in lifecycle_text
    assert '--gui' in lifecycle_text
    assert 'test-overlay-instance.py' in lifecycle_text


def test_nix_flake_can_package_filtered_dirty_worktree_source():
    flake=(ROOT/'flake.nix').read_text()
    assert 'JARVIS_SOURCE_TREE' in flake
    assert 'builtins.path' in flake
    assert 'builtins.hasPrefix' not in flake
    assert 'builtins.hasSuffix' not in flake
    assert 'builtins.substring 0' in flake
    for excluded in ('.git', '.venv', 'node_modules', 'target', 'dist', '.worktrees'):
        assert excluded in flake


def test_nix_opencode_binary_is_not_stripped():
    recipe=(ROOT/'packaging/nix/default.nix').read_text()
    opencode=recipe.split('opencode = stdenvNoCC.mkDerivation {',1)[1].split('\n  };',1)[0]
    assert 'dontStrip = true;' in opencode
    assistant=recipe.split('stdenvNoCC.mkDerivation {',2)[2]
    assert 'dontStrip = true;' in assistant


def test_nix_lifecycle_script_uses_an_isolated_profile_and_preserves_user_data(tmp_path):
    import os, platform, shutil, subprocess
    store=tmp_path/'store'
    (store/'bin').mkdir(parents=True)
    xdg_store=tmp_path/'store/abc123-xdg-utils-1.0'
    (xdg_store/'bin').mkdir(parents=True)
    (xdg_store/'bin/xdg-open').write_text('#!/bin/sh\nexit 0\n')
    (store/'bin/jarvis').write_text(f'#!/bin/sh\nexport PATH="{xdg_store}/bin:$PATH"\nexit 0\n')
    (store/'bin/jarvis-overlay').write_text('#!/bin/sh\nexit 0\n')
    (store/'lib/jarvis/bin').mkdir(parents=True)
    (store/'lib/jarvis/bin/opencode').write_text('#!/bin/sh\nprintf "1.18.23\\n"\n')
    (store/'lib/jarvis/runtime/bin').mkdir(parents=True)
    (store/'lib/jarvis/runtime/bin/python3').write_text('#!/bin/sh\ncat >/dev/null\n')
    (store/'share/licenses/jarvis').mkdir(parents=True)
    (store/'share/licenses/jarvis/opencode-MIT.txt').write_text(
        'Copyright (c) 2025 opencode\nPermission is hereby granted\n')
    for path in store.rglob('*'):
        if path.is_file():path.chmod(0o755)
    previous_store=tmp_path/'previous-store'
    shutil.copytree(store, previous_store)
    fake_bin=tmp_path/'bin';fake_bin.mkdir()
    fake_nix=fake_bin/'nix'
    fake_nix.write_text('''#!/bin/sh
    set -eu
profile=
action=
need_profile=0
upgrade_all=0
remove_all=0
impure=0
installable=
for arg in "$@"; do
    if [ "$need_profile" = 1 ]; then profile=$arg; need_profile=0; continue; fi
    [ "$arg" = --profile ] && { need_profile=1; continue; }
    [ "$arg" = --all ] && upgrade_all=1
    [ "$action" = remove ] && [ "$arg" = --all ] && remove_all=1
    [ "$arg" = --impure ] && impure=1
    case "$arg" in *#packages.*.jarvis-assistant) installable=$arg ;; esac
    case "$arg" in install|upgrade|remove) action=$arg ;; esac
done
printf '%s\n' "$action" >> "$JARVIS_NIX_ACTIONS"
case "$action" in
    install)
        [ "$JARVIS_SOURCE_TREE" = "$JARVIS_EXPECTED_SOURCE_TREE" ]
        [ "$impure" = 1 ]
        case "$installable" in path:*) ;; *) exit 10 ;; esac
        task_flake_dir=${installable#path:}
        task_flake_dir=${task_flake_dir%%#*}
        grep -F "$JARVIS_PREVIOUS_STORE" "$task_flake_dir/flake.nix" >/dev/null
        mkdir -p "$profile/bin"
        ln -s "$JARVIS_EXPECTED_PREVIOUS_BINARY" "$profile/bin/jarvis"
        ;;
    upgrade)
        [ "$JARVIS_SOURCE_TREE" = "$JARVIS_EXPECTED_SOURCE_TREE" ]
        [ "$impure" = 1 ]
        [ "$upgrade_all" = 1 ] && [ -x "$profile/bin/jarvis" ]
        task_flake_dir=${JARVIS_NIX_TEST_FLAKE_URL#path:}
        task_flake_dir=${task_flake_dir%%#*}
        task_expected_store=${JARVIS_EXPECTED_PROFILE_BINARY%/bin/jarvis}
        grep -F "$task_expected_store" "$task_flake_dir/flake.nix" >/dev/null
        rm "$profile/bin/jarvis"
        ln -s "$JARVIS_EXPECTED_PROFILE_BINARY" "$profile/bin/jarvis"
        ;;
    remove) [ "$remove_all" = 1 ]; rm -f "$profile/bin/jarvis" ;;
    *) exit 9 ;;
esac
''')
    fake_nix.chmod(0o755)
    fake_nix_store=fake_bin/'nix-store'
    fake_nix_store.write_text('#!/bin/sh\nprintf "%s\\n" "$JARVIS_XDG_STORE"\n')
    fake_nix_store.chmod(0o755)
    gui_marker=tmp_path/'gui-called'
    fake_python=fake_bin/'python3'
    fake_python.write_text('''#!/bin/sh
set -eu
[ "$#" = 2 ]
[ "$2" = "$JARVIS_EXPECTED_OVERLAY" ]
printf '%s\\n' called > "$JARVIS_GUI_MARKER"
''')
    fake_python.chmod(0o755)
    env={**os.environ,'PATH':f'{fake_bin}:/usr/bin:/bin',
         'JARVIS_EXPECTED_OVERLAY':str(store/'bin/jarvis-overlay'),
         'JARVIS_EXPECTED_PROFILE_BINARY':str(store/'bin/jarvis'),
         'JARVIS_PREVIOUS_STORE':str(previous_store),
         'JARVIS_EXPECTED_PREVIOUS_BINARY':str(previous_store/'bin/jarvis'),
         'JARVIS_EXPECTED_FLAKE':f'{ROOT}#packages.{platform.machine()}-linux.jarvis-assistant',
         'JARVIS_SOURCE_TREE':str(ROOT),
         'JARVIS_EXPECTED_SOURCE_TREE':str(ROOT),
         'JARVIS_NIX_TEST_FLAKE_URL':f'path:{tmp_path}/upgrade-flake#packages.{platform.machine()}-linux.jarvis-assistant',
         'JARVIS_XDG_STORE':str(xdg_store),
         'JARVIS_NIX_ACTIONS':str(tmp_path/'nix-actions'),
         'JARVIS_GUI_MARKER':str(gui_marker)}
    result=subprocess.run(['sh',str(ROOT/'scripts/test-nix-package.sh'),str(store),'--gui',str(previous_store)],
                          env=env,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'Nix profile old-to-current upgrade, runtime imports, removal and user data preservation' in result.stdout
    assert gui_marker.read_text().strip()=='called'
    assert (tmp_path/'nix-actions').read_text().splitlines()==['install','upgrade','remove']


def test_linux_target_claims_match_recipe_files_and_lifecycle_evidence():
    import json
    catalog=json.loads((ROOT/'packaging/targets.json').read_text())
    matrix=json.loads((ROOT/'docs/notes/linux-matrix.json').read_text())
    meta_targets={
        'linux source archive': {'source_archive_integrity'},
        'debian cross-distro smoke': {'arch_overlay_cross_distro_debian_wayland'},
        'linux-packaging': {
            'reproducible_npm_ci_across_old_distribution_npm',
            'source_archive_includes_required_ignored_node_manifests',
        },
        'linux-port': {
            'linux_current_worktree_python_gui_opencode_unit_tests',
            'current_worktree_model_selection_python_node_regression',
            'current_worktree_linux_package_tests',
            'current_worktree_full_runtime_python_node_regression',
            'current_worktree_full_voice_regression_2026_10_26',
            'current_worktree_gui_regression_2026_10_26',
            'current_worktree_opencode_regression_2026_10_26',
            'linux_worktree_verifier_full_suite_2026_10_26',
            'linux_worktree_verifier_full_suite_2026_10_27',
            'linux_overlay_xvfb_atspi_current_worktree_2026_10_27',
            'kde_wayland_background_atspi_focus_preservation_2026_10_26',
            'kde_wayland_background_atspi_focus_precondition_2026_10_27',
            'kde_wayland_background_atspi_focus_preservation_2026_10_27_retry',
            'kde_wayland_background_atspi_focus_preservation_2026_10_27_rerun_1747',
            'kde_wayland_background_atspi_focus_preservation_2026_10_27_rerun_1954',
            'linux_worktree_verifier_full_suite_2026_10_27_eis',
            'kde_wayland_eis_click_portal_start_timeout_2026_10_27',
            'wayland_eis_revocation_cleanup_and_pause_guard_2026_10_27',
            'current_worktree_full_voice_regression_2026_10_27_eis_pause_guard',
            'current_worktree_full_voice_regression_2026_10_27_eis_initial_pause',
            'nix_guix_libei_recipe_source_validation_2026_10_27',
            'nix_current_worktree_eis_package_build_doctor_failure_2026_10_27',
            'nix_dirty_worktree_source_override_validation_2026_10_27',
            'nix_dirty_worktree_profile_install_runtime_remove_2026_10_27',
            'nix_current_worktree_profile_lifecycle_2026_10_27',
            'guix_aarch64_optional_libei_fallback_smoke_harness_2026_10_27',
            'guix_libei_aarch64_native_output_2026_10_27',
            'guix_aarch64_current_recipe_dry_run_libei_2026_10_27',
            'current_worktree_full_voice_regression_2026_10_27_guix_libei_smoke',
            'current_worktree_full_voice_regression_2026_10_27_eis_revocation',
            'kde_wayland_background_atspi_focus_preservation_2026_10_27_rerun_2040',
            'synthetic_virtual_audio_linux_ptt_vad_roundtrip_2026_10_27',
            'linux_current_tts_pulse_virtual_output_roundtrip_2026_10_27',
            'linux_worktree_verifier_full_suite_2026_10_27_virtual_audio',
            'linux_state_api_origin_protection_current_worktree_2026_10_27',
            'linux_current_worktree_full_regression_after_model_save_fix_2026_10_28',
            'linux_file_write_atomic_hardlink_race_2026_10_28',
            'portal_session_match_cleanup_current_worktree_2026_10_28',
            'linux_current_worktree_security_cleanup_full_regression_2026_10_28',
        },
        'slackware-current': {
            'slackware_current_worktree_build_install_remove_smoke',
        },
    }
    lifecycle=[r for r in matrix['results'] if r['capability']=='native_package_lifecycle']
    passed={(r['target'],r['arch']) for r in lifecycle if r['status']=='passed'}
    for target,item in catalog.items():
        assert (ROOT/item['recipe']).is_file(),target
        assert set(item['validated_architectures']) <= set(item['architectures']),target
        for arch in item['validated_architectures']:
            if item['validation']=='bundle-smoke':
                assert any(r['target']==target and r['arch']==arch and r['status']=='passed'
                           and r['capability'] in ('flatpak_native_bundle_lifecycle','flatpak_installed_runtime_smoke') for r in matrix['results']), (target,arch)
            else:
                assert (target,arch) in passed,(target,arch)
    for result in matrix['results']:
        if result['target'] not in catalog:
            assert result['capability'] in meta_targets.get(result['target'], set()),result
        if result['capability']=='native_package_lifecycle' and result['status']=='passed':
            if result['arch'] in catalog[result['target']]['architectures']:
                assert result['arch'] in catalog[result['target']]['validated_architectures'],result
            else:
                assert result['arch']=='aarch64',result


def test_prepared_linux_runtime_includes_and_checks_optional_libei_bindings():
    requirements=(ROOT/'voice/requirements-linux.txt').read_text()
    preparer=(ROOT/'scripts/prepare-package.py').read_text()
    assert 'python-libei==0.6.1; sys_platform == "linux"' in requirements
    assert 'dbus_next,libei' in preparer


def test_nix_and_guix_package_optional_libei_runtime():
    nix=(ROOT/'packaging/nix/default.nix').read_text()
    guix=(ROOT/'packaging/guix/jarvis.scm').read_text()
    assert 'pname = "python-libei"' in nix
    assert 'pythonLibei' in nix and 'libei' in nix
    assert 'lib.makeLibraryPath [ libei ]' in nix
    assert 'python-libei-jarvis' in guix
    assert '(list libei)' in guix
    assert "(if (target-aarch64?) '() (list libei))" not in guix
    assert '(assoc-ref inputs "libei")' in guix


def test_nix_ci_builds_and_runs_profile_lifecycle_on_x86_64_only():
    workflow=ROOT/'.github/workflows/linux-nix.yml'
    assert workflow.is_file()
    text=workflow.read_text()
    for required in ('ubuntu-24.04', 'x86_64-linux', 'scripts/test-nix-package.sh',
                         'releases.nixos.org/nix/nix-2.35.3/install',
                     'xvfb', 'dbus-x11', 'gir1.2-atspi-2.0', '--gui'):
        assert required in text
    assert 'aarch64-linux' not in text and 'ubuntu-24.04-arm' not in text
    assert 'aarch64-linux' not in (ROOT/'scripts/test-nix-package.sh').read_text()


def test_flatpak_source_preparation_is_x86_64_only():
    source=(ROOT/'scripts/prepare-flatpak.py').read_text()
    assert "arch not in ('x86_64','aarch64')" not in source
    assert "arch != 'x86_64'" in source


def test_guix_package_selects_the_native_glibc_loader_for_both_architectures():
    recipe=(ROOT/'packaging/guix/jarvis.scm').read_text()
    assert '#$(if (target-aarch64?)' in recipe
    assert '"/lib/ld-linux-aarch64.so.1"' in recipe
    assert '"/lib/ld-linux-x86-64.so.2"' in recipe


def test_void_glibc_ci_builds_and_tests_native_xbps_on_x86_64_only():
    workflow=ROOT/'.github/workflows/linux-void.yml'
    assert workflow.is_file()
    text=workflow.read_text()
    for required in ('ubuntu-24.04', 'x86_64',
                     'packaging/void/Dockerfile', 'test-native-package.sh',
                     'void-glibc', 'ghcr.io/void-linux/void-glibc-full:latest',
                     'timeout-minutes: 240', 'dist/upgrade',
                     'jarvis-assistant-0.1.0_1.*.xbps',
                     'jarvis-assistant-0.1.0_2.*.xbps'):
        assert required in text
    assert 'ubuntu-24.04-arm' not in text and 'aarch64' not in text
    dockerfile=(ROOT/'packaging/void/Dockerfile').read_text()
    assert 'scripts/repack-xbps-previous.py' in dockerfile


def test_void_upgrade_steps_locate_previous_package_in_their_own_shell():
    text=(ROOT/'.github/workflows/linux-void.yml').read_text()
    for step_name in ('Install, inspect and remove in clean Void container',
                      'Install, inspect and remove in clean Void musl container'):
        start=text.index(f'- name: {step_name}')
        end=text.find('\n      - name:',start+1)
        step=text[start:end if end!=-1 else None]
        assert 'previous=$(find dist/upgrade ' in step
        assert '"/upgrade/$(basename "$previous")"' in step


def test_void_builder_supports_a_musl_target_without_changing_glibc_defaults():
    dockerfile=(ROOT/'packaging/void/Dockerfile').read_text()
    assert 'ARG JARVIS_VOID_LIBC=glibc' in dockerfile
    assert 'void-${JARVIS_VOID_LIBC}-full:latest' in dockerfile
    assert 'ARG JARVIS_VOID_TARGET=void-glibc' in dockerfile
    assert '--target "$JARVIS_VOID_TARGET"' in dockerfile
    workflow=(ROOT/'.github/workflows/linux-void.yml').read_text()
    assert 'void-musl:' in workflow
    for required in ('--build-arg JARVIS_VOID_LIBC=musl', '--build-arg JARVIS_VOID_TARGET=void-musl',
                     'ghcr.io/void-linux/void-musl-full:latest', 'timeout-minutes: 360',
                     'jarvis-assistant-0.1.0_1.*-musl.xbps', 'jarvis-assistant-0.1.0_2.*-musl.xbps'):
        assert required in workflow
    native=(ROOT/'scripts/test-native-package.sh').read_text()
    for required in ('task_previous_package=${3:-}', 'xbps-query -p pkgver jarvis-assistant',
                     'xbps-install -yu -R "$task_repository" jarvis-assistant'):
        assert required in native


def test_void_arm_bootstrap_installs_binary_mesa_before_xbps_src_build():
    dockerfile=(ROOT/'packaging/void/Dockerfile').read_text()
    assert 'libffi-devel ca-certificates mesa tar zstd && \\' in dockerfile


def test_void_builder_keeps_binary_repository_and_source_snapshot_aligned():
    dockerfile=(ROOT/'packaging/void/Dockerfile').read_text()
    driver=(ROOT/'scripts/build-package.sh').read_text()
    snapshot='08c37783199592347f91cc3e3bf6f97213450ec5'
    assert f'ARG JARVIS_VOID_PACKAGES_COMMIT={snapshot}' in dockerfile
    assert 'fetch --depth 1 origin "$JARVIS_VOID_PACKAGES_COMMIT"' in dockerfile
    assert f'${{JARVIS_VOID_PACKAGES_COMMIT:-{snapshot}}}' in driver
    assert driver.count('fetch --depth 1 origin "$task_void_commit"') == 2


def test_void_recipes_install_tar_for_source_archive_extraction():
    for recipe_path in ('packaging/void/template', 'packaging/void-musl/template'):
        recipe=(ROOT/recipe_path).read_text()
        hostdeps=next(line for line in recipe.splitlines() if line.startswith('hostmakedepends='))
        assert 'tar' in hostdeps.split('=',1)[1].strip('"').split()
        assert 'zstd' in hostdeps.split('=',1)[1].strip('"').split()
        assert 'tar -xzf "${FILESDIR}/jarvis-${version}.tar.gz"' in recipe
        assert 'bsdtar -xf' not in recipe
    dockerfile=(ROOT/'packaging/void/Dockerfile').read_text()
    assert 'python3-pip pkg-config gtk+3-devel libwebkit2gtk41-devel libffi-devel ca-certificates mesa tar zstd' in dockerfile


def test_xbps_previous_revision_preserves_arch_and_rewrites_versioned_provides():
    spec=importlib.util.spec_from_file_location('xbps_previous_revision',ROOT/'scripts/repack-xbps-previous.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source={
        'pkgname':'jarvis-assistant',
        'pkgver':'jarvis-assistant-0.1.0_2',
        'version':'0.1.0_2',
        'architecture':'aarch64-musl',
        'provides':['cmd:jarvis-0.1.0_2','cmd:jarvis-overlay-0.1.0_2'],
        'run_depends':['python3>=3.14<3.15','ffmpeg>=0'],
    }
    result=module.previous_revision_properties(source)
    assert result['pkgver']=='jarvis-assistant-0.1.0_1'
    assert result['version']=='0.1.0_1'
    assert result['architecture']=='aarch64-musl'
    assert result['provides']==['cmd:jarvis-0.1.0_1','cmd:jarvis-overlay-0.1.0_1']
    assert result['run_depends']==source['run_depends']


def test_xbps_previous_revision_rejects_first_or_inconsistent_revision():
    spec=importlib.util.spec_from_file_location('xbps_previous_revision',ROOT/'scripts/repack-xbps-previous.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError,match='no previous XBPS revision'):
        module.previous_revision_properties({'pkgname':'jarvis-assistant','pkgver':'jarvis-assistant-0.1.0_1','version':'0.1.0_1'})
    with pytest.raises(ValueError,match='pkgver/version mismatch'):
        module.previous_revision_properties({'pkgname':'jarvis-assistant','pkgver':'jarvis-assistant-0.1.0_2','version':'0.1.0_3'})


def test_native_driver_builds_the_nix_flake(tmp_path):
    import os, subprocess
    tools=tmp_path/'tools';tools.mkdir()
    marker=tmp_path/'nix-arguments'
    nix=tools/'nix'
    nix.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$JARVIS_NIX_ARGUMENTS"\n')
    nix.chmod(0o755)
    env=dict(os.environ,PATH=str(tools)+os.pathsep+os.environ['PATH'],JARVIS_NIX_ARGUMENTS=str(marker))
    output=tmp_path/'packages'
    result=subprocess.run([str(ROOT/'scripts/build-package.sh'),'--target','nix','--output',str(output)],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert marker.read_text().splitlines()==['--extra-experimental-features','nix-command flakes','build',str(ROOT)+'#jarvis-assistant','--out-link',str(output/'jarvis-assistant')]


def test_void_musl_recipe_uses_libc_qualified_architecture():
    recipe=(ROOT/'packaging/void-musl/template').read_text()
    assert 'archs="x86_64-musl"' in recipe
    assert 'tar -xzf "${FILESDIR}/jarvis-${version}.tar.gz"' in recipe
    assert 'bsdtar' not in recipe
    assert 'sh packaging/alpine/build-runtime.sh "$wrksrc" "$XBPS_BUILDDIR/native"' in recipe
    assert 'python3 packaging/alpine/build-runtime.sh' not in recipe
    driver=(ROOT/'scripts/build-package.sh').read_text()
    assert 'jarvis-assistant-*.$task_arch-musl.xbps' in driver
    assert 'python3-numpy-devel' not in recipe
    assert 'python3-numpy' in recipe
    assert 'python3-setuptools python3-wheel' in recipe
    assert 'python3 scripts/fetch-opencode.py --target "${XBPS_TARGET_MACHINE}"' in recipe
    assert 'openblas musl"' in recipe
    assert 'depends="python3>=3.14<3.15 python3-numpy' in recipe
    assert 'libc.musl-x86_64.so.1' in recipe and 'libc.musl-aarch64.so.1' not in recipe


def test_slackware_uses_native_slackbuild_and_package_lifecycle():
    import json
    catalog=json.loads((ROOT/'packaging/targets.json').read_text())
    item=catalog['slackware']
    assert item['implementation']=='recipe'
    assert item['version']=='current'
    assert item['validation']=='installed-smoke'
    assert item['validated_architectures']==['x86_64']
    recipe=ROOT/item['recipe']
    assert recipe.is_file()
    build=recipe.read_text()
    assert 'makepkg' in build and '.txz' in build
    assert 'scripts/prepare-package.py' in build
    assert 'for task_tool in makepkg rustc cargo node npm pkg-config python3' in build
    assert 'sys.version_info >= (3,10)' in build
    assert 'same Python minor version used to build' in build
    assert 'ALSA libraries and utilities' in ' '.join(build.split())
    assert 'ldd /usr/bin/ffmpeg /usr/bin/ffplay' in build
    helpers=(ROOT/'scripts/build-slackware-helpers.py').read_text()
    for revision in ('d37c16111dbe38ea29194f20ac9de03cff8dfc1c',
                     '9aa7090c3b8b437c6489edca32ae43d82e0c1281',
                     '67a7b937895bceec1ae5ccebb10216f63f70ca1b'):
        assert revision in helpers
    assert 'make", "-j2", "static' in helpers
    assert 'autoreconf' in helpers and 'meson' in helpers and 'ninja' in helpers
    assert 'build-slackware-helpers.py' in build
    assert 'test-x11-tools.py' in (ROOT/'scripts/test-native-package.sh').read_text()
    driver=(ROOT/'scripts/build-package.sh').read_text()
    assert 'slackware)' in driver and 'jarvis.SlackBuild' in driver
    docs=(ROOT/'docs/linux-packages.md').read_text()
    assert 'test-native-package.sh slackware' in docs
    assert 'upgradepkg dist/native/jarvis-assistant-0.1.0-x86_64-1_local.txz%dist/upgrade/jarvis-assistant-0.1.0-x86_64-2_local.txz' in docs
    assert 'removepkg jarvis-assistant-0.1.0-x86_64-2_local' in docs
    assert 'upgradepkg old-package.txz%new-package.txz' in build


def test_solus_target_uses_eopkg_recipe_and_native_builder(tmp_path):
    import json
    import subprocess
    catalog=json.loads((ROOT/'packaging/targets.json').read_text())
    item=catalog['solus']
    assert item['implementation']=='recipe'
    assert item['recipe']=='packaging/solus/package.yml'
    assert item['format']=='eopkg'
    recipe=(ROOT/item['recipe']).read_text()
    assert 'cd "$workdir/jarvis-0.1.0"' not in recipe
    assert any(line.replace(' ', '') == 'strip:false' for line in recipe.splitlines())
    for key in ('name', 'version', 'release', 'source', 'builddeps', 'rundeps', 'build', 'install'):
        assert f'{key} ' in recipe
    driver=(ROOT/'scripts/build-package.sh').read_text()
    assert 'solus)' in driver and 'solbuild build' in driver
    lifecycle=(ROOT/'scripts/test-native-package.sh').read_text()
    assert 'solus:solus)' in lifecycle and 'eopkg -y install' in lifecycle
    assert "root=Path('/usr/lib/jarvis').resolve()" in lifecycle
    assert 'eopkg -y install xorg-server-xvfb dbus' in lifecycle
    assert 'eopkg -y install "$task_package"' in lifecycle
    assert 'solus) eopkg check jarvis-assistant; eopkg -y remove jarvis-assistant ;;' in lifecycle
    if 'ID=arch' in Path('/etc/os-release').read_text():
        result=subprocess.run([str(ROOT/'scripts/build-package.sh'),'--target','solus','--output',str(tmp_path)],capture_output=True,text=True)
        assert result.returncode==2
        assert 'fora do escopo de build' in result.stderr


def test_solus_recipe_injects_a_local_checksummed_source(tmp_path):
    import hashlib
    import subprocess
    recipe=tmp_path/'package.yml.in'
    archive=tmp_path/'jarvis source.tar.gz'
    output=tmp_path/'package.yml'
    recipe.write_text('source:\n  - "@JARVIS_SOURCE_URI@" : "@JARVIS_SOURCE_SHA256@"\n')
    archive.write_bytes(b'local source fixture')
    subprocess.run([str(ROOT/'scripts/prepare-solus-package.py'),str(recipe),str(archive),str(output)],check=True)
    generated=output.read_text()
    assert archive.as_uri() in generated
    assert hashlib.sha256(archive.read_bytes()).hexdigest() in generated
    assert '@JARVIS_SOURCE_' not in generated


def test_slackbuild_extracts_the_source_archive_root_when_run_directly(tmp_path):
    import os,subprocess
    fakebin=tmp_path/'bin';fakebin.mkdir()
    for name in ('rustc','cargo','node','npm','chown','make','gcc','ar','autoconf','automake','m4','meson','ninja'):
        tool=fakebin/name;tool.write_text('#!/bin/sh\nexit 0\n');tool.chmod(0o755)
    makepkg=fakebin/'makepkg'
    makepkg.write_text('#!/bin/sh\ntest -f install/slack-desc\n')
    makepkg.chmod(0o755)
    pkgconfig=fakebin/'pkg-config';pkgconfig.write_text('#!/bin/sh\nexit 0\n');pkgconfig.chmod(0o755)
    python=fakebin/'python3'
    python.write_text('''#!/bin/sh
if [ "$1" = -c ] || [ "$1" = -m ]; then exec "$JARVIS_TEST_PYTHON" "$@"; fi
if [ "$1" = "$JARVIS_TEST_ROOT/scripts/source-archive.py" ]; then exec "$JARVIS_TEST_PYTHON" "$@"; fi
case "$1" in scripts/fetch-opencode.py|scripts/prepare-package.py|scripts/build-slackware-helpers.py|*/scripts/build-slackware-helpers.py) exit 0 ;; esac
echo "unexpected python invocation: $*" >&2
exit 98
''')
    python.chmod(0o755)
    env=os.environ.copy()
    env.update(PATH=str(fakebin)+os.pathsep+env['PATH'],JARVIS_TEST_PYTHON=os.sys.executable,
               JARVIS_TEST_ROOT=str(ROOT),JARVIS_BUILD_ROOT=str(tmp_path/'build'),
               JARVIS_PACKAGE_OUTPUT=str(tmp_path/'out'))
    env.pop('JARVIS_SOURCE_ROOT',None)
    result=subprocess.run(['sh',str(ROOT/'packaging/slackware/jarvis.SlackBuild')],
                          env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    readme=tmp_path/'build/package/usr/doc/jarvis-assistant-0.1.0/README'
    assert 'removepkg jarvis-assistant-0.1.0-x86_64-1_local' in readme.read_text()
    assert 'ldd /usr/bin/ffmpeg /usr/bin/ffplay' in readme.read_text()


def test_musl_runtime_bootstrap_skips_gpu_only_ctranslate2_submodules():
    script=(ROOT/'packaging/alpine/build-runtime.sh').read_text()
    assert 'remote set-url origin "$1"' in script
    assert 'rev-parse HEAD 2>/dev/null || true' in script
    assert 'git -C "$task_native/ct2-source" submodule update --init --recursive --depth 1 --' in script
    assert 'third_party/cutlass' not in script
    assert 'third_party/thrust' not in script
    assert '-DWITH_CUDA=OFF' in script
    assert '-DWITH_HIP=OFF' in script
    assert '-DOPENBLAS_INCLUDE_DIR="$(pkg-config --variable=includedir openblas)"' in script


def test_musl_source_patches_are_idempotent(tmp_path):
    import subprocess
    root=tmp_path/'native';ct2=root/'ct2-source/third_party/spdlog/include/spdlog/details'
    piper=root/'piper-source';espeak=root/'espeak-source/src/ucd-tools/src/include'
    ct2.mkdir(parents=True);piper.mkdir(parents=True);espeak.mkdir(parents=True)
    (ct2/'os-inl.h').write_text('(defined(__linux__) || defined(__sun) || defined(_AIX))\n')
    include='${ESPEAKNG_BUILD_DIR}/src/espeak_ng_external/src/ucd-tools/src/include'
    cmake=('    GIT_REPOSITORY https://github.com/espeak-ng/espeak-ng.git\n'
           '    GIT_TAG 724808c  # 2026-Apr-06\n'+include+'\n'+include+'\n')
    (piper/'CMakeLists.txt').write_text(cmake)
    script=ROOT/'packaging/alpine/patch-sources.py'
    for _ in range(2):subprocess.run(['python3',str(script),str(root)],check=True,capture_output=True,text=True)


def test_void_musl_builds_and_installs_native_onnxruntime_wheel():
    recipe=(ROOT/'packaging/void-musl/template').read_text()
    runtime=(ROOT/'packaging/alpine/build-runtime.sh').read_text()
    builder=ROOT/'packaging/void-musl/build-onnxruntime.sh'
    assert 'JARVIS_BUILD_ONNXRUNTIME=1' in recipe
    assert 'CMAKE_INSTALL_LIBDIR=lib' in runtime
    assert 'ctranslate2/lib64' in recipe
    assert 'XBPS_SRCDISTDIR/$pkgname-$version/onnxruntime-1.24.4.tar.gz' in recipe
    assert 'distfiles="https://github.com/microsoft/onnxruntime/archive/refs/tags/v1.24.4.tar.gz>onnxruntime-1.24.4.tar.gz"' in recipe
    assert 'checksum=0cf4d2ee4392fbb8aedaabc6b2ba11b4a680d1071fa4f75546c2289ca5b404cf' in recipe
    assert 'skip_extraction="onnxruntime-1.24.4.tar.gz"' in recipe
    assert builder.is_file()
    build=builder.read_text()
    assert 'task_version=1.24.4' in build
    assert '53b3aed02e085c83aa3c7e1faffeae7f70675d6770bc44d148085ded47940f29471eef76e0c4565bbb471f0f814610e0d1892ce9305c63d011fe851a22b1f7ab' in build
    assert '--build_wheel' in build and '--skip_tests' in build
    assert 'onnxruntime_BUILD_UNIT_TESTS=OFF' in build
    assert '--use_full_protobuf' not in build
    assert 'Protobuf_USE_STATIC_LIBS=OFF' in build
    assert 'Wno-error=maybe-uninitialized' in build
    assert 'Wno-error=unused-result' in build
    assert 'libprotobuf abseil-cpp' in recipe
    assert 'protobuf protobuf-devel' in recipe
    assert 'onnxruntime-$task_version-*.whl' in build
    assert 'JARVIS_ONNX_SOURCE_ARCHIVE' in build
    assert 'build-onnxruntime.sh' in runtime
    assert ',onnxruntime,' in recipe
    for name in ('no-execinfo.patch','system.patch','upb-fix.patch',
                 'protobuf35-unused-dimension.patch','protobuf35-unused-shape.patch',
                 'protobuf35-check-serialization.patch','protobuf35-unused-attr.patch'):
        assert (ROOT/'packaging/void-musl/patches'/name).is_file()
    assert 'find_package(Protobuf CONFIG REQUIRED)' in (ROOT/'packaging/void-musl/patches/system.patch').read_text()


def test_native_driver_resolves_relative_output_before_changing_directory(tmp_path):
    import os,subprocess
    if 'ID=arch' not in Path('/etc/os-release').read_text():pytest.skip('requires Arch host')
    tools=tmp_path/'tools';tools.mkdir()
    makepkg=tools/'makepkg'
    makepkg.write_text('#!/bin/sh\nprintf "%s" "$PKGDEST" > "$TEST_DESTINATION"\n')
    makepkg.chmod(0o755)
    marker=tmp_path/'destination'
    env=dict(os.environ,PATH=str(tools)+os.pathsep+os.environ['PATH'],TEST_DESTINATION=str(marker))
    result=subprocess.run([str(ROOT/'scripts/build-package.sh'),'--target','arch','--output','packages ação'],env=env,cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert marker.read_text()==str(tmp_path/'packages ação')


def test_native_python_binding_survives_default_interpreter_switch(tmp_path):
    import os, shlex, subprocess, sys
    loader=importlib.util.spec_from_file_location('prepare_package_binding',ROOT/'scripts/prepare-package.py')
    package=importlib.util.module_from_spec(loader)
    sys.path.insert(0,str(ROOT/'scripts'))
    try:loader.loader.exec_module(package)
    finally:sys.path.pop(0)
    prefix=tmp_path/'installed ação'
    overlay=tmp_path/'overlay';overlay.write_text('#!/bin/sh\nexit 0\n');overlay.chmod(0o755)
    subprocess.run([sys.executable,str(ROOT/'scripts/stage-linux.py'),'--prefix',str(prefix),'--overlay',str(overlay)],check=True,capture_output=True)
    app=prefix/'lib/jarvis'
    runtime=app/'python/bin';runtime.mkdir(parents=True)
    tools=tmp_path/'tools';tools.mkdir()
    versioned=tools/'python3.frozen'
    versioned.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' "$@"\n');versioned.chmod(0o755)
    default=tools/'python3';default.symlink_to(versioned.name)
    console=runtime/'piper';console.write_text('#!'+str(default)+'\nprint("console ABI retained")\n');console.chmod(0o755)
    package.bind_python(app,default)
    default.unlink();default.write_text('#!/bin/sh\nexit 97\n');default.chmod(0o755)
    env=dict(os.environ,PATH=str(tools)+os.pathsep+os.environ['PATH'])
    env.pop('JARVIS_PYTHON',None);env.pop('JARVIS_PROJECT_ROOT',None)
    result=subprocess.run([str(prefix/'bin/jarvis'),'--doctor'],env=env,cwd=tmp_path,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert (app/'runtime/bin/python3').resolve()==versioned
    result=subprocess.run([str(console)],env=env,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='console ABI retained'


def test_prepared_python_environment_relocates_without_build_paths(tmp_path):
    import os, subprocess, sys
    loader=importlib.util.spec_from_file_location('prepared_runtime',ROOT/'scripts/prepare-package.py')
    package=importlib.util.module_from_spec(loader)
    sys.path.insert(0,str(ROOT/'scripts'))
    try:loader.loader.exec_module(package)
    finally:sys.path.pop(0)
    environment=tmp_path/'build env ação'
    subprocess.run([sys.executable,'-m','venv','--without-pip','--system-site-packages',str(environment)],check=True)
    vpython=environment/'bin/python'
    site=Path(subprocess.check_output([str(vpython),'-I','-c','import sysconfig; print(sysconfig.get_path("purelib"))'],text=True).strip())
    (site/'native_probe.py').write_text('VALUE="private module retained"\n')
    console=environment/'bin/native-probe'
    (site/'native_probe.py').write_text('def main():\n    print("private module retained")\n')
    metadata=site/'native_probe-0.1.dist-info';metadata.mkdir()
    (metadata/'METADATA').write_text('Metadata-Version: 2.1\nName: native-probe\nVersion: 0.1\n')
    (metadata/'entry_points.txt').write_text('[console_scripts]\nnative-probe = native_probe:main\n')
    # pip uses a shell trampoline when a build venv has spaces in its path.
    console.write_text('#!/bin/sh\nexit 97\n');console.chmod(0o755)
    app=tmp_path/'installed/lib/jarvis';app.mkdir(parents=True)
    package.copy_python_environment(environment,app,sys.executable)
    package.bind_python(app,Path(sys.executable))
    import shutil
    shutil.rmtree(environment)
    env=dict(os.environ,PYTHONPATH=str(app/'python'),PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run([str(app/'python/bin/native-probe')],env=env,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='private module retained'
    assert not list((app/'python').rglob('__pycache__'))


def test_nix_package_links_immutable_python_runtime_without_pip(tmp_path,monkeypatch):
    import importlib.util, json, sys
    loader=importlib.util.spec_from_file_location('nix_prepare_package',ROOT/'scripts/prepare-package.py')
    package=importlib.util.module_from_spec(loader)
    sys.path.insert(0,str(ROOT/'scripts'))
    try:loader.loader.exec_module(package)
    finally:sys.path.pop(0)
    prefix=tmp_path/'nix output'
    app=prefix/'lib/jarvis'
    staged=[]
    def fake_stage(stage_prefix,destdir,overlay,with_node_modules):
        staged.append(with_node_modules)
        app.mkdir(parents=True)
        (app/'voice').mkdir()
        (app/'voice/loop.py').write_text('pass\n')
        (prefix/'bin').mkdir()
    monkeypatch.setattr(package,'stage',fake_stage)
    external_python=tmp_path/'nix-python'
    external_python.write_text('#!/bin/sh\nexit 0\n');external_python.chmod(0o755)
    opencode=tmp_path/'opencode'
    opencode.write_text('#!/bin/sh\nexit 0\n');opencode.chmod(0o755)
    calls=[]
    def check_output(command,**kwargs):
        if command[0]==str(app/'bin/opencode'):return '1.3.14\n'
        if command[0]==str(external_python):
            return str(external_python)+'\n' if 'sys.executable' in command[-1] else '3.14\n'
        raise AssertionError(command)
    def run(command,**kwargs):
        calls.append((command,kwargs.get('env',{})))
    monkeypatch.setattr(package.subprocess,'check_output',check_output)
    monkeypatch.setattr(package.subprocess,'run',run)
    monkeypatch.setenv('PYTHONPATH',str(tmp_path/'host-python'))
    package.prepare(str(prefix),'','/unused',str(external_python),str(opencode),external_python_runtime=str(external_python),with_node_modules=False,expected_opencode_version='1.3.14')
    assert (app/'runtime/bin/python3').resolve()==external_python.resolve()
    assert staged==[False]
    assert not (app/'python').exists()
    assert json.loads((app/'install-manifest.json').read_text())['python_abi']=='3.14'
    assert len(calls)==2
    assert all(command[0]==str(external_python) for command,_ in calls)
    assert all('PYTHONPATH' not in env for _,env in calls)


@pytest.mark.parametrize('redirection',['symlink','pth','abi'])
def test_prepared_python_rejects_build_links_and_wrong_abi(tmp_path,monkeypatch,redirection):
    import json, subprocess, sys
    loader=importlib.util.spec_from_file_location('prepared_runtime_guard',ROOT/'scripts/prepare-package.py')
    package=importlib.util.module_from_spec(loader)
    sys.path.insert(0,str(ROOT/'scripts'))
    try:loader.loader.exec_module(package)
    finally:sys.path.pop(0)
    environment=tmp_path/'build-env'
    subprocess.run([sys.executable,'-m','venv','--without-pip',str(environment)],check=True)
    vpython=environment/'bin/python'
    site=Path(subprocess.check_output([str(vpython),'-c','import sysconfig; print(sysconfig.get_path("purelib"))'],text=True).strip())
    if redirection=='symlink':
        outside=tmp_path/'outside';outside.write_text('private build fixture')
        (site/'external.py').symlink_to(outside)
    elif redirection=='pth':(site/'external.pth').write_text(str(tmp_path/'outside')+'\n')
    else:
        check_output=package.subprocess.check_output
        def wrong_abi(argv,**kw):
            output=check_output(argv,**kw)
            if argv[0]==str(vpython):
                data=json.loads(output);data['abi']='incompatible-python-abi';return json.dumps(data)
            return output
        monkeypatch.setattr(package.subprocess,'check_output',wrong_abi)
    app=tmp_path/'app';app.mkdir()
    with pytest.raises(ValueError):package.copy_python_environment(environment,app,sys.executable)
    assert not (app/'python').exists()


def test_native_driver_rejects_alpine_target_on_arch(tmp_path):
    import subprocess
    if 'ID=arch' not in Path('/etc/os-release').read_text():pytest.skip('requires Arch host')
    result=subprocess.run([str(ROOT/'scripts/build-package.sh'),'--target','alpine','--output',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==2
    assert 'exige ambiente Alpine' in result.stderr


def test_native_driver_rejects_rhel_target_on_arch(tmp_path):
    import subprocess
    if 'ID=arch' not in Path('/etc/os-release').read_text():pytest.skip('requires Arch host')
    result=subprocess.run([str(ROOT/'scripts/build-package.sh'),'--target','rhel','--output',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==2
    assert 'exige ambiente RHEL 10' in result.stderr


def test_native_driver_rejects_void_glibc_target_on_arch(tmp_path):
    import subprocess
    if 'ID=arch' not in Path('/etc/os-release').read_text():pytest.skip('requires Arch host')
    result=subprocess.run([str(ROOT/'scripts/build-package.sh'),'--target','void-glibc','--output',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==2
    assert 'exige ambiente Void Linux' in result.stderr


def test_native_driver_rejects_gentoo_target_on_arch(tmp_path):
    import subprocess
    if 'ID=arch' not in Path('/etc/os-release').read_text():pytest.skip('requires Arch host')
    result=subprocess.run([str(ROOT/'scripts/build-package.sh'),'--target','gentoo','--output',str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==2
    assert 'exige ambiente Gentoo' in result.stderr


def test_gentoo_builder_resolves_ebuild_dependencies_before_packaging():
    driver=(ROOT/'scripts/build-package.sh').read_text()
    gentoo_branch=driver.split('    gentoo)\n',1)[1].split('    nix)',1)[0]
    resolve=gentoo_branch.index('emerge --oneshot --getbinpkg --usepkg --onlydeps')
    package=gentoo_branch.index('ebuild "$task_package/jarvis-assistant-0.1.0.ebuild" clean package')
    assert resolve < package
    assert 'ACCEPT_KEYWORDS=' in gentoo_branch
    assert 'USE=' in gentoo_branch
    assert 'X wayland introspection alsa pulseaudio sdl gles2 atomic-base64 harfbuzz icu opengl' in gentoo_branch


def test_deb_upgrade_runner_refuses_to_run_outside_disposable_container():
    import subprocess
    script=ROOT/'scripts/test-native-deb-upgrade.sh'
    result=subprocess.run(['sh',str(script),'debian','old.deb','new.deb'],capture_output=True,text=True)
    assert result.returncode==2
    assert 'container descartavel' in result.stderr


def test_arch_upgrade_runner_refuses_to_run_outside_disposable_container():
    import subprocess
    script=ROOT/'scripts/test-native-arch-upgrade.sh'
    result=subprocess.run(['sh',str(script),'old.pkg.tar.zst','new.pkg.tar.zst'],capture_output=True,text=True)
    assert result.returncode==2
    assert 'container descartavel' in result.stderr


def test_rpm_upgrade_runner_refuses_to_run_outside_disposable_container():
    import subprocess
    script=ROOT/'scripts/test-native-rpm-upgrade.sh'
    result=subprocess.run(['sh',str(script),'fedora','old.rpm','new.rpm'],capture_output=True,text=True)
    assert result.returncode==2
    assert 'container descartavel' in result.stderr


def test_rpm_upgrade_runner_uses_native_upgrade_commands_and_checks_user_data():
    script=ROOT/'scripts/test-native-rpm-upgrade.sh'
    assert script.is_file()
    source=script.read_text()
    assert 'dnf upgrade' in source
    assert 'zypper --non-interactive install' in source
    assert 'rpm -V jarvis-assistant' in source
    assert 'sha256sum -c' in source


def test_rpm_upgrade_fixture_hashes_do_not_require_find():
    source=(ROOT/'scripts/test-native-rpm-upgrade.sh').read_text()
    assert 'find "$task_state"' not in source
    normalized=' '.join(source.replace('\\\n',' ').split())
    assert 'sha256sum "$XDG_CONFIG_HOME/jarvis/settings.json" "$XDG_DATA_HOME/jarvis/models/opaque-user-data.bin" "$XDG_CACHE_HOME/jarvis/cache-sentinel" > "$task_state.sha256"' in normalized


def test_native_package_workflow_runs_rpm_upgrade_lifecycle_on_all_rpm_targets():
    workflow=(ROOT/'.github/workflows/linux-packages.yml').read_text()
    assert "if: matrix.family == 'fedora' || matrix.family == 'suse' || matrix.family == 'rhel'" in workflow
    assert 'test-native-rpm-upgrade.sh' in workflow
    for dockerfile in ('fedora','suse','rhel'):
        assert 'JARVIS_TEST_PACKAGE_UPGRADE=1' in (ROOT/f'packaging/rpm/{dockerfile}/Dockerfile').read_text()
    builder=(ROOT/'scripts/build-package.sh').read_text()
    assert 'JARVIS_TEST_PACKAGE_UPGRADE' in builder
    assert "Release:\\s*)1" in builder


def test_native_package_workflow_runs_arch_upgrade_lifecycle():
    workflow=(ROOT/'.github/workflows/linux-packages.yml').read_text()
    assert "if: matrix.family == 'arch'" in workflow
    assert 'test-native-arch-upgrade.sh' in workflow
    arch_upgrade=(ROOT/'scripts/test-native-arch-upgrade.sh').read_text()
    assert "sed -i '/^[[:space:]]*NoExtract[[:space:]]*=/d' /etc/pacman.conf" in arch_upgrade
