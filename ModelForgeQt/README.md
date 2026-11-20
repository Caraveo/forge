# Model Forge Qt Design Studio project

Open `ModelForge.qmlproject` in Qt Design Studio or Qt Creator.

The layout uses Qt Quick anchors, `RowLayout`/`ColumnLayout` spacing, explicit margins, reusable panel styling, and a tabbed result/log surface. The current QML provides a working interaction prototype; the next native Qt integration point is a `QProcess` backend that invokes `dimension` with the selected prompt, model, resolution, and output folder.
