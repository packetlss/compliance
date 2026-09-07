#!/usr/bin/env python3
"""Run the synthetic examples using project-registry project locations."""

try:
    from ._verify_examples_core import *  # noqa: F403
    from ._verify_examples_core import main
except ImportError:  # Direct execution by path.
    from _verify_examples_core import *  # noqa: F403
    from _verify_examples_core import main


if __name__ == "__main__":
    main()
