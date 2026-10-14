import QtQuick
import QtQuick.Controls.Material as Controls

// Material's CheckBox, with the pointer over it like the pictures' buttons have, see MainWindow
Controls.CheckBox {
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
