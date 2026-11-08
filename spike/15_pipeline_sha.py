"""Spike 15: tìm pipeline theo commit trên GitLab thật. Chỉ đọc, không cần winIDEA.

Token lấy từ biến môi trường GITLAB_TOKEN, không ghi ra file kết quả.
"""
import argparse
import os
from urllib.parse import quote

import requests
from _common import Report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://gitlab.hella.com")
    parser.add_argument("--project", required=True)
    parser.add_argument("--sha", required=True, help="Commit đầy đủ (git rev-parse HEAD)")
    parser.add_argument("--ca-bundle")
    args = parser.parse_args()
    report = Report("15_pipeline_sha")
    try:
        session = requests.Session()
        session.headers["PRIVATE-TOKEN"] = os.environ["GITLAB_TOKEN"]
        session.verify = args.ca_bundle or True
        base = f"{args.url}/api/v4/projects/{quote(args.project, safe='')}"
        resp = session.get(f"{base}/pipelines", params={"sha": args.sha, "per_page": 20}, timeout=30)
        report.line(f"pipelines: HTTP {resp.status_code}")
        for pipeline in resp.json():
            report.line(f"pipeline {pipeline['id']} ref={pipeline['ref']} status={pipeline['status']} sha={pipeline['sha']}")
            jobs = session.get(f"{base}/pipelines/{pipeline['id']}/jobs", params={"per_page": 100}, timeout=30).json()
            for job in jobs:
                report.line(f"    {job['name']}: {job['status']} archive={bool(job.get('artifacts_file'))}")
    except Exception:
        report.exc("fatal")
    finally:
        report.close()


if __name__ == "__main__":
    main()
