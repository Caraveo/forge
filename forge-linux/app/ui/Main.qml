import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import FORGE.UI 1.0

Window {
    id: root
    width: 980
    height: 810
    minimumWidth: 720
    minimumHeight: 520
    visible: true
    title: "FORGE v" + controller.version
    color: theme.paper
    readonly property int contentPadding: 24
    property bool buildLogExpanded: false
    property bool forceClose: false
    property bool savingClose: false

    property var messageEntries: ({})
    property var messageItems: ({})
    property var jobItems: ({})

    function scrollChat() {
        chat.contentY = Math.max(0, chat.contentHeight - chat.height)
    }

    function scrollJobs() {
        jobScroller.contentY = Math.max(0, jobScroller.contentHeight - jobScroller.height)
    }

    function ensureWelcome() {
        if (!controller.runtimeReady || messages.count > 0)
            return
        appendEntry({
            kind: "text", key: "welcome", text: "What would you like to build?", large: true
        })
    }

    function appendEntry(entry) {
        messageEntries[entry.key] = entry
        messages.append({ kind: entry.kind, key: entry.key })
        Qt.callLater(root.scrollChat)
    }

    function updateEntry(key, patch) {
        var entry = messageEntries[key]
        if (!entry)
            return
        var updated = Object.assign({}, entry, patch)
        messageEntries[key] = updated
        var item = messageItems[key]
        if (item)
            item.entry = updated
        Qt.callLater(root.scrollChat)
    }

    function removeEntry(key) {
        for (var i = 0; i < messages.count; i++) {
            if (messages.get(i).key === key) {
                messages.remove(i, 1)
                delete messageEntries[key]
                delete messageItems[key]
                Qt.callLater(root.scrollChat)
                return
            }
        }
    }

    function delegateFor(model) {
        if (!model || !model.kind)
            return textComp
        switch (model.kind) {
        case "user":
        case "assistant":
            return textComp
        case "note":
            return noteComp
        case "image":
            return imageComp
        case "model":
            return modelComp
        case "imageResult":
            return imageResultComp
        case "actions":
        case "choices":
            return actionsComp
        case "name":
            return nameComp
        default:
            return textComp
        }
    }

    function requestSave(path) {
        saveDialog.sourcePath = path
        saveDialog.selectedFile = controller.urlFor(path)
        saveDialog.open()
    }

    function onSaveDialogAccepted() {
        controller.saveAsset(saveDialog.sourcePath, saveDialog.selectedFile)
    }

    function requestExpand(path, caption) {
        var component = Qt.createComponent("components/ModelWindow.qml")
        if (component.status === Component.Ready) {
            var win = component.createObject(root, { path: path, caption: caption })
            if (win)
                win.show()
        }
    }

    property QtObject theme: QtObject {
        readonly property bool dark: controller.darkMode
        readonly property color ink: dark ? "#EDF1F5" : "#192838"
        readonly property color paper: dark ? "#161B20" : "#F2F5F8"
        readonly property color card: dark ? "#232B33" : "#FFFFFF"
        readonly property color accent: dark ? "#80DCCC" : "#13685F"
        readonly property color line: dark ? Qt.rgba(1, 1, 1, 0.14)
                                           : Qt.rgba(0.098, 0.157, 0.22, 0.12)
        readonly property color wash: dark ? Qt.rgba(1, 1, 1, 0.08)
                                            : Qt.rgba(0.098, 0.157, 0.22, 0.04)
        readonly property color washHover: dark ? Qt.rgba(1, 1, 1, 0.14)
                                                : Qt.rgba(0.098, 0.157, 0.22, 0.08)
        readonly property color muted: dark ? "#9AA7B4" : "#5E6B78"
        readonly property color onAccent: dark ? "#000000" : "#FFFFFF"
        readonly property color accentSoft: dark ? Qt.rgba(0.502, 0.863, 0.8, 0.15)
                                                 : Qt.rgba(0.075, 0.408, 0.373, 0.1)
        readonly property color danger: "#E5484D"
    }

    Item {
        id: mainPage
        anchors.fill: parent
        anchors.margins: root.contentPadding
        visible: controller.runtimeReady
        z: 1

        ColumnLayout {
            id: layout
            anchors.fill: parent
            spacing: 8

            Item {
                id: header
                Layout.fillWidth: true
                Layout.preferredHeight: root.buildLogExpanded ? 44 : 0
                visible: root.buildLogExpanded

                Text {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "FORGE"
                    font.pixelSize: 24
                    font.weight: Font.DemiBold
                    color: theme.ink
                }

                ResourceGlyphs {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    metrics: controller.resources
                    accent: theme.accent
                    secondary: theme.dark ? "#B7A1FF" : "#7257AA"
                    muted: theme.dark ? "#4A5864" : "#C5CFD7"
                }
            }

            Flickable {
                id: chat
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: chatColumn.width
                contentHeight: chatColumn.height
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                    width: 8
                    visible: messages.count > 0
                    contentItem: Rectangle {
                        implicitWidth: 6
                        anchors.right: parent.right
                        radius: 3
                        color: theme.muted
                        opacity: 0.35
                    }
                }
                onContentHeightChanged: root.scrollChat()

                Column {
                    id: chatColumn
                    width: chat.width
                    spacing: 0

                    Repeater {
                        model: messages
                        Loader {
                            width: chatColumn.width
                            sourceComponent: root.delegateFor(model)
                            onLoaded: {
                                item.forgeTheme = theme
                                item.entry = root.messageEntries[model.key]
                                root.messageItems[model.key] = item
                            }
                        }
                    }
                }
            }

            Column {
                id: footer
                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                spacing: 8

                Flickable {
                    id: jobScroller
                    width: parent.width
                    height: jobs.count > 0 ? Math.min(jobColumn.height, 230, mainPage.height * 0.22) : 0
                    contentHeight: jobColumn.height
                    visible: jobs.count > 0
                    clip: true

                    Column {
                        id: jobColumn
                        width: parent.width
                        spacing: 6

                        Repeater {
                            id: jobs
                            model: jobModel
                            Loader {
                                width: jobColumn.width
                                sourceComponent: jobComp
                                onLoaded: {
                                    if (model.id) {
                                        item.applyJob({
                                            jobId: model.id,
                                            name: model.name,
                                            kind: model.kind,
                                            detail: model.detail,
                                            state: model.state,
                                            progress: model.progress,
                                            indeterminate: model.indeterminate,
                                            done: model.done,
                                            working: model.working,
                                            failed: model.failed,
                                            cancelled: model.cancelled,
                                            recoverable: model.recoverable
                                        })
                                        item.forgeTheme = theme
                                        root.jobItems[model.id] = item
                                    }
                                }
                            }
                        }
                    }
                }

                Flow {
                    width: parent.width
                    height: implicitHeight
                    spacing: 6
                    padding: 6
                    visible: controller.attachmentActions.length > 0

                    Repeater {
                        model: controller.attachmentActions
                        ActionButton {
                            forgeTheme: theme
                            text: modelData.label
                            compact: true
                            onClicked: controller.handleAction(modelData.command, modelData.arg)
                        }
                    }
                }

                Composer {
                    id: composer
                    width: parent.width
                    height: controller.attachmentPath !== "" ? 152 : 128
                    forgeTheme: theme
                    attachmentPath: controller.attachmentPath
                    attachmentName: controller.attachmentName
                    attachmentTag: controller.attachmentTag
                    attachmentUrl: controller.attachmentUrl
                    attachmentKind: controller.attachmentKind
                    onSubmit: function(text) { controller.submit(text) }
                    onAttachRequested: attachDialog.open()
                    onClearAttachmentRequested: controller.clearAttachment()
                }

                Item {
                    id: buildLogWrap
                    width: parent.width
                    height: root.buildLogExpanded ? logToggle.height + buildLogArea.height : 0
                    visible: root.buildLogExpanded

                    Item {
                        id: logToggle
                        width: parent.width
                        height: 34

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.buildLogExpanded = !root.buildLogExpanded
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Build log  (Ctrl + L)"
                            color: theme.muted
                            font.pixelSize: 12
                        }
                    }

                    Rectangle {
                        id: buildLogArea
                        anchors.top: logToggle.bottom
                        visible: root.buildLogExpanded
                        width: parent.width
                        height: root.buildLogExpanded ? 96 : 0
                        color: theme.wash
                        radius: 8
                        clip: true

                        TextArea {
                            id: buildLog
                            anchors.fill: parent
                            anchors.margins: 8
                            text: controller.buildLogText
                            readOnly: true
                            wrapMode: TextArea.NoWrap
                            font.family: "DejaVu Sans Mono"
                            font.pixelSize: 11
                            color: theme.muted
                            background: Item {}
                            onTextChanged: cursorPosition = text.length
                        }
                    }
                }
            }
        }
    }

    Item {
        id: setupPage
        anchors.fill: parent
        anchors.margins: root.contentPadding
        visible: !controller.runtimeReady
        z: 0

        SetupPage {
            anchors.fill: parent
            forgeTheme: theme
            running: controller.setupRunning
            logText: controller.setupLogText
            onSetupRequested: controller.runSetup()
        }
    }

    Connections {
        target: controller
        function onAppendEntry(entry) {
            root.appendEntry(entry)
        }
        function onUpdateEntry(key, patch) {
            root.updateEntry(key, patch)
        }
        function onRemoveEntry(key) {
            root.removeEntry(key)
        }
        function onAppendJob(job) {
            jobModel.append(job)
            Qt.callLater(root.scrollJobs)
        }
        function onUpdateJob(id, patch) {
            var found = -1
            for (var i = 0; i < jobModel.count; i++) {
                if (jobModel.get(i).id === id) {
                    found = i
                    break
                }
            }
            if (found < 0)
                return
            for (var p in patch)
                jobModel.setProperty(found, p, patch[p])
            var item = root.jobItems[id]
            if (item && item.applyPatch)
                item.applyPatch(patch)
        }
        function onRemoveJob(id) {
            for (var i = 0; i < jobModel.count; i++) {
                if (jobModel.get(i).id === id) {
                    jobModel.remove(i, 1)
                    delete root.jobItems[id]
                    return
                }
            }
        }
        function onCloseReady() {
            root.forceClose = true
            root.close()
        }
        function onAttachmentChanged() {}
        function onClearComposer() {
            composer.clear()
        }
        function onSetComposerText(text) {
            composer.setText(text)
        }
        function onFocusComposer() {
            composer.focusInput()
        }
        function onRuntimeReadyChanged() {
            root.ensureWelcome()
        }
    }

    Shortcut {
        sequence: "Ctrl+L"
        onActivated: root.buildLogExpanded = !root.buildLogExpanded
    }

    DropArea {
        anchors.fill: parent
        keys: ["png", "jpg", "jpeg", "webp", "glb", "fbx", "txt"]

        onEntered: {
            if (drop.hasUrls)
                drop.acceptProposedAction()
        }

        onDropped: {
            if (drop.hasUrls) {
                for (var i = 0; i < drop.urls.length; i++)
                    controller.acceptFile(drop.urls[i].toString())
            }
            drop.acceptProposedAction()
        }
    }

    Popup {
        id: closeDialog
        modal: true
        width: 380
        anchors.centerIn: parent
        background: Rectangle {
            color: theme.card
            radius: 16
            border.color: theme.line
            border.width: 1
        }

        contentItem: Column {
            width: parent.width - 32
            x: 16
            y: 20

            Text {
                text: "A build is still running. Save your progress and close FORGE?"
                font.pixelSize: 14
                color: theme.ink
                wrapMode: Text.Wrap
            }

            Row {
                width: parent.width
                height: 40
                spacing: 8

                ActionButton {
                    forgeTheme: theme
                    text: "Keep working"
                    onClicked: closeDialog.close()
                }
                ActionButton {
                    forgeTheme: theme
                    text: "Save & Close"
                    onClicked: {
                        root.savingClose = true
                        closeDialog.close()
                        controller.saveAndClose()
                    }
                }
                ActionButton {
                    forgeTheme: theme
                    text: "Cancel & Close"
                    danger: true
                    onClicked: {
                        root.forceClose = true
                        controller.cancelAndClose()
                        root.close()
                    }
                }
            }
        }
    }

    FileDialog {
        id: attachDialog
        fileMode: FileDialog.OpenFile
        title: "Attach a file"
        nameFilters: [
            "Images, 3D models and text prompts (*.png *.jpg *.jpeg *.webp *.glb *.fbx *.txt)",
            "Images (*.png *.jpg *.jpeg *.webp)",
            "3D models (*.glb *.fbx)",
            "Text prompt (*.txt)"
        ]
        onAccepted: controller.acceptFile(selectedFile)
    }

    FileDialog {
        id: saveDialog
        fileMode: FileDialog.SaveFile
        title: "Save asset"
        property string sourcePath: ""
        onAccepted: root.onSaveDialogAccepted()
    }

    Component { id: textComp; TextBubble { forgeTheme: theme } }
    Component { id: noteComp; NoteLine { forgeTheme: theme } }
    Component { id: imageComp; ImageBubble { forgeTheme: theme } }
    Component {
        id: modelComp
        ModelCard {
            forgeTheme: theme
            onSaveRequested: function(path) { root.requestSave(path) }
            onExpandRequested: function(path, caption) { root.requestExpand(path, caption) }
        }
    }
    Component { id: imageResultComp; ImageResultCard { forgeTheme: theme } }
    Component { id: actionsComp; ActionsCard { forgeTheme: theme } }
    Component { id: nameComp; NameCard { forgeTheme: theme } }
    Component { id: jobComp; JobCard { forgeTheme: theme } }

    ListModel { id: messages }
    ListModel { id: jobModel }

    Component.onCompleted: {
        ensureWelcome()
        composer.focusInput()
    }

    onActiveChanged: {
        if (active)
            composer.focusInput()
    }

    onClosing: function(close) {
        if (!controller.busy || root.forceClose) {
            controller.shutdown()
            return
        }
        close.accepted = false
        if (!root.savingClose)
            closeDialog.open()
    }
}
