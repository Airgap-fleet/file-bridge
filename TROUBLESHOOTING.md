# File Bridge - troubleshooting

## The bridge does not appear in Claude Desktop or Cursor

1. Restart the AI app completely (quit from the system tray, then reopen).
2. Run the configuration check with the same folder the installer used:

   ```powershell
   $env:FILE_BRIDGE_ROOT_PATH = "C:\Path\To\Your\Files"
   & "$env:LOCALAPPDATA\AirgapFleet\file-bridge\bin\file-bridge.cmd" --check
   ```

   `OK: File Bridge … is set up for …` means the bridge itself is fine.
3. Open `%APPDATA%\Claude\claude_desktop_config.json` and check there is a `file-bridge` entry whose `command` points at `file-bridge.cmd`. The installer keeps a backup next to the file (`claude_desktop_config.json.bak-<date>`) every time it changes it.

## "File Bridge cannot start: No folder is configured"

`FILE_BRIDGE_ROOT_PATH` is missing from the connector settings. Re-run the installer with `-RootPath`, or add it to the `env` block of the connector entry.

## "The configured folder is a whole drive or your entire user folder"

Choose a specific folder, such as the matters share. If you really need a whole drive, set `FILE_BRIDGE_ALLOW_BROAD_ROOT=true`.

## "Writing is switched off: the bridge is in read-only mode"

This is the default. To let the AI create and edit files, re-run the installer with `-AllowWrites`, or set `FILE_BRIDGE_READ_ONLY=false` in the connector settings. Previous versions of changed files are kept in `.file-bridge\versions` inside the folder.

## "The file is open in another program or is read-only"

Close the document in Word (or whichever program has it open) and ask again.

## "old_str appears N times but expected_replacements is 1"

The text the AI wanted to change appears more than once. Ask it to include more surrounding text so it matches one place, or to set `expected_replacements` to the number of places it really means to change.

## Search says "ripgrep (rg) not found"

Install ripgrep, for example `winget install BurntSushi.ripgrep.MSVC`, then restart the AI app.

## Search fails with "Search failed: regex parse error"

The search pattern is not a valid regular expression. Ask for a plain-text search (`fixed_strings: true`) instead.

## A file comes back as base64

The file is binary (for example a Word document or a PDF). This bridge reads plain-text formats only.

## Installer stops with "Could not read … because it is not valid JSON"

The existing Claude Desktop or Cursor config file is damaged. The installer leaves it untouched. Fix or remove it, or run the installer with `-SkipClientConfig` and add the entry by hand.

## Getting logs

Logs go to stderr, which Claude Desktop writes to `%APPDATA%\Claude\logs\mcp-server-file-bridge.log`. Set `FILE_BRIDGE_LOG_LEVEL=DEBUG` for more detail. Logs record file paths and actions, never file contents.
