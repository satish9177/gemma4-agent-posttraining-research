#!/usr/bin/env python3
"""Tier A mining pilot: build an environment and gold-validate each prepared candidate, CPU only, in Docker.

No model is used anywhere. Per candidate (pilot_id order, a fixed number of workers):

  S1 prepared      PR data and diff retrieved; a test patch, a gold patch and >= 1 runnable test file exist
  S2 license       repository license (GitHub SPDX at preparation time) is open (same list as the inventory)
  S3 checkout      fresh container from python:<version>; clone; checkout the PR base commit
  S4 patches       test patch and gold patch both apply at the base commit (git apply, then patch --fuzz=5)
  S5 environment   recipe R1 = install_config of the latest published task for the repo (if any);
                   if R1 fails, recipe R2 = generic pip recipe on Python 3.12 in a fresh container;
                   success = install command exits 0 and pytest imports
  S6 tests         network disconnected; apply test patch; run the test files twice (B1, B2); apply the gold patch;
                   run twice (A1, A2). Results parsed from pytest -rA output.
  S7 classify      F2P = failing (FAILED / ERROR / not collected) in B1 and B2 and PASSED in A1 and A2
                   P2P = PASSED in all four runs; flaky = status differs between the two runs of one state
                   gold-valid = at least one stable F2P test

    python -I analysis/tier_a_pilot/validate_pilot.py [--workers 3] [--only P001,P002] [--tasks FILE] [--out DIR]
"""
import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import post_release_inventory as INV  # noqa: E402  (OPEN_LICENSES, MANUAL_LICENSE_REVIEW)

DEFAULT_PY = "3.12"
TIMEOUT_CLONE, TIMEOUT_INSTALL, TIMEOUT_TEST = 900, 1800, 900
CPUS, MEMORY = "4", "4g"
MIN_FREE_GB = 6.0
LOG_TAIL = 400_000
GENERIC_TEST_CMD = "python -m pytest -rA -p no:cacheprovider --continue-on-collection-errors"
STATUS_FIRST = re.compile(r"^(PASSED|FAILED|ERROR|XFAIL|XPASS)\s+(\S+)")
STATUS_LAST = re.compile(r"^(\S+::\S+)\s+(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b")
NETWORK_HINTS = re.compile(r"Temporary failure in name resolution|Name or service not known|Network is unreachable|"
                           r"ConnectionError|ConnectTimeout|MaxRetryError|socket\.gaierror", re.I)
HW_HINTS = re.compile(r"CUDA|cuda|nvidia|No GPU|torch\.cuda|metal|Apple Silicon|mlx", re.I)
_DISK_LOCK = threading.Lock()


def sh(args, timeout, input_=None):
    try:
        p = subprocess.run(args, input=input_, capture_output=True, timeout=timeout, text=True,
                           encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"")
        out = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
        return 124, out + "\n[TIMEOUT]"


def dexec(cid, script, timeout):
    return sh(["docker", "exec", cid, "timeout", str(timeout), "bash", "-lc", script], timeout + 60)


def free_gb():
    return shutil.disk_usage(Path.home().anchor).free / 1e9


class Box:
    """One container for one recipe attempt."""

    def __init__(self, pid, py):
        self.name = f"pilot_{pid.lower()}_{int(time.time())}"
        rc, out = sh(["docker", "run", "-d", "--name", self.name, "--cpus", CPUS, "--memory", MEMORY,
                      "--pids-limit", "4096", "-e", "PIP_NO_CACHE_DIR=1", "-e", "PIP_DISABLE_PIP_VERSION_CHECK=1",
                      "-e", "DEBIAN_FRONTEND=noninteractive", "-e", "PYTHONDONTWRITEBYTECODE=1",
                      f"python:{py}", "sleep", "infinity"], 1800)
        self.ok, self.err = rc == 0, out[-2000:]

    def run(self, script, timeout):
        return dexec(self.name, script, timeout)

    def put(self, text, path):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", newline="\n", suffix=".txt") as f:
            f.write(text)
            tmp = f.name
        rc, out = sh(["docker", "cp", tmp, f"{self.name}:{path}"], 300)
        Path(tmp).unlink(missing_ok=True)
        return rc == 0

    def offline(self):
        return sh(["docker", "network", "disconnect", "bridge", self.name], 120)[0] == 0

    def close(self):
        sh(["docker", "rm", "-f", self.name], 300)


def checkout(box, task):
    url, sha = task["clone_url"], task["base_sha"]
    return box.run(f"git clone -q --filter=blob:none --no-checkout {shlex.quote(url)} /testbed && cd /testbed && "
                   f"(git cat-file -e {sha} 2>/dev/null || git fetch -q origin {sha}) && git checkout -q {sha}",
                   TIMEOUT_CLONE)


APPLY = ("cd /testbed && (git apply --whitespace=nowarn {check} {p} || "
         "patch --batch --fuzz=5 -p1 {dry} -i {p})")


def apply(box, path, check=False):
    return box.run(APPLY.format(p=path, check="--check" if check else "",
                                dry="--dry-run" if check else ""), 300)


def cap_script(cutoff):
    """Upgrade pip, then cap every later pip resolution at the PR merge time (pip >= 26: --uploaded-prior-to)."""
    if not cutoff:
        return "pip install -q -U pip setuptools wheel || true"
    conf = f"[global]\nuploaded-prior-to = {cutoff}\n"
    return ("pip install -q -U pip setuptools wheel || true\n"
            "if pip install --help 2>/dev/null | grep -q uploaded-prior-to; then "
            f"printf %s {shlex.quote(conf)} > /etc/pip.conf; echo '[pip capped at {cutoff}]'; "
            "else echo '[pip too old for a date cap: uncapped]'; fi")


def r1_script(cfg, cutoff=None):
    lines = ["set -o pipefail", "cd /testbed", env_prefix(cfg), cap_script(cutoff)]
    for c in cfg.get("pre_install") or []:
        lines.append(f"({c}) || echo '[pre_install failed: continuing]'")
    pk = cfg.get("packages")
    reqs = cfg.get("reqs_path") or []
    if isinstance(reqs, str):
        reqs = [reqs]
    if pk == "requirements.txt":
        for r in reqs or ["requirements.txt"]:
            lines.append(f"[ -f {shlex.quote(r)} ] && pip install -r {shlex.quote(r)} || echo '[reqs failed: {r}]'")
    elif pk and pk not in ("environment.yml",) and not str(pk).endswith((".yml", ".yaml")):
        lines.append(f"pip install {pk} || echo '[packages failed]'")
    pp = cfg.get("pip_packages") or []
    if isinstance(pp, str):
        pp = pp.split()
    if pp:
        lines.append("pip install " + " ".join(shlex.quote(x) for x in pp) + " || echo '[pip_packages failed]'")
    inst = cfg.get("install") or "pip install -e ."
    lines.append(f"{inst}")
    return "\n".join(lines)


R2_SCRIPT = r"""set -o pipefail
cd /testbed
__CAP__
if [ -f pyproject.toml ] || [ -f setup.py ] || [ -f setup.cfg ]; then
  pip install -e ".[test]" || pip install -e ".[tests]" || pip install -e ".[testing]" || pip install -e ".[dev]" || pip install -e . || exit 3
elif [ -f requirements.txt ]; then
  pip install -r requirements.txt || exit 3
fi
for f in requirements-test*.txt requirements_test*.txt requirements-dev*.txt requirements_dev*.txt test-requirements*.txt \
         dev-requirements*.txt requirements/test*.txt requirements/dev*.txt requirements/testing*.txt; do
  [ -f "$f" ] && (pip install -r "$f" || echo "[optional requirements failed: $f]")
done
pip install --group test 2>/dev/null || pip install --group dev 2>/dev/null || true
pip install pytest
"""


VALUE_OPTS = {"-W", "-p", "-k", "-m", "-c", "-o", "-n", "--rootdir", "--ignore", "--deselect", "--timeout",
              "--durations", "--tb", "--import-mode", "--log-level"}


def strip_targets(cmd):
    """Remove test-file / node-id targets from a published pytest command (it named that task's own tests)."""
    out, prev = [], ""
    for tok in shlex.split(cmd):
        if prev in VALUE_OPTS or tok.startswith("-") or not (tok.endswith(".py") or "::" in tok or "/" in tok):
            out.append(tok)
        prev = tok
    return " ".join(shlex.quote(t) for t in out)


def env_prefix(cfg):
    ev = (cfg or {}).get("env_vars") or {}
    return "".join(f"export {k}={shlex.quote(str(v))}; " for k, v in ev.items() if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k))


def test_cmd(recipe_used, cfg):
    if recipe_used == "R1":
        c = (cfg or {}).get("test_cmd") or ""
        if isinstance(c, list):
            c = " && ".join(c)
        if "pytest" in c and "&&" not in c and ";" not in c and "|" not in c:
            c = strip_targets(c)
            if "-rA" not in c:
                c += " -rA"
            return env_prefix(cfg) + c
    return GENERIC_TEST_CMD


def ensure_xdist(box, cmd):
    if re.search(r"(^|\s)(-n\s*\S+|--numprocesses)", cmd):
        box.run("python -c 'import xdist' 2>/dev/null || pip install -q pytest-xdist", 600)


def parse(log):
    st = {}
    for line in log.splitlines():
        line = line.strip()
        m = STATUS_FIRST.match(line)
        if m and "::" in m.group(2):
            st[m.group(2)] = m.group(1)
            continue
        m = STATUS_LAST.match(line)
        if m:
            st[m.group(1)] = m.group(2)
    started = "test session starts" in log or bool(st)
    return st, started


def classify(runs):
    names = set().union(*[set(r["status"]) for r in runs.values()])
    fail = lambda s: s in (None, "FAILED", "ERROR")  # noqa: E731  (None = not collected / not run)
    g = {k: runs[k]["status"] for k in runs}
    f2p_run1 = sorted(t for t in names if fail(g["B1"].get(t)) and g["A1"].get(t) == "PASSED")
    f2p_gold_twice = [t for t in f2p_run1 if g["A2"].get(t) == "PASSED"]
    f2p_stable = [t for t in f2p_gold_twice if fail(g["B2"].get(t))]
    p2p = sorted(t for t in names if all(g[k].get(t) == "PASSED" for k in ("B1", "B2", "A1", "A2")))
    p2f = sorted(t for t in names if g["B1"].get(t) == "PASSED" and g["B2"].get(t) == "PASSED"
                 and g["A1"].get(t) in ("FAILED", "ERROR") and g["A2"].get(t) in ("FAILED", "ERROR"))
    flaky = sorted(t for t in names if g["B1"].get(t) != g["B2"].get(t) or g["A1"].get(t) != g["A2"].get(t))
    return {"n_tests_seen": len(names), "f2p_run1": len(f2p_run1), "f2p_gold_twice": len(f2p_gold_twice),
            "f2p_stable": len(f2p_stable), "p2p_stable": len(p2p), "p2f_stable": len(p2f), "flaky": len(flaky),
            "F2P": f2p_stable, "P2P_count": len(p2p), "flaky_tests": flaky[:50]}


def validate(task, outdir: Path):
    pid = task["pilot_id"]
    d = outdir / pid
    d.mkdir(parents=True, exist_ok=True)
    res = {"pilot_id": pid, "repo": task["repo"], "pr_number": task["pr_number"], "stage": {}, "reason": None,
           "recipe_used": None, "python": None, "t0": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    t_start = time.time()

    def log(name, text):
        (d / f"{name}.log").write_text(text[-LOG_TAIL:], encoding="utf-8")

    def stop(stage, reason):
        res["stage"][stage] = False
        res["reason"] = reason
        return res

    # S1
    if task.get("prep_error") or not task.get("test_patch") or not task.get("gold_patch") or not task.get("test_files"):
        why = task.get("prep_error") or ("no test patch" if not task.get("test_patch") else
                                         "no gold patch" if not task.get("gold_patch") else "no runnable test file")
        return stop("S1_prepared", why)
    res["stage"]["S1_prepared"] = True
    # S2
    lic = task.get("license_now")
    if not (lic in INV.OPEN_LICENSES or (task["repo"].lower() in INV.MANUAL_LICENSE_REVIEW
                                         and lic in (None, "NOASSERTION", "OTHER"))):
        return stop("S2_license", f"license {lic}")
    res["stage"]["S2_license"] = True
    recipe = task["recipe"]
    cfg = recipe.get("install_config")
    attempts = [("R1", str((cfg or {}).get("python") or DEFAULT_PY), cfg)] if cfg else []
    attempts.append(("R2", DEFAULT_PY, None))
    box = None
    try:
        installed = False
        for i, (rname, py, c) in enumerate(attempts):
            box = Box(pid, py)
            if not box.ok:
                log(f"container_{rname}", box.err)
                box.close(); box = None
                continue
            rc, out = checkout(box, task)
            log(f"checkout_{rname}", out)
            if rc != 0:
                return stop("S3_checkout", "clone or checkout failed")
            res["stage"]["S3_checkout"] = True
            if i == 0:   # S4 once, before any install
                ok_t = box.put(task["test_patch"], "/tmp/test.patch") and apply(box, "/tmp/test.patch", True)[0] == 0
                ok_g = box.put(task["gold_patch"], "/tmp/gold.patch") and apply(box, "/tmp/gold.patch", True)[0] == 0
                res["test_patch_applies"], res["gold_patch_applies"] = ok_t, ok_g
                if not (ok_t and ok_g):
                    return stop("S4_patches", "test patch does not apply" if not ok_t else "gold patch does not apply")
                res["stage"]["S4_patches"] = True
            else:
                box.put(task["test_patch"], "/tmp/test.patch")
                box.put(task["gold_patch"], "/tmp/gold.patch")
            cutoff = task.get("merged_at")
            script = r1_script(c, cutoff) if rname == "R1" else R2_SCRIPT.replace("__CAP__", cap_script(cutoff))
            rc, out = box.run(script, TIMEOUT_INSTALL)
            log(f"install_{rname}", out)
            if rc == 0 and box.run("cd /testbed && python -m pytest --version", 120)[0] == 0:
                installed, res["recipe_used"], res["python"] = True, rname, py
                break
            res[f"install_{rname}_rc"] = rc
            box.close(); box = None
        if not installed:
            return stop("S5_environment", "install failed under every recipe")
        res["stage"]["S5_environment"] = True
        cmd = test_cmd(res["recipe_used"], cfg)
        ensure_xdist(box, cmd)
        res["test_cmd"] = cmd
        if not box.offline():
            return stop("S6_tests", "could not disconnect network")
        files = " ".join(shlex.quote(f) for f in task["test_files"])
        if apply(box, "/tmp/test.patch")[0] != 0:
            return stop("S6_tests", "test patch failed to apply in the built environment")
        runs = {}
        for k in ("B1", "B2"):
            rc, out = box.run(f"cd /testbed && {cmd} {files}", TIMEOUT_TEST)
            st, started = parse(out)
            runs[k] = {"rc": rc, "status": st, "started": started}
            log(f"test_{k}", out)
        if apply(box, "/tmp/gold.patch")[0] != 0:
            return stop("S6_tests", "gold patch failed to apply after the test patch")
        for k in ("A1", "A2"):
            rc, out = box.run(f"cd /testbed && {cmd} {files}", TIMEOUT_TEST)
            st, started = parse(out)
            runs[k] = {"rc": rc, "status": st, "started": started}
            log(f"test_{k}", out)
        res["runs"] = {k: {"rc": v["rc"], "started": v["started"], "n_parsed": len(v["status"])} for k, v in runs.items()}
        if not (runs["A1"]["started"] and runs["A1"]["status"]):
            alltxt = "".join((d / f"test_{k}.log").read_text(encoding="utf-8") for k in ("A1",))
            res["hint_network"] = bool(NETWORK_HINTS.search(alltxt))
            res["hint_hardware"] = bool(HW_HINTS.search(alltxt))
            return stop("S6_tests", "no parsable test results with the gold patch")
        res["stage"]["S6_tests"] = True
        c = classify(runs)
        res["classification"] = {k: v for k, v in c.items() if k != "F2P"}
        res["F2P"] = c["F2P"][:200]
        alltxt = "".join((d / f"test_{k}.log").read_text(encoding="utf-8") for k in ("B1", "A1"))
        res["hint_network"] = bool(NETWORK_HINTS.search(alltxt))
        res["hint_hardware"] = bool(HW_HINTS.search(alltxt))
        res["stage"]["S7a_gold_makes_tests_pass"] = c["f2p_run1"] > 0
        res["stage"]["S7b_gold_repeat"] = c["f2p_gold_twice"] > 0
        res["stage"]["S7c_empty_patch_fails_twice"] = c["f2p_stable"] > 0
        res["gold_valid"] = c["f2p_stable"] > 0
        if not res["gold_valid"]:
            res["reason"] = ("gold patch makes no test pass that failed before" if c["f2p_run1"] == 0 else
                             "F2P not reproduced in the second gold run" if c["f2p_gold_twice"] == 0 else
                             "F2P passed in the second empty-patch run (nondeterministic)")
        return res
    finally:
        if box:
            box.close()
        res["seconds"] = round(time.time() - t_start, 1)
        res.setdefault("gold_valid", False)
        (d / "result.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default=str(HERE / "data" / "pilot_tasks.jsonl"))
    ap.add_argument("--out", default=str(HERE / "runs"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--only", default="")
    ap.add_argument("--resume", action="store_true", help="skip candidates that already have result.json")
    a = ap.parse_args()
    tasks = [json.loads(l) for l in open(a.tasks, encoding="utf-8")]
    if a.only:
        keep = set(a.only.split(","))
        tasks = [t for t in tasks if t["pilot_id"] in keep]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stop_flag = threading.Event()

    def one(t):
        if a.resume and (out / t["pilot_id"] / "result.json").exists():
            return
        if stop_flag.is_set():
            return
        with _DISK_LOCK:
            waited = 0
            while free_gb() < MIN_FREE_GB and waited < 1800:   # amendment 1: wait only; never prune containers
                time.sleep(60); waited += 60
            if free_gb() < MIN_FREE_GB:
                stop_flag.set()
                print(f"STOP: free disk {free_gb():.1f} GB < {MIN_FREE_GB} GB; {t['pilot_id']} not started", flush=True)
                return
        r = validate(t, out)
        print(f"{r['pilot_id']} {r['repo']}#{r['pr_number']} valid={r.get('gold_valid')} "
              f"reason={r.get('reason')} recipe={r.get('recipe_used')} {r.get('seconds')}s free={free_gb():.1f}GB",
              flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(one, tasks))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
