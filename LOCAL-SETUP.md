# Product Video Studio — local installation

Run **Start Product Video Studio.cmd**, then open http://127.0.0.1:8766.
Port 8766 keeps the original studio on 8765 separate. The original installation is unchanged.

## Pages

- `/`: Posewear reference galleries, with the original authors' attribution retained.
- `/video-studio`: the existing studio, including jobs, wardrobe, models, video references and exports.
- `/library`: shared assets and private R2 settings.

Open a reference and click **Use in Video Studio**. Portraits also become model records; clothing becomes wardrobe records. In Shared library choose a job and attach the reference. Preparing a new chat handoff copies references into that job; selected pose references override the corresponding default poses. Generating six images remains a Codex/ChatGPT handoff. Rendering remains local.

## Storage

Dedicated private Cloudflare bucket: `product-video-studio`, account `0ebe9972b1b37d1975a18feb6f790fc0`.
Create R2 S3 credentials scoped to this bucket with object read/write permissions, then enter them in **Shared library → Private Cloudflare R2 settings**. Secrets are saved only in git-ignored `studio/storage-private.json`. They are never returned to the browser. The Cloudflare connector's account authorization does not supply S3 credentials to this local Python process.

After credentials are entered, the app synchronizes every minute; **Sync to R2** runs it immediately. Files are content-addressed and uploads are checked for size and stored SHA256 metadata. The app keeps local originals, with no automatic deletions. Missing cloud assets can be fetched using **Keep offline**. **Load cloud library** imports missing catalog records; database snapshots are saved separately under `backups/studio.sqlite` in R2.

The default local folder is `studio/data`. Set `STUDIO_DATA_DIR` before launch to use another folder; copy the existing data folder there first. Do not point the old and new apps at the same live database. A pre-integration database backup is included in the local data directory.

Gallery metadata is installed locally; gallery previews initially load from the original sources. Selecting a reference saves a full local copy. To download the complete available galleries in advance, run **Download All Gallery Assets.cmd**; this may download several GB. It resumes files already cached and preserves source attribution. Then sync the library to R2. Extra upstream modules without bundled metadata are empty in this build.

Offline use covers downloaded files; downloading new references, R2 sync, product extraction and chat generation need their respective connections. Cloud-only job recovery on a new installation also requires restoring the SQLite backup into a stopped app.

## Validation

`cd studio` then `python -m pytest tests -q`: 43 tests, including frozen references, upload verification and cloud download recovery with a simulated R2 client. No live R2 object roundtrip has been performed without local credentials.

Publishing and automated intake remain paused. This integration does not authorize publishing.

## Full organized gallery transfer

Run `python sync_gallery_assets.py` from the repository folder to download all five gallery collections (originals and thumbnails), then upload and verify them in the private R2 bucket. It resumes existing local files and verifies existing cloud objects before skipping uploads. Local files and object keys share `galleries/<catalog>/<item-id>/original/` and `thumbnail/` paths. Metadata and attribution are stored in `catalogs/` and `attribution/`; transfer and SQLite backups are retained. The latest progress and any source failures are recorded in `studio/data/gallery-transfer.json`.

The app uses `gallery-sources.json` to serve locally cached gallery images directly.
