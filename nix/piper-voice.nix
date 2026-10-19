{ stdenvNoCC, fetchurl }:

stdenvNoCC.mkDerivation {
  pname = "piper-voice-de-thorsten-medium";
  version = "2023-09-09";

  model = fetchurl {
    url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx";
    hash = "sha256-fmR2LY5RGLtXjy7qYgfho1qODDBZUBC2ZvmD/Ie7eBk=";
  };
  config = fetchurl {
    url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json";
    hash = "sha256-l0re55BTOtsnOhrIj0kCfSobjw8s9JBZVKR5HnkmToU=";
  };

  dontUnpack = true;

  installPhase = ''
    mkdir -p $out
    cp $model $out/de_DE-thorsten-medium.onnx
    cp $config $out/de_DE-thorsten-medium.onnx.json
  '';
}
