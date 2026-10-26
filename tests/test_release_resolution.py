import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "resolve_release.py"
spec = importlib.util.spec_from_file_location("resolve_release", SCRIPT)
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class ReleaseResolutionTests(unittest.TestCase):
    def test_stable_tags_and_version_sort(self):
        sha = "a" * 40
        refs = "\n".join(
            f"{sha}\trefs/tags/{t}" for t in (
                "n8.1.3", "n9.0.1", "n9.0.2", "n9.0-rc1", "n9.0.2-beta",
                "n8.10.0", "n9.0.2^{}", "n10.0", "n10.0-rc2"
            )
        )
        tags = resolver.stable_tags(refs)
        self.assertEqual(resolver.newest_tag(tags), "10.0")
        self.assertNotIn("9.0-rc1", tags)

    def test_no_tags_fail_closed(self):
        with self.assertRaises(RuntimeError):
            resolver.newest_tag({})

    def test_existing_release_skips_daily_build(self):
        self.assertFalse(resolver.decide_build("schedule", True, False, [])[0])

    def test_missing_release_starts_build(self):
        self.assertTrue(resolver.decide_build("schedule", False, False, [])[0])

    def test_manual_force_starts_build(self):
        self.assertTrue(resolver.decide_build("workflow_dispatch", True, True, [])[0])

    def test_push_source_change_starts_build(self):
        self.assertTrue(resolver.decide_build("push", True, False, ["codec/src/main/cpp/codec_jni.c"])[0])

    def test_workflow_only_push_skips(self):
        self.assertFalse(resolver.is_build_input(".github/workflows/build-aar.yml"))
        self.assertFalse(resolver.decide_build("push", True, False, [])[0])

    def test_gradle_is_build_input(self):
        self.assertTrue(resolver.is_build_input("gradle/wrapper/gradle-wrapper.jar"))
        self.assertFalse(resolver.is_build_input("README_KO.md"))

    def test_version_rejects_prerelease(self):
        with self.assertRaises(ValueError):
            resolver.version_tuple("9.1-rc1")

    def test_release_asset_completeness(self):
        assets = resolver.required_assets("0.1.0", "9.0.2")
        self.assertEqual(len(assets), 5)
        self.assertIn("VERIFICATION.json", assets)


if __name__ == "__main__":
    unittest.main()
