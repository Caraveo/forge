import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    property QtObject forgeTheme
    property string text: ""
    property bool primary: false
    property bool compact: false
    property bool danger: false
    property real cornerRadius: compact ? 16 : 10
    signal clicked()

    implicitWidth: label.implicitWidth + (compact ? 24 : 30)
    implicitHeight: label.implicitHeight + (compact ? 10 : 14)
    radius: cornerRadius
    color: !enabled ? forgeTheme.wash
                    : primary ? forgeTheme.accent
                              : hover.hovered ? forgeTheme.washHover : forgeTheme.wash
    opacity: enabled ? 1 : 0.4

    Text {
        id: label
        text: root.text
        anchors.centerIn: parent
        color: root.primary ? forgeTheme.onAccent : root.danger ? forgeTheme.danger : forgeTheme.ink
        font.pixelSize: root.compact ? 12 : 13
        font.weight: Font.Medium
    }

    HoverHandler { id: hover; enabled: root.enabled }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        enabled: root.enabled
        onClicked: root.clicked()
    }
}
