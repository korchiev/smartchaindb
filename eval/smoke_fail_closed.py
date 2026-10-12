"""Live check: stolen advertisement and BUY_OFFER after CLOSE must be HTTP 4xx."""
from __future__ import print_function

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bdb_professor_eval import run_fail_closed, run_mix_mutate, wait_api

os.environ.setdefault("N_OFFER", "4")


def main():
    wait_api()
    stolen = run_fail_closed()
    print("stolen", stolen["status"], stolen["rejected"], stolen["body"][:180])
    mix = run_mix_mutate(4)
    print(
        "mutate attempted=%s committed=%s rejected=%s abort_rate=%s"
        % (mix["attempted"], mix["committed"], mix["rejected"], mix["abort_rate"])
    )
    after = mix.get("after_close") or {}
    print("after_close n=%s" % after.get("n"))
    ok_stolen = bool(stolen.get("rejected"))
    ok_close = mix["rejected"] >= 2
    if not ok_stolen or not ok_close:
        print("FAIL fail-closed")
        sys.exit(1)
    print("PASS fail-closed")


if __name__ == "__main__":
    main()
