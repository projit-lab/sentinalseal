"""
Check that the real deepfake models load on THIS machine (run before the demo).

    python -m detector.check_models [optional_video.mp4]

Prints which models loaded and, if a video is given, the full verdict.
If a model is listed as NOT USED, the detector refuses to guess with it.
"""

from __future__ import annotations

import json
import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from detector.classifiers import get_effnet_detector, get_siglip_detector  # noqa: E402
from detector.faces import _get_detector  # noqa: E402


def main() -> int:
    t = time.time()
    ok_faces = _get_detector() is not None
    ok_eff = get_effnet_detector().load()
    ok_sig = get_siglip_detector().load()
    print("\n=== SentinelSeal model check ===")
    print(f"MTCNN face detector:        {'OK' if ok_faces else 'NOT LOADED'}")
    print(f"EfficientNet-B4 (honi05):   {'OK' if ok_eff else 'NOT USED (see warning above)'}")
    print(f"SigLIP (prithivMLmods):     {'OK' if ok_sig else 'NOT USED (see warning above)'}")
    print(f"Load time: {time.time() - t:.1f} s")
    if not (ok_eff or ok_sig):
        print("\nNo deepfake model loaded: every uploaded video will be held for callback, unchecked.")
    if len(sys.argv) > 1:
        from detector import analyze
        print(f"\nAnalysing {sys.argv[1]} ...")
        print(json.dumps(analyze(sys.argv[1]), indent=2))
    return 0 if (ok_faces and (ok_eff or ok_sig)) else 1


if __name__ == "__main__":
    sys.exit(main())
