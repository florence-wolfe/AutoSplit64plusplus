import QtQuick
import QtQuick.Shapes

// A five-pointed star in `color`, in a square of `size`
Item {
    id: root
    property color color
    property real size: 12
    width: size
    height: size

    Shape {
        width: 24
        height: 24
        scale: root.size / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: root.color
            strokeColor: "transparent"
            PathSvg { path: "M 12 2.5 l 2.9 6.1 l 6.6 0.8 l -4.9 4.6 l 1.3 6.6 L 12 17.3 l -5.9 3.3 l 1.3 -6.6 L 2.5 9.4 l 6.6 -0.8 z" }
        }
    }
}
