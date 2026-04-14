import os
from VeraGrid.Gui.Main.VeraGridMain import VeraGridMainGUI, QApplication
from VeraGrid.Gui.Diagrams.MapWidget.map_widget import MapWidget
from VeraGrid.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget, generate_map_diagram2
from VeraGrid.Gui.Diagrams.MapWidget.Tiles.TileProviders.cartodb import CartoDbTiles
from VeraGridEngine.IO.file_system import tiles_path
import VeraGridEngine as vg


def check1():
    """
    Check standalone coordinate conversion
    :return:
    """
    app = QApplication()

    gui = VeraGridMainGUI()

    editor = GridMapWidget(
        gui=gui,
        tile_src=CartoDbTiles(
            name='Open Street Map',
            tiles_dir=os.path.join(tiles_path(), 'osm'),
            tile_servers=["https://tile.openstreetmap.org"],
            max_zoom=21
        ),
        start_level=10,
        longitude=-4.0,
        latitude=40.0,
        name="",
        diagram=None
    )

    print()

    lat = 40.1234
    lon = -4.5678

    x, y = editor.to_x_y(lat=lat, lon=lon)
    lat2, lon2 = editor.to_lat_lon(x=x, y=y)

    print(f"LAT: {lat}, new {lat2}")
    print(f"LON: {lon}, new {lon2}")

    assert (lat2 - lat) < 1e-8
    assert (lon2 - lon) < 1e-8

    # Simulate mouse wheel out
    for i in range(5):
        editor.zoom_out()

    # simulate mouse wheel in
    for i in range(5):
        editor.zoom_in()

    lat2, lon2 = editor.to_lat_lon(x=x, y=y)

    print(f"LAT: {lat}, new {lat2}")
    print(f"LON: {lon}, new {lon2}")

    assert (lat2 - lat) < 1e-8
    assert (lon2 - lon) < 1e-8


def check2():
    """
    Check substation coordinate conversion
    :return:
    """
    app = QApplication()

    gui = VeraGridMainGUI()

    se = vg.Substation(latitude=40.1234, longitude=-4.5678)
    gui.circuit.add_substation(obj=se)

    diagram = generate_map_diagram2(gui.circuit)

    editor = GridMapWidget(
        gui=gui,
        tile_src=CartoDbTiles(
            name='Open Street Map',
            tiles_dir=os.path.join(tiles_path(), 'osm'),
            tile_servers=["https://tile.openstreetmap.org"],
            max_zoom=21
        ),
        start_level=10,
        longitude=-4.0,
        latitude=40.0,
        name="",
        diagram=None
    )

    print()


def check3():
    """
    Check substation coordinate conversion
    :return:
    """
    app = QApplication()

    gui = VeraGridMainGUI()

    se = vg.Substation(latitude=40.1234, longitude=-4.5678)
    gui.circuit.add_substation(obj=se)

    gui.circuit = vg.open_file("Hawaii40.gridcal")

    diagram = generate_map_diagram2(gui.circuit)

    editor = GridMapWidget(
        gui=gui,
        tile_src=CartoDbTiles(
            name='Open Street Map',
            tiles_dir=os.path.join(tiles_path(), 'osm'),
            tile_servers=["https://tile.openstreetmap.org"],
            max_zoom=21
        ),
        start_level=10,
        longitude=-4.0,
        latitude=40.0,
        name="",
        diagram=diagram
    )

    se_graphics_dict = editor.graphics_manager.get_device_type_dict(device_type=vg.DeviceType.SubstationDevice)

    _, se_graphic = list(se_graphics_dict.items())[0]
    se_graphic.setSelected(True)

    # True coordinates
    lat = se_graphic.api_object.latitude
    lon = se_graphic.api_object.longitude

    editor.consolidate_object_coordinates()

    editor.reset_coordinates()

    lat2 = se_graphic.lat
    lon2 = se_graphic.lon

    print(f"LAT: {lat}, new {lat2}")
    print(f"LON: {lon}, new {lon2}")

    assert (lat2 - lat) < 1e-8
    assert (lon2 - lon) < 1e-8


if __name__ == "__main__":
    check3()
