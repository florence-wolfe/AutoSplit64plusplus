import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

// The game capture editor's content. `capture` is the Python Capture object (capture_editor_dialog.py): its
// values are what's shown, choose() and set_region() the QML's changes, and its signals the buttons' clicks.
// The capture is image://capture/<version>. The game region is in the capture's pixels, whatever the zoom.
ThemedPane {
    id: root

    SystemPalette { id: system }

    readonly property var region: capture.values.region

    RowLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16

        // Where the capture comes from
        ColumnLayout {
            spacing: 8
            Layout.preferredWidth: 240
            Layout.maximumWidth: 240
            Layout.fillHeight: true

            // On macOS, a video device or a window, each with its own permission
            RowLayout {
                visible: capture.values.mac
                Label { text: "Source"; Layout.preferredWidth: 64 }
                CompactCombo {
                    objectName: "source"
                    model: ["Video Device", "Window"]
                    currentIndex: capture.values.source === "device" ? 0 : 1
                    Layout.fillWidth: true
                    onActivated: capture.choose("source", currentIndex === 0 ? "device" : "window")
                }
            }
            // While the permission for the source is missing
            ColumnLayout {
                objectName: "permission"
                visible: capture.values.mac && capture.values.permissionMissing
                spacing: 4
                Layout.fillWidth: true
                Label {
                    text: capture.values.permissionText
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    Layout.fillWidth: true
                }
                PointerButton { text: capture.values.allowText; highlighted: true; Layout.fillWidth: true; onClicked: capture.allow() }
                PointerButton { text: "Open System Settings"; Layout.fillWidth: true; onClicked: capture.open_settings() }
            }
            // The OBS plugin is only on Windows
            PointerCheckBox {
                objectName: "useObs"
                visible: capture.values.obs
                text: "Use OBS plugin"
                checked: capture.values.useObs
                onToggled: capture.choose("useObs", checked)
            }
            RowLayout {
                visible: !capture.values.useObs && capture.values.source !== "device"
                Label { text: "Process"; Layout.preferredWidth: 64 }
                CompactCombo {
                    objectName: "process"
                    model: capture.values.processes
                    currentIndex: capture.values.process
                    Layout.fillWidth: true
                    onActivated: capture.choose("process", currentIndex)
                }
            }
            RowLayout {
                visible: capture.values.mac && capture.values.source === "device"
                Label { text: "Device"; Layout.preferredWidth: 64 }
                CompactCombo {
                    objectName: "device"
                    model: capture.values.devices
                    currentIndex: capture.values.device
                    Layout.fillWidth: true
                    onActivated: capture.choose("device", currentIndex)
                }
            }
            PointerButton { text: "Capture screen"; Layout.fillWidth: true; Layout.topMargin: 8; onClicked: capture.capture_screen() }
            PointerButton { text: "Auto detect region"; Layout.fillWidth: true; onClicked: capture.auto_detect() }
            PointerCheckBox {
                objectName: "vcFix"
                text: "VC fix (experimental)"
                checked: capture.values.vcFix
                onToggled: capture.choose("vcFix", checked)
            }

            // Zoom out, show the whole capture, zoom in, and the zoom
            RowLayout {
                Layout.topMargin: 8
                spacing: 4
                Label { text: "Zoom"; Layout.preferredWidth: 48 }
                ZoomButton { objectName: "zoomOut"; text: "−"; tip: "Zoom out"; onClicked: preview.zoomBy(1 / preview.step) }
                ZoomButton { objectName: "fit"; text: "Fit"; tip: "Show the whole capture"; onClicked: preview.fit() }
                ZoomButton { objectName: "zoomIn"; text: "+"; tip: "Zoom in"; onClicked: preview.zoomBy(preview.step) }
                Label {
                    objectName: "zoom"
                    text: Math.round(preview.zoom * 100) + "%"
                    horizontalAlignment: Text.AlignRight
                    // Wide enough for any zoom, so the buttons don't move
                    Layout.preferredWidth: 48
                }
            }
            Item { Layout.fillHeight: true }
        }

        // The capture, scrolled and zoomed, with the game region over it
        Rectangle {
            color: system.base
            radius: 4
            clip: true
            Layout.fillWidth: true
            Layout.fillHeight: true

            Flickable {
                id: preview
                objectName: "preview"
                anchors.fill: parent
                boundsBehavior: Flickable.StopAtBounds
                contentWidth: Math.max(width, picture.implicitWidth * zoom)
                contentHeight: Math.max(height, picture.implicitHeight * zoom)
                ScrollBar.horizontal: ScrollBar {}
                ScrollBar.vertical: ScrollBar {}

                readonly property real minimum: 0.1
                readonly property real maximum: 10
                readonly property real step: 1.25
                property real zoom: 1

                // Zooms keeping the capture's point at x, y in the view where it is, the view's center by default
                function zoomBy(factor, x = width / 2, y = height / 2) {
                    const to = Math.min(Math.max(zoom * factor, minimum), maximum)
                    const pointX = (contentX + x) / zoom, pointY = (contentY + y) / zoom
                    zoom = to
                    contentX = Math.max(0, Math.min(pointX * to - x, contentWidth - width))
                    contentY = Math.max(0, Math.min(pointY * to - y, contentHeight - height))
                }

                function fit() {
                    zoom = Math.min(Math.max(Math.min(width / picture.implicitWidth, height / picture.implicitHeight), minimum), maximum)
                    contentX = 0
                    contentY = 0
                }

                Item {
                    id: canvas
                    objectName: "canvas"
                    width: picture.implicitWidth
                    height: picture.implicitHeight
                    scale: preview.zoom
                    transformOrigin: Item.TopLeft

                    Image {
                        id: picture
                        // None until the first capture
                        source: capture.values.preview ? "image://capture/" + capture.values.preview : ""
                        cache: false
                    }

                    Selector {}
                }

                // Ctrl (⌘ on macOS) and scrolling, or pinching on a trackpad, zooms towards the mouse
                WheelHandler {
                    acceptedModifiers: Qt.ControlModifier
                    onWheel: event => preview.zoomBy(event.angleDelta.y > 0 ? preview.step : 1 / preview.step, point.position.x, point.position.y)
                }
                PinchHandler {
                    target: null
                    property real last: 1
                    onActiveChanged: last = 1
                    onActiveScaleChanged: {
                        preview.zoomBy(activeScale / last, centroid.position.x, centroid.position.y)
                        last = activeScale
                    }
                }
            }
        }

        // The game region's numbers, and applying
        ColumnLayout {
            spacing: 8
            Layout.preferredWidth: 200
            Layout.maximumWidth: 200
            Layout.fillHeight: true

            Label { text: "Game region"; font.pixelSize: 18 }
            GridLayout {
                columns: 2
                columnSpacing: 12
                rowSpacing: 8
                Layout.topMargin: 8
                Label { text: "X offset" }
                RegionField { index: 0 }
                Label { text: "Y offset" }
                RegionField { index: 1 }
                Label { text: "Width" }
                RegionField { index: 2 }
                Label { text: "Height" }
                RegionField { index: 3 }
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Item { Layout.fillWidth: true }
                PointerButton { text: "Cancel"; onClicked: capture.cancel() }
                PointerButton { text: "Apply"; highlighted: true; onClicked: capture.apply() }
            }
        }
    }

    // The game region over the capture. Its body moves it and its handles resize it.
    component Selector: Rectangle {
        id: selector
        objectName: "selector"
        x: root.region[0]
        y: root.region[1]
        width: root.region[2]
        height: root.region[3]
        color: Qt.alpha(system.highlight, 0.1)
        border.color: system.dark
        // A pixel on screen, at any zoom
        border.width: 1 / preview.zoom

        RegionDrag { horizontal: 0; vertical: 0; cursor: Qt.SizeAllCursor; anchors.fill: parent; z: -1 }
        Repeater {
            model: [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [-1, 1], [0, 1], [1, 1]]
            RegionDrag {
                required property var modelData
                horizontal: modelData[0]
                vertical: modelData[1]
                cursor: horizontal * vertical > 0 ? Qt.SizeFDiagCursor : horizontal * vertical < 0 ? Qt.SizeBDiagCursor
                      : horizontal ? Qt.SizeHorCursor : Qt.SizeVerCursor
                // 8 pixels on screen, at any zoom, centered on the edge or corner
                width: 8 / preview.zoom
                height: width
                x: (horizontal + 1) / 2 * selector.width - width / 2
                y: (vertical + 1) / 2 * selector.height - height / 2
                Rectangle { anchors.fill: parent; radius: width / 2; color: system.highlight; border.color: system.dark; border.width: 1 / preview.zoom }
            }
        }
    }

    // Dragging moves the region's edges: the left (horizontal -1) or right (1) one, the top (vertical -1) or
    // bottom (1) one, or all of them (0, 0)
    component RegionDrag: Item {
        id: drag
        required property int horizontal
        required property int vertical
        property int cursor
        property var start
        property point from

        HoverHandler { cursorShape: drag.cursor }
        DragHandler {
            target: null
            // Not given up to the view, which pans when dragged elsewhere
            grabPermissions: PointerHandler.CanTakeOverFromAnything
            // The capture's pixel at the mouse, where it is or where it was pressed: dragging starts a few pixels later
            function point(position = centroid.scenePosition) { return canvas.mapFromItem(null, position) }
            onActiveChanged: if (active) { drag.start = root.region.slice(); drag.from = point(centroid.scenePressPosition) }
            onCentroidChanged: {
                if (!active)
                    return
                const to = point(), dx = Math.round(to.x - drag.from.x), dy = Math.round(to.y - drag.from.y)
                let [left, top, width, height] = drag.start
                let right = left + width, bottom = top + height
                if (drag.horizontal === 0 && drag.vertical === 0) {
                    left += dx; right += dx; top += dy; bottom += dy
                }
                if (drag.horizontal < 0) left = Math.min(left + dx, right - 1)
                if (drag.horizontal > 0) right = Math.max(right + dx, left + 1)
                if (drag.vertical < 0) top = Math.min(top + dy, bottom - 1)
                if (drag.vertical > 0) bottom = Math.max(bottom + dy, top + 1)
                capture.set_region(left, top, right - left, bottom - top)
            }
        }
    }

    // One of the game region's numbers, set when it's done being typed
    component RegionField: CompactField {
        property int index
        objectName: "region" + index
        text: root.region[index]
        validator: IntValidator { locale: "C" }
        Layout.preferredWidth: 90
        onEditingFinished: {
            const region = root.region.slice()
            region[index] = Number(text)
            capture.set_region(...region)
        }
    }

    component ZoomButton: CompactButton {
        property string tip
        // In a row, the tooltip above, not left over the button beside it
        property bool tipAbove: true
        implicitWidth: 40
        // Narrow enough for "Fit" and no wider
        leftPadding: 4
        rightPadding: 4
        ToolTip.visible: hovered
        ToolTip.text: tip
    }
}
