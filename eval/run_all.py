"""
Replaced by eval/evaluate.py.

The previous version of this script did not run the detector: it generated scores from
random draws and wrote them out as results. Those numbers were removed. Use:

    python eval/evaluate.py --labels eval/labels.csv [--robustness]
"""
import sys

if __name__ == "__main__":
    sys.exit("eval/run_all.py was replaced by eval/evaluate.py (it simulated results). "
             "Run: python eval/evaluate.py --labels eval/labels.csv")
