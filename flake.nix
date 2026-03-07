{
  description = "Self-hosted status page for personal infrastructure";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
    flake-utils.url = "github:numtide/flake-utils";
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    { self
    , nixpkgs
    , flake-utils
    , pyproject-nix
    , uv2nix
    , pyproject-build-systems
    , ...
    }:
    flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = nixpkgs.legacyPackages.${system};

      statuspage-frontend = pkgs.callPackage ./frontend { };

      statuspage = pkgs.callPackage ./backend {
        inherit pyproject-nix uv2nix pyproject-build-systems statuspage-frontend;
      };
    in
    {
      packages = {
        statuspage-frontend = statuspage-frontend;
        statuspage = statuspage;
        default = statuspage;
      };

      devShells.default = pkgs.mkShell {
        packages = [
          pkgs.uv
          pkgs.nodejs_22
          pkgs.python313
        ];
      };
    })
    // {
      nixosModules.statuspage = {
        imports = [ ./nix/nixos-module.nix ];
        nixpkgs.overlays = [
          (final: prev: {
            statuspage = self.packages.${final.stdenv.system}.statuspage;
          })
        ];
      };
    };
}
