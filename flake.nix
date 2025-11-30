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
        #"aarch64-linux"
        #"aarch64-darwin"
        #"x86_64-darwin"
      ];

      perSystem =
        { pkgs, ... }:
        {
          # 1. Define the development shell
          devShells.default =
            let

              python = pkgs.python313;

            in
            pkgs.mkShell {
              name = "flet-dev-shell";

              # Packages available in the environment
              packages = with pkgs; [
                # The Python environment with Flet installed declaratively
                (python.withPackages (
                  ps: with ps; [
                    flet
                    flet-desktop
                    # Add other python deps below as needed
                  ]
                ))
              ];

              # Runtime libraries required by Flet/Flutter on Linux
              # We export these to LD_LIBRARY_PATH so the Flet binary can find them at runtime.
              shellHook =
                let
                  libPath = pkgs.lib.makeLibraryPath (
                    with pkgs;
                    [
                      gtk3
                      gst_all_1.gstreamer
                      gst_all_1.gst-plugins-base
                      gst_all_1.gst-plugins-good
                      gst_all_1.gst-plugins-bad
                      gst_all_1.gst-plugins-ugly
                      libglvnd # For OpenGL
                      xorg.libX11
                      wayland
                    ]
                  );
                in
                ''
                  export LD_LIBRARY_PATH="${libPath}:$LD_LIBRARY_PATH"
                  echo "🚀 Flet Dev Shell Activated!"
                  echo "Python: $(python --version)"
                  #echo "Flet: $(python -c 'import flet; print(flet.version.version)')"
                '';
            };
        };
    };
}
