import QtQuick
import QtQuick3D
import QtQuick3D.AssetUtils

Item {
    id: root
    property url modelSource
    property real yaw: 0.48
    property real pitch: 0.16
    property real zoomLevel: 1.0
    property vector3d center: Qt.vector3d(0, 0, 0)
    property real radius: 1
    property bool ready: false
    property string errorText: ""
    property point previous

    implicitHeight: 335
    clip: true
    onWidthChanged: Qt.callLater(root.frame)
    onHeightChanged: Qt.callLater(root.frame)
    onModelSourceChanged: {
        root.zoomLevel = 1.0
        Qt.callLater(root.frame)
    }

    Rectangle {
        id: background
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#313B48" }
            GradientStop { position: 1.0; color: "#151B24" }
        }
    }

    View3D {
        id: view
        anchors.fill: parent
        environment: SceneEnvironment {
            clearColor: "transparent"
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
            tonemapMode: SceneEnvironment.TonemapModeAces
        }

        PerspectiveCamera {
            id: camera
            fieldOfView: 48
            clipNear: 0.01
            clipFar: 1000
        }

        Node { id: targetNode }

        Node {
            rotation: camera.rotation

            DirectionalLight {
                eulerRotation: Qt.vector3d(-32, -35, 0)
                color: "#FFF5E9"
                ambientColor: "#484848"
                brightness: 1.65
            }

            DirectionalLight {
                eulerRotation: Qt.vector3d(-12, 55, 0)
                color: "#E0EDFF"
                brightness: 0.75
            }

            DirectionalLight {
                eulerRotation: Qt.vector3d(-28, 145, 0)
                color: "#E8F1FF"
                brightness: 1.1
            }
        }

        RuntimeLoader {
            id: loader
            source: root.modelSource
            onStatusChanged: {
                if (loader.status === RuntimeLoader.Success) {
                    root.ready = true
                    root.errorText = ""
                    Qt.callLater(root.frame)
                } else {
                    root.ready = false
                    root.errorText = loader.status === RuntimeLoader.Error ? loader.errorString : ""
                }
            }
            onBoundsChanged: Qt.callLater(root.frame)
        }
    }

    Text {
        anchors.centerIn: parent
        visible: !root.ready
        text: root.errorText !== "" ? "Preview unavailable. " + root.errorText
                                    : "Loading model…"
        color: "#FFFFFF"
        font.pixelSize: 13
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.OpenHandCursor
        onPressed: function(mouse) {
            root.previous = Qt.point(mouse.x, mouse.y)
            cursorShape = Qt.ClosedHandCursor
        }
        onReleased: cursorShape = Qt.OpenHandCursor
        onPositionChanged: function(mouse) {
            if (!pressed)
                return
            root.yaw -= (mouse.x - root.previous.x) * 0.012
            root.pitch = Math.max(-1.5, Math.min(1.5,
                root.pitch + (mouse.y - root.previous.y) * 0.012))
            root.previous = Qt.point(mouse.x, mouse.y)
            root.frame()
        }
        onWheel: function(wheel) {
            if (wheel.modifiers & Qt.ControlModifier) {
                root.setZoom(wheel.angleDelta.y > 0 ? root.zoomLevel * 0.84
                                                    : root.zoomLevel * 1.19)
                wheel.accepted = true
            }
        }
    }

    function frame() {
        if (!root.ready || width < 4 || height < 4)
            return
        var min = loader.bounds.minimum
        var max = loader.bounds.maximum
        var sx = Math.max(0.001, max.x - min.x)
        var sy = Math.max(0.001, max.y - min.y)
        var sz = Math.max(0.001, max.z - min.z)
        root.center = Qt.vector3d(min.x + sx / 2, min.y + sy / 2, min.z + sz / 2)
        var aspect = Math.max(0.25, width / Math.max(1, height))
        var tan = Math.tan(Math.PI * 24 / 180)
        var cy = Math.cos(root.yaw), sy2 = Math.sin(root.yaw)
        var cp = Math.cos(root.pitch), sp = Math.sin(root.pitch)
        var fx = sy2 * cp, fy = sp, fz = cy * cp
        var rx = cy, ry = 0, rz = -sy2
        var ux = fy * rz - fz * ry
        var uy = fz * rx - fx * rz
        var uz = fx * ry - fy * rx
        root.radius = Math.max(0.001, Math.sqrt(sx * sx + sy * sy + sz * sz) / 2)
        var distance = root.radius
        for (var corner = 0; corner < 8; corner++) {
            var vx = sx * ((corner & 1) - 0.5)
            var vy = sy * (((corner >> 1) & 1) - 0.5)
            var vz = sz * (((corner >> 2) & 1) - 0.5)
            var dotR = vx * rx + vy * ry + vz * rz
            var dotU = vx * ux + vy * uy + vz * uz
            var dotF = vx * fx + vy * fy + vz * fz
            var extent = Math.max(Math.abs(dotR) / aspect, Math.abs(dotU))
            // Leave generous breathing room around unusually wide, tall, or
            // deeply nested imports so the complete asset is visible on load.
            distance = Math.max(distance, dotF + 1.32 * extent / tan)
        }
        var d = distance * root.zoomLevel
        camera.position = Qt.vector3d(root.center.x + fx * d,
                                      root.center.y + fy * d,
                                      root.center.z + fz * d)
        targetNode.position = root.center
        camera.lookAt(targetNode)
        camera.clipNear = root.radius * 0.005
        camera.clipFar = root.radius * 100
    }

    function setZoom(value) {
        // Large imported scenes can require substantially more distance than
        // generated assets; do not trap users against an arbitrary far limit.
        root.zoomLevel = Math.max(0.18, Math.min(25, value))
        root.frame()
    }

    function zoom(factor) {
        setZoom(root.zoomLevel * factor)
    }

    function reset() {
        root.yaw = 0.48
        root.pitch = 0.16
        root.zoomLevel = 1
        root.frame()
    }

}
