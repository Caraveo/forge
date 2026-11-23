import QtQuick

Item {
    id: root
    property QtObject forgeTheme
    property var entry

    implicitHeight: note.height + 6
    width: parent ? parent.width : 0

    Text {
        id: note
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.top: parent.top
        width: Math.min(560, implicitWidth)
        text: root.entry ? root.entry.text : ""
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
        horizontalAlignment: Text.AlignRight
        color: root.forgeTheme.muted
        font.pixelSize: 12
    }
}
