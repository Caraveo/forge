import QtQuick
import QtQuick.Controls

Item {
    id: root
    property QtObject forgeTheme
    property bool running
    property string logText
    signal setupRequested()

    anchors.fill: parent

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(620, parent.width)
        height: Math.min(520, parent.height)
        color: forgeTheme.card
        radius: 16

        Column {
            id: column
            anchors.fill: parent
            anchors.margins: 28
            spacing: 8

            Text {
                id: title
                text: "FORGE needs its runtime"
                font.pixelSize: 20
                font.weight: Font.DemiBold
                color: forgeTheme.ink
                wrapMode: Text.Wrap
                width: parent.width
            }

            Text {
                text: running ? "Installing the Python, tool and weight runtimes under " +
                               "~/.local/share/FORGE-Data. This downloads a private Python/ROCm " +
                               "environment, TRELLIS, Blender, Real-ESRGAN, UniRig and chat models."
                             : "FORGE is not installed yet. Run the setup command to install its private " +
                               "runtime. This downloads a private Python/ROCm environment, TRELLIS, " +
                               "Blender, Real-ESRGAN, UniRig and chat models under " +
                               "~/.local/share/FORGE-Data. It does not modify system Python or existing " +
                               "AI projects."
                font.pixelSize: 13
                color: forgeTheme.muted
                wrapMode: Text.Wrap
                width: parent.width
            }

            Rectangle {
                id: start
                color: root.forgeTheme ? root.forgeTheme.accent : "#13685F"
                radius: 10
                width: 200
                height: 36
                anchors.left: column.left

                Text {
                    anchors.centerIn: parent
                    text: running ? "Installing…" : "Set up FORGE"
                    color: root.forgeTheme ? root.forgeTheme.onAccent : "#FFFFFF"
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: !root.running
                    onClicked: root.setupRequested()
                }
            }

            Text {
                text: "Setup command: " + controller.setupCommand
                font.pixelSize: 11
                color: forgeTheme.muted
                width: parent.width
                wrapMode: Text.Wrap
            }

            Rectangle {
                id: logArea
                width: parent.width
                height: Math.min(200, column.height - y)
                color: forgeTheme.wash
                border.color: forgeTheme.line
                border.width: 1
                radius: 8
                clip: true

                TextArea {
                    id: log
                    anchors.fill: parent
                    anchors.margins: 8
                    text: root.logText
                    readOnly: true
                    wrapMode: TextArea.NoWrap
                    font.family: "DejaVu Sans Mono"
                    font.pixelSize: 11
                    color: forgeTheme.muted
                    background: Item {}
                    onTextChanged: cursorPosition = text.length
                }
            }
        }
    }
}
