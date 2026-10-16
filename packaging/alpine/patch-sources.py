"""Narrow musl/CMake source adaptations for pinned native dependencies."""
from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve()
p=root/'ct2-source/third_party/spdlog/include/spdlog/details/os-inl.h'
s=p.read_text()
old='(defined(__linux__) || defined(__sun) || defined(_AIX))'
assert s.count(old)==1
p.write_text(s.replace(old,'((defined(__linux__) && defined(__GLIBC__)) || defined(__sun) || defined(_AIX))'))
p=root/'piper-source/CMakeLists.txt'
s=p.read_text()
old='    GIT_REPOSITORY https://github.com/espeak-ng/espeak-ng.git\n    GIT_TAG 724808c  # 2026-Apr-06'
assert s.count(old)==1
s=s.replace(old,'    SOURCE_DIR "'+str(root/'espeak-source')+'"\n    DOWNLOAD_COMMAND ""\n    UPDATE_COMMAND ""')
old='${ESPEAKNG_BUILD_DIR}/src/espeak_ng_external/src/ucd-tools/src/include'
assert s.count(old)==2
p.write_text(s.replace(old,str(root/'espeak-source/src/ucd-tools/src/include')))
