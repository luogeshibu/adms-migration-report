# Frozen Row Locator (v0.6.8)

## Goal

The review workspaces contain many horizontal columns. When reviewers scroll far to the right, the frozen locator keeps the business row identity visible so values cannot easily be read against the wrong RMU.

## RMU Data Review

The fixed locator shows:

- `No.`
- `RMU`
- `Status` (`Pass`, `1 Issue`, `2 Issues`, `Critical / NAME`)

`Status` uses the same severity engine as the main row and Excel export. The main review grid remains horizontally scrollable.

## Signal Mapping Review

The fixed locator shows:

- `RMU`
- `Type`
- `Review` (`UNREVIEWED`, `REVIEWED`, `NEEDS ACTION`)

## Tracking behavior

- Locator and main grid synchronize vertical scrolling in both directions.
- Hovering either side paints a subtle top/bottom guide across the same visual row.
- The current/active row uses a stronger blue guide.
- Tracking is border-only: business severity colors, FALSE-field colors and review colors are never replaced.
- Clicking a locator row activates the same main-grid row but restores the user's horizontal scroll position.
- Ctrl/Shift multi-range selection remains available in the main grid and is not converted to row selection.

## Implementation

Both views are populated from the exact same filtered `shown` sequence. The locator is presentation-only and does not create a second business data model. This prevents row-order drift after search/filter refreshes.
