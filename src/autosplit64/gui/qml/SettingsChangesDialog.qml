import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Material

// The settings changes of an update, each checked to apply. `changes` is the Python Changes object
// (settings_changes_dialog.py). As tall as its content, which the dialog sizes itself to.
ThemedPane {
    implicitWidth: 460
    implicitHeight: content.implicitHeight + 48

    ColumnLayout {
        id: content
        x: 24
        y: 24
        width: parent.width - 48
        spacing: 4

        Label {
            text: "This version of AutoSplit64++ changes some settings"
            font.pixelSize: 18
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            Layout.bottomMargin: 8
        }

        Repeater {
            model: changes.items
            // The change and why, wrapped: a check box's own text doesn't wrap, and file paths are long
            delegate: RowLayout {
                required property var modelData
                required property int index
                spacing: 4
                Layout.fillWidth: true
                Layout.bottomMargin: 8

                PointerCheckBox {
                    id: check
                    objectName: "change" + index
                    checked: true
                    Layout.alignment: Qt.AlignTop
                    onCheckedChanged: changes.set_checked(index, checked)
                }
                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true
                    Layout.topMargin: 12
                    Label { text: modelData.text; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    Label { text: modelData.reason; wrapMode: Text.Wrap; opacity: 0.7; Layout.fillWidth: true }
                    TapHandler { onTapped: check.toggle() }
                }
            }
        }

        RowLayout {
            Layout.topMargin: 8
            Item { Layout.fillWidth: true }
            PointerButton { text: "Keep My Settings"; flat: true; onClicked: changes.keep() }
            PointerButton { text: "Apply"; highlighted: true; onClicked: changes.apply() }
        }
    }
}
