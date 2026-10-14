from pathlib import Path
import os
import pytest
from local_files import read_text,write_text,parse_allowlist


def test_write_requires_confirmation_and_allowlist(tmp_path):
    path=tmp_path/'note.txt'
    for confirm,allowlist in ((False,[str(tmp_path)]),(True,[])):
        with pytest.raises(ValueError):write_text(str(path),'x',False,confirm,allowlist)
    assert not path.exists()


def test_write_append_read_and_parent_creation(tmp_path):
    path=tmp_path/'nested'/'note.txt'
    assert write_text(str(path),'Olá',False,True,[str(tmp_path)])['status']=='ok'
    write_text(str(path),' Linux',True,True,[str(tmp_path)])
    assert read_text(str(path))=='Olá Linux'
    assert parse_allowlist('["'+str(tmp_path)+'"]')==[str(tmp_path)]


def test_prefix_sibling_and_credentials_rejected(tmp_path):
    root=tmp_path/'allowed';root.mkdir()
    sibling=tmp_path/'allowed-other';sibling.mkdir()
    for path in (sibling/'note',root/'.env',root/'.ssh'/'id_rsa'):
        with pytest.raises(ValueError):write_text(str(path),'x',False,True,[str(root)])


def test_symlink_and_hardlink_cannot_escape(tmp_path):
    root=tmp_path/'allowed';root.mkdir()
    outside=tmp_path/'outside';outside.write_text('untouched')
    (root/'symlink').symlink_to(outside)
    os.link(outside,root/'hardlink')
    for path in (root/'symlink',root/'hardlink'):
        with pytest.raises((ValueError,OSError)):write_text(str(path),'bad',False,True,[str(root)])
    assert outside.read_text()=='untouched'


def test_symlink_swap_at_open_is_rejected(tmp_path,monkeypatch):
    root=tmp_path/'allowed';root.mkdir()
    destination=root/'note';destination.write_text('old')
    outside=tmp_path/'outside';outside.write_text('untouched')
    real_open=os.open
    def raced_open(path,flags,*args,**kwargs):
        if path=='note':
            destination.unlink();destination.symlink_to(outside)
        return real_open(path,flags,*args,**kwargs)
    monkeypatch.setattr(os,'open',raced_open)
    with pytest.raises((ValueError,OSError)):write_text(str(destination),'bad',False,True,[str(root)])
    assert outside.read_text()=='untouched'


def test_missing_allowlist_root_does_not_create_ancestors(tmp_path):
    root=tmp_path/'outside-scope'/'allowed'
    with pytest.raises((ValueError,OSError)):
        write_text(str(root/'note'),'x',False,True,[str(root)])
    assert not (tmp_path/'outside-scope').exists()


def test_read_rejects_hardlinked_alias(tmp_path):
    secret=tmp_path/'.env';secret.write_text('secret')
    alias=tmp_path/'note';os.link(secret,alias)
    with pytest.raises(ValueError):read_text(str(alias))
