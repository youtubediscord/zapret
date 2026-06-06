from __future__ import annotations

import inspect
import unittest


class BlobsFeatureRemovedTests(unittest.TestCase):
    def test_old_blobs_page_and_feature_are_not_registered(self) -> None:
        from app.features import AppFeatures
        from app.page_names import PageName
        from app import feature_assembly
        from ui import page_composition
        from ui.navigation import schema as navigation_schema

        self.assertFalse(hasattr(PageName, "BLOBS"))
        self.assertNotIn("blobs", AppFeatures.__dataclass_fields__)
        self.assertNotIn("PageName.BLOBS", inspect.getsource(page_composition))
        self.assertNotIn("PageName.BLOBS", inspect.getsource(navigation_schema))
        self.assertNotIn("build_blobs_feature", inspect.getsource(feature_assembly.build_app_features))


if __name__ == "__main__":
    unittest.main()
