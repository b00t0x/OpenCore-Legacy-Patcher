"""Exercise the real updater with a fake release API, without GUI dependencies."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


def load_updater():
    modules = {name: types.ModuleType(name) for name in (
        "update_test", "update_test.support", "update_test.constants",
        "update_test.support.network_handler",
    )}
    modules["update_test.constants"].Constants = types.SimpleNamespace
    path = Path(__file__).resolve().parents[1] / "opencore_legacy_patcher/support/updates.py"
    spec = importlib.util.spec_from_file_location("update_test.support.updates", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


updates = load_updater()


def release(tag, *, draft=False, asset="OpenCore-Patcher.pkg"):
    return {"tag_name": tag, "draft": draft, "html_url": f"https://example.invalid/{tag}",
            "assets": [{"name": asset, "browser_download_url": "https://example.invalid/app.pkg"}]}


class UpdateTests(unittest.TestCase):
    def checker(self, local="3.0.0-rc.3+m.1", branch="mod", special=False):
        return updates.CheckBinaryUpdates(types.SimpleNamespace(
            patcher_version=local, commit_info=(branch, "", ""), special_build=special))

    def fetch(self, checker, releases):
        network = Mock()
        network.return_value.verify_network_connection.return_value = True
        network.return_value.get.return_value.json.return_value = releases
        with patch.object(updates.network_handler, "NetworkUtilities", network, create=True):
            return checker.check_binary_updates()

    def test_same_version_never_updates(self):
        for branch in ("mod", "refs/tags/3.0.0-rc.3+m.1", "feature"):
            for tag in ("3.0.0-rc.3+m.1", "3.0.0rc3+m.1", "v3.0.0-rc.3+m.1"):
                with self.subTest(branch=branch, tag=tag):
                    self.assertIsNone(self.fetch(self.checker(branch=branch), [release(tag)]))

    def test_next_mod_updates_and_keeps_hyphen(self):
        result = self.fetch(self.checker(), [release("3.0.0-rc.3+m.2")])
        self.assertEqual(result["Version"], "3.0.0-rc.3+m.2")
        self.assertEqual(result["Link"], "https://example.invalid/app.pkg")

    def test_rc3_mod3_updates_from_mod2(self):
        result = self.fetch(self.checker("3.0.0-rc.3+m.2"), [release("3.0.0-rc.3+m.3")])
        self.assertEqual(result["Version"], "3.0.0-rc.3+m.3")

    def test_rc_correction_does_not_downgrade_final_version(self):
        self.assertIsNone(self.fetch(self.checker("3.0.0+m.1"), [release("3.0.0-rc.3+m.3")]))

    def test_older_release_does_not_update(self):
        self.assertIsNone(self.fetch(self.checker("3.0.0-rc.3+m.2"), [release("3.0.0-rc.3+m.1")]))

    def test_semantic_order_and_ineligible_releases(self):
        result = self.fetch(self.checker(), [
            release("3.0.0-rc.3+m.9"), release("3.0.0-rc.3+m.10"),
            release("3.0.0", draft=True), release("4.0.0", asset="AutoPkg-Assets.pkg"),
            release("not-a-version"),
        ])
        self.assertEqual(result["Version"], "3.0.0-rc.3+m.10")

    def test_next_upstream_version_updates(self):
        self.assertIsNotNone(self.fetch(self.checker(), [release("3.0.0-rc.4+m.1")]))

    def test_special_build_does_not_update(self):
        self.assertIsNone(self.fetch(self.checker(special=True), [release("3.0.0")]))

    def test_shared_comparison_is_strict(self):
        checker = self.checker()
        self.assertFalse(checker.check_if_newer("3.0.0rc3+m.1"))
        self.assertTrue(checker.check_if_newer("3.0.0-rc.3+m.2"))


if __name__ == "__main__":
    unittest.main()
