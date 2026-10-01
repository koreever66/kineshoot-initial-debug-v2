# Player Video Archive

This directory stores the original capture videos for each player.

Use one subdirectory per player:

```text
data/player_videos/001/
data/player_videos/002/
...
data/player_videos/015/
```

Rules:

- Keep the original `.MOV` or `.MP4` files without transcoding or trimming.
- Do not delete old videos when adding new players.
- Keep filenames in capture order.
- New player video directories are local-only by default.
- Do not add, commit, or push new player videos unless the user explicitly approves it.
- Only player `001` is currently archived in GitHub.
- Recommended naming for future exports: `video_001`, `video_002`, ... matching capture order.

## Current Players

| Player | Files | GitHub status | Local source |
| --- | ---: | --- | --- |
| 001 | 12 | uploaded | IMG_7129 through IMG_7140 |
| 002 | 18 | local only | IMG_7154 through IMG_7171 |
| 003 | 18 | local only | IMG_7172 through IMG_7189 |
| 004 | 18 | local only | IMG_7190 through IMG_7207 |
| 005 | 18 | local only | IMG_7261 through IMG_7278 |
| 006 | 18 | local only | IMG_7279 through IMG_7296 |

## Archive Script

Use:

```powershell
tools/archive_player_videos.ps1 -Player 007 -Source "C:\Users\kore\Desktop\007"
```

By default the script only copies video files into the local ignored archive directory. It does not stage, commit, or push anything. Use `-Upload` only after explicit approval.
