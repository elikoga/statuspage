{
  callPackage,
  lib,
  pyproject-nix,
  pyproject-build-systems,
  uv2nix,
  python313,
  writeShellApplication,
  statuspage-frontend,
}:
let
  python = python313;

  # Copy the entire backend source to the store so alembic can find its
  # migration scripts alongside alembic.ini (script_location = alembic).
  backendSrc = builtins.path { path = ./.; name = "statuspage-backend-src"; };

  workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

  overlay = workspace.mkPyprojectOverlay {
    sourcePreference = "wheel";
  };

  pythonSet =
    (callPackage pyproject-nix.build.packages {
      inherit python;
    }).overrideScope
      (
        lib.composeManyExtensions [
          pyproject-build-systems.overlays.default
          overlay
        ]
      );

  env = pythonSet.mkVirtualEnv "statuspage-env" workspace.deps.default;

  app = writeShellApplication {
    name = "statuspage";
    runtimeInputs = [ env ];
    text = ''
      export UVICORN_HOST="''${UVICORN_HOST:=127.0.0.1}"
      export UVICORN_PORT="''${UVICORN_PORT:=8001}"
      export STATUSPAGE_FRONTEND_BINARY_PATH="''${STATUSPAGE_FRONTEND_BINARY_PATH:=${statuspage-frontend}/bin/statuspage-frontend}"
      export STATUSPAGE_ALEMBIC_INI_PATH="''${STATUSPAGE_ALEMBIC_INI_PATH:=${backendSrc}/alembic.ini}"
      exec ${env}/bin/uvicorn statuspage.main:app "$@"
    '';
  };
in
app
