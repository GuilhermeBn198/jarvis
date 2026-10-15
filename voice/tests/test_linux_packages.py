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
    assert catalog['fedora']['validation']=='unverified'


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
