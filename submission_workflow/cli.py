"""Command-line entry point: python -m submission_workflow.cli [options]."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from googleapiclient.discovery import build

from submission_workflow.config import Settings
from submission_workflow.drive.client import DriveClient
from submission_workflow.google_auth import get_credentials
from submission_workflow.social.linkedin_client import LinkedInClient
from submission_workflow.social.x_client import XClient
from submission_workflow.workflow import SubmissionWorkflow
from submission_workflow.youtube.uploader import YouTubeUploader


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit a Drive video to YouTube (scheduled) and prepare X/LinkedIn posts."
    )
    parser.add_argument("--folder-id", help="Drive folder id (default: DRIVE_FOLDER_ID env)")
    parser.add_argument("--work-dir", default="out", help="Directory for downloads and pre-posts")
    parser.add_argument(
        "--publish-social", action="store_true",
        help="Also publish the pre-posts to X and LinkedIn now (default: save for review)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = Settings.from_env()
    folder_id = args.folder_id or settings.drive.folder_id
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    creds = get_credentials(settings.google.client_secrets_file, settings.google.token_file)
    workflow = SubmissionWorkflow(
        drive=DriveClient(build("drive", "v3", credentials=creds)),
        uploader=YouTubeUploader(build("youtube", "v3", credentials=creds)),
        x_client=XClient(settings.x),
        linkedin_client=LinkedInClient(settings.linkedin),
        publish_delay_days=settings.youtube.publish_delay_days,
        category_id=settings.youtube.category_id,
        x_max_chars=settings.x.max_post_chars,
    )
    result = workflow.run(folder_id, work_dir, publish_social=args.publish_social)

    pre_posts_path = work_dir / "pre_posts.json"
    pre_posts_path.write_text(json.dumps({
        "video_id": result.video_id,
        "watch_url": result.watch_url,
        "publish_at": result.publish_at,
        "x": {"text": result.x_post, "post_id": result.x_post_id},
        "linkedin": {"text": result.linkedin_post, "post_id": result.linkedin_post_id},
    }, indent=2))

    print(f"Uploaded video {result.video_id} (goes public {result.publish_at})")
    print(f"Watch URL: {result.watch_url}")
    if args.publish_social:
        print(f"Posted to X ({result.x_post_id}) and LinkedIn ({result.linkedin_post_id})")
    else:
        print(f"Pre-posts saved for review: {pre_posts_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
