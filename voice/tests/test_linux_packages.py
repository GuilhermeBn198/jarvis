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
