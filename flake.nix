{
  description = "Jarvis voice assistant and desktop overlay";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/714a5f8c4ead6b31148d829288440ed033ccc041";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forSystems = f: builtins.listToAttrs (map (system: {
        name = system;
        value = f system;
      }) systems);
    in {
      packages = forSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          jarvis = pkgs.callPackage ./packaging/nix/default.nix {
            src = self.outPath;
          };
        in {
          jarvis-assistant = jarvis;
          default = jarvis;
        });
    };
}
