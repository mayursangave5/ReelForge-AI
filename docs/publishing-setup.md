# Publishing setup (YouTube Shorts + Instagram Reels)

Both platforms use their official APIs. Everything here is free; no billing is
required. Tokens stay on disk under `data/tokens/` and are never printed.

## 1. YouTube (Data API v3, free quota)

1. Open https://console.cloud.google.com/ and create a project (no billing
   account needed).
2. **APIs & Services -> Library -> YouTube Data API v3 -> Enable**.
3. **OAuth consent screen**: External, Testing. Add your own Google account as
   a test user. Scopes: `https://www.googleapis.com/auth/youtube.upload` and
   `https://www.googleapis.com/auth/youtube.readonly` (readonly is for analytics).
4. **Credentials -> Create credentials -> OAuth client ID -> Desktop app**.
5. Download the JSON and save it as `data/tokens/client_secret.json`
   (or set `YOUTUBE_CLIENT_SECRETS` in `.env` to its path).
6. Authorize once (opens a browser, stores `data/tokens/youtube_token.json`):

   ```
   python -m reels auth --platform youtube
   ```

Notes:
- Free quota is 10,000 units/day; one upload uses ~1,600.
- While the consent screen is in **Testing**, refresh tokens expire after
  ~7 days. Re-run the auth command when uploads start failing. Publish the
  consent screen (still free) for long-lived tokens.
- Uploads default to `YOUTUBE_PRIVACY=private`. Set `unlisted` or `public`
  when you are ready.

## 2. Instagram (Graph API, free)

1. Convert the Instagram account to **Professional** (Creator/Business) and
   link it to a Facebook Page (both free).
2. Create a Meta app at https://developers.facebook.com/apps/ (type: Business).
3. Add the **Instagram Graph API** product. Request
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
   `pages_read_engagement`, `instagram_manage_insights` (last one is for
   analytics).
4. Get the Instagram user id:
   - `GET /me/accounts` -> page id
   - `GET /{page-id}?fields=instagram_business_account` -> IG user id
5. Exchange the short-lived user token for a long-lived token (60 days) in the
   Graph API Explorer, then put both values in `.env`:

   ```
   IG_USER_ID=1784...
   IG_ACCESS_TOKEN=EAA...
   IG_API_VERSION=v21.0
   ```

6. Instagram requires a **public HTTPS video URL** (it downloads the file
   itself). With Cloudflare R2 configured (section 3), the pipeline uploads the
   MP4, verifies it and passes the URL automatically. You can still override it
   manually:

   ```
   python -m reels publish --voice-run runs/<run>_voice1 --platform instagram \
     --video-url https://your-host/reel.mp4 --confirm
   ```

## 3. Cloudflare R2 (free tier, automatic Instagram URL)

1. Create a bucket at https://dash.cloudflare.com/ -> **R2 Object Storage**.
2. Enable public access: bucket -> **Settings -> Public access**. Either allow the
   `r2.dev` subdomain (fine for Instagram) or connect a custom domain. Copy the
   public base URL (no trailing path).
3. Create an API token: **R2 -> Manage R2 API Tokens -> Create API token** with
   **Object Read & Write** permission, scoped to the bucket. Copy the
   **Access Key ID** and **Secret Access Key** (the secret is shown once).
4. Find the **Account ID** on the R2 overview page (or reuse
   `CLOUDFLARE_ACCOUNT_ID`).
5. Fill `.env`:

   ```
   R2_ACCOUNT_ID=your-account-id
   R2_ACCESS_KEY_ID=your-access-key-id
   R2_SECRET_ACCESS_KEY=your-secret-access-key
   R2_BUCKET=reels
   R2_PUBLIC_BASE_URL=https://pub-xxxxxxxx.r2.dev
   R2_PREFIX=reels
   R2_RETENTION_HOURS=24
   ```

   The endpoint is derived as
   `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com`.

Behaviour: every rendered MP4 is uploaded (retried on network errors),
`HEAD`-checked for public HTTPS access, and its URL is reused for Instagram.
Expired cloud copies are deleted after successful publishing; set
`R2_RETENTION_HOURS=0` to delete right after publishing. Use the dashboard's
**Videos -> Clean up expired cloud videos** button for a manual sweep.

## 4. Publish workflow (approval-first)

```
python -m reels auth --platform status      # readiness, no secrets shown
python -m reels publish --voice-run runs/<run>_voice1            # dry run
python -m reels publish --voice-run runs/<run>_voice1 --confirm  # live upload
```

- `--platform both|youtube|instagram` (default `both`).
- Default is a dry run: it validates credentials, builds the payload and
  records `dry_run` in `publications` - nothing is uploaded.
- Uploads require `--confirm`, which is the approval step while
  `APPROVAL_MODE=true` and `AUTO_PUBLISH=false`.
- Duplicate guard: one publication row per `run_id:platform`; already
  published items are skipped, failures are recorded in `publications.error`
  and the `errors` table.
- Successful uploads store the platform id/URL and mark the video and topic
  `published`.

## 5. Analytics (optional)

```
python -m reels analytics --capture   # fetch views/likes/comments/shares
python -m reels analytics             # latest totals per topic
```

- YouTube uses the Data API `videos.list` (cheap, 1 unit per call). Re-run
  `python -m reels auth --platform youtube` once to grant the readonly scope.
- Instagram uses Reels insights; the token needs `instagram_manage_insights`.
- Views feed back into topic selection: titles similar to high-performing
  topics get a small score bonus.
- Audience retention needs the YouTube Analytics API and is not collected yet.

## 6. Troubleshooting

- `YouTube is not authorized` -> run the auth command again.
- `missing OAuth client JSON` -> step 5 above.
- Instagram `public HTTPS --video-url required` -> configure R2 or pass a URL.
- `uploaded video is not publicly reachable` -> enable R2 public access and
  check `R2_PUBLIC_BASE_URL`.
- Quota errors -> wait for the daily reset; the code never retries with a paid
  model or paid API.
