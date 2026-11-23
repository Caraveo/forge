import QtQuick

Window {
    id: root
    property string path: ""
    property string caption: ""

    width: 900
    height: 700
    visible: true
    title: root.caption !== "" ? root.caption : "Model preview"

    color: "#161B20"

    DimensionViewer {
        anchors.fill: parent
        modelPath: root.path
        fallbackSource: controller.urlFor(root.path)
    }
}
