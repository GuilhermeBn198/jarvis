"""Narrow musl/CMake source adaptations for pinned native dependencies."""
from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve()

def replace_exactly(text,old,new,count=1):
    found=text.count(old)
    if found==count:return text.replace(old,new)
    assert found==0 and text.count(new)==count
    return text

p=root/'ct2-source/third_party/spdlog/include/spdlog/details/os-inl.h'
s=p.read_text()
old='(defined(__linux__) || defined(__sun) || defined(_AIX))'
s=replace_exactly(s,old,'((defined(__linux__) && defined(__GLIBC__)) || defined(__sun) || defined(_AIX))')
p.write_text(s)
p=root/'piper-source/CMakeLists.txt'
s=p.read_text()
old='    GIT_REPOSITORY https://github.com/espeak-ng/espeak-ng.git\n    GIT_TAG 724808c  # 2026-Apr-06'
s=replace_exactly(s,old,'    SOURCE_DIR "'+str(root/'espeak-source')+'"\n    DOWNLOAD_COMMAND ""\n    UPDATE_COMMAND ""')
old='${ESPEAKNG_BUILD_DIR}/src/espeak_ng_external/src/ucd-tools/src/include'
s=replace_exactly(s,old,str(root/'espeak-source/src/ucd-tools/src/include'),2)
p.write_text(s)
