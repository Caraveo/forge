import QtQuick

Item {
    id: root
    property QtObject forgeTheme
    property var entry
    property string entryKey: entry && entry.key ? entry.key : ""

    readonly property bool mine: entry ? entry.kind === "user" : false
    readonly property string jobName: entry && entry.jobName ? entry.jobName : ""
    readonly property bool large: entry ? entry.large === true : false

    function esc(value) {
        return String(value === undefined || value === null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
    }

    readonly property string body: {
        if (!entry)
            return ""
        if (jobName !== "")
            return "<b><font color='" + forgeTheme.accent + "'>" + esc(jobName)
                + "</font></b>&nbsp;&nbsp;&nbsp; " + esc(entry.text)
        return esc(entry.text)
    }

    implicitHeight: bubble.height + 12
    width: parent ? parent.width : 0

    Rectangle {
        id: bubble
        anchors.top: parent.top
        anchors.topMargin: 6
        anchors.left: root.mine ? undefined : parent.left
        anchors.right: root.mine ? parent.right : undefined
        anchors.leftMargin: 4
        anchors.rightMargin: 4
        width: Math.min(640, bodyText.width + 28)
        height: bodyText.height + 19
        radius: 18
        topLeftRadius: 18
        topRightRadius: 18
        bottomLeftRadius: root.mine ? 18 : 6
        bottomRightRadius: root.mine ? 6 : 18
        color: root.mine ? "#13685F" : forgeTheme.card
        border.width: root.mine ? 0 : 1
        border.color: forgeTheme.line

        Text {
            id: bodyText
            anchors.centerIn: parent
            width: Math.min(612, implicitWidth)
            text: root.body
            textFormat: Text.StyledText
            wrapMode: Text.Wrap
            color: root.mine ? "#FFFFFF" : forgeTheme.ink
            font.pixelSize: root.large ? 20 : root.mine ? 15 : 15
            lineHeight: 1.12
        }
    }
}
