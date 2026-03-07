{
  buildNpmPackage,
  runtimeShell,
  nodejs_22,
}:
buildNpmPackage {
  pname = "statuspage-frontend";
  version = (builtins.fromJSON (builtins.readFile ./package.json)).version;
  src = ./.;
  npmDepsHash = "sha256-V44j+5enX5IFPxYrTVKHAKrab1eGb5uHbFYKBcdKxXY=";
  dontNpmInstall = true;
  installPhase = ''
    runHook preInstall

    mkdir -p $out/lib/statuspage-frontend/build
    cp -r ./build/* $out/lib/statuspage-frontend/build
    mkdir -p $out/bin
    cat > $out/bin/statuspage-frontend <<EOF
    #!${runtimeShell}
    exec ${nodejs_22}/bin/node $out/lib/statuspage-frontend/build/index.js "\$@"
    EOF
    chmod +x $out/bin/statuspage-frontend

    runHook postInstall
  '';
}
