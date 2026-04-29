# LOCAL MACHINE CODE (local_server.py)
from click import clear
from flask import Flask, request, jsonify
import logging
import sys
import time
import tempfile
import os
import subprocess
from textwrap import dedent

sys.path.append(r"<path_to_your_workspace>\AI_Temperature")
base_dir   = r"<path_to_your_workspace>\AI_Temperature\Micro150"
xls_dir = os.path.join(base_dir, "ansys_temp_only")
input_dir= os.path.join(base_dir, "input_temp")
target_dir = os.path.join(base_dir, "target_temp")
csv_file = r"<path_to_your_workspace>\AI_Temperature\results.csv"
os.makedirs(input_dir,  exist_ok=True)
os.makedirs(target_dir, exist_ok=True)
os.makedirs(xls_dir,  exist_ok=True)
#from dataset_gen import *
from ansys_io import *
index=0
# Set up logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("local_server.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

print("Script starting...")
logging.info("Initializing local server")

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    logging.info("Home endpoint accessed")
    return "Local server is running!"

@app.route('/execute_local_function', methods=['POST'])
def execute_local_function():
    # Get data sent from the remote server
    logging.info("Received request at /execute_local_function")
    
    try:
        data = request.json
        logging.info(f"Received power density: {data.get('power_density')}")
        
        # Process file contents to obtain layers
        file_contents = data.get('file_contents', '')
        # Now call your simulation or further processing
        temp_current, stress_current = run_ansys_simulation(file_contents, data.get('power_density'))
        
        results = {
            'temp_current': temp_current,
            'stress_current': stress_current
        }
        
        logging.info(f"Returning results: {results}")
        return jsonify(results)
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return jsonify({
            'temp_current': 1000,
            'stress_current': 2000
        })


def run_ansys_simulation(file_contents, power_density):
    """
    This function calls Ansys to perform thermal simulation.

    Args:
        file_contents (str): The layer data contents.
        power_density: Power density parameter.
        
    Returns:
        tuple: (temp_current, stress_current) calculated values.
    """
    logging.info(f"Running Ansys simulation with power_density: {power_density}")
    
    try:
        # Call the thermal-mechanical function
        temp_current, stress_current = therm_mech(file_contents, power_density)
        return temp_current, stress_current
    except Exception as e:
        logging.error(f"Error running Ansys simulation: {str(e)}")
        # Return default values rather than None to avoid errors in the optimizer
        return 100.0, 200.0


def therm_mech(layer_file, power):
    import pandas as pd
    import math
    import tempfile
    import time
    import ansys.aedt.core
    from IPython.display import Image
    from textwrap import dedent
    import numpy as np

    temp_folder = tempfile.TemporaryDirectory(suffix=".ansys")
    input_file = layer_file
    power_input = power

    # Generate geometry from input file
    chiplets=geometry_from_layers(input_file)
    # Run Ansys thermal mechanical analysis
    ansys_therm_mech()
    temp = np.random.randint(90,100)
    # stress = float(last_row['stress'])
    print("completed thermal mechanical simulation")
    power_list= [150,150,150,150,20,20,20,20]
    if len(power_list) != len(chiplets):
        raise ValueError("power_list length must match number of chiplets")
    for ch, p in zip(chiplets, power_list):
        ch["power"]    = p            # total W
        ch["material"] = "Si"   
    global index, base_dir, xls_dir, input_dir, target_dir
    id=index
    print("id:", id)
    #print("yes line#129", chiplets)
    arch="micro150"
    pd.DataFrame(chiplets).to_csv(os.path.join(input_dir, f"{arch}_{id:05d}_chiplets.csv"), index=False)
    process_ansys_iteration(
        xls_file_path=os.path.join(xls_dir, f"{arch}_34407_{index}_temp.xls"),
        chiplets=chiplets,
        architecture_name=arch,
        sample_id=id,
        interposer_size_mm=50.0,
        input_dir=input_dir,
        target_dir=target_dir
    )
    return temp,400

#     process_ansys_iteration(
#     xls_file_path="multi_gpu_34407_16_temp.xls",
#     chiplets=chiplets,
#     architecture_name="archA",
#     sample_id=16,
#     interposer_size_mm=50.0,
#     input_dir="input",
#     target_dir="target",
#     visualise=True,      # turn off once you’re happy
# )   

def read_layers(file_path):
    """
    Reads a layer definition file with alternating header and geometry lines.
    Each header line has format:
        <index> <LayerName> <thickness_in_meters>
    Followed by geometry lines:
        <element_name> <width_m> <length_m> <offset_x_m> <offset_y_m> [extras...]
    All linear dimensions are converted from meters to mm.
    """
    layers = []
    with open(file_path, 'r') as f:
        lines = f.read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        tokens = line.split()
        if len(tokens) < 3:
            i += 1
            continue
        layer_index = int(tokens[0])
        layer_name = tokens[1]
        thickness_mm = float(tokens[2]) * 1000
        i += 1
        elements = []
        while i < len(lines) and lines[i].strip() and not lines[i].split()[0].isdigit():
            t = lines[i].split()
            if len(t) >= 5:
                elem = {
                    "name": t[0],
                    "width": float(t[1]) * 1000,
                    "length": float(t[2]) * 1000,
                    "offset_x": float(t[3]) * 1000,
                    "offset_y": float(t[4]) * 1000
                }
                if len(t) > 5:
                    elem["extras"] = t[5:]
                elements.append(elem)
            i += 1
        layers.append({
            "index": layer_index,
            "name": layer_name,
            "thickness": thickness_mm,
            "elements": elements
        })
    layers.sort(key=lambda x: x["index"])
    return layers


def read_layers_from_data(file_contents):
    """
    Processes layer definition data from a string containing alternating header and geometry lines.
    Each header line has format:
        <index> <LayerName> <thickness_in_meters>
    Followed by geometry lines:
        <element_name> <width_m> <length_m> <offset_x_m> <offset_y_m> [extras...]
    All linear dimensions are converted from meters to mm.
    
    Args:
        file_contents (str): Contents of the layer definition file.
        
    Returns:
        list: List of layer dictionaries.
    """
    layers = []
    lines = file_contents.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        tokens = line.split()
        if len(tokens) < 3:
            i += 1
            continue
        layer_index = int(tokens[0])
        layer_name = tokens[1]
        thickness_mm = float(tokens[2]) * 1000
        i += 1
        elements = []
        while i < len(lines) and lines[i].strip() and not lines[i].split()[0].isdigit():
            t = lines[i].split()
            if len(t) >= 5:
                elem = {
                    "name": t[0],
                    "width": float(t[1]) * 1000,
                    "length": float(t[2]) * 1000,
                    "offset_x": float(t[3]) * 1000,
                    "offset_y": float(t[4]) * 1000
                }
                if len(t) > 5:
                    elem["extras"] = t[5:]
                elements.append(elem)
            i += 1
        layers.append({
            "index": layer_index,
            "name": layer_name,
            "thickness": thickness_mm,
            "elements": elements
        })
    layers.sort(key=lambda x: x["index"])
    return layers


def within_boundary(center, radius, bounds):
    """
    Checks if a circle with given center=(x,y) and radius
    is inside a rectangular boundary defined by:
      bounds["offset_x"], bounds["offset_y"], bounds["width"], bounds["length"].
    """
    cx, cy = center
    if (cx - radius < bounds["offset_x"] or 
        cx + radius > bounds["offset_x"] + bounds["width"] or
        cy - radius < bounds["offset_y"] or 
        cy + radius > bounds["offset_y"] + bounds["length"]):
        return False
    return True


def linspace(start, end, num):
    """Returns 'num' evenly spaced values between start and end (inclusive)."""
    if num == 1:
        return [start]
    step = (end - start) / float(num - 1)
    return [start + step * i for i in range(num)]


def geometry_from_layers(file_contents):
    from pyaedt import Icepak, Desktop
    import tempfile
    desktop = Desktop(version="2024.1", non_graphical=True, new_desktop=True)
    ipk = Icepak(
        project="PackageBumpProject",
        design="PackageWithBumps",
        solution_type="SteadyState",
        version="2024.1"
    )
    ipk.modeler.model_units = "mm"
    
    # Read layers file from data
    layers = read_layers_from_data(file_contents)
    
    # Variables to help with special logic:
    interposer_bounds = None     # For checking if C4 bumps are inside the interposer
    ubump_thickness = None       # We'll place microbumps after we know chip positions
    ubump_z_start = None
    ubump_radius = None          # Radius derived from the file (but ignoring file offsets)
    chiplets = []                # Store chip bounding boxes to place microbumps beneath them
    
    current_z = 0
    for layer in layers:
        lname = layer["name"]
        thickness = layer["thickness"]
        elements = layer["elements"]
        
        # 4a. Substrate, Interposer, TIM, etc. (boxes)
        if lname not in ["C4Layer", "UbumpLayer", "ChipLayer"]:
            for e in elements:
                if e["name"].startswith("Edge"):
                    continue
                #mat = choose_material(lname)
                ipk.modeler.create_box(
                    origin=[e["offset_x"], e["offset_y"], current_z],
                    sizes=[e["width"], e["length"], thickness],
                    name=e["name"],
                    #material=mat
                )
            if lname == "Interposer":
                for e in elements:
                    if not e["name"].startswith("Edge"):
                        interposer_bounds = {
                            "offset_x": e["offset_x"],
                            "offset_y": e["offset_y"],
                            "width": e["width"],
                            "length": e["length"]
                        }
                        break
            current_z += thickness
            continue
        
        # 4b. C4Layer: create a denser grid of bumps
        if lname == "C4Layer":
            c4_elem = None
            for e in elements:
                if not e["name"].startswith("Edge"):
                    c4_elem = e
                    break
            if not c4_elem:
                current_z += thickness
                continue
            c4_offset_x = c4_elem["offset_x"]
            c4_offset_y = c4_elem["offset_y"]
            c4_w = c4_elem["width"]
            c4_l = c4_elem["length"]
            num_bumps = 8
            c4_bump_height = thickness
            c4_bump_radius = 0.5
            x_positions = linspace(c4_offset_x + c4_bump_radius, c4_offset_x + c4_w - c4_bump_radius, num_bumps)
            y_positions = linspace(c4_offset_y + c4_bump_radius, c4_offset_y + c4_l - c4_bump_radius, num_bumps)
            #mat = choose_material(lname)
            for i, x in enumerate(x_positions):
                for j, y in enumerate(y_positions):
                    if interposer_bounds and not within_boundary([x, y], c4_bump_radius, interposer_bounds):
                        continue
                    bump_name = f"C4Bump_{i}_{j}"
                    origin_z = current_z
                    ipk.modeler.create_cylinder(
                        orientation='Z',
                        origin=[x, y, origin_z],
                        radius=c4_bump_radius,
                        height=c4_bump_height,
                        name=bump_name,
                        #material=mat
                    )
            current_z += thickness
            continue
        
        # 4c. UbumpLayer: record thickness and radius
        if lname == "UbumpLayer":
            ubump_thickness = thickness
            ubump_z_start = current_z
            for e in elements:
                if e["name"].startswith("Edge"):
                    continue
                if "Chiplet" in e["name"]:
                    continue
                r = min(e["width"], e["length"]) / 2.0
                ubump_radius = r
                break
            current_z += thickness
            continue
        
        # 4d. ChipLayer: create boxes for chiplets and record bounding boxes
        if lname == "ChipLayer":
            #mat = choose_material(lname)
            for e in elements:
                if "Chiplet" not in e["name"]:
                    continue
                ipk.modeler.create_box(
                    origin=[e["offset_x"], e["offset_y"], current_z],
                    sizes=[e["width"], e["length"], thickness],
                    name=e["name"],
                    #material=mat
                )
                chiplets.append({
                    "name": e["name"],
                    "x": e["offset_x"],
                    "y": e["offset_y"],
                    "width": e["width"],
                    "length": e["length"]
                })
            current_z += thickness
            continue

    # 5. Create microbumps at corners + center of each chiplet
    if ubump_thickness and ubump_z_start is not None and ubump_radius:
        #mat = "Solder"
        for chip in chiplets:
            corners = [
                (chip["x"], chip["y"]),
                (chip["x"] + chip["width"], chip["y"]),
                (chip["x"] + chip["width"], chip["y"] + chip["length"]),
                (chip["x"], chip["y"] + chip["length"])
            ]
            center_pt = (chip["x"] + chip["width"] / 2.0, chip["y"] + chip["length"] / 2.0)
            positions = corners + [center_pt]
            for i, (px, py) in enumerate(positions):
                bump_name = f"Ubump_{chip['name']}_{i}"
                ipk.modeler.create_cylinder(
                    orientation='Z',
                    origin=[px, py, ubump_z_start],
                    radius=ubump_radius,
                    height=ubump_thickness,
                    name=bump_name,
                    #material=mat
                )
    
    # 6. Place heatsink on top of the TIM
    tim_layer = next((ly for ly in layers if ly["name"] == "TIM"), None)
    if tim_layer and tim_layer["elements"]:
        tim_elem = None
        for e in tim_layer["elements"]:
            if not e["name"].startswith("Edge"):
                tim_elem = e
                break
        if tim_elem:
            tim_top_z = current_z
            hs_base_thick = 2
            hs_fin_height = 8
            hs_total_z = hs_base_thick + hs_fin_height
            hs_center_x = tim_elem["offset_x"]
            hs_center_y = tim_elem["offset_y"]
            hs_center_z = tim_top_z
            heatsink = ipk.create_parametric_fin_heat_sink(
                hs_height=tim_elem["width"],
                hs_width=tim_elem["length"],
                hs_basethick=hs_base_thick,
                draftangle=1.5,
                patternangle=8,
                numcolumn_perside=6,
                pitch=5,
                thick=2,
                length=tim_elem["length"],
                height=hs_fin_height,
                separation=1,
                symmetric=True,
                symmetric_separation=1,
                vertical_separation=1,
                material="Copper",
                center=[hs_center_x, hs_center_y, hs_center_z],
                plane_enum=ipk.PLANE.XY,
                rotation=0,
                tolerance=0.005
            )
    
    import tempfile, os
    step_file = os.path.join(tempfile.gettempdir(), "geometry_export")
    path_ = r"<path_to_your_workspace>\AI_Temperature\Micro150"
    ipk.modeler.export_3d_model(file_name="geometry_export", file_path=path_, file_format=".step", assignment_to_remove=None)
    print(f"Geometry exported to STEP file: {path_}")
    ipk.close_desktop()
    return chiplets


def ansys_therm_mech():
    from ansys.mechanical.core import launch_mechanical, App, find_mechanical, global_variables
    from textwrap import dedent
    mechanical = launch_mechanical(
        exec_file=None,
        batch=True,
        start_instance=True,
        log_mechanical='pymechanical_log.txt',
        verbose_mechanical=False
    )
    #print(mechanical)
    
    # Import Geometry to Ansys Mechanical
    script_GeometryImport = dedent("""\
geomImport = Model.GeometryImportGroup.AddGeometryImport()
geometryPath = r"<path_to_your_workspace>\\AI_Temperature\\Micro150\\geometry_export.step"
geomImport.Import(geometryPath)
""")
    mechanical.run_python_script(script_GeometryImport)
    mechanical.log_message("INFO", "Geometry Import Success")

    
    Material_Assignment_Script = dedent("""\
mat = DataModel.Project.Model.Materials
mat_path = r"<path_to_your_repo>\\data\\Final_Materials.xml"
mat.Import(mat_path)
geometry = ExtAPI.DataModel.Project.Model.Geometry
for part in geometry.Children:
    # Debug print to see the part name
    #ExtAPI.LogMessage("INFO", "Assigning material for: " + part.Name)
    if "Substrate" in part.Name:
        part.Material = "FR-4"
    elif "geometry_export-FreeParts|Ubump_" in part.Name:
        part.Material = "Solder, tin-silver-copper (95.5-3.8-0.7)"
    elif "geometry_export-FreeParts|Chiplet_" in part.Name:
        part.Material = "Silicon Anisotropic"
    elif "Interposer" in part.Name:
        part.Material = "Silicon Anisotropic"
    elif "TIM" in part.Name:
        part.Material = "Indium, pure"
    elif "Heatsink" in part.Name:
        part.Material = "Copper Alloy"
    elif "geometry_export-FreeParts|C4Bump_" in part.Name:
        part.Material = "Solder, tin-lead (60-40)"
""")
    mechanical.run_python_script(Material_Assignment_Script)
    mechanical.log_message("INFO", "Material_Assigned")

    # Generate Mesh
    mesh_prop = dedent("""\
mesh_ = Model.Mesh
mesh_.PhysicsPreference = MeshPhysicsPreferenceType.Electromagnetics
mesh_.ElementOrder = ElementOrder.Quadratic
mesh_.SpanAngleCenter = 1
mesh_.SpanAngleCenter = 0
mesh_.Resolution = 3
mesh_.DisplayStyle = MeshDisplayStyle.ElementQuality
mesh_.GenerateMesh()
""")
    mechanical.run_python_script(mesh_prop)
    mechanical.log_message("INFO", "meshing done")

    thermal_analysis = dedent("""\
S_therm = Model.AddSteadyStateThermalAnalysis()
""")
    thermal_analysis += dedent("""\
S_internal_heat_0 = S_therm.AddInternalHeatGeneration()
S_internal_heat_0.Magnitude.Output.SetDiscreteValue(0, Quantity(1.13468e10, "W m^-1 m^-1 m^-1"))
selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
selection.Ids = [826]
geo_entity = DataModel.GeoData.GeoEntityById(selection.Ids[0])
if geo_entity.Name == r'geometry_export-FreeParts|Chiplet_0':
    S_internal_heat_0.Location = selection
""")
    thermal_analysis += dedent("""\
S_internal_heat_1 = S_therm.AddInternalHeatGeneration()
S_internal_heat_1.Magnitude.Output.SetDiscreteValue(0, Quantity(1.13468e10, "W m^-1 m^-1 m^-1"))
selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
selection.Ids = [853]
geo_entity = DataModel.GeoData.GeoEntityById(selection.Ids[0])
if geo_entity.Name == r'geometry_export-FreeParts|Chiplet_1':
    S_internal_heat_1.Location = selection
""")
    thermal_analysis += dedent("""\
S_internal_heat_2 = S_therm.AddInternalHeatGeneration()
S_internal_heat_2.Magnitude.Output.SetDiscreteValue(0, Quantity(1.13468e10, "W m^-1 m^-1 m^-1"))
selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
selection.Ids = [880]
geo_entity = DataModel.GeoData.GeoEntityById(selection.Ids[0])
if geo_entity.Name == r'geometry_export-FreeParts|Chiplet_2':
    S_internal_heat_2.Location = selection
""")
    thermal_analysis += dedent("""\
S_internal_heat_3 = S_therm.AddInternalHeatGeneration()
S_internal_heat_3.Magnitude.Output.SetDiscreteValue(0, Quantity(1.13468e10, "W m^-1 m^-1 m^-1"))
selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
selection.Ids = [907]
geo_entity = DataModel.GeoData.GeoEntityById(selection.Ids[0])
if geo_entity.Name == r'geometry_export-FreeParts|Chiplet_3':
    S_internal_heat_3.Location = selection
""")
    thermal_analysis += dedent("""\
S_internal_heat_4 = S_therm.AddInternalHeatGeneration()
S_internal_heat_4.Magnitude.Output.SetDiscreteValue(0, Quantity(1.73913e9, "W m^-1 m^-1 m^-1"))
selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
selection.Ids = [934]
geo_entity = DataModel.GeoData.GeoEntityById(selection.Ids[0])
if geo_entity.Name == r'geometry_export-FreeParts|Chiplet_4':
    S_internal_heat_4.Location = selection
""")
    thermal_analysis += dedent("""\
S_internal_heat_5 = S_therm.AddInternalHeatGeneration()
S_internal_heat_5.Magnitude.Output.SetDiscreteValue(0, Quantity(1.73913e9, "W m^-1 m^-1 m^-1"))
selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
selection.Ids = [961]
geo_entity = DataModel.GeoData.GeoEntityById(selection.Ids[0])
if geo_entity.Name == r'geometry_export-FreeParts|Chiplet_5':
    S_internal_heat_5.Location = selection
""")
    thermal_analysis += dedent("""\
S_internal_heat_6 = S_therm.AddInternalHeatGeneration()
S_internal_heat_6.Magnitude.Output.SetDiscreteValue(0, Quantity(1.73913e9, "W m^-1 m^-1 m^-1"))
selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
selection.Ids = [988]
geo_entity = DataModel.GeoData.GeoEntityById(selection.Ids[0])
if geo_entity.Name == r'geometry_export-FreeParts|Chiplet_6':
    S_internal_heat_6.Location = selection
""")
    thermal_analysis += dedent("""\
S_internal_heat_7 = S_therm.AddInternalHeatGeneration()
S_internal_heat_7.Magnitude.Output.SetDiscreteValue(0, Quantity(1.73913e9, "W m^-1 m^-1 m^-1"))
selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
selection.Ids = [1015]
geo_entity = DataModel.GeoData.GeoEntityById(selection.Ids[0])
if geo_entity.Name == r'geometry_export-FreeParts|Chiplet_7':
    S_internal_heat_7.Location = selection
""")

    mechanical.run_python_script(thermal_analysis)
    
    thermal_analysis = dedent("""\
convection_ = S_therm.AddConvection()
convection_.FilmCoefficient.Output.SetDiscreteValue(0, Quantity(800, "W m^-1 m^-1 C^-1"))
selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
selection.Ids = [2183]
convection_.Location = selection
Model.Analyses[0].Solution.AddTemperature()
S_therm.Solve()
""")
    mechanical.run_python_script(thermal_analysis)


    mechanical.log_message("INFO", "thermal_done")
    arch="micro150" 
    global index,xls_dir
    index+=1
    txt_path_temp = os.path.join(xls_dir, f"{arch}_34407_{index}_temp.xls")
    #text_path_stress = os.path.join(xls_dir, f"{arch}_34407_{index}_stress.xls")
    global csv_file
    export_script = dedent(fr"""
import os, re
Model.Analyses[0].Solution.Children[1].ExportToTextFile(r"{txt_path_temp}")
""")
    mechanical.run_python_script(export_script)

    mechanical.exit()


if __name__ == '__main__':
    port = 8080  # Use 8080 on local machine since we're forwarding to 5000 on remote
    print(f"Starting Flask server on port {port}...")
    logging.info(f"Starting Flask server on port {port}")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port)
    
    # This code won't be reached until the server stops
    print("Server has stopped.")