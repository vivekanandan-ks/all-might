{
  description = "Flet GUI App with flake-parts";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    flake-parts.url = "github:hercules-ci/flake-parts";
  };

  outputs =
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
        "x86_64-darwin"
      ];

      perSystem =
        { pkgs, ... }:
        let
          fletRuntimeLibs = with pkgs; [
            #gtk3
            #gst_all_1.gstreamer
            #gst_all_1.gst-plugins-base
            #gst_all_1.gst-plugins-good
            #gst_all_1.gst-plugins-bad
            #gst_all_1.gst-plugins-ugly
            #libglvnd # For OpenGL
            #xorg.libX11
            #wayland
          ];

          pythonEnv = pkgs.python313.withPackages (ps: with ps; [
            flet
            flet-desktop
          ]);
        in
        {
          packages.default = pkgs.stdenv.mkDerivation {
            name = "all-might";
            version = "0.1.0";
            src = ./.;

            nativeBuildInputs = [ pkgs.makeWrapper ];

            installPhase = ''
              mkdir -p $out/bin $out/share/all-might
              cp -r src $out/share/all-might/src
              
              makeWrapper ${pythonEnv}/bin/python $out/bin/all-might \
                --add-flags "$out/share/all-might/src/main.py" \
                --prefix LD_LIBRARY_PATH : "${pkgs.lib.makeLibraryPath fletRuntimeLibs}"
            '';
            
            meta = with pkgs.lib; {
              description = "GUI App store like experience for nixpkgs";
              mainProgram = "all-might";
              #platforms = platforms.linux;
            };
          };

          # 1. Define the development shell
          devShells.default =
            pkgs.mkShell {
              name = "flet-dev-shell";

              # Packages available in the environment
              packages = [
                # The Python environment with Flet installed declaratively
                pythonEnv
              ];

              # Runtime libraries required by Flet/Flutter on Linux
              # We export these to LD_LIBRARY_PATH so the Flet binary can find them at runtime.
              env.LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath fletRuntimeLibs;

              shellHook =
                ''
                  echo "🚀 Flet Dev Shell Activated!"
                  echo "Python: $(python --version)"
                  echo "Flet: $(python -c 'import flet; print(flet.version.version)')"
                '';
            };
        };
    };
}