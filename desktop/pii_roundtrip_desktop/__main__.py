import multiprocessing

# a frozen app re-runs itself for multiprocessing helpers (torch uses a resource tracker)
multiprocessing.freeze_support()

from pii_roundtrip_desktop.app import main  # noqa: E402

main()
