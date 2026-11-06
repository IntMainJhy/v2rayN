"""Track official stable releases without overwriting the fork's default branch."""

import hashlib
import json
import os
import subprocess
import sys

UPSTREAM = "2dust/v2rayN"
REPO = os.environ.get("GH_REPO", "IntMainJhy/v2rayN")


def command(*args, check=True):
    return subprocess.run(args, text=True, capture_output=True, check=check)


def api(path, method="GET", **fields):
    result = command(
        "gh", "api", "--method", method, path,
    ) if not fields else subprocess.run(
        ["gh", "api", "--method", method, path, "--input", "-"],
        input=json.dumps(fields), text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


def items(path):
    """Paginate lists so old bot PRs/issues still prevent duplicates."""
    page = 1
    while True:
        batch = api(f"{path}&per_page=100&page={page}")
        yield from batch
        if len(batch) < 100:
            break
        page += 1


def notice(key, title, body):
    marker = f"<!-- upstream-release-sync:{key} -->"
    existing = next((i for i in items(f"repos/{REPO}/issues?state=all")
                     if "pull_request" not in i and marker in (i.get("body") or "")), None)
    body = f"{marker}\n@{REPO.split('/')[0]}\n\n{body}"
    if existing:
        if existing["state"] == "closed" or existing.get("body") != body:
            api(f"repos/{REPO}/issues/{existing['number']}", "PATCH",
                state="open", title=title, body=body)
    else:
        api(f"repos/{REPO}/issues", "POST", title=title, body=body)


def merge_check(base, head):
    # merge-tree does not check out or execute any upstream code.
    result = command("git", "merge-tree", "--write-tree", base, head, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr or result.stdout)
    return result.returncode == 0, result.stdout


def sync():
    release = api(f"repos/{UPSTREAM}/releases/latest")
    if release["draft"] or release["prerelease"]:
        raise RuntimeError("Expected an official stable release")
    tag = release["tag_name"]
    metadata = api(f"repos/{REPO}")
    base = metadata["default_branch"]
    command("git", "check-ref-format", f"refs/tags/{tag}")
    command("git", "fetch", "--no-tags", "origin",
            f"+refs/heads/{base}:refs/remotes/origin/{base}")
    command("git", "fetch", "--no-tags", f"https://github.com/{UPSTREAM}.git",
            f"+refs/tags/{tag}:refs/upstream-release/latest")
    head = command("git", "rev-parse", "refs/upstream-release/latest^{commit}").stdout.strip()
    base_ref = f"refs/remotes/origin/{base}"
    ancestor = command("git", "merge-base", "--is-ancestor", head, base_ref, check=False)
    if ancestor.returncode == 0:
        print(f"Official {tag} is already included; no PR needed.")
        return
    if ancestor.returncode != 1:
        raise RuntimeError(ancestor.stderr)

    # The tag hash keeps branch names safe even if upstream uses slashes in tags.
    key = hashlib.sha256(tag.encode()).hexdigest()[:16]
    branch = f"upstream/stable-{key}"
    prs = list(items(f"repos/{REPO}/pulls?state=all&head={REPO.split('/')[0]}:{branch}"))
    if prs and prs[0]["state"] == "closed":
        print(f"PR for {tag} was already closed; respecting that decision.")
        return
    clean, details = merge_check(base_ref, head)
    if not prs:
        # Forks share Git objects with their parent; create a ref to the fetched
        # release commit rather than copying/merging upstream files on master.
        refs = api(f"repos/{REPO}/git/matching-refs/heads/{branch}")
        exact = next((r for r in refs if r["ref"] == f"refs/heads/{branch}"), None)
        if exact and exact["object"]["sha"] != head:
            raise RuntimeError(f"{branch} has changed; refusing to overwrite it")
        if not exact:
            api(f"repos/{REPO}/git/refs", "POST", ref=f"refs/heads/{branch}", sha=head)
        pr = api(f"repos/{REPO}/pulls", "POST", title=f"同步官方正式版 {tag}",
                 head=branch, base=base, body=(
                     f"官方正式版：{release['html_url']}\n\n"
                     f"固定提交：`{head}`\n\n"
                     "此 PR 将官方正式版合并到定制分支，保留 fork 自己的提交。"
                     "请检查 UI 兼容性并完成构建验证后手动合并；不会自动发布安装包。\n\n"
                     "注意：GITHUB_TOKEN 创建的 PR 不会自动触发通常的 PR 检查，"
                     "合并前需要手动运行相应验证。\n"
                 ))
    else:
        pr = prs[0]
        # A maintainer may have resolved conflicts on the sync branch.
        command("git", "fetch", "--no-tags", "origin",
                f"+refs/heads/{branch}:refs/remotes/origin/{branch}")
        clean, details = merge_check(base_ref, f"refs/remotes/origin/{branch}")
    print(pr["html_url"])
    if not clean:
        notice(key, f"同步官方 {tag} 需要解决合并冲突",
               f"同步 PR：{pr['html_url']}\n官方版本：{release['html_url']}\n\n"
               "Git 检测到合并冲突，请在同步分支解决并验证后再合并。"
               "你的默认分支未被修改。\n\n"
               f"```text\n{details[:12000]}\n```")
    else:
        print("No merge conflicts detected. Manual review is still required.")


if __name__ == "__main__":
    try:
        sync()
    except Exception as error:
        print(f"Sync failed: {error}", file=sys.stderr)
        run_url = (f"https://github.com/{REPO}/actions/runs/"
                   f"{os.environ.get('GITHUB_RUN_ID', '')}")
        try:
            notice("failure", "官方正式版自动同步运行失败",
                   f"请查看运行日志：{run_url}\n\n"
                   "检查 Actions 是否允许创建 PR、Issues 是否开启，以及仓库写入权限。")
        except Exception as notification_error:
            print(f"Could not create notification: {notification_error}", file=sys.stderr)
        sys.exit(1)
