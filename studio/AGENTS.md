# Publishing and queue pause

The user canceled on 2026-11-20 and said: "cancel and dont publish any more videos".

- Do not publish, schedule, retry, or submit TikTok videos, or resume the automated video queue, unless the user explicitly asks to resume after this cancellation.
- The process-product-video-queue schedule has been removed. The active generation job bed5599bfcaa was stopped before image generation; preserve its references and files.
- Do not delete already-published videos. Cider job 1072729 was published before cancellation; do not republish it.
- Read-only status checks and local work specifically requested by the user remain allowed.

# Publishing preferences

- Future captions must contain exactly five hashtags, including #aigc and #tiktokshop. Choose the other three from generic fashion tags; do not use brand or product-specific hashtags.
- Default set: #Fashion #OOTD #OutfitInspo #aigc #tiktokshop.
- On 2026-11-20 the user authorized publishing only the new Wan video for job be6cca9308d9 to @annieisokay6. CreatOK job 1072836 was submitted; check it, never duplicate it. The automated publishing queue remains paused.
