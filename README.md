# Submission → Social Media Workflow

Automates the whiteboard flow: a **Google Drive folder** (video + transcript +
PPTs) is submitted to **YouTube** as a *private* upload **scheduled to go public
in 2 days**, and **pre-posts for X and LinkedIn** are generated (and optionally
published) with the title, tags, and the YouTube watch link.

```
Google Drive folder ──► YouTube (private + publishAt = now + 2 days) ──► pre-posts
  ├─ video                 ├─ title                                       ├─ X (≤210 chars, tags, link)
  ├─ transcript            ├─ description (+ PPT urls)                    └─ LinkedIn (message, tags, link)
  ├─ PPTs                  └─ tags
  └─ settings.json (optional overrides)
```

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in values, then export them (e.g. `set -a; . ./.env; set +a`)
```

Google: create an OAuth client (Desktop) in Google Cloud Console with the
**Drive API** and **YouTube Data API v3** enabled; download the client secrets
JSON to the path in `GOOGLE_CLIENT_SECRETS_FILE`. First run opens a browser to
grant `drive.readonly` + `youtube.upload`; the token is cached in `GOOGLE_TOKEN_FILE`.

All configuration comes from environment variables — see `.env.example`.
No secrets are hardcoded anywhere in the codebase.

## Usage

```bash
# Upload scheduled video + save pre-posts to out/pre_posts.json for review
.venv/bin/python -m submission_workflow.cli --folder-id <DRIVE_FOLDER_ID>

# Also publish the posts to X and LinkedIn immediately
.venv/bin/python -m submission_workflow.cli --publish-social
```

Optional `settings.json` in the Drive folder overrides metadata:

```json
{"title": "...", "description": "...", "tags": ["AI"], "ppt_urls": ["https://..."]}
```

## Web front-end + HTTP server (WebMCP)

`submission_workflow/server.py` exposes the same workflow as a small FastAPI API
and serves the WebMCP front-end from the `webmcps` repo so an AI agent (or you)
can review a submission, set the publish time, upload, and publish posts — with
on-screen confirmation before anything goes public.

```bash
.venv/bin/pip install -r requirements.txt          # adds fastapi + uvicorn
set -a; . ./.env; set +a                             # DRIVE_PARENT_FOLDER_ID, WEBMCP_DIR=../webmcps, …
.venv/bin/uvicorn submission_workflow.server:app --port 8000
# open http://localhost:8000/submission-publisher/
```

| Endpoint | Does |
| --- | --- |
| `GET /api/health` | liveness; also how the page detects the backend |
| `GET /api/submissions` | every subfolder of `DRIVE_PARENT_FOLDER_ID` (or the single `DRIVE_FOLDER_ID`) with its video, transcript text, slide links and `settings.json` |
| `POST /api/submissions/{id}/youtube` | downloads the video and uploads it **private** with the reviewed title/description/tags and `publishAt` (RFC 3339, ≥ 15 min ahead) |
| `POST /api/submissions/{id}/social` | posts the given X and/or LinkedIn text; 503 if that platform isn't configured, 502 with partial results on API errors |

Google OAuth runs on the first API call (the browser consent flow opens on the
machine running the server, token cached in `GOOGLE_TOKEN_FILE`). X/LinkedIn
credentials are optional in server mode. Set `ORIGIN_TRIAL_TOKEN` to send Chrome's
`Origin-Trial` header on HTML once you register the origin for the WebMCP trial.

## Tests

Test-first development; run with:

```bash
.venv/bin/python -m pytest
```

## Architecture (SOLID, single responsibility per module)

| Module | Responsibility |
| --- | --- |
| `config.py` | Typed settings from environment variables |
| `models.py` | Domain models (`DriveFile`, `Submission`) |
| `google_auth.py` | Google OAuth flow + token cache |
| `drive/client.py` | Find/classify/download the submission files |
| `youtube/schedule.py` | Compute the RFC3339 `publishAt` (now + N days) |
| `youtube/metadata.py` | Build title/description/tags (PPT urls included) |
| `youtube/uploader.py` | Resumable upload, private + scheduled |
| `social/post_builder.py` | Compose X (≤210 chars) and LinkedIn texts |
| `social/x_client.py` | POST /2/tweets |
| `social/linkedin_client.py` | POST /rest/posts (versioned) |
| `workflow.py` | Orchestration via dependency injection |
| `cli.py` | Entry point, wires real clients |
| `server.py` | FastAPI API + static host for the WebMCP front-end |

## Prerequisites beyond API credentials (from the official docs)

**YouTube — API project audit (critical for this workflow).** Videos uploaded
via `videos.insert` from **unverified API projects** (created after
2020-07-28) are **restricted to private viewing mode** until the project passes
YouTube's API audit. Since this workflow relies on a private upload flipping
public at `publishAt`, an unaudited project means the video never launches —
submit the [API audit / compliance form](https://developers.google.com/youtube/v3/guides/auth/compliance-audit)
first. Also note the upload quota bucket (videos.insert is capped per day;
see the [videos.insert reference](https://developers.google.com/youtube/v3/docs/videos/insert)),
and the 256GB / `video/*` file constraints.

**Google OAuth consent screen.** While the OAuth app is in *Testing* status,
add your Google account as a **test user**, and expect cached refresh tokens to
[expire after 7 days](https://developers.google.com/identity/protocols/oauth2#expiration)
until the app is moved to *In production*.

**X — app permission level.** A developer app defaults to read access; posting
requires the **"Read and write"** permission, and per the
[developer apps docs](https://docs.x.com/resources/fundamentals/developer-apps)
changing permissions requires **re-authorizing / regenerating the access
tokens** afterwards. The app must live inside a developer-portal **Project**
for v2 endpoints, and write volume is capped by your access tier — check the
[pricing page](https://docs.x.com/x-api/getting-started/pricing) (the Free tier
is heavily write-limited).

**LinkedIn — product access + author URN.** The app (created on the
[developer portal](https://developer.linkedin.com/), associated with a
LinkedIn Page) must be granted the **"Share on LinkedIn"** product to obtain
the `w_member_social` scope the [Posts API requires](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api#permissions)
(`w_organization_social` + an admin page role if posting as an organization).
`LINKEDIN_AUTHOR_URN` needs your member id (`urn:li:person:{id}`) — enable
**"Sign In with LinkedIn using OpenID Connect"** and call `/v2/userinfo` to get
it. Member access tokens come from the 3-legged OAuth flow (or the portal's
token generator), last ~60 days, and programmatic refresh is limited to
approved partners — plan to re-issue the token when it expires.

## Evidence from official docs

- **YouTube** `videos.insert`: `status.publishAt` is RFC3339 and *"can be set
  only if the privacy status of the video is private"* — youtube.v3 discovery
  document / [videos.insert reference](https://developers.google.com/youtube/v3/docs/videos/insert).
- **LinkedIn Posts API**: `POST https://api.linkedin.com/rest/posts` with
  `LinkedIn-Version: YYYYMM` and `X-Restli-Protocol-Version: 2.0.0`; body fields
  `author`, `commentary`, `visibility`, `distribution`, `lifecycleState`,
  `isReshareDisabledByAuthor`; 201 response carries the post id in the
  `x-restli-id` header; reserved "little text format" characters in commentary
  are escaped — [Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api).
- **X API v2**: `POST https://api.x.com/2/tweets` with `{"text": ...}`; created
  id at `data.id` — [Creation of a Post](https://docs.x.com/x-api/posts/creation-of-a-post).
  The 210-char target from the plan stays well inside X's 280 limit.
