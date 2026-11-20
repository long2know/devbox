import contextlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader(
    "desktop_media_smoke",
    str(ROOT / "root/usr/local/bin/desktop-media-smoke-test"),
)
spec = importlib.util.spec_from_loader(loader.name, loader)
media = importlib.util.module_from_spec(spec)
loader.exec_module(media)


class MediaSmokeTests(unittest.TestCase):
    def run_checker(
        self, *, gpu=False, software_pixel_format="yuv420p10le", missing=(),
        matroska_codec="V_MPEGH/ISO/HEVC", extracted_pixel_format="yuv420p10le",
    ):
        def output(arguments, **_):
            if arguments[0] == "ffmpeg":
                if "-version" in arguments:
                    return "ffmpeg test version\n"
                return "\n".join(
                    " V..... " + name
                    for name in ("libx265", "h264_nvenc", "hevc_nvenc")
                    if name not in missing
                )
            if arguments[0] == "mkvmerge":
                if "--version" in arguments:
                    return "mkvmerge test version\n"
                return json.dumps({
                    "container": {"properties": {"title": "Devbox MKVToolNix verification"}},
                    "tracks": [{
                        "id": 0, "type": "video", "properties": {"codec_id": matroska_codec},
                    }],
                })
            encoder = Path(arguments[-1]).stem
            stream = {
                "codec_name": "h264" if encoder == "h264_nvenc" else "hevc",
                "profile": "High" if encoder == "h264_nvenc" else "Main 10",
                "pix_fmt": (
                    "yuv420p"
                    if encoder == "h264_nvenc"
                    else software_pixel_format if encoder == "libx265"
                    else extracted_pixel_format if encoder == "extracted"
                    else "yuv420p10le"
                ),
            }
            return json.dumps({"streams": [stream]})

        with patch.object(sys, "argv", ["desktop-media-smoke-test", *(["--gpu"] if gpu else [])]), \
                patch.object(media.subprocess, "check_output", side_effect=output), \
                patch.object(media.subprocess, "run") as encode, \
                contextlib.redirect_stdout(io.StringIO()) as stdout:
            media.main()
        return encode, stdout.getvalue()

    def test_cpu_and_gpu_outputs_are_probed_for_real_codec_and_pixel_format(self):
        encode, output = self.run_checker(gpu=True)
        self.assertEqual(
            sum(call.args[0][0] == "ffmpeg" for call in encode.call_args_list), 3
        )
        for encoder in ("libx265", "h264_nvenc", "hevc_nvenc"):
            self.assertIn(f"PASS: {encoder} encoded", output)
        self.assertIn("'pix_fmt': 'yuv420p10le'", output)
        self.assertIn("PASS: MKVToolNix mux", output)

    def test_main10_profile_does_not_hide_eight_bit_output(self):
        with self.assertRaisesRegex(RuntimeError, "unexpected video"):
            self.run_checker(software_pixel_format="yuv420p")

    def test_build_rejects_ffmpeg_without_the_required_nvenc_encoder(self):
        with self.assertRaisesRegex(SystemExit, "hevc_nvenc"):
            self.run_checker(missing=("hevc_nvenc",))

    def test_matroska_identification_rejects_an_unexpected_track_codec(self):
        with self.assertRaisesRegex(RuntimeError, "expected video and metadata"):
            self.run_checker(matroska_codec="V_VP9")

    def test_extracted_track_must_retain_ten_bit_video(self):
        with self.assertRaisesRegex(RuntimeError, "extraction changed the video format"):
            self.run_checker(extracted_pixel_format="yuv420p")


if __name__ == "__main__":
    unittest.main()
