#define main function
def therm_mech(layer_file, power):
    import pandas as pd
    import math
    import tempfile
    import time
    import ansys.aedt.core
    import pandas as pd
    from IPython.display import Image
    temp_folder = tempfile.TemporaryDirectory(suffix=".ansys")
    input_file = layer_file
    power_input = power
    #generate geometry from input file
    geometry_from_layers(input_file)
    #run ansys thermal mechanical analysis
    ansys_therm_mech()
    csv_file = "C:\\Users\\<your_username>\\Documents\\PhD_Chiplets\\scripting_files\\results_test1.csv"
    # Read the CSV file into a DataFrame
    df = pd.read_csv(csv_file)
    # read the last row of the dataframe
    last_row = df.iloc[-1]
    # print the last row
    print(last_row)
    # extract the temp and stress values from the last row
    temp = last_row['temp']
    stress = last_row['stress']
    # print the temp and stress values
    print(temp)
    print(stress)
    return temp, stress



# -----------------------------------------------------------------------------
# 1. File parsing
# -----------------------------------------------------------------------------
def read_layers(file_contents):
    """
    Reads a layer definition from file contents with alternating header and geometry lines.
    Each header line has format:
        <index> <LayerName> <thickness_in_meters>
    Followed by geometry lines:
        <element_name> <width_m> <length_m> <offset_x_m> <offset_y_m> [extras...]
    All linear dimensions are converted from meters to mm.
    
    Args:
        file_contents: String containing the contents of the layer file
        
    Returns:
        list: List of layer dictionaries
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

# -----------------------------------------------------------------------------
# 2. Helper functions
# -----------------------------------------------------------------------------
def choose_material(layer_name):
    """
    Maps layer names to material names (simple version).
    """
    if layer_name == "Substrate":
        return "FR4_epoxy"
    elif layer_name == "Interposer":
        return "Silicon"
    elif layer_name in ["C4Layer", "UbumpLayer"]:
        return "Solder"
    elif layer_name == "ChipLayer":
        return "Silicon"
    elif layer_name == "TIM":
        return "Solder"
    else:
        return "DefaultMaterial"

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

# -----------------------------------------------------------------------------
# 3. Initialize the Icepak project
# -----------------------------------------------------------------------------
def geometry_from_layers(layers_file):
    import os
    import tempfile
    from pyaedt import Icepak, Desktop
    desktop = Desktop(version="2024.1", non_graphical=False, new_desktop=True)
    ipk = Icepak(
        project="PackageBumpProject",
        design="PackageWithBumps",
        solution_type="SteadyState",
        version="2024.1"
    )
    ipk.modeler.model_units = "mm"

    # -----------------------------------------------------------------------------
    # 4. Read layers file
    # -----------------------------------------------------------------------------
    layers = read_layers(layers_file)

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

        # --------------------------------------------------
        # 4a. Substrate, Interposer, TIM, etc. (boxes)
        # --------------------------------------------------
        if lname not in ["C4Layer", "UbumpLayer", "ChipLayer"]:
            # For these layers (e.g. Substrate, Interposer, TIM):
            # create boxes for each non-edge element
            for e in elements:
                if e["name"].startswith("Edge"):
                    continue  # ignore edges
                mat = choose_material(lname)
                ipk.modeler.create_box(
                    origin=[e["offset_x"], e["offset_y"], current_z],
                    sizes=[e["width"], e["length"], thickness],
                    name=e["name"],
                    material=mat
                )
            # Record interposer bounds for C4 bump checks
            if lname == "Interposer":
                # Assume the first non-edge polygon is the main interposer bounding box
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

        # --------------------------------------------------
        # 4b. C4Layer: create a denser grid of bumps
        # --------------------------------------------------
        if lname == "C4Layer":
            # We assume there's a single bounding box (ignoring edges).
            c4_elem = None
            for e in elements:
                if not e["name"].startswith("Edge"):
                    c4_elem = e
                    break
            if not c4_elem:
                current_z += thickness
                continue
            # We create a NxN grid of bumps within that bounding box
            c4_offset_x = c4_elem["offset_x"]
            c4_offset_y = c4_elem["offset_y"]
            c4_w = c4_elem["width"]
            c4_l = c4_elem["length"]

            # Increase the density from 4×4 to 8×8
            num_bumps = 8

            # Fixed C4 bump dimension (example):
            c4_bump_height = thickness  # or a fraction if you prefer
            c4_bump_radius = 0.5        # you can adjust to typical C4 radius

            # Build the candidate x,y positions
            x_positions = linspace(
                c4_offset_x + c4_bump_radius,
                c4_offset_x + c4_w  - c4_bump_radius,
                num_bumps
            )
            y_positions = linspace(
                c4_offset_y + c4_bump_radius,
                c4_offset_y + c4_l  - c4_bump_radius,
                num_bumps
            )

            mat = choose_material(lname)
            for i, x in enumerate(x_positions):
                for j, y in enumerate(y_positions):
                    # Ensure the entire bump is inside the interposer boundary
                    if interposer_bounds and not within_boundary([x, y], c4_bump_radius, interposer_bounds):
                        continue
                    bump_name = f"C4Bump_{i}_{j}"
                    # Place the bump so its bottom is at current_z
                    # and top is at current_z + c4_bump_height
                    origin_z = current_z
                    ipk.modeler.create_cylinder(
                        orientation='Z',
                        origin=[x, y, origin_z],
                        radius=c4_bump_radius,
                        height=c4_bump_height,
                        name=bump_name,
                        material=mat
                    )
            current_z += thickness
            continue

        # --------------------------------------------------
        # 4c. UbumpLayer: just record thickness and radius
        #     but do NOT create geometry from the file
        # --------------------------------------------------
        if lname == "UbumpLayer":
            ubump_thickness = thickness
            ubump_z_start   = current_z

            # Use the first non-edge, non-chiplet polygon to get the radius
            # (assuming all microbumps have the same dimension).
            for e in elements:
                if e["name"].startswith("Edge"):
                    continue
                if "Chiplet" in e["name"]:
                    continue
                # Inscribed circle radius
                r = min(e["width"], e["length"]) / 2.0
                ubump_radius = r
                break

            # Skip geometry creation for now
            current_z += thickness
            continue

        # --------------------------------------------------
        # 4d. ChipLayer: create boxes for chiplets, record them for microbumps
        # --------------------------------------------------
        if lname == "ChipLayer":
            mat = choose_material(lname)
            for e in elements:
                if "Chiplet" not in e["name"]:
                    continue
                # Create the chip
                ipk.modeler.create_box(
                    origin=[e["offset_x"], e["offset_y"], current_z],
                    sizes=[e["width"], e["length"], thickness],
                    name=e["name"],
                    material=mat
                )
                # Record chip bounding box so we can place microbumps
                chiplets.append({
                    "name": e["name"],
                    "x": e["offset_x"],
                    "y": e["offset_y"],
                    "width": e["width"],
                    "length": e["length"]
                })
            current_z += thickness
            continue

    # -----------------------------------------------------------------------------
    # 5. Create microbumps (UbumpLayer) at corners + center of each chiplet
    # -----------------------------------------------------------------------------
    if ubump_thickness and ubump_z_start is not None and ubump_radius:
        mat = "Solder"  # or choose_material("UbumpLayer")
        for chip in chiplets:
            # Four corners + center
            corners = [
                (chip["x"], chip["y"]),
                (chip["x"] + chip["width"], chip["y"]),
                (chip["x"] + chip["width"], chip["y"] + chip["length"]),
                (chip["x"], chip["y"] + chip["length"])
            ]
            center_pt = (
                chip["x"] + chip["width"] / 2.0,
                chip["y"] + chip["length"] / 2.0
            )
            positions = corners + [center_pt]
            for i, (px, py) in enumerate(positions):
                bump_name = f"Ubump_{chip['name']}_{i}"
                # Place the microbump so bottom is at ubump_z_start
                ipk.modeler.create_cylinder(
                    orientation='Z',
                    origin=[px, py, ubump_z_start],
                    radius=ubump_radius,
                    height=ubump_thickness,
                    name=bump_name,
                    material=mat
                )

    # -----------------------------------------------------------------------------
    # 6. Place heatsink on top of the TIM
    # -----------------------------------------------------------------------------
    # We'll assume the TIM was the last layer among Substrate, Interposer, etc.
    # so the final 'current_z' is the top of the TIM. We'll match the footprint
    # to the TIM's bounding box, with some example param for total height.
    tim_layer = next((ly for ly in layers if ly["name"] == "TIM"), None)
    if tim_layer and tim_layer["elements"]:
        # Grab the first non-edge element for the TIM bounding box
        tim_elem = None
        for e in tim_layer["elements"]:
            if not e["name"].startswith("Edge"):
                tim_elem = e
                break
        if tim_elem:
            tim_top_z = current_z  # The top of TIM is at the final 'current_z'
            # Example param: 2 mm base thickness + 8 mm fin height = total 10 mm in Z
            hs_base_thick = 2
            hs_fin_height = 8
            hs_total_z = hs_base_thick + hs_fin_height

            # Center in XY so the HS covers exactly the same rectangle as TIM
            hs_center_x = tim_elem["offset_x"] #+ tim_elem["width"] / 2
            hs_center_y = tim_elem["offset_y"] #+ tim_elem["length"] / 2
            # Put the bottom of the HS at tim_top_z => center is bottom + (hs_total_z/2)
            hs_center_z = tim_top_z #+ hs_total_z / 2

            # Because create_parametric_fin_heat_sink arguments can be tricky,
            # we do a “best guess” so that the bounding box in X–Y matches the TIM.
            # For example, we might interpret:
            #   hs_width => dimension in X
            #   length   => dimension in Y
            #   height   => the fin height (Z minus base thickness)
            #   hs_basethick => thickness of the base
            #   hs_height => ???

            # You may need to tweak these if the fins do not appear as expected.
            heatsink = ipk.create_parametric_fin_heat_sink(
                hs_height=tim_elem["width"],   # Interpreted as X dimension
                hs_width=tim_elem["length"],   # Interpreted as Y dimension
                hs_basethick=hs_base_thick,    # base thickness
                draftangle=1.5,
                patternangle=8,
                numcolumn_perside=6,
                pitch=5,
                thick=2,
                length=tim_elem["length"],     # sometimes used as overall length in Y
                height=hs_fin_height,          # fin height (above the base)
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
    step_file = os.path.join(tempfile.gettempdir(), "geometry_export")
    path_=r"C:\\Users\\<your_username>\Documents\\PhD_Chiplets\\scripting_files"
    ipk.modeler.export_3d_model(file_name="geometry_export", file_path=path_, file_format=".step", assignment_to_remove=None)
    print(f"Geometry exported to STEP file: {path_}")

def ansys_therm_mech():
    from ansys.mechanical.core import launch_mechanical, App, find_mechanical, global_variables
    mechanical = launch_mechanical(
        exec_file = None,
        batch= False, 
        start_instance = True, 
        loglevel= 'INFO', 
        log_mechanical='pymechanical_log.txt', 
        verbose_mechanical= True
        )
    print(mechanical)

    #Import Geometry to Ansys Mechanical
    script_GeometryImport= """geomImport = Model.GeometryImportGroup.AddGeometryImport()
    # Format of Geometry file
    #geomImport_format = Ansys.Mechanical.DataModel.Enums.GeometryImportPreference.Format.Automatic
    geometryPath = r"C:\\Users\\<your_username>\Documents\\PhD_Chiplets\\scripting_files\\geometry_export.step"

    #Preferences for Geometry file
    #geomImport_preferences = Ansys.ACT.Mechanical.Utilities.GeometryImportPreferences()

    #geomImport_preferences.ProcessSolids = True
    # geomImport_preferences.ProcessSurfaces = False
    # geomImport_preferences.ProcessLines = False

    # geomImport_preferences.ProcessNamedSelections = True
    # geomImport_preferences.NamedSelectionKey = "NSel"

    #geomImport_preferences.ProcessMaterialProperties = True
    #geomImport_preferences.MixedImportResolution = GeometryImportPreference.MixedImportResolution.Solid

    #geomImport_preferences.ProcessCoordinateSystems = True
    #geomImport_preferences.CoordinateSystemKey = "CSys"
    geomImport.Import(geometryPath)"""#, geomImport_preferences)"""

    mechanical.run_python_script(script_GeometryImport)
    mechanical.log_message("INFO", "Geometry Import Success")

    #Create Microbumps named selection
    ubump_ns='''geometry = ExtAPI.DataModel.Project.Model.Geometry
    ns=ExtAPI.DataModel.Project.Model.AddNamedSelection()
    ns.Name="ubump"
    ns.ScopingMethod=GeometryDefineByType.Worksheet
    nsc = ns.GenerationCriteria
    nsc0=nsc.Add(None)
    nsc0= nsc[0]
    nsc0.Action=SelectionActionType.Add
    nsc0.EntityType=SelectionType.GeoFace
    nsc0.Criterion=SelectionCriterionType.Type
    nsc0.Operator=SelectionOperatorType.Equal
    nsc0.Value=2
    ns.Generate()
    '''
    mechanical.run_python_script(ubump_ns)

    #Create bottom face named selection
    bottom_face_ns="""
    geometry = ExtAPI.DataModel.Project.Model.Geometry
    ns1=ExtAPI.DataModel.Project.Model.AddNamedSelection()
    ns1.Name = "Bottom_Face"
    ns1.ScopingMethod = GeometryDefineByType.Worksheet
    nsc1=ns1.GenerationCriteria
    nsc1_0=nsc1.Add(None)
    nsc1_0=nsc1[0]
    nsc1_0.Action=SelectionActionType.Add
    nsc1_0.EntityType = SelectionType.GeoFace
    nsc1_0.Criterion = SelectionCriterionType.LocationZ
    nsc1_0.Operator = SelectionOperatorType.Smallest
    ns1.Generate()
    """
    mechanical.run_python_script(bottom_face_ns)

    #Assign Material to the geometry
    Material_Assignment_Script = """
    mat = DataModel.Project.Model.Materials
    mat_path = "<path_to_your_workspace>/Ansys CAD/python_files/Material_Data_all.xml"
    mat.Import(mat_path)
    for part in geometry.Children:
        if "Chiplet_" in part.Name:
            part.Material="Silicon Anisotropic"
        elif "Substrate" in  part.Name::
            part.Material="FR-4"
        elif "Interposer" part.Name:
            part.Material="Silicon Anisotropic"
        elif "Bump_" in part.Name:
            part.Material="Solder, lead-indium (50-50)"
        elif TIM in part.Name:":
            part.Material="PCB laminate, Composite Epoxy Material, CEM-1"
        else:
            part.Material="Copper Alloy"
    """
    mechanical.run_python_script(Material_Assignment_Script)

    #Generate Mesh
    mesh_prop="""

    mesh_ = Model.Mesh

    mesh_.PhysicsPreference = MeshPhysicsPreferenceType.Electromagnetics

    mesh_.ElementOrder = ElementOrder.Quadratic

    mesh_.SpanAngleCenter = 1

    mesh_.SpanAngleCenter = 0

    mesh_.Resolution = 3

    mesh_.DisplayStyle = MeshDisplayStyle.ElementQuality

    mesh_.GenerateMesh()
    """
    mechanical.run_python_script(mesh_prop)


    thermal_analysis = """\
    S_therm = Model.AddSteadyStateThermalAnalysis()

    """

    # Chiplet 0
    thermal_analysis += """\
    S_internal_heat_0 = S_therm.AddInternalHeatGeneration()
    S_internal_heat_0.Magnitude.Output.SetDiscreteValue(0, Quantity(3.75e9, "W m^-1 m^-1 m^-1"))
    selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    selection.Ids = [802] 
    S_internal_heat_0.Location = selection

    """

    # Chiplet 1
    thermal_analysis += """\
    S_internal_heat_1 = S_therm.AddInternalHeatGeneration()
    S_internal_heat_1.Magnitude.Output.SetDiscreteValue(0, Quantity(5.56e8, "W m^-1 m^-1 m^-1"))
    selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    selection.Ids = [829]
    S_internal_heat_1.Location = selection

    """

    # Chiplet 2
    thermal_analysis += """\
    S_internal_heat_2 = S_therm.AddInternalHeatGeneration()
    S_internal_heat_2.Magnitude.Output.SetDiscreteValue(0, Quantity(1.45e9, "W m^-1 m^-1 m^-1"))
    selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    selection.Ids = [856]
    S_internal_heat_2.Location = selection

    """

    # Chiplet 3
    thermal_analysis += """\
    S_internal_heat_3 = S_therm.AddInternalHeatGeneration()
    S_internal_heat_3.Magnitude.Output.SetDiscreteValue(0, Quantity(1.45e9, "W m^-1 m^-1 m^-1"))
    selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    selection.Ids = [910]
    S_internal_heat_3.Location = selection

    """

    # Chiplet 4
    thermal_analysis += """\
    S_internal_heat_4 = S_therm.AddInternalHeatGeneration()
    S_internal_heat_4.Magnitude.Output.SetDiscreteValue(0, Quantity(1.45e9, "W m^-1 m^-1 m^-1"))
    selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    selection.Ids = [883] 
    S_internal_heat_4.Location = selection

    """

    # Chiplet 5
    thermal_analysis += """\
    S_internal_heat_5 = S_therm.AddInternalHeatGeneration()
    S_internal_heat_5.Magnitude.Output.SetDiscreteValue(0, Quantity(1.45e9, "W m^-1 m^-1 m^-1"))
    selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    selection.Ids = [937]
    S_internal_heat_5.Location = selection
    """

    # Now, run the complete script in ANSYS:
    mechanical.run_python_script(thermal_analysis)




    #Create Thermal Analysis
    """
    S_therm=Model.AddSteadyStateThermalAnalysis()

    #####Assign Sources########
    S_internal_heat_0=S_therm.AddInternalHeatGeneration() 
    S_internal_heat_0.Magnitude.Output.SetDiscreteValue(0, Quantity(25, "W m^-1 m^-1 m^-1"))
    selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    selection.Ids = [802] #chiplet 0
    S_internal_heat_0.Location = selection"""


    #####Assign Boundaries and solve######
    thermal_analysis= """
    convection_ = S_therm.AddConvection()
    convection_.FilmCoefficient.Output.SetDiscreteValue(0, Quantity(220, "W m^-1 m^-1 C^-1"))
    selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    selection.Ids = [1727, 1728, 1729, 1730, 1731, 1732, 1733, 1734, 1735, 1736, 1737, 1738, 1739, 1740, 1741, 1742, 1743, 1744, 1745, 1746, 1747, 1748, 1749, 1750, 1751, 1752, 1753, 1754, 1755, 1756, 1757, 1758, 1759, 1760, 1761, 1762, 1763, 1764, 1765, 1766, 1767, 1768, 1769, 1770, 1771, 1772, 1773, 1774, 1775, 1776, 1777, 1778, 1779, 1780, 1781, 1782, 1783, 1784, 1785, 1786, 1787, 1788, 1789, 1790, 1791, 1792, 1793, 1794, 1795, 1796, 1797, 1798, 1799, 1800, 1801, 1802, 1804, 1805, 1806, 1807, 1808, 1809, 1810, 1811, 1812, 1813, 1814, 1815, 1816, 1817, 1818, 1819, 1820, 1821, 1822, 1823, 1824, 1825, 1826, 1827, 1828, 1829, 1830, 1831, 1832, 1833, 1834, 1835, 1836, 1837, 1838, 1839, 1840, 1841, 1842, 1843, 1844, 1845, 1846, 1847, 1848, 1849, 1850, 1851, 1852, 1853, 1854, 1855, 1856, 1857, 1858, 1859, 1860]
    convection_.Location = selection
    Model.Analyses[0].Solution.AddTemperature()
    S_therm.Solve()
    """
    mechanical.run_python_script(thermal_analysis)

    Structural_analysis_script="""
    ss1=Model.AddStaticStructuralAnalysis()
    ss1.AddEarthGravity()
    fs = ss1.AddFixedSupport()
    selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    selection.Ids = [231]
    fs.Location = selection
    thermal_in=ss1.ImportLoad(Model.Analyses[0])
    von_miss_stress = ss1.Solution.AddEquivalentStress()
    thermal_strain = ss1.Solution.AddThermalStrain()
    strain_energy = ss1.Solution.AddStructuralStrainEnergy()
    ss1.Solve()
    """
    mechanical.run_python_script(Structural_analysis_script)


    export_script = """
    import os, re

    # Define the output filename
    filename = r"C:\\Users\\<your_username>\\Documents\\PhD_Chiplets\\scripting_files\\results_test1.csv"

    # If the file does not exist, write the header line.
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write("temp,stress,max_stress_part,max_thermal_strain\\n")

    # Define the iteration number (you can update this externally as needed)
    temp_string = Model.Analyses[0].Solution.Children[1].PropertyByName("Maximum").StringValue
    stress_string = Model.Analyses[0].Solution.Children[1].PropertyByName("Maximum").StringValue
    max_stress_part = Model.Analyses[1].Solution.Children[1].PropertyByName("MaximumBodyName").StringValue
    max_thermal_strain = Model.Analyses[1].Solution.Children[2].PropertyByName("Maximum").StringValue

    # Extract numeric values (assuming the strings contain numeric data followed by units)
    temp_value = re.findall(r"[\\d\\.]+", temp_string)[0]
    stress_value = re.findall(r"[\\d\\.]+", stress_string)[0]
    max_thermal_strain_value = re.findall(r"[\\d\\.]+", max_thermal_strain)[0]

    # Build the CSV line: iteration, temp, stress, max_stress_part, max_thermal_strain
    line = "{0},{1},{2},{3}\\n".format(temp_value, stress_value, max_stress_part, max_thermal_strain_value)

    # Append the line to the CSV file
    with open(filename, "a") as f:
        f.write(line)
    """
    mechanical.run_python_script(export_script)
    mechanical.close()



#close the connection

if __name__ == "__main__": 
  ansys_therm_mech()
  




