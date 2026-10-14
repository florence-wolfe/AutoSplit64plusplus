import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Controls.Material as M

// A section's title in a grid of label and field columns
Label {
    Layout.columnSpan: 2
    Layout.topMargin: 16
    color: M.Material.accent
    font.weight: Font.DemiBold
}
