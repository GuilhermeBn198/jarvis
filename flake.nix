{
  description = "Jarvis voice assistant and desktop overlay";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/714a5f8c4ead6b31148d829288440ed033ccc041";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" ];
      dirtySource = builtins.getEnv "JARVIS_SOURCE_TREE";
      source = if dirtySource == "" then self.outPath else builtins.path {
        path = builtins.toPath dirtySource;
        name = "jarvis-worktree-source";
        filter = path: type:
          let
            root = toString (builtins.toPath dirtySource);
            pathString = toString path;
            relative = if pathString == root then "" else builtins.substring
              (builtins.stringLength root + 1)
              (builtins.stringLength pathString - builtins.stringLength root - 1)
              pathString;
            top = if relative == "" then "" else builtins.head
              (builtins.match "([^/]+).*" relative);
            name = builtins.baseNameOf pathString;
            allowedDirectories = [
              "voice" "gui" "mcp_servers" ".opencode" "scripts"
              "packaging" "docs"
            ];
            allowedFiles = [
              "LICENSE" "README.md" "jarvis" "opencode.json"
              "flake.nix" "flake.lock"
            ];
            hasSuffix = suffix:
              let
                nameLength = builtins.stringLength name;
                suffixLength = builtins.stringLength suffix;
              in
                nameLength >= suffixLength
                && builtins.substring (nameLength - suffixLength) suffixLength name == suffix;
            excludedDirectories = [
              ".git" ".venv" "node_modules" "target" "dist"
              "__pycache__" ".pytest_cache" ".superpowers" ".worktrees"
            ];
            excludedFile =
              builtins.substring 0 4 name == ".env"
              || builtins.elem name [ "local.conf" "settings.json" "jarvis-config.json" ]
              || builtins.any hasSuffix [ ".log" ".onnx" ];
            inSource = relative == ""
              || builtins.elem top allowedDirectories
              || builtins.elem relative allowedFiles;
          in
            inSource
            && type != "symlink"
            && !(builtins.elem name excludedDirectories)
            && !excludedFile;
      };
      forSystems = f: builtins.listToAttrs (map (system: {
        name = system;
        value = f system;
      }) systems);
    in {
      packages = forSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          jarvis = pkgs.callPackage ./packaging/nix/default.nix {
            src = source;
          };
        in {
          jarvis-assistant = jarvis;
          default = jarvis;
        });
    };
}
