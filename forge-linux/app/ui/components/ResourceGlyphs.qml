import QtQuick

Item {
    id: root
    property var metrics: ({ vram: 0, ram: 0, gpu: 0, cpu: 0 })
    property color accent: "#80DCCC"
    property color secondary: "#A890CC"
    property color muted: "#63717D"
    implicitWidth: 118
    implicitHeight: 30

    Canvas {
        id: glyphs
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var m = root.metrics || {}
            function clamp(v) { return Math.max(0, Math.min(1, Number(v) || 0)) }
            function arc(cx, cy, radius, from, to, color, width) {
                ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = width
                ctx.arc(cx, cy, radius, from, to); ctx.stroke()
            }
            // Two compact pie slices: free VRAM and free system memory.
            ctx.fillStyle = root.muted; ctx.beginPath(); ctx.arc(15, 15, 12, 0, Math.PI * 2); ctx.fill()
            ctx.fillStyle = root.accent; ctx.beginPath(); ctx.moveTo(15, 15); ctx.arc(15, 15, 12, -Math.PI / 2, -Math.PI / 2 + Math.PI * (1 - clamp(m.vram))); ctx.closePath(); ctx.fill()
            ctx.fillStyle = root.secondary; ctx.beginPath(); ctx.moveTo(15, 15); ctx.arc(15, 15, 8, -Math.PI / 2, -Math.PI / 2 + Math.PI * (1 - clamp(m.ram))); ctx.closePath(); ctx.fill()
            // Clockwise GPU utilisation ring.
            arc(45, 15, 11, -Math.PI / 2, Math.PI * 1.5, root.muted, 4)
            arc(45, 15, 11, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * clamp(m.gpu), root.accent, 4)
            // Memory and CPU bars.
            for (var i = 0; i < 4; i++) { ctx.fillStyle = i < Math.ceil(clamp(m.ram) * 4) ? root.secondary : root.muted; ctx.fillRect(68 + i * 5, 25 - (i + 1) * 4, 3, (i + 1) * 4) }
            for (var j = 0; j < 4; j++) { ctx.fillStyle = j < Math.ceil(clamp(m.cpu) * 4) ? root.accent : root.muted; ctx.fillRect(94 + j * 5, 25 - (j + 1) * 4, 3, (j + 1) * 4) }
        }
        Connections { target: root; function onMetricsChanged() { glyphs.requestPaint() } }
    }
}
