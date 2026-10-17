"""Verify integrity and extraction boundaries of release dependency archives."""
import base64
import hashlib
import importlib.util
import io
import tarfile
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('fetch_opencode',ROOT/'scripts/fetch-opencode.py')
fetch=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def archive(binary=b'\x7fELFtest',kind=tarfile.REGTYPE,extra=None):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as tar:
        member=tarfile.TarInfo('package/bin/opencode')
        member.type=kind
        member.linkname='../../outside'
        member.size=len(binary) if kind==tarfile.REGTYPE else 0
        tar.addfile(member,io.BytesIO(binary) if member.size else None)
        if extra:
            member=tarfile.TarInfo(extra);member.size=4
            tar.addfile(member,io.BytesIO(b'evil'))
    data=stream.getvalue()
    integrity='sha512-'+base64.b64encode(hashlib.sha512(data).digest()).decode()
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
    with pytest.raises(ValueError,match='SHA512'):
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
                     '.opencode/package-lock.json'):
        assert 'jarvis-0.1.0/'+required in names
    assert not any('/.venv/' in name or '/node_modules/' in name or '/.superpowers/' in name or '/target/' in name for name in names)
    assert all(name.startswith('jarvis-0.1.0/') for name in names)


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


def test_target_catalog_records_recipe_and_validation_separately():
    import json
    catalog=json.loads((ROOT/'packaging/targets.json').read_text())
    assert {'arch','debian','fedora','suse','alpine','void-glibc','void-musl',
            'gentoo','nix','guix','slackware','solus'} <= set(catalog)
    for target,item in catalog.items():
        assert item['libc'] in ('glibc','musl')
        assert item['architectures'] and set(item['architectures']) <= {'x86_64','aarch64'}
        assert item['validation'] in ('unverified','extracted-smoke','installed-smoke')
        if item['recipe'] is not None:
            assert (ROOT/item['recipe']).is_file(),target
        else:
            assert item['implementation']=='pending'
    assert catalog['void-musl']['libc']=='musl'
    for item in catalog.values():
        assert set(item['validated_architectures']) <= set(item['architectures'])
        if item['validation']=='unverified':assert not item['validated_architectures']
        else:assert item['validated_architectures']


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
