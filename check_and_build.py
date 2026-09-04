#!/usr/bin/env python3
"""
CLI entrypoint wrapper for Nimbus Match upstream release checker and orchestrator.
Delegates to nimbus_match.orchestrator.main.
"""

from nimbus_match.orchestrator import main

if __name__ == "__main__":
    main()
