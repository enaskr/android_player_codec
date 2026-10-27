import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "resolve_release.py"
spec = importlib.util.spec_from_file_location("resolve_release", SCRIPT)
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)

LIBVLC_METADATA = """<metadata><versioning><versions>
<version>3.7.6</version><version>3.7.7</version>
<version>4.0.0-eap29</version><version>4.0.0-rc1</version>
</versions></versioning></metadata>"""


class ReleaseResolutionTests(unittest.TestCase):
    def test_stable_tags_and_version_sort(self):
        sha = "a" * 40
        refs = "\n".join(
            f"{sha}\trefs/tags/{tag}" for tag in (
                "n8.1.3", "n9.0.1", "n9.0.2", "n9.0-rc1",
                "n8.10.0", "n9.0.2^{}", "n10.0", "n10.0-rc2"
            )
        )
        tags = resolver.stable_tags(refs)
        self.assertEqual(resolver.newest_tag(tags), "10.0")
        self.assertNotIn("9.0-rc1", tags)

    def test_latest_stable_libvlc_excludes_previews(self):
        self.assertEqual(resolver.latest_libvlc(LIBVLC_METADATA), "3.7.7")
        self.assertEqual(resolver.libvlc_versions(LIBVLC_METADATA), ["3.7.6", "3.7.7"])

    def test_no_libvlc_versions_fails_closed(self):
        with self.assertRaises(RuntimeError):
            resolver.latest_libvlc("<metadata><versioning><versions></versions></versioning></metadata>")

    def test_no_ffmpeg_tags_fail_closed(self):
        with self.assertRaises(RuntimeError):
            resolver.newest_tag({})

    def test_existing_bundle_skips_daily_build(self):
        self.assertFalse(resolver.decide_build("schedule", True, False, [])[0])

    def test_missing_libvlc_bundle_starts_build(self):
        self.assertTrue(resolver.decide_build("schedule", False, False, [])[0])

    def test_manual_force_starts_build(self):
        self.assertTrue(resolver.decide_build("workflow_dispatch", True, True, [])[0])

    def test_push_builder_change_starts_build(self):
        self.assertTrue(resolver.decide_build("push", True, False, ["scripts/vendor_libvlc.py"])[0])

    def test_workflow_only_push_skips(self):
        self.assertFalse(resolver.is_build_input(".github/workflows/build-aar.yml"))
        self.assertFalse(resolver.decide_build("push", True, False, [])[0])

    def test_gradle_and_libvlc_are_build_inputs(self):
        self.assertTrue(resolver.is_build_input("gradle/wrapper/gradle-wrapper.jar"))
        self.assertTrue(resolver.is_build_input("scripts/verify_libvlc.py"))
        self.assertFalse(resolver.is_build_input("README_KO.md"))

    def test_invalid_release_tag_rejected(self):
        with self.assertRaises(ValueError):
            resolver.version_tuple("9.1-rc1")

    def test_release_asset_completeness(self):
        assets = resolver.required_assets("0.3.0", "9.0.2", "3.7.7")
        self.assertEqual(len(assets), 10)
        self.assertNotIn("libvlc-all-3.7.7.aar", assets)
        self.assertIn("SUPPLEMENTAL_CODECS.json", assets)
        self.assertIn("android-player-codec-pack-0.3.0-ffmpeg9.0.2-libvlc3.7.7.aar", assets)
        self.assertIn("FFmpeg-source-9.0.2.tar.gz", assets)

    def test_release_tag_includes_both_engine_versions(self):
        self.assertEqual(
            resolver.release_tag("0.2.0", "9.0.2", "3.7.7"),
            "codec-v0.2.0-ffmpeg9.0.2-libvlc3.7.7",
        )


if __name__ == "__main__":
    unittest.main()
