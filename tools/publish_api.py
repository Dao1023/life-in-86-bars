# -*- coding: utf-8 -*-
"""把本地提交复刻到 GitHub（沙箱禁止创建管道、也禁止子进程，故所有 git 输出预先落盘）。

前置（由 shell 完成）：
  git diff --name-status <parent> <sha> > tmp/<sha>.names
  git archive <sha> -o tmp/<sha>.tar && 解包到 tmp/<sha>/
  git log -1 --format=%B <sha> > tmp/<sha>.msg

用法： python tools/publish_api.py <repo> <branch> <sha> [<sha> ...]
"""
import base64
import json
import os
import sys
import urllib.request

API = "https://api.github.com"
TMP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_publish")


def req(method, url, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", "token " + token)
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("Content-Type", "application/json")
    r.add_header("User-Agent", "publish-api")
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode())


def main():
    repo, branch = sys.argv[1], sys.argv[2]
    commits = sys.argv[3:]
    token = os.environ["GITHUB_TOKEN"]
    for sha in commits:
        with open(os.path.join(TMP, sha + ".names"), encoding="utf-8") as f:
            lines = [l.rstrip("\n") for l in f if l.strip()]
        with open(os.path.join(TMP, sha + ".msg"), encoding="utf-8") as f:
            msg = f.read()
        if msg.endswith("\n"):          # %B 会多给一个换行；提交体本身以一个换行结尾
            msg = msg[:-1]
        with open(os.path.join(TMP, sha + ".parent"), encoding="utf-8") as f:
            parent = f.read().strip()
        with open(os.path.join(TMP, sha + ".ident"), encoding="utf-8") as f:
            an, ae, ad, cn, ce, cd = f.read().strip().split("|")
        ident = {"author": {"name": an, "email": ae, "date": ad},
                 "committer": {"name": cn, "email": ce, "date": cd}}

        remote_parent = req("GET", f"{API}/repos/{repo}/commits/{parent}", token)
        base_tree = remote_parent["commit"]["tree"]["sha"]

        tree = []
        for line in lines:
            parts = line.split("\t")
            status, path = parts[0], parts[-1]
            if status.startswith("D"):
                tree.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
                continue
            full = os.path.join(TMP, sha, *path.split("/"))
            with open(full, "rb") as f:
                blob = f.read()
            created = req("POST", f"{API}/repos/{repo}/git/blobs", token,
                          {"content": base64.b64encode(blob).decode(), "encoding": "base64"})
            tree.append({"path": path, "mode": "100644", "type": "blob", "sha": created["sha"]})

        new_tree = req("POST", f"{API}/repos/{repo}/git/trees", token,
                       {"base_tree": base_tree, "tree": tree})
        new_commit = req("POST", f"{API}/repos/{repo}/git/commits", token,
                         dict({"message": msg, "tree": new_tree["sha"], "parents": [parent]}, **ident))
        req("PATCH", f"{API}/repos/{repo}/git/refs/heads/{branch}", token,
            {"sha": new_commit["sha"], "force": False})
        print(f"pushed {sha} -> {new_commit['sha']}  (files {len(tree)})")
        if new_commit["sha"] != sha:
            print("!! 远端 SHA 与本地不一致，停止")
            sys.exit(1)


if __name__ == "__main__":
    main()
