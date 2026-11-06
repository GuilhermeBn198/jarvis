import io
from pathlib import Path
import pytest
from models import download_file

SHA_ABC='ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'


def test_verified_download_is_atomic_and_cached(tmp_path):
    output=tmp_path/'voice.onnx'
    download_file('https://example.test/voice',output,SHA_ABC,3,fetch=lambda *a,**kw:io.BytesIO(b'abc'))
    assert output.read_bytes()==b'abc'
    download_file('https://example.test/voice',output,SHA_ABC,3,fetch=lambda *a,**kw:pytest.fail('cached artifact must not download'))


def test_bad_hash_preserves_existing_file_and_removes_temporary(tmp_path):
    output=tmp_path/'voice.onnx';output.write_bytes(b'old')
    with pytest.raises(ValueError,match='checksum'):
        download_file('https://example.test/voice',output,SHA_ABC,3,fetch=lambda *a,**kw:io.BytesIO(b'bad'))
    assert output.read_bytes()==b'old'
    assert sorted(path.name for path in tmp_path.iterdir())==['voice.onnx']


def test_download_rejects_oversize_and_non_https(tmp_path):
    with pytest.raises(ValueError):
        download_file('http://example.test/voice',tmp_path/'voice',SHA_ABC,3,fetch=lambda *a,**kw:io.BytesIO(b'abc'))
    with pytest.raises(ValueError,match='tamanho'):
        download_file('https://example.test/voice',tmp_path/'voice',SHA_ABC,3,fetch=lambda *a,**kw:io.BytesIO(b'abcd'))
    assert list(tmp_path.iterdir())==[]
