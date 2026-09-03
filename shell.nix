let
  nixpkgs-ref = "b6018f87da91d19d0ab4cf979885689b469cdd41"; # nixos-25.11
  pyproject-nix-ref = "69f57f27e52a87c54e28138a75ec741cd46663c9";
  zephyr-nix-ref = "6966fb1cbf2fdb494bea3062c5e8e7d44dd8ac9c";
  nixpkgs-esp-dev-ref = "5287d6e1ca9e15ebd5113c41b9590c468e1e001b";

  nixpkgs-esp-dev = builtins.fetchGit {
    url = "https://github.com/mirrexagon/nixpkgs-esp-dev.git";
    rev = nixpkgs-esp-dev-ref;
  };
in

{
  pkgs ? (import (builtins.fetchTarball "https://github.com/NixOS/nixpkgs/archive/${nixpkgs-ref}.tar.gz") {
    overlays = [ (import "${nixpkgs-esp-dev}/overlay.nix") ];
    # The Python library ecdsa is marked as insecure, but we need it for esptool.
    # See https://github.com/mirrexagon/nixpkgs-esp-dev/issues/109
    config.permittedInsecurePackages = [
      "python3.13-ecdsa-0.19.1"
    ];
  }),
  zephyr-src-ref ? "v4.2.0",
  zephyr-sdk-version ? "0_16"
}:

let
  zephyr-nix = ((import (builtins.fetchTarball "https://github.com/nix-community/zephyr-nix/archive/${zephyr-nix-ref}.tar.gz")) {
    inherit (pkgs) lib newScope openocd autoreconfHook fetchFromGitHub gcc_multi python312;
    zephyr-src = builtins.fetchTarball "https://github.com/zephyrproject-rtos/zephyr/archive/${zephyr-src-ref}.tar.gz";
    pyproject-nix = (import (builtins.fetchTarball "https://github.com/pyproject-nix/pyproject.nix/archive/${pyproject-nix-ref}.tar.gz")) {
      inherit (pkgs) lib;
    };
  });

  zephyr-sdk = zephyr-nix.sdkFull;
in
pkgs.mkShell {
  packages = with pkgs; [
    zephyr-sdk
    # zephyr-nix.hosttools
    # esp-idf-full
    (zephyr-nix.pythonEnv.override {
      extraPackages = ps: with ps; [
        jsonschema
      ];
    })
    cmake
    ninja
    esptool

    sphinx
    doxygen

    clang-tools
    black
  ];

  ZEPHYR_TOOLCHAIN_VARIANT = "zephyr";
  ZEPHYR_SDK_INSTALL_DIR = "${zephyr-sdk}";
}
