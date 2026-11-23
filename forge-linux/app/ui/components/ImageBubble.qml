import QtQuick

Item {
    id: root
    property QtObject forgeTheme
    property var entry
    property string entryKey: entry && entry.key ? entry.key : ""

    implicitHeight: plate.height + 12
    width: parent ? parent.width : 0

    Rectangle {
        id: plate
        anchors.left: parent.left
        anchors.leftMargin: 4
        anchors.top: parent.top
        anchors.topMargin: 4
        width: picture.width + (root.entry && root.entry.cutout ? 20 : 0)
        height: picture.height + (root.entry && root.entry.cutout ? 20 : 0)
        radius: 12
        color: root.entry && root.entry.cutout ? "#1E252C" : "transparent"
        clip: true

        Image {
            id: picture
            anchors.centerIn: parent
            width: Math.min(560, 220 * (implicitWidth / Math.max(1, implicitHeight)))
            height: 220
            source: root.entry ? root.entry.url : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            cache: true
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: controller.openPath(root.entry.path)
        }
    }
}
