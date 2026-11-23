import QtQuick

Item {
    id: root
    property QtObject forgeTheme
    property string path: ""
    property string name: ""
    property string tag: ""
    property string url: ""
    property string kind: ""
    signal removeRequested()

    implicitWidth: 258
    implicitHeight: 56
    width: 258

    Rectangle {
        id: body
        color: forgeTheme.wash
        radius: 12
        anchors.fill: parent
    }

    Row {
        width: parent.width - 12
        height: 40
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: 6

        Rectangle {
            id: thumb
            width: 40
            height: 40
            radius: 8
            clip: true
            color: forgeTheme.accentSoft

            Image {
                visible: root.url !== ""
                source: root.url
                anchors.fill: parent
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
            }

            Text {
                visible: root.url === ""
                text: root.tag
                color: forgeTheme.accent
                font.pixelSize: 13
                font.weight: Font.DemiBold
                anchors.centerIn: parent
            }
        }

        Column {
            width: parent.width - 50
            spacing: 3

            Text {
                id: title
                text: root.name
                font.pixelSize: 13
                font.weight: Font.DemiBold
                color: forgeTheme.ink
                wrapMode: Text.Wrap
                width: parent.width
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            Text {
                text: (root.kind === "3D model" ? "3D model" : "Image") + " · " + root.tag
                font.pixelSize: 12
                color: forgeTheme.muted
                width: parent.width
                elide: Text.ElideRight
            }
        }
    }

    Rectangle {
        id: close
        width: 20
        height: 20
        radius: 10
        color: forgeTheme.danger
        anchors.top: parent.top
        anchors.topMargin: 12
        anchors.right: parent.right
        anchors.rightMargin: 12
        visible: hover.hovered

        Text {
            text: "✕"
            color: forgeTheme.onAccent
            font.pixelSize: 11
            font.weight: Font.Bold
            anchors.centerIn: parent
        }

        MouseArea {
            anchors.fill: parent
            onClicked: root.removeRequested()
        }
    }

    HoverHandler { id: hover }
}
