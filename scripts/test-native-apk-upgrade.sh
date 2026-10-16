#!/bin/sh
# Run only in a disposable Alpine container, with two native APK revisions.
set -eu
[ -f /.dockerenv ] || [ -f /run/.containerenv ] || { echo 'Execute apenas em container descartavel.' >&2; exit 2; }
. /etc/os-release
[ "$ID" = alpine ] || { echo 'Teste APK exige ambiente Alpine.' >&2; exit 2; }
task_old_package=${1:?APK anterior obrigatorio}
task_old_version=${2:?versao anterior obrigatoria}
task_new_package=${3:?APK novo obrigatorio}
task_new_version=${4:?versao nova obrigatoria}
[ "$task_old_version" != "$task_new_version" ] || { echo 'O teste exige duas versoes distintas.' >&2; exit 2; }
task_checks=$(CDPATH= cd -P "$(dirname "$0")" && pwd)

apk add --no-cache --allow-untrusted "$task_old_package"
apk --no-network info -e "jarvis-assistant=$task_old_version"
umask 077
task_state=$(mktemp -d)
export XDG_DATA_HOME=$task_state/data XDG_CONFIG_HOME=$task_state/config XDG_CACHE_HOME=$task_state/cache
mkdir -p "$XDG_DATA_HOME/jarvis/models" "$XDG_CONFIG_HOME/jarvis" "$XDG_CACHE_HOME/jarvis"
printf '%s\n' '{"language":"pt","fixture":"preserve upgrade"}' > "$XDG_CONFIG_HOME/jarvis/settings.json"
# Opaque writable data tests preservation; this is not a speech model fixture.
dd if=/dev/urandom of="$XDG_DATA_HOME/jarvis/models/opaque-user-data.bin" bs=1024 count=8 2>/dev/null
printf '%s\n' model-cache-fixture > "$XDG_CACHE_HOME/jarvis/cache-sentinel"
find "$task_state" -type f -exec sha256sum '{}' \; > "$task_state.sha256"

apk add --no-cache --allow-untrusted "$task_new_package"
apk --no-network info -e "jarvis-assistant=$task_new_version"
sha256sum -c "$task_state.sha256"
# Includes installed imports, GUI relaunch/exit, integrity and package removal.
sh "$task_checks/test-native-package.sh" alpine "$task_new_package"
sha256sum -c "$task_state.sha256"
! apk --no-network info -e jarvis-assistant
printf '%s\n' 'PASS: APK update, installed runtime/GUI/integrity, removal and unchanged config/model-data/cache fixture hashes'
