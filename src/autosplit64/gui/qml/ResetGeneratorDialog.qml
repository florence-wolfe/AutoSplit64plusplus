import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

// The reset template generator's content. `templates` is the Python Templates object
// (reset_generator_dialog.py): its values are what's shown, and its signals are the buttons' clicks.
ThemedPane {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        // Frames two and three of the logo: the generated frame chosen for each, above the default
        RowLayout {
            spacing: 24
            FrameColumn { column: 0; frame: "two" }
            FrameColumn { column: 1; frame: "three" }
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            PointerButton { text: "Help"; flat: true; onClicked: help.open() }
            Item { Layout.fillWidth: true }
            PointerButton { text: "Cancel"; flat: true; onClicked: templates.cancel() }
            PointerButton {
                objectName: "generate"
                text: templates.values.status
                enabled: !templates.values.busy
                onClicked: templates.generate()
            }
            PointerButton {
                objectName: "apply"
                text: "Apply"
                highlighted: true
                enabled: templates.values.generated
                onClicked: templates.apply()
            }
        }
    }

    MessageDialog {
        id: help
        heading: "Reset templates"
        text: "AutoSplit64's reset feature works based on matching the second and third frame of the Super Mario 64 logo that appears when launching the game.\n\n"
            + "If the colours or capture size of your particular game feed differ from the default standard it may be required to generate custom templates from your game capture.\n\n"
            + "While in-game, press generate, then RESET your console. Ensure the generated images look similar to the examples."
    }

    MessageDialog {
        id: error
        objectName: "error"
        heading: "Error"
    }

    Connections {
        target: templates
        function onFailed(message) {
            error.text = message
            error.open()
        }
    }

    component FrameColumn: ColumnLayout {
        required property int column
        required property string frame
        spacing: 8

        RowLayout {
            Label { text: "Generated frame " + frame; Layout.fillWidth: true }
            CompactSpinBox {
                objectName: "frame" + column
                Layout.preferredWidth: 110
                from: 1
                to: captureCount
                value: templates.values.chosen[column]
                enabled: templates.values.generated
                onValueModified: templates.choose(column, value)
            }
        }
        FrameImage { source: templates.values.shown[column] }
        Label { text: "Desired frame " + frame; Layout.topMargin: 8 }
        FrameImage { source: defaults[column] }
    }

    component FrameImage: Image {
        Layout.preferredWidth: 251
        Layout.preferredHeight: 137
        fillMode: Image.PreserveAspectFit
        // The generated frames are written to the same files each time
        cache: false
    }
}
