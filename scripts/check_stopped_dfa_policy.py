"""Compatibility CLI for the trusted stopped-policy completion controller."""
from pathlib import Path
import sys

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.run_science_policy_probe import main
    main('stopped-maintenance')
