import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Material

// A section's title in a grid of label and field columns
Label {
    Layout.columnSpan: 2
    Layout.topMargin: 16
    color: Material.accent
    font.weight: Font.DemiBold
}
