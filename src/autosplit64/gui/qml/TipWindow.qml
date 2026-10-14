import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material as M

// A tooltip that's a window of its own, see tip_window.py: like Material's, in the theme's colors
Rectangle {
    id: root
    property string text

    SystemPalette { id: system }
    M.Material.theme: system.window.hslLightness < 0.5 ? M.Material.Dark : M.Material.Light

    // As wide as the label once it wraps: its implicit width is on one line
    implicitWidth: label.width + 16
    implicitHeight: label.implicitHeight + 10
    radius: 4
    color: M.Material.tooltipColor

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
