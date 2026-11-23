import QtQuick
import QtQuick.Controls

Item {
    id: root
    property QtObject forgeTheme
    property var entry
    property string entryKey: entry && entry.key ? entry.key : ""

    implicitHeight: surface.height + 8
    width: parent ? parent.width : 0

    Rectangle {
        id: surface
        width: Math.min(parent.width - 8, 620)
        height: column.height + 26
        radius: 14
        color: root.forgeTheme.card
        border.color: root.forgeTheme.line
        border.width: 1

        Column {
            id: column
            x: 14
            y: 13
            width: parent.width - 28
            spacing: 6

            Text {
                text: root.entry ? root.entry.title : ""
                color: root.forgeTheme.ink
                font.pixelSize: 14
                wrapMode: Text.Wrap
                width: parent.width
            }

            Flow {
                width: parent.width
                spacing: 6

                Repeater {
                    model: root.entry && root.entry.buttons ? root.entry.buttons : []

                    ActionButton {
                        forgeTheme: root.forgeTheme
                        text: modelData.label
                        primary: index === 0
                        compact: true
                        onClicked: controller.handleAction(modelData.command, modelData.arg)
                    }
                }
            }
        }
    }
}
