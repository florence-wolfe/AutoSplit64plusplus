import QtQuick
import QtQuick.Controls.Material

// A tooltip that's a window of its own, see tip_window.py: like Material's, in the theme's colors
Rectangle {
    id: root
    property string text

    SystemPalette { id: system }
    Material.theme: system.window.hslLightness < 0.5 ? Material.Dark : Material.Light

    implicitWidth: label.implicitWidth + 16
    implicitHeight: label.implicitHeight + 10
    radius: 4
    color: Material.tooltipColor

    Label {
        id: label
        x: 8
        y: 5
        text: root.text
        // Long ones wrap
        width: Math.min(implicitWidth, 320)
        wrapMode: Text.Wrap
        color: "white"
    }
}
