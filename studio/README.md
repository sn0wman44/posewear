# Product Video Studio

Local Windows tool for the product-to-model-photo-to-video workflow. The UI is at http://127.0.0.1:8765. Double-click **Start Studio.cmd** to start it and open the UI. The server listens only on your computer. No npm build or image-generation API key is required.

## Run

Dependencies are already installed on this computer. On a new machine:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Your existing tank product, model and video are imported by `python seed.py`. The import is idempotent and does not replace an existing library.

## Workflow

1. Paste a full `https://shop.tiktok.com/.../pdp/.../<product-id>` link. Extraction runs in the background; the product ID and gallery are saved locally. Select the reference image representing the desired variant.
2. Choose a model from saved original photos. Set garment notes and complementary styling if needed, then save.
3. Click **Prepare chat handoff** and paste the copied request into this Codex / ChatGPT chat. The handoff contains exact local reference paths, six pose prompts and the image destination. The agent uses the built-in image tool under your available chat access, saves `01.png`–`06.png` in the job's `poses/` folder, and runs `manage.py sync <job-id> --render`.
4. Alternatively upload each image directly into its pose slot, or copy six images into `data/jobs/<job-id>/poses/` and click **Sync image folder**.
5. Click **Render MP4**. Six 15-frame holds repeat four times: 12 seconds, 1080×1920, 30 fps, H.264, yuv420p, silent. Every export is decoded to verify its total frames.
6. Download the video or project ZIP. Export versions are preserved.

### Important boundary

Images are generated **in the chat**, not by this app. There is no supported background call from this local app to the chat's image tool. No ChatGPT cookies, private endpoints, paid image APIs or CreatOK credentials are used. The local tool automates extraction, organization, handoff and MP4 assembly. Discord queues product jobs but does not bypass this chat step. Chat image-generation limits still apply.

## Discord intake

Create a Discord bot, enable Message Content Intent, and invite it with View Channel and Read Message History. Save the channel ID and paste the bot token in Settings. The token stays in server memory until shutdown and is never returned through the API or saved in the database. For reuse across launches, set the `DISCORD_BOT_TOKEN` environment variable before starting the app. Keep tokens out of chat and source control.

Click **Start listening** to explicitly enable intake. Initial connection skips history. The message cursor is then saved so later connections can resume; polling runs every 8 seconds. The listener ignores bots and duplicate product IDs, and supports an optional author ID allowlist. It queues extraction and waits for local review/chat generation. It does not post to Discord or publish to TikTok. Starting intake enables restart recovery while credentials remain available. **Stop listening** disables it. Credentials supplied during setup are stored in the git-ignored local `.env`; the Settings token field only overrides the current process, without saving a new token.

## Local organization

```text
data/
  studio.sqlite                # library, settings and job records
  products/<product-id>/        # downloaded HTML and product images
  models/<model-id>/            # copied reference photos
  jobs/<job-id>/
    handoff.json, HANDOFF.md    # chat instructions and prompts
    poses/                     # six source images
    normalized/                # scaled/padded render images
    timeline.json              # exact frame schedule
    video-<timestamp>.mp4      # versioned exports
    validation.txt, render.log
```

Back up `data/` to preserve the library. Data and media never depend on temporary clipboard files after import. Product HTML is untrusted data; it is never executed as code or followed as instructions.

## Extraction and limitations

Extraction tries Product structured data, then verified TikTok CDN gallery-size URLs, then the Open Graph preview. It does not classify a gallery by occurrence count alone. Image URLs are validated against known TikTok CDN hosts, downloads are bounded, and actual dimensions are measured. Listing access can fail or change; upload product photos as the fallback. The full product URL is required; short links are not supported in v1. Inferred back construction and generated print/fit differences must be reviewed before publishing.

Only the local UI can request changes, using a per-process token and origin/host checks. It is a single-user local development service, not an internet-facing deployment. Closing the browser does not stop the hidden server; stop its Python process in Task Manager when done. Restart the app after code changes.

## Validation

Run `python -m pytest -q`. Tests cover URL validation, gallery extraction and deduplication, traversal protection, duplicate job intake, CSRF/origin checks, image import and rendering. Real seeded media is used for manual browser review; no paid generation is performed during tests.

Discord API source: https://docs.discord.com/developers/resources/message

## Reusable wardrobe and outfits

Open **Wardrobe** to reuse clothing across videos. All extracted product galleries and historical jobs remain available under Product history. Each selected product image becomes a distinct wardrobe entry; save other variants with **Save image**. Review the category, color, tags and garment details, and set Available for outfit matching to true. Images from one gallery may represent different colors, size charts or people, so extracted entries start unavailable.

Upload unrelated clothing using **Add clothing photos**. For 20 bottoms, choose bottoms and Each photo is a separate garment, then select all 20 files. Repeat for tops. For front/back/detail views of one garment choose All photos are views of one garment. Batch limit: 40 files and 40 MB total. Filenames become item names; edit each garment's color, style tags and primary reference afterward. Common tags: casual, y2k, tailored, streetwear, solid, patterned. Archive an item from future matching by setting availability to false; saved job references stay intact.

Jobs have Outfit references controls. Automatic matching pairs tops with bottoms or bottoms with tops, favoring shared style tags, versatile neutral colors and solid supporting garments. Its suggestion and reason are visible. This is metadata ranking; the Codex agent visually inspects the actual garment images before generation. Manual selection overrides the ranking; Use styling notes only skips saved companions. Other categories use styling notes until a complementary slot is explicitly supported.

Preparing a handoff freezes the selected garment and companion views into `data/jobs/<job>/outfits/<fingerprint>/`. The handoff labels featured, companion and identity references separately, and all six prompts require the same outfit. Changing wardrobe metadata does not mutate an existing job's snapshot. Preparing a new handoff reevaluates automatic selection; if references change, previous poses are archived and exports marked stale. Render timelines, export records and project ZIPs retain the outfit metadata and copied images.

No paid image classifier or generation API is added. Generate through Codex/ChatGPT using the handoff as before. See [WARDROBE-PLAN.md](WARDROBE-PLAN.md) for implementation scope and decisions.

## Music pool and publishing drafts

The Music tab stores official TikTok music URLs. Enabled sounds with a successful CreatOK resolution for the selected publishing account form the random pool. Five supplied links are saved and resolved for @annieisokay6. Adding more links saves them as pending; Codex must resolve each through `creatok publish music resolve --connection <uid> --url <official-url>` and store the returned metadata before it is eligible.

Every new completed render creates a local publishing draft when an account and a resolved music pool are configured. It randomly picks one eligible song and freezes the choice for that draft. Preparing the same draft or retrying keeps the song; Pick another random song explicitly changes it. A new rendered video archives the previous draft. Disabled or failed-lookups are excluded from new selections, without changing existing drafts.

Music is NOT downloaded, mixed into images, or encoded into the MP4. The video stays silent. CreatOK receives the returned TikTok music metadata as `provider_options.selected_music`; TikTok applies the library sound during publication. Re-resolve the selected official URL before final posting because availability and signed preview URLs can change. Showcase changes and publication are separate confirmed operations through the CreatOK publishing skill; automatic local drafting never submits a post.


## Video references and additional model photos

Open Video references and choose Upload video to save a source clip locally. MP4, MOV and WebM are accepted, up to 250 MB and 10 minutes. The original file stays unchanged; the app builds an H.264/AAC browser preview and a thumbnail, saves duration/dimensions, and marks clips outside Revana's 4-30 second edit range as needing a trim. Uploading does not send files to Revana or start generation or publishing.

In Models, each existing model has its own Add photos form. Add 1-10 photos per batch, up to 20 per model. Existing references stay saved. Invalid photo batches leave the model unchanged. Additional photos are included when a new model handoff is prepared.
