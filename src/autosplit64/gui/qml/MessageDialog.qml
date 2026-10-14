import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material as M
import QtQuick.Controls.Universal as U

// A message over the window it's in, with an OK button. The heading is in its content: Dialog's own title
// is in a header whose height loops back through the dialog's once its text wraps.
Dialog {
    id: dialog
    property string heading
    property string text
    anchors.centerIn: parent
    width: parent.width - 96
    modal: true
    standardButtons: Dialog.Ok
    // A popup doesn't take the colors of the item it's in, see ThemedPane
    M.Material.theme: parent.M.Material.theme
    M.Material.accent: parent.M.Material.accent
    M.Material.background: parent.M.Material.background
    M.Material.foreground: parent.M.Material.foreground
    U.Universal.theme: parent.U.Universal.theme
    U.Universal.accent: parent.U.Universal.accent
    U.Universal.background: parent.U.Universal.background
    U.Universal.foreground: parent.U.Universal.foreground
    palette: parent.palette
    // Material's dims the window light for its light theme, and the window's theme doesn't reach it either
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.5) }

    Column {
        width: dialog.width - dialog.leftPadding - dialog.rightPadding
        spacing: 16
        Label { text: dialog.heading; font.pixelSize: 20 }
        Label { width: parent.width; text: dialog.text; wrapMode: Text.Wrap; lineHeight: 1.2 }
    }
}
