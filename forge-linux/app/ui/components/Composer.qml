import QtQuick
import QtQuick.Controls

Item {
    id: root
    property QtObject forgeTheme
    property string attachmentPath
    property string attachmentName
    property string attachmentTag
    property string attachmentUrl
    property string attachmentKind
    property var attachmentActions
    property string text: input.text

    signal submit(string text)
    signal attachRequested()
    signal clearAttachmentRequested()

    function setText(value) {
        input.text = String(value === undefined || value === null ? "" : value)
    }

    function clear() {
        input.text = ""
    }

    function focusInput() {
        input.forceActiveFocus()
    }

    implicitHeight: card.height
    width: parent ? parent.width : 0

    Rectangle {
        id: card
        anchors.fill: parent
        color: forgeTheme.card
        radius: 24
        border.color: input.activeFocus ? forgeTheme.accent : forgeTheme.line
        border.width: 1
        opacity: 0.98
    }

    Column {
        id: content
        width: parent.width - 12
        x: 6
        y: 6
        spacing: 0

        Flow {
            id: tray
            width: parent.width
            height: attachmentPath === "" ? 0 : 56
            spacing: 8
            visible: attachmentPath !== ""

            AttachmentChip {
                width: 252
                forgeTheme: root.forgeTheme
                name: attachmentName
                tag: attachmentTag
                url: attachmentUrl
                kind: attachmentKind
                path: attachmentPath
                onRemoveRequested: root.clearAttachmentRequested()
            }
        }

        Row {
            id: fieldRow
            width: parent.width
            height: 44
            spacing: 2

            IconButton {
                id: attach
                forgeTheme: root.forgeTheme
                glyph: "+"
                tip: "Attach an image, 3D model or text prompt"
                onClicked: root.attachRequested()
            }

            TextInput {
                id: input
                width: parent.width - 88
                height: 40
                text: root.text
                font.pixelSize: 15
                color: root.forgeTheme.ink
                selectionColor: root.forgeTheme.accent
                padding: 8
                clip: true
                onTextChanged: root.text = input.text
                onAccepted: root.submit(input.text)
                Keys.onPressed: function(event) {
                    if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                            && (event.modifiers & Qt.ShiftModifier)) {
                        input.insert(input.cursorPosition, "\\n")
                        event.accepted = true
                    }
                }
            }

            IconButton {
                id: send
                forgeTheme: root.forgeTheme
                glyph: "➤"
                tip: "Send"
                primary: true
                onClicked: root.submit(input.text)
            }
        }
    }
}
