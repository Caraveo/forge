import QtQuick

Item {
    id: root
    property string modelPath: ""
    property url fallbackSource

    implicitHeight: 335
    clip: true

    // QtWebEngine is optional in the compact FORGE runtime. The embedded
    // viewport remains interactive on every supported install; the Dimension
    // Studio action opens the full Ubuntu renderer when it is available.
    ModelViewer {
        id: fallback
        anchors.fill: parent
        modelSource: root.fallbackSource
    }

    function zoom(factor) { fallback.zoom(factor) }
    function reset() { fallback.reset() }
}
