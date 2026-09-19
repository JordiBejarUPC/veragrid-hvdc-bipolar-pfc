import QtQuick

Rectangle {
    property color pointColor
    property color pointBorderColor
    property color pointSelectedColor
    property real pointBorderWidth
    property bool pointSelected

    width: 10
    height: 10
    radius: width / 2
    color: pointSelected ? pointSelectedColor : pointColor
    border.color: pointBorderColor
    border.width: pointBorderWidth
}
