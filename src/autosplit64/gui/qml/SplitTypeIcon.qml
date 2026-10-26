import QtQuick
import QtQuick.Shapes

// A glyph for a split's type, in `color`, in a square of `size`: a flag for the final split, a rabbit for Mips, a
// star with an x for X-Cam, a rabbit with an x for Mips-X and a half-filled circle for a fade. None for the others.
Item {
    id: root
    property string type
    property color color
    property real size: 16
    readonly property bool mips: type === "Mips" || type === "Mips-X"
    readonly property bool xmark: type === "X-Cam" || type === "Mips-X"
    width: size
    height: size

    // Drawn in a 24 by 24 square
    Item {
        width: 24
        height: 24
        scale: root.size / 24
        transformOrigin: Item.TopLeft

        StarIcon { visible: root.type === "X-Cam"; size: 19; color: root.color }

        Shape {
            visible: root.mips
            // Smaller where the x takes the corner
            scale: root.xmark ? 0.8 : 1
            transformOrigin: Item.TopLeft
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: root.color
                strokeColor: "transparent"
                // Where its parts overlap, the rabbit is all filled
                fillRule: ShapePath.WindingFill
                // Ears, head, body and tail
                PathSvg { path: "M 14 7.5 C 12.4 4 12.6 1.6 14.2 1.8 C 15.8 2 16.4 4.6 16.2 7.6 Z" }
                PathSvg { path: "M 17.2 7.8 C 17.6 4.4 19 2.4 20.2 3.2 C 21.4 4 20.2 6.6 18.8 8.4 Z" }
                PathSvg { path: "M 12.4 11.4 A 4.2 3.6 0 1 0 20.8 11.4 A 4.2 3.6 0 1 0 12.4 11.4 Z" }
                PathSvg { path: "M 3.6 21 C 2.6 16 6 12.8 10.6 13.2 L 14.6 14 C 17.6 15 18.4 18.4 16.8 21 Z" }
                PathSvg { path: "M 2.2 17 A 1.7 1.7 0 1 0 5.6 17 A 1.7 1.7 0 1 0 2.2 17 Z" }
            }
        }

        Shape {
            visible: root.xmark
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: "transparent"
                strokeColor: root.color
                strokeWidth: 2.4
                capStyle: ShapePath.RoundCap
                PathSvg { path: "M 15.5 15.5 L 22 22 M 22 15.5 L 15.5 22" }
            }
        }

        Shape {
            visible: root.type === "Final"
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: "transparent"
                strokeColor: root.color
                strokeWidth: 2.2
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: "M 5.5 3 L 5.5 21.5 M 5.5 4.5 L 19 4.5 L 15.5 9.5 L 19 14.5 L 5.5 14.5" }
            }
        }

        Shape {
            visible: root.type === "Fade"
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: root.color
                strokeColor: root.color
                strokeWidth: 2
                PathSvg { path: "M 12 3 A 9 9 0 0 0 12 21 Z" }
            }
            ShapePath {
                fillColor: "transparent"
                strokeColor: root.color
                strokeWidth: 2
                PathSvg { path: "M 12 3 A 9 9 0 0 1 12 21 A 9 9 0 0 1 12 3 Z" }
            }
        }
    }
}
