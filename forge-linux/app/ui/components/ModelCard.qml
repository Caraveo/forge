import QtQuick

Item {
    id: root
    property QtObject forgeTheme
    property var entry
    property string path: root.entry ? root.entry.path : ""
    property string caption: root.entry ? (root.entry.caption === "" ? "Model preview" : root.entry.caption) : ""
    property string folder: root.entry ? root.entry.folder : ""
    property string entryKey: root.entry && root.entry.key ? root.entry.key : ""

    signal saveRequested(string path)
    signal expandRequested(string path, string caption)

    implicitHeight: column.implicitHeight + 32
    width: parent ? parent.width : 0

    property var controls: [
        { label: "🦴 Rig", command: "rig" },
        { label: "Save", command: "save" },
        { label: "Select", command: "select" },
        { label: "Expand", command: "expand" },
        { label: "Zoom out", command: "zoomOut" },
        { label: "Zoom in", command: "zoomIn" },
        { label: "Reset", command: "reset" }
    ]

    property var allControls: root.folder !== ""
        ? root.controls.concat([{ label: "📁 Open folder", command: "open" }])
        : root.controls

    Rectangle {
        id: card
        color: forgeTheme.card
        radius: 12
        anchors.fill: parent
    }

    Column {
        id: column
        x: 16
        y: 16
        width: parent.width - 32
        spacing: 8

        Text {
            id: title
            text: root.caption
            font.pixelSize: 17
            font.weight: Font.DemiBold
            color: root.forgeTheme.ink
            width: parent.width
            elide: Text.ElideRight
            wrapMode: Text.NoWrap
        }

        ModelViewer {
            id: viewer
            width: parent.width
            height: 335
            modelSource: root.entry ? root.entry.url : ""
        }

        Flow {
            width: parent.width
            spacing: 6

            Repeater {
                model: root.allControls
                ActionButton {
                    forgeTheme: root.forgeTheme
                    text: modelData.label
                    onClicked: root.onAction(modelData.command)
                }
            }
        }
    }

    function onAction(command) {
        if (command === "rig")
            controller.handleAction("rig", root.path)
        else if (command === "save")
            root.saveRequested(root.path)
        else if (command === "select")
            controller.handleAction("select", root.path)
        else if (command === "expand")
            root.expandRequested(root.path, root.caption)
        else if (command === "zoomOut")
            viewer.zoom(1.2)
        else if (command === "zoomIn")
            viewer.zoom(0.83)
        else if (command === "reset")
            viewer.reset()
        else if (command === "open")
            controller.handleAction("open", root.folder)
    }
}
