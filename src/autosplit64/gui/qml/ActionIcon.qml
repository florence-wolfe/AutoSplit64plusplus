import QtQuick
import QtQuick.Shapes

// A glyph for a button, in `color`, in a square of `size`: "play", "stop" or "restart"
Item {
    id: root
    property string name
    property color color
    property real size: 18
    width: size
    height: size

    // Drawn in a 24 by 24 square
    Item {
        width: 24
        height: 24
        scale: root.size / 24
        transformOrigin: Item.TopLeft

        // Filled, with round corners from a stroke of its own color
        Shape {
            visible: root.name === "play" || root.name === "stop"
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: root.color
                strokeColor: root.color
                strokeWidth: 3
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: root.name === "play" ? "M 7.5 5.5 L 18.5 12 L 7.5 18.5 Z" : "M 7 7 L 17 7 L 17 17 L 7 17 Z" }
            }
        }

        Shape {
            visible: root.name === "restart"
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: "transparent"
                strokeColor: root.color
                strokeWidth: 2.2
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                // An arc almost all the way round, with an arrow head at its end
                PathSvg { path: "M 19 12 A 7 7 0 1 1 16.6 6.7 M 19.5 3.8 L 19.5 8.6 L 14.7 8.6" }
            }
        }
    }
}
