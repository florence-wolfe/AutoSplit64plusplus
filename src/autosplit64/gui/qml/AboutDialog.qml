import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Material

// The about window's content. `links` opens links (about_dialog.py), the rest are the app's details.
ThemedPane {
    RowLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 24

        Image {
            source: icon
            sourceSize.width: 150
            sourceSize.height: 150
            Layout.alignment: Qt.AlignVCenter
        }

        ColumnLayout {
            Layout.alignment: Qt.AlignVCenter
            spacing: 4

            Label { text: title; font.pixelSize: 22 }
            Label { text: "Version " + version; opacity: 0.7 }
            Heading { text: "Authors" }
            Label { objectName: "authors"; text: authors; lineHeight: 1.2 }

            RowLayout {
                Layout.topMargin: 16
                spacing: 8
                Button { objectName: "github"; text: "GitHub"; highlighted: true; onClicked: links.open(githubUrl) }
                Button { objectName: "discord"; text: "Discord"; flat: true; onClicked: links.open(discordUrl) }
            }
        }
    }
}
