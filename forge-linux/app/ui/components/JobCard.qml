import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property QtObject forgeTheme
    property string jobId
    property string name
    property string kind
    property string detail
    property string state
    property bool recoverable
    property bool done
    property bool working
    property bool failed
    property bool cancelled
    property real progress
    property bool indeterminate

    function applyPatch(patch) {
        for (var key in patch) {
            if (key in root)
                root[key] = patch[key]
        }
    }

    function pillText() {
        return root.state === "Done" ? "Done ✓" : root.state
    }

    function applyJob(job) {
        for (var key in job)
            root[key] = job[key]
    }

    implicitHeight: card.height + progressWrap.height
    width: parent ? parent.width : 0

    Rectangle {
        id: card
        color: root.forgeTheme.card
        border.color: root.forgeTheme.line
        border.width: 1
        radius: 14
        height: 56

        anchors.left: parent.left
        anchors.right: parent.right

        Item {
            id: content
            width: parent.width - 28
            height: 44
            anchors.centerIn: parent

            RowLayout {
                id: layout
                width: parent.width
                height: 44

                Item {
                    Layout.preferredWidth: 200
                    Layout.minimumWidth: 110
                    height: 44

                    Text {
                        text: root.name
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                        color: root.forgeTheme.ink
                        elide: Text.ElideRight
                        width: parent.width
                    }

                    Rectangle {
                        id: pill
                        x: 0
                        y: 16
                        width: 90
                        height: 20
                        radius: 8
                        color: root.working ? root.forgeTheme.accentSoft
                                            : root.failed ? root.forgeTheme.danger
                                                          : root.done ? root.forgeTheme.accent
                                                                      : root.forgeTheme.muted

                        Text {
                            anchors.centerIn: parent
                            text: root.pillText()
                            color: root.working ? root.forgeTheme.accent
                                                : root.failed ? root.forgeTheme.onAccent
                                                              : root.done ? root.forgeTheme.onAccent
                                                                          : root.forgeTheme.muted
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: root.detail
                    font.pixelSize: 12
                    color: root.forgeTheme.muted
                    elide: Text.ElideRight
                    verticalAlignment: Text.AlignVCenter
                }

                ActionButton {
                    forgeTheme: root.forgeTheme
                    visible: root.recoverable && !root.done
                    enabled: root.state !== "Pausing"
                    text: root.state === "Paused" ? "Resume" : root.state === "Pausing" ? "Pausing…" : "Pause"
                    compact: true
                    onClicked: {
                        if (root.state === "Paused")
                            controller.resumeJob(root.jobId)
                        else
                            controller.pauseJob(root.jobId)
                    }
                }

                ActionButton {
                    id: action
                    forgeTheme: root.forgeTheme
                    text: root.done ? "✕" : "Cancel"
                    compact: true
                    danger: root.done
                    onClicked: {
                        if (root.done)
                            controller.dismissJob(root.jobId)
                        else
                            controller.cancelJob(root.jobId)
                    }
                }
            }
        }
    }

    Item {
        id: progressWrap
        width: parent.width - 28
        height: root.working ? 12 : 0
        anchors.left: card.left
        anchors.top: card.bottom
        anchors.leftMargin: 14
        visible: root.working

        Rectangle {
            id: track
            width: parent.width
            height: 3
            radius: 1.5
            color: root.forgeTheme.wash

            Rectangle {
                id: fill
                height: parent.height
                radius: parent.radius
                color: root.forgeTheme.accent
                width: root.indeterminate ? track.width * 0.28
                                           : track.width * Math.max(0, Math.min(1, root.progress / 100))

                NumberAnimation on x {
                    running: root.indeterminate
                    loops: Animation.Infinite
                    from: 0
                    to: track.width - fill.width
                    duration: 1000
                    easing.type: Easing.InOutQuad
                }
            }
        }
    }
}
