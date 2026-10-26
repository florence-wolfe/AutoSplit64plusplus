import QtQuick
import QtQuick.Shapes

// A check mark in `color`, in a 16 by 16 square
Item {
    id: root
    property color color
    width: 16
    height: 16

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: "transparent"
            strokeColor: root.color
            strokeWidth: 2
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: "M 3 8.5 L 6.2 11.5 L 13 4.5" }
        }
    }
}
