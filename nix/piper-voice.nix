{ stdenvNoCC, fetchurl }:

stdenvNoCC.mkDerivation {
  pname = "piper-voice-de-thorsten-medium";
  version = "2023-09-09";

  # Pinned to a HuggingFace revision, not `main`: the .onnx.json on main was
  # re-uploaded after 2023-09-09, which broke the fixed-output hash of every build
  # that consumes this derivation (the model file itself is unchanged).
  model = fetchurl {
    url = "https://huggingface.co/rhasspy/piper-voices/resolve/04ca88f5685ca5253c701af3687e155b113bd512/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx";
    hash = "sha256-fmR2LY5RGLtXjy7qYgfho1qODDBZUBC2ZvmD/Ie7eBk=";
  };
  config = fetchurl {
    url = "https://huggingface.co/rhasspy/piper-voices/resolve/04ca88f5685ca5253c701af3687e155b113bd512/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json";
    hash = "sha256-5bt0ENy7zAvm9FRPa8ZmErMVq1yzCZ7ES7RthgvHzKk=";
  };

  dontUnpack = true;

  installPhase = ''
    mkdir -p $out
    cp $model $out/de_DE-thorsten-medium.onnx
    cp $config $out/de_DE-thorsten-medium.onnx.json
  '';
}
