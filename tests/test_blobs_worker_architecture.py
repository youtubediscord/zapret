from __future__ import annotations

import inspect
import unittest

from app.feature_facades.blobs import build_blobs_feature
import blobs.workers as blobs_workers


class BlobsWorkerArchitectureTests(unittest.TestCase):
    def test_blobs_workers_use_public_commands_not_feature_object(self) -> None:
        feature_source = inspect.getsource(build_blobs_feature)
        worker_source = "\n".join(
            (
                inspect.getsource(blobs_workers.BlobsLoadWorker),
                inspect.getsource(blobs_workers.BlobActionWorker),
                inspect.getsource(blobs_workers.BlobOpenActionWorker),
            )
        )

        self.assertNotIn("blobs_feature=feature", feature_source)
        self.assertNotIn("self._blobs", worker_source)
        self.assertIn("blobs_public.get_blobs_info", worker_source)
        self.assertIn("blobs_public.reload_blobs", worker_source)
        self.assertIn("blobs_public.save_user_blob", worker_source)
        self.assertIn("blobs_public.delete_user_blob", worker_source)
        self.assertIn("blobs_public.open_bin_folder", worker_source)
        self.assertIn("blobs_public.open_blobs_json", worker_source)


if __name__ == "__main__":
    unittest.main()
