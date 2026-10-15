import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]


def test_manifest_requires_local_verified_sources_and_keeps_portal_sandbox(tmp_path):
    script=ROOT/'scripts/prepare-flatpak.py'
    assert script.is_file()
    spec=importlib.util.spec_from_file_location('prepare_flatpak',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source=tmp_path/'source.tar.gz';source.write_bytes(b'prepared source')
    output=tmp_path/'manifest.json'
    module.write_manifest(source,output)
    manifest=json.loads(output.read_text())
    assert manifest['command']=='jarvis-overlay'
    assert manifest['runtime']=='org.gnome.Platform'
    assert '--share=network' in manifest['finish-args']
    assert not any(arg.startswith('--filesystem=host') or arg.startswith('--filesystem=home') or arg=='--socket=session-bus' for arg in manifest['finish-args'])
    assert 'org.freedesktop.Flatpak' not in ' '.join(manifest['finish-args'])
    application=next(module for module in manifest['modules'] if module['name']=='jarvis')
    sources=application['sources']
    assert sources==[{'type':'archive','path':str(source.resolve()),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}]
    commands='\n'.join(application['build-commands'])
    assert 'cargo build --offline' in commands
    assert '--wheelhouse wheels' in commands
    assert 'flatpak-spawn' not in commands


def test_manifest_cannot_be_created_without_prepared_sources(tmp_path):
    import subprocess
    result=subprocess.run(['python3',str(ROOT/'scripts/prepare-flatpak.py'),'--manifest-only',str(tmp_path/'missing.tar.gz'),'--output',str(tmp_path/'build')],capture_output=True,text=True)
    assert result.returncode!=0
    assert not (tmp_path/'build/com.jarvis.overlay.json').exists()


def test_manifest_bundles_missing_desktop_tools_from_pinned_sources():
    manifest=json.loads((ROOT/'packaging/flatpak/com.jarvis.overlay.yml').read_text())
    modules={module['name']:module for module in manifest['modules']}
    for name in ('libXmu','xclip','xdotool','wl-clipboard'):
        sources=modules[name]['sources']
        assert sources and all(source['url'].startswith('https://') and len(source['sha256'])==64 for source in sources)
    assert list(modules)[-1]=='jarvis'


def test_partial_preparation_can_resume_without_overwriting_checkout(tmp_path,monkeypatch):
    import pytest
    spec=importlib.util.spec_from_file_location('prepare_flatpak_resume',ROOT/'scripts/prepare-flatpak.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source=tmp_path/'source';source.mkdir()
    marker=source/'preserved';marker.write_text('partial preparation')
    calls=[]
    class StopBeforeNetwork(Exception):pass
    def run(argv,**kwargs):
        calls.append(argv)
        raise StopBeforeNetwork()
    monkeypatch.setattr(module.subprocess,'run',run)
    with pytest.raises(StopBeforeNetwork):module.prepare(tmp_path,resume=True)
    assert marker.read_text()=='partial preparation'
    assert calls[0][0]=='cargo'


def test_github_tag_archives_declare_archive_type():
    manifest=json.loads((ROOT/'packaging/flatpak/com.jarvis.overlay.yml').read_text())
    for module in manifest['modules']:
        for source in module.get('sources',[]):
            if 'codeload.github.com' in source.get('url',''):
                assert source.get('archive-type')=='tar-gzip'


def test_wl_clipboard_completions_stay_inside_application_prefix():
    manifest=json.loads((ROOT/'packaging/flatpak/com.jarvis.overlay.yml').read_text())
    module=next(module for module in manifest['modules'] if module['name']=='wl-clipboard')
    assert '-Dfishcompletiondir=/app/share/fish/vendor_completions.d' in module.get('config-opts',[])


@pytest.mark.parametrize('arch',['x86_64','aarch64'])
@pytest.mark.parametrize('builder',['app','host'])
def test_build_refreshes_manifest_when_prepared_sources_are_reused(tmp_path,arch,builder):
    import os,subprocess,sys
    output=tmp_path/'build';sources=output/'sources';sources.mkdir(parents=True)
    (sources/'jarvis-sources.tar.gz').write_bytes(b'prepared source')
    (sources/'com.jarvis.overlay.json').write_text('{"stale":true}')
    tools=tmp_path/'tools';tools.mkdir()
    uname=tools/'uname';uname.write_text('#!/bin/sh\nprintf "%s\\n" "'+arch+'"\n');uname.chmod(0o755)
    flatpak=tools/'flatpak'
    flatpak.write_text('#!'+sys.executable+'''\nimport json,sys
pins={
'org.gnome.Sdk//49':'faf37bdc962236ef8e61fd0b289fd311f7961cc5a7b4bc11a6e29506d7874003',
'org.gnome.Platform//49':'2bb946ea4ebb050f6a32f90e979feb975b08280d1ff1aac881dec3d1361ad84d',
'org.freedesktop.Sdk.Extension.rust-stable//25.08':'09784a9989ae5a7fda6a2280033ca9aa32aac6907961da8b18be4590dd261507'}
import os
if os.environ['TEST_ARCH']=='aarch64':pins=dict(zip(pins,[
'fff4a1de0b4cef7dc8163dcad095aac1fe076639a097de0b945687e8cb4b3806',
'c3daeced6f88f9c4ffc4f88c798c48fffd395d873fc0d36b7fc73b753d7f59c9',
'ff31047b5582073ea1284807c0d654c787a731d5ffda7dfba0922635dfad8d7b']))
if sys.argv[1]=='info':print(pins[sys.argv[-1]])
elif sys.argv[1]=='run':
    manifest=json.load(open(sys.argv[-1]))
    sys.exit(77 if 'modules' in manifest and 'stale' not in manifest else 4)
else:sys.exit(5)
''')
    flatpak.chmod(0o755)
    host_builder=tools/'flatpak-builder'
    host_builder.write_text('#!'+sys.executable+'\nimport json,sys\nmanifest=json.load(open(sys.argv[-1]));sys.exit(78 if "modules" in manifest and "stale" not in manifest else 4)\n')
    host_builder.chmod(0o755)
    result=subprocess.run([str(ROOT/'scripts/build-flatpak.sh'),str(output)],env=dict(os.environ,JARVIS_FLATPAK_BUILDER=builder,TEST_ARCH=arch,PATH=str(tools)+os.pathsep+os.environ['PATH']),capture_output=True,text=True)
    assert result.returncode==({'app':77,'host':78}[builder]),result.stderr


def test_prebuilt_agent_is_not_rewritten_during_debug_extraction():
    manifest=json.loads((ROOT/'packaging/flatpak/com.jarvis.overlay.yml').read_text())
    module=next(module for module in manifest['modules'] if module['name']=='jarvis')
    options=module.get('build-options',{})
    assert options.get('no-debuginfo') is True
    assert options.get('strip') is False


def test_preparation_accepts_verified_offline_wheelhouse(tmp_path,monkeypatch):
    import pytest
    spec=importlib.util.spec_from_file_location('prepare_flatpak_offline',ROOT/'scripts/prepare-flatpak.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    (tmp_path/'source').mkdir()
    wheelhouse=tmp_path/'cached wheels';wheelhouse.mkdir()
    calls=[]
    class StopBeforeDownload(Exception):pass
    def run(argv,**kwargs):
        if argv[0]=='flatpak':calls.append(argv);raise StopBeforeDownload()
    monkeypatch.setattr(module.subprocess,'run',run)
    with pytest.raises(StopBeforeDownload):module.prepare(tmp_path,resume=True,wheelhouse=wheelhouse)
    assert '--no-index' in calls[0]
    assert calls[0][calls[0].index('--find-links')+1]==str(wheelhouse.resolve())
    assert '--filesystem='+str(wheelhouse.resolve())+':ro' in calls[0]


def test_bundle_checksum_remains_verifiable_after_download(tmp_path):
    import os,shutil,subprocess,sys
    output=tmp_path/'build';sources=output/'sources';sources.mkdir(parents=True)
    (sources/'jarvis-sources.tar.gz').write_bytes(b'prepared source')
    (sources/'com.jarvis.overlay.json').write_text('{}')
    tools=tmp_path/'tools';tools.mkdir()
    uname=tools/'uname';uname.write_text('#!/bin/sh\nprintf "x86_64\\n"\n');uname.chmod(0o755)
    flatpak=tools/'flatpak'
    flatpak.write_text('#!'+sys.executable+'\nimport json,sys\nfrom pathlib import Path\n'+
        'pins=json.loads(Path('+repr(str(ROOT/'packaging/flatpak/runtime-pins.json'))+').read_text())["x86_64"]\n'+
        '''if sys.argv[1]=='info':print(pins[sys.argv[-1]])
elif sys.argv[1]=='build':print('1.18.23')
elif sys.argv[1]=='build-bundle':Path(sys.argv[4]).write_bytes(b'bundle fixture')
elif sys.argv[1]!='run':sys.exit(3)
''')
    flatpak.chmod(0o755)
    result=subprocess.run([str(ROOT/'scripts/build-flatpak.sh'),str(output)],env=dict(os.environ,JARVIS_FLATPAK_BUILDER='app',PATH=str(tools)+os.pathsep+os.environ['PATH']),capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    downloaded=tmp_path/'downloaded';shutil.move(str(output),downloaded)
    result=subprocess.run(['sha256sum','-c','jarvis-x86_64.flatpak.sha256'],cwd=downloaded,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
