# Responsive UI Standard — v0.5.2

The application distinguishes normal operational tables from the engineering DATA grid.

## ResponsiveTable policy

Used by Site Repository, Audit Log and Versions. Compact identity/status columns keep predictable widths; one content-heavy column stretches to consume remaining viewport width. Users may resize interactive columns where appropriate.

## Site Repository

The Sites panel and Source Inventory are separated by a horizontal QSplitter. Default sizing favors the inventory but users can drag the divider. `Detected File` is the stretch column.

## Audit Log

`Reason` is the stretch column. Empty tables render an explanatory empty state.

## Versions

`Description` is the stretch column. Empty tables render an explanatory empty state.

## Comparison DATA grid

Comparison contains 54 columns and a two-row grouped header. It must not use global Stretch because that would make columns unreadable. It retains explicit engineering widths and horizontal per-pixel scrolling.

## v0.6.0 Empty-state layout contract

Empty-state pages use a shared bounded content container. Wrapped explanatory text must receive a real width before Qt calculates height-for-width; do not center wrapped QLabel widgets independently with layout alignment flags. Audit Log and Versions use this shared component. Normal responsive tables use a 40 px minimum header height and 36 px default row height.
