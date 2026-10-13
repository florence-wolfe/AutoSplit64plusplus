import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Material

// The Debug window's content. `debug` is the Python Debug object (debug_dialog.py): its values are what's
// shown, its line signal each new event, and its other signals the QML's changes and clicks.
ThemedPane {
    id: root
    // The window is at least this tall, see DebugDialog
    implicitHeight: content.implicitHeight + 32

    readonly property bool running: debug.values.split !== ""

    SystemPalette { id: system }

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 16
        spacing: 8

        // What split detection is doing
        Label { objectName: "status"; text: debug.values.status; font.weight: Font.DemiBold; wrapMode: Text.Wrap; Layout.fillWidth: true }
        Label { objectName: "split"; text: debug.values.split; visible: root.running; wrapMode: Text.Wrap; Layout.fillWidth: true }
        GridLayout {
            objectName: "progress"
            visible: root.running
            columns: 2
            columnSpacing: 12
            rowSpacing: 2
            Layout.fillWidth: true
            Label { text: "Needs"; opacity: 0.7 }
            Explained {
                objectName: "needs"
                text: debug.values.needs
                explanation: "What the current split needs for split detection to split"
            }
            Label { text: "Counted"; opacity: 0.7 }
            Explained {
                objectName: "counted"
                text: debug.values.counted
                explanation: "What split detection counted since the last split or star"
            }
        }

        // What split detection did in this session, like in the log, the latest at the bottom
        Label { text: "Recent events"; opacity: 0.7; Layout.topMargin: 8 }
        Rectangle {
            color: system.base
            radius: 4
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 80
            implicitHeight: 140

            ListView {
                id: events
                objectName: "events"
                anchors.fill: parent
                anchors.margins: 8
                clip: true

                // Following the latest, unless scrolled further up. Kept as the lines and the size change.
                property bool following: true
                property bool positioning: false
                function follow() {
                    if (!following)
                        return
                    positioning = true
                    positionViewAtEnd()
                    positioning = false
                }
                onContentYChanged: if (!positioning) following = atYEnd
                onContentHeightChanged: follow()
                onHeightChanged: follow()
                model: ListModel { id: lines; objectName: "lines" }
                delegate: Label {
                    required property string line
                    text: line
                    width: ListView.view.width
                    wrapMode: Text.Wrap
                    font.pixelSize: 12
                }
                ScrollBar.vertical: ScrollBar {}
            }
        }

        // Everything else split detection sees, collapsed at first
        Button {
            objectName: "advancedButton"
            text: (debug.values.advanced ? "▾  " : "▸  ") + "Advanced"
            flat: true
            leftPadding: 4
            onClicked: debug.advanced_toggled(!debug.values.advanced)
        }
        GridLayout {
            objectName: "advanced"
            visible: debug.values.advanced
            columns: 2
            columnSpacing: 16
            rowSpacing: 8
            Layout.fillWidth: true

            Value { label: "Fade status"; key: "fade_status"; Layout.columnSpan: 2 }
            Value { label: "Fade-out count"; key: "fadeout_count" }
            Value { label: "Fade-in count"; key: "fadein_count" }
            Divider {}
            Value { label: "X-Cam percent"; key: "xcam_percent"; Layout.columnSpan: 2 }
            Value { label: "X-Cam count"; key: "xcam_count" }
            Value { label: "X-Cam status"; key: "xcam_status" }
            Divider {}
            Value { label: "Prediction"; key: "prediction" }
            Value { label: "Probability"; key: "probability" }
            Divider {}
            Value { label: "Execution time"; key: "execution"; Layout.columnSpan: 2 }
            Divider {}

            Label { text: "Update rate"; opacity: 0.7 }
            CompactSpinBox {
                objectName: "updateRate"
                from: 1
                to: 30
                editable: true
                value: debug.values.updateRate
                onValueModified: debug.update_rate_changed(value)
            }
            Label {
                objectName: "updateRateHelp"
                text: "How many times a second this window shows split detection's latest values. Split detection itself isn't affected."
                wrapMode: Text.Wrap
                opacity: 0.7
                font.pixelSize: 12
                Layout.columnSpan: 2
                Layout.fillWidth: true
            }
        }

        // The logs open in the text editor
        GridLayout {
            columns: 2
            columnSpacing: 8
            rowSpacing: 0
            Layout.fillWidth: true
            Layout.topMargin: 8
            Button { objectName: "openLog"; text: "Open log"; flat: true; Layout.fillWidth: true; onClicked: debug.open_log() }
            Button {
                objectName: "openOldLog"
                text: "Open previous log"
                flat: true
                enabled: debug.values.oldLog
                Layout.fillWidth: true
                onClicked: debug.open_old_log()
            }
            Button {
                objectName: "saveInfo"
                // The logs, settings, route and a captured frame in one file, for a bug report
                text: "Save debug info"
                highlighted: true
                Layout.columnSpan: 2
                Layout.fillWidth: true
                onClicked: debug.save_info()
            }
        }
    }

    function add(line) {
        lines.append({ line: line })
        if (lines.count > maxEvents)
            lines.remove(0)
    }

    Component.onCompleted: {
        for (const line of debug.lines)
            lines.append({ line: line })
    }

    Connections {
        target: debug
        function onLine(line) { root.add(line) }
    }

    // A label above an output value
    component Value: ColumnLayout {
        required property string label
        required property string key
        spacing: 0
        // The two columns share the width equally. A layout is only as wide as its items' widest, so they fill too.
        Layout.fillWidth: true
        Layout.preferredWidth: 1
        Label { text: parent.label; opacity: 0.7; font.pixelSize: 12; Layout.fillWidth: true }
        Label { objectName: parent.key; text: debug.values.fields[parent.key] ?? ""; font.pixelSize: 16; Layout.fillWidth: true }
    }

    component Divider: Rectangle {
        implicitHeight: 1
        color: root.Material.dividerColor
        Layout.columnSpan: 2
        Layout.fillWidth: true
    }

    // Text with its explanation shown on hover
    component Explained: Label {
        property string explanation
        wrapMode: Text.Wrap
        Layout.fillWidth: true
        HoverHandler { id: hover }
        ToolTip.visible: hover.hovered
        ToolTip.text: explanation
    }
}
