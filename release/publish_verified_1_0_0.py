"""Publish the already verified 1.0.0 APK; never rebuild or access signing secrets."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import zipfile

REPO = "Kok1Ne/feishu-wake"
TAG = "v1.0.0"
SOURCE = "0093293c1f29287012f41281b836e72308f04872"
RELEASE_RUN = 44051893821
CORE_RUN = 44048061951
ARTIFACT = 14313828841
ARTIFACT_SHA = "146cbaa61b266c20c270d0bbfeeac2bc21aacd220de594820178776b15e121af"
APK_SHA = "f9d7b8e6f52a09a51c21ca74b0a09159ddd7975f759c69426b3e9641fac3f759"
CERT_SHA = "323c450b86e5e0439bd0928e7ad574daa08fe2e5b66c13ea68aa9fe2cba96a45"
APK = "FeishuWake-1.0.0.apk"
ORIGINAL_NAMES = {
    APK, "APK-SIGNATURE.txt", "CLOUD_TEST_REPORT_ZH.md",
    "FeishuWake-AndroidStudio-source.zip", "FeishuWake-cloud-evidence.zip",
    "REALME_COMPATIBILITY.md", "SHA256SUMS.txt", "SOURCE_COMMIT.txt",
    "USER_GUIDE_ZH.md",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def gh(*args, payload=None):
    command = ["gh", *args]
    result = subprocess.run(
        command, input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=120, check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"GitHub operation failed ({result.returncode}): "
            + result.stderr.decode("utf-8", errors="replace")[:2000]
        )
    return result.stdout


def api(path):
    return json.loads(gh("api", f"repos/{REPO}/{path}"))


def release_for_tag():
    releases = api("releases?per_page=100")
    matches = [r for r in releases if r["tag_name"] == TAG]
    require(len(matches) <= 1, "Duplicate release tag")
    return matches[0] if matches else None


def check_run(run_id, workflow_path):
    run = api(f"actions/runs/{run_id}")
    require(run["status"] == "completed" and run["conclusion"] == "success",
            f"Run {run_id} did not complete successfully")
    require(run["head_sha"] == SOURCE and run["path"] == workflow_path,
            "Verification provenance does not match")
    require(run["repository"]["full_name"] == REPO, "Unexpected repository")


def main():
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Cloud Actions only")
    require(os.environ.get("GITHUB_REPOSITORY") == REPO, "Wrong repository")
    require(os.environ.get("GITHUB_REF") == "refs/heads/main", "Main branch only")
    require(os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Standard cloud runner required")
    require(release_for_tag() is None,
            "Release already exists; inspect it instead of overwriting")
    refs = api(f"git/matching-refs/tags/{TAG}")
    for ref in refs:
        if ref["ref"] == f"refs/tags/{TAG}":
            require(ref["object"]["type"] == "commit"
                    and ref["object"]["sha"] == SOURCE,
                    "Existing tag does not point at verified source")

    check_run(CORE_RUN, ".github/workflows/android11-core.yml")
    check_run(RELEASE_RUN, ".github/workflows/verified-release.yml")
    artifact = api(f"actions/artifacts/{ARTIFACT}")
    require(not artifact["expired"], "Verified artifact expired")
    require(artifact["workflow_run"]["id"] == RELEASE_RUN
            and artifact["workflow_run"]["head_sha"] == SOURCE,
            "Artifact has wrong source/run")
    require(artifact["name"] == "FeishuWake-1.0.0-verified-release",
            "Wrong artifact name")
    require(artifact["digest"] == "sha256:" + ARTIFACT_SHA,
            "Artifact server digest mismatch")
    archive = gh("api", f"repos/{REPO}/actions/artifacts/{ARTIFACT}/zip")
    require(len(archive) == 7045480 and sha(archive) == ARTIFACT_SHA,
            "Downloaded artifact digest mismatch")
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        require(len(z.infolist()) == len(ORIGINAL_NAMES)
                and set(z.namelist()) == ORIGINAL_NAMES, "Unexpected artifact files")
        require(sum(i.file_size for i in z.infolist()) < 20_000_000,
                "Oversized artifact contents")
        payloads = {name: z.read(name) for name in ORIGINAL_NAMES}
    checksums = {}
    for line in payloads["SHA256SUMS.txt"].decode("utf-8").splitlines():
        digest, name = line.split("  ", 1)
        require(name in ORIGINAL_NAMES and name not in checksums,
                "Unexpected checksum entry")
        require(sha(payloads[name]) == digest, f"Payload mismatch: {name}")
        checksums[name] = digest
    require(set(checksums) == ORIGINAL_NAMES - {"SHA256SUMS.txt"},
            "Incomplete checksum manifest")
    require(sha(payloads[APK]) == APK_SHA, "APK has changed")
    require(payloads["SOURCE_COMMIT.txt"].decode().strip() == SOURCE,
            "Source commit mismatch")
    signature = payloads["APK-SIGNATURE.txt"].decode()
    require(signature.startswith("Verifies\n")
            and "Verified using v2 scheme (APK Signature Scheme v2): true" in signature
            and f"Signer #1 certificate SHA-256 digest: {CERT_SHA}" in signature,
            "APK signature evidence mismatch")
    with zipfile.ZipFile(io.BytesIO(payloads["FeishuWake-cloud-evidence.zip"])) as z:
        smoke = json.loads(z.read("reports/release-device/results.json"))
        identity = json.loads(z.read("reports/release-build/identity.json"))
        gate = json.loads(z.read("release-evidence.json"))
    require(smoke["source_commit"] == SOURCE and smoke["apk_sha256"] == APK_SHA
            and len(smoke["checks"]) == 16
            and all(value == "PASS" for value in smoke["checks"].values()),
            "Release device validation incomplete")
    require(identity["package"] == "dev.feishuwake"
            and identity["certificate_sha256"] == CERT_SHA
            and identity["apk_sha256"] == APK_SHA
            and identity["source_commit"] == SOURCE, "Release identity mismatch")
    require(gate["source_commit"] == SOURCE and int(gate["run_id"]) == CORE_RUN
            and all(value == "PASS" for value in gate["checks"].values()),
            "Full acceptance evidence incomplete")
    print("Verified exact source, artifact, APK, signature and emulator evidence.")

    # Adapt explanatory documents to Android 11 without changing binaries or raw evidence.
    del payloads["REALME_COMPATIBILITY.md"]
    payloads["USER_GUIDE_ZH.md"] = Path("docs/USER_GUIDE_ZH.md").read_bytes()
    payloads["ANDROID11_COMPATIBILITY.md"] = Path("docs/ANDROID11_COMPATIBILITY.md").read_bytes()
    report = payloads["CLOUD_TEST_REPORT_ZH.md"].decode("utf-8")
    report = report.replace(
        "realme UI 2.0 自启动、冻结、锁屏和电池策略仍待指定真机一次最终验收。",
        "不同设备的自启动、冻结、锁屏和电池策略仍待首次安装后的实际验收。"
    )
    payloads["CLOUD_TEST_REPORT_ZH.md"] = report.encode("utf-8")
    for name in ("USER_GUIDE_ZH.md", "ANDROID11_COMPATIBILITY.md", "CLOUD_TEST_REPORT_ZH.md"):
        require("realme" not in payloads[name].decode("utf-8").lower(),
                "Brand-specific explanatory text remains")
    payloads["SHA256SUMS.txt"] = "".join(
        f"{sha(payloads[name])}  {name}\n"
        for name in sorted(payloads) if name != "SHA256SUMS.txt"
    ).encode("utf-8")

    with tempfile.TemporaryDirectory(prefix="feishuwake-publish-") as temporary:
        folder = Path(temporary)
        for name, data in payloads.items():
            (folder / name).write_bytes(data)
        paths = [str(folder / name) for name in sorted(payloads)]
        gh("release", "create", TAG, "--repo", REPO, "--target", SOURCE,
           "--title", "Feishu Wake 1.0.0", "--notes-file", "release/1.0.0-notes.md",
           "--draft", *paths)
        draft = release_for_tag()
        require(draft is not None and draft["draft"] and not draft["prerelease"],
                "Expected complete release draft")
        assets = {a["name"]: a for a in draft["assets"]}
        require(set(assets) == set(payloads), "Release assets incomplete")
        for name, data in payloads.items():
            asset = assets[name]
            require(asset["state"] == "uploaded" and asset["size"] == len(data)
                    and asset.get("digest") == "sha256:" + sha(data),
                    f"Uploaded asset mismatch: {name}")
        print(f"All {len(assets)} uploaded release assets match SHA-256.")
        published = json.loads(gh(
            "api", "--method", "PATCH", f"repos/{REPO}/releases/{draft['id']}",
            "--input", "-", payload=json.dumps({"draft": False, "make_latest": "true"}).encode()
        ))
        require(not published["draft"] and not published["prerelease"],
                "Release was not published")
        tag = api(f"git/ref/tags/{TAG}")
        require(tag["object"]["type"] == "commit"
                and tag["object"]["sha"] == SOURCE, "Published tag mismatch")
        apk_asset = next(a for a in published["assets"] if a["name"] == APK)
        expected_url = f"https://github.com/{REPO}/releases/download/{TAG}/{APK}"
        require(apk_asset["browser_download_url"] == expected_url,
                "Unexpected public APK URL")
        request = urllib.request.Request(expected_url, headers={"User-Agent": "FeishuWake-Release-Verification"})
        with urllib.request.urlopen(request, timeout=60) as response:
            downloaded_apk = response.read(2_000_000)
        require(sha(downloaded_apk) == APK_SHA, "Public APK download hash mismatch")
        print("Public APK download SHA-256 matches verified release.")
        print(published["html_url"])
        Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(
            f"# Published Feishu Wake 1.0.0\n\n{published['html_url']}\n\n"
            f"- {len(assets)} assets checked against SHA-256\n"
            f"- APK source: {SOURCE}\n- APK SHA-256: {APK_SHA}\n"
            "- Original signed APK reused; no rebuild or re-signing.\n"
            "- Public APK download verified.\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
