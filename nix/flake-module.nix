{ self, inputs, ... }:
{
  perSystem = { config, self', inputs', pkgs, system, ... }: {
    packages.default = let
      pythonEnv = pkgs.python313.withPackages (ps: with ps; [
        flet
        flet-desktop
      ]);
      
      runtimeLibs = with pkgs; [
        gtk3
        gst_all_1.gstreamer
        gst_all_1.gst-plugins-base
        gst_all_1.gst-plugins-good
        gst_all_1.gst-plugins-bad
        gst_all_1.gst-plugins-ugly
        libglvnd
        xorg.libX11
        wayland
      ];
    in pkgs.stdenv.mkDerivation {
      name = "all-might";
      version = "0.1.0";
      src = ../.;

      nativeBuildInputs = [ pkgs.makeWrapper ];

      installPhase = ''
        mkdir -p $out/bin $out/share/all-might
        cp -r src $out/share/all-might/src
        
        makeWrapper ${pythonEnv}/bin/python $out/bin/all-might \
          --add-flags "$out/share/all-might/src/main.py" \
          --prefix LD_LIBRARY_PATH : "${pkgs.lib.makeLibraryPath runtimeLibs}"
      '';
      
      meta = with pkgs.lib; {
        description = "Flet GUI App";
        mainProgram = "all-might";
        platforms = platforms.linux;
      };
    };
  };
}
