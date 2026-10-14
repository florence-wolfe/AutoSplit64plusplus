import QtQuick
import QtQuick.Controls as Controls

// The style's CheckBox, with the pointer over it like the pictures' buttons have, see MainWindow
Controls.CheckBox {
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
