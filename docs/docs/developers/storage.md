# Storage File Identity

Storage separates logical media identity from physical placement.

- `files.id` is the stable logical ID for one media artifact.
- `files.camera_identifier`, `files.category`, `files.subcategory`, and
  `files.filename` form the logical key.
- `file_locations` stores physical tier/path rows for a logical file.
- `file_locations.path` is the physical key and may move between tiers without
  changing `files.id`.
- Public file-serving and HLS segment URLs must use `files.id`.
- `files.path`, `files.tier_id`, `files.tier_path`, `files.directory`, and
  `files.size` are compatibility shadow fields maintained from a current
  location. New serving, cleanup, and tier logic should use `file_locations`.

When moving media between tiers, publish the destination as an `available`
`file_locations` row for the existing `files.id`. Delete the source location only
after source cleanup succeeds; if cleanup fails, mark it `pending_delete` so
cleanup can retry without changing the logical ID.
