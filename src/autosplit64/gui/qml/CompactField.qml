import QtQuick
import QtQuick.Controls.Material

// Material sizes its controls for touch, even in its Dense variant. The Compact controls are 32 pixels tall.
TextField {
    implicitHeight: 32
    topPadding: 0
    bottomPadding: 0
    verticalAlignment: TextInput.AlignVCenter
    selectByMouse: true
}
