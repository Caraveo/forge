import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    property QtObject forgeTheme
    property string glyph: ""
    property string tip: ""
    property bool primary: false
    property bool danger: false
    property real size: 38
    signal clicked()

    width: size
    height: size
    radius: size / 2
    color: primary ? forgeTheme.accent
                   : danger ? forgeTheme.wash
                            : hover.hovered ? forgeTheme.washHover : forgeTheme.wash

    Text {
        anchors.centerIn: parent
        text: root.glyph
        color: root.primary ? forgeTheme.onAccent : root.danger ? forgeTheme.danger : forgeTheme.ink
        font.pixelSize: Math.round(root.size * 0.4)
        font.weight: Font.DemiBold
    }

    HoverHandler { id: hover }
    ToolTip.visible: hover.hovered && root.tip !== ""
    ToolTip.text: root.tip
    ToolTip.delay: 500

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
