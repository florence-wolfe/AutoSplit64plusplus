import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Material

// The route editor's content. `editor` is the Python Editor object (route_editor_dialog.py), with the route's
// details and the buttons' clicks, and `splits` the Splits model, which the table shows and edits.
ThemedPane {
    id: root

    SystemPalette { id: system }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        RowLayout {
            spacing: 4
            PointerButton { text: "New"; flat: true; onClicked: editor.new() }
            // Or LiveSplit splits (.lss) to convert to a route
            PointerButton { text: "Open"; flat: true; onClicked: editor.open() }
            PointerButton { text: "Save"; flat: true; onClicked: editor.save() }
            PointerButton { text: "Save as…"; flat: true; onClicked: editor.save_as() }
        }

        // The route's details
        GridLayout {
            columns: 4
            columnSpacing: 16
            rowSpacing: 8

            Label { text: "Title" }
            CompactField {
                objectName: "title"
                text: editor.values.title
                Layout.columnSpan: 3
                Layout.fillWidth: true
                onTextEdited: editor.set("title", text)
            }
            Label { text: "Category" }
            CompactCombo {
                objectName: "category"
                editable: true
                model: categories
                // Its text is the category, also one that isn't an item, and none until a route has one
                currentIndex: -1
                editText: editor.values.category
                Layout.preferredWidth: 200
                onEditTextChanged: editor.set("category", editText)
            }
            Label { text: "Initial star" }
            CompactField {
                objectName: "initialStar"
                text: editor.values.initialStar
                validator: IntValidator { locale: "C" }
                Layout.preferredWidth: 80
                onTextEdited: editor.set("initialStar", text)
            }
            Label { text: "Version" }
            CompactCombo {
                objectName: "version"
                model: ["JP", "US"]
                currentIndex: model.indexOf(editor.values.version)
                Layout.preferredWidth: 200
                onActivated: editor.set("version", currentText)
            }
            Label { text: "Timing" }
            CompactCombo {
                objectName: "timing"
                model: timings
                currentIndex: model.indexOf(editor.values.timing)
                Layout.preferredWidth: 200
                onActivated: editor.set("timing", currentText)
            }
        }

        // The splits, with what's done to the selected ones beside them
        RowLayout {
            spacing: 16
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                spacing: 0
                Layout.alignment: Qt.AlignTop
                // Its buttons fill it, which would make it fill the row like the table otherwise
                Layout.fillWidth: false
                PointerButton { text: "Insert above"; flat: true; Layout.fillWidth: true; onClicked: editor.insert_above() }
                PointerButton { text: "Insert below"; flat: true; Layout.fillWidth: true; onClicked: editor.insert_below() }
                PointerButton { text: "Remove"; flat: true; Layout.fillWidth: true; onClicked: editor.remove() }
                PointerButton { text: "Move up"; flat: true; Layout.fillWidth: true; onClicked: editor.move_up() }
                PointerButton { text: "Move down"; flat: true; Layout.fillWidth: true; onClicked: editor.move_down() }
            }

            Rectangle {
                color: system.base
                radius: 4
                Layout.fillWidth: true
                Layout.fillHeight: true

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 4

                    // The columns' titles, as wide as the rows' fields
                    RowLayout {
                        spacing: 8
                        Layout.leftMargin: 8
                        Layout.rightMargin: 8
                        Header { text: "#"; Layout.preferredWidth: 24 }
                        Header { text: "Icon"; Layout.preferredWidth: 32 }
                        Header { text: "Split title"; Layout.fillWidth: true }
                        Header { text: "Stars"; Layout.preferredWidth: 64 }
                        Header { text: "Fadeout"; Layout.preferredWidth: 64 }
                        Header { text: "Fade-in"; Layout.preferredWidth: 64 }
                        Header { text: "X-Cam"; Layout.preferredWidth: 64 }
                        Header { text: "Split type"; Layout.preferredWidth: 120 }
                    }

                    ListView {
                        objectName: "splits"
                        model: splits
                        clip: true
                        spacing: 2
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        ScrollBar.vertical: ScrollBar {}
                        delegate: SplitRow {}
                    }
                }
            }
        }

        RowLayout {
            Item { Layout.fillWidth: true }
            PointerButton { text: "Cancel"; flat: true; onClicked: editor.cancel() }
            PointerButton { text: "Apply"; highlighted: true; onClicked: editor.apply() }
        }
    }

    MessageDialog { id: error; objectName: "error" }

    Connections {
        target: editor
        function onFailed(title, message) {
            error.heading = title
            error.text = message
            error.open()
        }
    }

    component Header: Label {
        opacity: 0.7
        font.pixelSize: 12
    }

    // A split, as wide as the table. Clicking its number selects it: with Ctrl or ⌘ as well, or Shift from the
    // current split. Its counts are "-" and disabled where its split type doesn't use them.
    component SplitRow: Rectangle {
        id: row
        required property int index
        required property string icon_url
        required property string title
        required property string star_count
        required property string fadeout
        required property string fadein
        required property string xcam
        required property string split_type
        required property var unused
        required property bool selected

        width: ListView.view.width
        height: 40
        radius: 4
        color: selected ? Qt.alpha(root.Material.accent, 0.25) : "transparent"

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 8

            Label {
                objectName: "number" + row.index
                text: row.index + 1
                opacity: 0.7
                horizontalAlignment: Text.AlignHCenter
                Layout.preferredWidth: 24
                Layout.fillHeight: true
                verticalAlignment: Text.AlignVCenter
                MouseArea {
                    anchors.fill: parent
                    onClicked: mouse => splits.select(row.index,
                        mouse.modifiers & Qt.ShiftModifier ? "range"
                        : mouse.modifiers & (Qt.ControlModifier | Qt.MetaModifier) ? "toggle" : "only")
                }
            }
            // Choosing another icon
            AbstractButton {
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
                onClicked: splits.click_icon(row.index)
                contentItem: Image { source: row.icon_url; sourceSize.width: 32; sourceSize.height: 32; fillMode: Image.PreserveAspectFit }
                background: Rectangle { color: parent.hovered ? Qt.alpha(root.Material.foreground, 0.1) : "transparent"; radius: 4 }
            }
            CompactField {
                text: row.title
                Layout.fillWidth: true
                onTextEdited: splits.set(row.index, "title", text)
                onActiveFocusChanged: if (activeFocus) splits.select(row.index, "only")
            }
            Count { objectName: "stars" + row.index; rowIndex: row.index; unused: row.unused; key: "star_count"; text: row.star_count }
            Count { rowIndex: row.index; unused: row.unused; key: "fadeout"; text: row.fadeout }
            Count { rowIndex: row.index; unused: row.unused; key: "fadein"; text: row.fadein }
            Count { rowIndex: row.index; unused: row.unused; key: "xcam"; text: row.xcam }
            CompactCombo {
                objectName: "type" + row.index
                model: splitTypes
                currentIndex: splitTypes.indexOf(row.split_type)
                Layout.preferredWidth: 120
                onActivated: splits.set_type(row.index, currentText)
            }
        }
    }

    // A split's count, in its row
    component Count: CompactField {
        required property int rowIndex
        required property var unused
        required property string key
        enabled: !unused.includes(key)
        horizontalAlignment: TextInput.AlignHCenter
        Layout.preferredWidth: 64
        onTextEdited: splits.set(rowIndex, key, text)
        onActiveFocusChanged: if (activeFocus) splits.select(rowIndex, "only")
    }
}
