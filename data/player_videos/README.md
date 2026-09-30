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
- Add each new player to the table below when archived.
- Recommended naming for future exports: `video_001`, `video_002`, ... matching capture order.

## Current Players

| Player | Files | Original filenames |
| --- | ---: | --- |
| 001 | 12 | IMG_7129 through IMG_7140 |
| 002 | 18 | IMG_7154 through IMG_7171 |
| 003 | 18 | IMG_7172 through IMG_7189 |
| 004 | 18 | IMG_7190 through IMG_7207 |
| 005 | 18 | IMG_7261 through IMG_7278 |
| 006 | 18 | IMG_7279 through IMG_7296 |

## Archive Script

Use:

```powershell
tools/archive_player_videos.ps1 -Player 007 -Source "C:\Users\kore\Desktop\007"
```

The script copies video files into the player directory, stages them, commits, and pushes to the software repository unless `-NoPush` is specified.

