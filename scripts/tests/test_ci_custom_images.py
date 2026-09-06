"""Regression tests for custom-image CI selection."""

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ci_custom_images", ROOT / "scripts/ci-custom-images.py")
CI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CI)


class ImageSelectionTests(unittest.TestCase):
    def setUp(self):
        self.images = json.loads((ROOT / ".github/custom-images.json").read_text())

    def test_full_run_keeps_every_image(self):
        self.assertEqual(CI.select(self.images, None, full=True), self.images)

    def test_empty_selection(self):
        self.assertEqual(CI.select(self.images, []), [])

    def test_single_and_shared_contexts(self):
        for image in self.images:
            self.assertEqual(CI.select(self.images, [image["image"]]), [image])
            self.assertIn(image["context"] + "/**", CI.filters(self.images)[image["image"]])
        contexts = [image for image in self.images if image["context"] == "stacks/ail-framework"]
        self.assertEqual(len(contexts), 2)
        self.assertEqual(CI.select(self.images, [image["image"] for image in contexts]), contexts)

    def test_shared_inputs_select_all_filters(self):
        for patterns in CI.filters(self.images).values():
            for shared in CI.SHARED:
                self.assertIn(shared, patterns)

    def test_invalid_detection_fails(self):
        for changed in (None, "", {}, ["unknown"], [None]):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                CI.select(self.images, changed)

    def test_duplicate_inventory_fails(self):
        with self.assertRaises(ValueError):
            CI.select(self.images + self.images[:1], [], full=True)

    def test_inventory_inputs_exist(self):
        for image in self.images:
            self.assertTrue((ROOT / image["context"]).is_dir())
            self.assertTrue((ROOT / image["dockerfile"]).is_file())

    def test_every_stack_dockerfile_has_a_publication_decision(self):
        # Keep reasons aligned with documents/CUSTOM-IMAGES.md. A new Dockerfile
        # must enter the publish matrix or receive a reviewed exclusion.
        excluded = {
            "stacks/ail-framework/Dockerfile.build",  # Untracked vendor source.
            "stacks/ail-framework/Dockerfile.runtime",  # Requires the local build.
            "stacks/searx-ng/Dockerfile.4get",  # Operator-managed unlicensed source.
            "stacks/searx-ng/Dockerfile.4get-sidecar",  # Same source restriction.
        }
        dockerfiles = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "stacks").rglob("*")
            if path.is_file() and "Dockerfile" in path.name
            and "repo" not in path.relative_to(ROOT).parts
        }
        published = {image["dockerfile"] for image in self.images}
        self.assertFalse(published & excluded)
        self.assertEqual(dockerfiles, published | excluded)


if __name__ == "__main__":
    unittest.main()
