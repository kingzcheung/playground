#!/usr/bin/env python3
"""在 GitHub Actions runner 上抓取 Chromium 105 android 构建所需的
googlesource git 依赖 + CIPD 包，按目标树布局打包输出。

输入: git_deps.txt (path|url|sha), cipd_deps.txt (subdir|package|version)
输出: <out>/root/<tree-relative-path> 目录树
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    rows = []
    p = os.path.join(HERE, name)
    for ln in open(p, encoding="utf-8"):
        ln = ln.rstrip("\n")
        if ln and "|" in ln:
            rows.append(ln.split("|"))
    return rows


def fetch_git(root):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    for path, url, sha in load("git_deps.txt"):
        dest = os.path.join(root, path[4:])  # 去掉开头的 src/
        os.makedirs(dest)
        def run(*cmd, quiet=False):
            r = subprocess.run(cmd, cwd=dest, env=env, capture_output=True, text=True)
            if r.returncode != 0 and not quiet:
                print(f"WARN: {' '.join(cmd)}\n{r.stderr[:400]}", flush=True)
            return r
        run("git", "init", "-q")
        run("git", "remote", "add", "origin", url)
        r = run("git", "fetch", "--depth", "1", "origin", sha, quiet=True)
        if r.returncode != 0:
            print(f"  shallow fetch failed, full fetch: {path}", flush=True)
            run("git", "fetch", "origin", quiet=True)
        r = run("git", "checkout", "--detach", sha, quiet=True)
        if r.returncode != 0:
            print(f"FATAL: cannot checkout {sha} in {path}\n{r.stderr}", flush=True)
            sys.exit(1)
        shutil.rmtree(os.path.join(dest, ".git"), ignore_errors=True)
        print(f"git ok: {path}", flush=True)


def fetch_cipd(root):
    blocks = []
    for sub, pkg, ver in load("cipd_deps.txt"):
        sub = sub[4:]  # 去掉 src/
        pkg = pkg.replace("${{platform}}", "linux-amd64").replace("${{arch}}", "amd64")
        blocks.append(f"@Subdir {sub}\n{pkg} {ver}\n")
    with open("ensure.txt", "w") as f:
        f.write("\n".join(blocks))
    subprocess.run(["cipd", "ensure", "-root", root, "-ensure-file", "ensure.txt"],
                   check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    root = os.path.join(args.out, "root")
    os.makedirs(root, exist_ok=True)
    fetch_git(root)
    fetch_cipd(root)
    print("RELAY_COMPLETE")


if __name__ == "__main__":
    main()
