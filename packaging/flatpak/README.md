# Build Flatpak em validação

O manifesto compila o overlay no SDK GNOME 49. O preparo anterior ao build
reúne fontes Cargo verificadas pelo lockfile, dependências npm do lockfile,
wheels para o Python do SDK e o agente cuja integridade está fixada. O arquivo
resultante e os fontes dos utilitários nativos têm SHA256; a compilação Cargo
usa `--offline` e a instalação Python usa apenas o wheelhouse local.

Pré-requisitos no computador de build: Git, Python, Cargo, Node/npm e Flatpak,
com org.flatpak.Builder, org.gnome.Sdk//49, org.gnome.Platform//49 e a extensão
org.freedesktop.Sdk.Extension.rust-stable//25.08 instalados para o usuário.
O script exige os commits da arquitetura registrados em `runtime-pins.json`
e recusa versões diferentes. Ele não altera automaticamente um runtime
instalado. Há pins separados para x86_64 e ARM64; ARM64 ainda aguarda o
resultado do build real. Não reutilize artefatos x86_64 nessa arquitetura.

```sh
scripts/build-flatpak.sh "$PWD/dist/flatpak"
```

Se o preparo for interrompido antes de criar o manifesto, continue explicitamente:

```sh
scripts/prepare-flatpak.py --resume --output "$PWD/dist/flatpak/sources"
scripts/build-flatpak.sh "$PWD/dist/flatpak"
```

Um diretório de fontes preparado é um snapshot: para compilar mudanças no código
do aplicativo, use um novo diretório de saída. O build regenera o manifesto
externo com as opções atuais, mantendo o hash do snapshot de fontes.

O bundle é `dist/flatpak/jarvis-x86_64.flatpak`; seu SHA256 fica ao lado.
No ARM64, o nome é `jarvis-aarch64.flatpak`. O workflow manual
`Linux Flatpak experimental` constrói cada arquitetura em runner nativo e
verifica instalação, versão do agente e imports; não valida desktop ou áudio.
A instalação para teste, quando o build estiver concluído, é:

```sh
flatpak install --user ./dist/flatpak/jarvis-x86_64.flatpak
flatpak run --command=jarvis com.jarvis.overlay --doctor
flatpak run --command=jarvis com.jarvis.overlay --download-voice
flatpak run com.jarvis.overlay
```

O sandbox inclui rede, áudio PulseAudio/PipeWire, Wayland, fallback X11 e
acessibilidade. Captura e controle Wayland usam portais com consentimento.
Não há acesso geral ao filesystem do host. Pastas para ferramentas de arquivos
precisam de uma permissão de pasta específica do Flatpak e da allowlist Jarvis.
ALSA direto não é exposto por este sandbox.

Ainda não há publicação no Flathub. Build, instalação, voz/desktop no sandbox,
atualização, remoção e arquiteturas devem ser registrados separadamente em
`docs/notes/linux-verification.md`; a presença desta receita não comprova toda
a matriz Linux.

Para reaproveitar wheels de um preparo anterior da mesma arquitetura e SDK,
use um novo snapshot com `scripts/prepare-flatpak.py --output NOVO_DIRETORIO
--wheelhouse DIRETORIO_ANTERIOR/source/wheels`. A resolução Python usa apenas
esse diretório, em leitura, e falha se faltar um wheel compatível. As outras
dependências de preparação ainda podem exigir rede.
