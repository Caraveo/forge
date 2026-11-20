import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    visible: true
    width: 1180; height: 760
    minimumWidth: 980; minimumHeight: 640
    title: "Model Forge — 3D AI Workbench"
    color: "#101216"

    property int jobNumber: 0
    property string enhancedPrompt: "a small forest cat, stylized low-poly, standing"

    function enhance() {
        if (!enhancedPrompt.includes("3D asset"))
            enhancedPrompt += "; 3D asset, clear silhouette, centered full body, clean topology, PBR-friendly materials, isolated neutral background, ready for Unity"
        addLog("Prompt enhanced with geometry + Unity constraints.")
    }
    function addTip(tip) { enhancedPrompt += ", " + tip; addLog("Tip applied: " + tip) }
    function build() {
        jobNumber++
        queueModel.append({name: "forge_%1".arg(jobNumber.toString().padStart(3, "0")), state: "QUEUED", command: "dimension → image → GLB"})
        addLog("Queued job " + jobNumber + ". Ready for local dimension runner.")
    }

    ListModel { id: queueModel }
    ListModel { id: logModel }
    function addLog(message) { logModel.append({message: "[" + Qt.formatTime(new Date(), "hh:mm:ss") + "] " + message}) }

    header: ToolBar {
        height: 76
        background: Rectangle { color: "#101216" }
        RowLayout { anchors.fill: parent; anchors.leftMargin: 28; anchors.rightMargin: 28; spacing: 14
            Label { text: "MODEL FORGE"; color: "#f3f6fb"; font.pixelSize: 24; font.bold: true }
            Label { text: "AI 3D model workbench"; color: "#8d96a8"; font.pixelSize: 14 }
            Item { Layout.fillWidth: true }
            Label { text: "LOCAL RUNNER  ●"; color: "#65d6a4"; font.pixelSize: 12 }
        }
    }

    RowLayout { anchors.fill: parent; anchors.margins: 28; anchors.topMargin: 94; spacing: 20
        Rectangle { Layout.preferredWidth: 410; Layout.fillHeight: true; radius: 12; color: "#171a20"
            ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 14
                Label { text: "Describe a 3D model"; color: "#f3f6fb"; font.pixelSize: 16; font.bold: true }
                Label { text: "Prompt enhancement stays focused on geometry, materials, pose, scale, and Unity readiness."; color: "#8d96a8"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                TextArea { id: prompt; text: enhancedPrompt; onTextChanged: enhancedPrompt = text; Layout.fillWidth: true; Layout.preferredHeight: 128; wrapMode: TextArea.Wrap; padding: 14; color: "#f3f6fb"; placeholderText: "Describe your model..."; background: Rectangle { radius: 8; color: "#20242c" } }
                RowLayout { Layout.fillWidth: true; spacing: 10
                    Button { text: "Enhance prompt"; onClicked: enhance() }
                    Label { text: "small model • geometry-first"; color: "#8d96a8" }
                }
                Label { text: "Quick tips"; color: "#f3f6fb"; font.pixelSize: 15; font.bold: true; Layout.topMargin: 4 }
                Flow { Layout.fillWidth: true; spacing: 8
                    Repeater { model: ["low-poly silhouette", "neutral T-pose", "separate accessories", "Unity-ready materials", "warm painted colors"]
                        Button { text: modelData; onClicked: addTip(modelData) }
                    }
                }
                RowLayout { spacing: 12; Layout.topMargin: 4
                    Label { text: "Resolution"; color: "#b9c2d2" }
                    ComboBox { model: ["512", "1024", "1536"] }
                    Label { text: "Model"; color: "#b9c2d2"; Layout.leftMargin: 8 }
                    ComboBox { model: ["trellis", "pixal3d"] }
                }
                Item { Layout.fillHeight: true }
                Button { text: "BUILD  3D MODEL"; Layout.fillWidth: true; Layout.preferredHeight: 46; onClicked: build(); background: Rectangle { radius: 8; color: "#6c5edc" } }
            }
        }
        Rectangle { Layout.fillWidth: true; Layout.fillHeight: true; radius: 12; color: "#171a20"
            ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 14
                RowLayout { Layout.fillWidth: true; Label { text: "Workspace"; color: "#f3f6fb"; font.pixelSize: 16; font.bold: true }; Item { Layout.fillWidth: true }; Label { text: queueModel.count ? "Jobs queued" : "Queue is empty"; color: "#8d96a8" } }
                ListView { Layout.fillWidth: true; Layout.preferredHeight: 150; model: queueModel; spacing: 6; clip: true
                    delegate: Rectangle { width: ListView.view.width; height: 34; radius: 6; color: "#20242c"; RowLayout { anchors.fill: parent; anchors.margins: 10; spacing: 12; Label { text: state; color: state === "DONE" ? "#65d6a4" : "#f2c66d"; font.bold: true }; Label { text: name; color: "#e7ebf2" }; Label { text: command; color: "#8d96a8" } } }
                }
                TabBar { id: tabs; Layout.fillWidth: true; TabButton { text: "Result / Preview" }; TabButton { text: "Logs & Debug" } }
                StackLayout { currentIndex: tabs.currentIndex; Layout.fillWidth: true; Layout.fillHeight: true
                    ScrollView { TextArea { readOnly: true; wrapMode: TextArea.Wrap; padding: 16; color: "#b9c2d2"; text: queueModel.count ? "Queued results will appear here after dimension completes.\n\nExpected outputs: IMAGE, GLB/FBX MODEL, and prompt TIPS." : "Your image and 3D model will appear here."; background: Rectangle { color: "#13161b"; radius: 8 } } }
                    ListView { model: logModel; spacing: 4; clip: true; delegate: Label { text: message; color: "#92e6bc"; font.family: "Consolas"; leftPadding: 14; rightPadding: 14 } }
                }
            }
        }
    }
}
