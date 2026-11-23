import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    property QtObject forgeTheme
    property var entry
    property string entryKey: entry && entry.key ? entry.key : ""
    property var suggestions: entry ? entry.suggestions : []
    property bool done: false

    function choose(name) {
        var cleaned = String(name).trim()
        if (done || !cleaned) {
            if (!cleaned)
                input.forceActiveFocus()
            return
        }
        done = true
        controller.chooseName(cleaned)
    }

    color: forgeTheme.card
    radius: 16
    width: Math.min(640, parent ? parent.width - 8 : 620)
    height: column.height + 18
    border.width: 1
    border.color: forgeTheme.line

    Column {
        id: column
        width: parent.width - 24
        x: 12
        y: 8
        spacing: 8

        Text {
            id: title
            text: "Name this project"
            font.pixelSize: 15
            font.weight: Font.DemiBold
            color: forgeTheme.ink
        }

        Text {
            text: "Pick a suggestion or type your own. Your files are saved under this name."
            font.pixelSize: 12
            color: forgeTheme.muted
            wrapMode: Text.Wrap
            width: parent.width
        }

        Flow {
            width: parent.width
            spacing: 6

            Repeater {
                model: root.suggestions
                ActionButton {
                    forgeTheme: root.forgeTheme
                    text: modelData
                    compact: true
                    enabled: !root.done
                    onClicked: root.choose(modelData)
                }
            }
        }

        Row {
            width: parent.width
            height: 40
            spacing: 6

            Rectangle {
                id: field
                width: parent.width - start.width - 8
                height: 40
                color: forgeTheme.paper
                border.color: input.activeFocus ? forgeTheme.accent : forgeTheme.line
                border.width: 1
                radius: 10

                TextField {
                    id: input
                    anchors.fill: parent
                    anchors.margins: 8
                    placeholderText: "Or type a name"
                    font.pixelSize: 14
                    background: Item {}
                    onAccepted: root.choose(text)
                }
            }

            ActionButton {
                id: start
                forgeTheme: root.forgeTheme
                text: "Start"
                primary: true
                radius: 10
                onClicked: root.choose(input.text)
            }
        }
    }

    Component.onCompleted: input.forceActiveFocus()
}
