{ stdenvNoCC, fetchurl }:

stdenvNoCC.mkDerivation {
  pname = "piper-voice-en-lessac-medium";
  version = "2023-09-09";

  model = fetchurl {
    url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx";
    hash = "sha256-Xv4J5pkCGHgnr2RuGm6dJp3udp+Yd9F7FrG0buqvAZ8=";
  };
  config = fetchurl {
    url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json";
    hash = "sha256-7+GcQXvtBV8taZCCSMa6ZQ+hNbyGiw5quz2hgdq2kKA=";
  };

  dontUnpack = true;

  installPhase = ''
    mkdir -p $out
    cp $model $out/en_US-lessac-medium.onnx
    cp $config $out/en_US-lessac-medium.onnx.json
  '';
}
