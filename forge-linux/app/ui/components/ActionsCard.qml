import QtQuick
import QtQuick.Controls

Item {
    id: root
    property QtObject forgeTheme
    property var entry
    property string entryKey: entry && entry.key ? entry.key : ""

    implicitHeight: column.height + 12
    width: parent ? parent.width : 0

    Column {
        id: column
        anchors.left: parent.left
        anchors.leftMargin: 4
        anchors.top: parent.top
        anchors.topMargin: 4
        spacing: 6

        Text {
            text: root.entry ? root.entry.title : ""
            color: root.forgeTheme.ink
            font.pixelSize: 13
            wrapMode: Text.Wrap
            width: parent.width - 8
        }

        Flow {
            width: parent.width
            spacing: 6

            Repeater {
                model: root.entry && root.entry.buttons ? root.entry.buttons : []

                ActionButton {
                    forgeTheme: root.forgeTheme
                    text: modelData.label
                    onClicked: controller.handleAction(modelData.command, modelData.arg)
                }
            }
        }
    }
}
