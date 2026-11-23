import QtQuick

Item {
    id: root
    property QtObject forgeTheme
    property var entry
    property string entryKey: entry && entry.key ? entry.key : ""
    signal saveRequested(string path)

    implicitHeight: column.height + 12
    width: parent ? parent.width : 0

    Column {
        id: column
        anchors.left: parent.left
        anchors.leftMargin: 4
        anchors.top: parent.top
        anchors.topMargin: 4
        width: parent.width - 8
        spacing: 0

        Text {
            visible: root.entry && root.entry.caption && root.entry.caption !== "image"
            text: root.entry ? root.entry.caption : ""
            color: root.forgeTheme.ink
            font.pixelSize: 17
            font.weight: Font.DemiBold
            bottomPadding: 8
        }

        Image {
            id: picture
            width: Math.min(parent.width, 640, 300 * (implicitWidth / Math.max(1, implicitHeight)))
            height: 300
            source: root.entry ? root.entry.url : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            cache: true

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: controller.openPath(root.entry.path)
            }
        }

        Flow {
            width: parent.width
            spacing: 6
            topPadding: 8
            visible: root.entry && root.entry.buttons && root.entry.buttons.length > 0

            Repeater {
                model: root.entry && root.entry.buttons ? root.entry.buttons : []

                ActionButton {
                    forgeTheme: root.forgeTheme
                    text: modelData.label
                    compact: false
                    onClicked: {
                        if (modelData.command === "save")
                            root.saveRequested(modelData.arg)
                        else
                            controller.handleAction(modelData.command, modelData.arg)
                    }
                }
            }
        }
    }
}
