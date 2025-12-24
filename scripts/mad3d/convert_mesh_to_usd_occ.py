import argparse

from isaaclab.app import AppLauncher
import shutil

# add argparse arguments
parser = argparse.ArgumentParser(description="Utility to convert a mesh file into USD format.")
parser.add_argument("input", type=str, help="The root to the input mesh file.")
parser.add_argument("output", type=str, help="The root to store the USD file.")
parser.add_argument(
    "--make-instanceable",
    action="store_true",
    default=False,
    help="Make the asset instanceable for efficient cloning.",
)
parser.add_argument(
    "--collision-approximation",
    type=str,
    default="none",
    choices=["convexDecomposition", "convexHull", "none", "meshSimplification"],
    help=(
        'The method used for approximating collision mesh. Set to "none" '
        "to not add a collision mesh to the converted mesh."
    ),
)
parser.add_argument(
    "--mass",
    type=float,
    default=None,
    help="The mass (in kg) to assign to the converted asset. If not provided, then no mass is added.",
)

parser.add_argument(
    "--subdirs",
    type=str,
    default=None,
    help=(
        "Range of top-level subdirectory names to include, exclusive of the endpoint (e.g. '000-000..000-010')."
        "If omitted, all subdirectories are processed."
    ),
)

# append AppLauncher cli args
AppLauncher.add_app_launcher_args(parser)
# parse the arguments
args_cli = parser.parse_args()

# launch omniverse app
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""
import contextlib
import os
import re
import builtins

from tqdm import tqdm
import carb
import glob
import isaacsim.core.utils.stage as stage_utils
import omni.kit.app

from isaaclab.sim.converters import MeshConverterMAD3D, MeshConverterCfg
from isaaclab.sim.schemas import schemas_cfg
from isaaclab.utils.assets import check_file_path
from isaaclab.utils.dict import print_dict

# normalize the max side of the 3D shape to max_len
MAX_LEN = 8
# env and grid size
ENV_SIZE = 20
GRID_SIZE = 20


def run_convert(mesh_path, dest_path):
    # check valid file path
    if not os.path.isabs(mesh_path):
        mesh_path = os.path.abspath(mesh_path)
    if not check_file_path(mesh_path):
        raise ValueError(f"Invalid mesh file path: {mesh_path}")

    # create destination path
    if not os.path.isabs(dest_path):
        dest_path = os.path.abspath(dest_path)

    print(dest_path)

    # Mass properties
    if args_cli.mass is not None:
        mass_props = schemas_cfg.MassPropertiesCfg(mass=args_cli.mass)
        rigid_props = schemas_cfg.RigidBodyPropertiesCfg()
    else:
        mass_props = None
        rigid_props = None

    # Collision properties
    collision_props = schemas_cfg.CollisionPropertiesCfg(collision_enabled=args_cli.collision_approximation != "none")

    # Create Mesh converter config
    mesh_converter_cfg = MeshConverterCfg(
        mass_props=mass_props,
        rigid_props=rigid_props,
        collision_props=collision_props,
        asset_path=mesh_path,
        force_usd_conversion=True,
        usd_dir=os.path.dirname(dest_path),
        usd_file_name=os.path.basename(dest_path),
        make_instanceable=args_cli.make_instanceable,
        collision_approximation=args_cli.collision_approximation,
    )

    # Print info
    print("-" * 80)
    print("-" * 80)
    print(f"Input Mesh file: {mesh_path}")
    print("Mesh importer config:")
    print_dict(mesh_converter_cfg.to_dict(), nesting=0)
    print("-" * 80)
    print("-" * 80)

    # Create Mesh converter and import the file
    mesh_converter = MeshConverterMAD3D(mesh_converter_cfg, max_len=MAX_LEN, env_size=ENV_SIZE, grid_size=GRID_SIZE)
    # print output
    print("Mesh importer output:")
    print(f"Generated USD file: {mesh_converter.usd_path}")
    print("-" * 80)
    print("-" * 80)

def split_prefix_num(s):
    m = re.search(r'(\d+)$', s)
    if not m:
        return s, None, 0
    num = int(m.group(1))
    prefix = s[:m.start(1)]
    width = len(m.group(1))

    return prefix, num, width

def expand_range(spec: str):
    if '..' not in spec:
        raise ValueError("Range must contain '..'")

    left, right = spec.split('..', 1)

    p1, n1, w1 = split_prefix_num(left)
    p2, n2, w2 = split_prefix_num(right)

    if n1 is None or n2 is None:
        raise ValueError("Both endpoints must end with a number")

    if p1 != p2:
        raise ValueError(f"Prefixes differ: {p1!r} vs {p2!r}")

    if n1 > n2:
        raise ValueError("Start is greater than end")

    width = max(w1, w2)
    return [f"{p1}{str(i).zfill(width)}" for i in range(n1, n2)]

def main():
    # load all 3D model paths  
    # list of file extensions to search for
    extensions = ['*.glb', '*.obj', '*.fbx']
    meshes_path = []
    for ext in extensions:
        meshes_path.extend(glob.glob(os.path.join(args_cli.input, '**', ext), recursive=True))

    if args_cli.subdirs:
        spec = args_cli.subdirs.strip()
        allowed = set(expand_range(spec))
        print(f"Looking in subdirectories: {allowed}")
        if allowed:
            filtered = []
            for p in meshes_path:
                rel = os.path.relpath(p, args_cli.input)
                top = rel.split(os.sep)[0]
                if top in allowed:
                    filtered.append(p)
            meshes_path = filtered 

    start = 0
    total = len(meshes_path)

    original_print = builtins.print
    builtins.print = tqdm.write

    try:
        print(f"Number of files to convert: {total}")
        # start conversion 3D model (glb, obj, fbx) to rescaled, shifted usd and occupancy grid (occ.npy)
        for i, mesh_path in enumerate(tqdm(meshes_path[start:])):
            relative_path = os.path.relpath(mesh_path, args_cli.input)

            dest_path = os.path.join(args_cli.output, relative_path)
            # save path
            dest_path = os.path.join(dest_path[:-4], os.path.split(relative_path)[-1][:-3]+'usd')
            run_convert(mesh_path, dest_path)
    finally:
        builtins.print = original_print

if __name__ == "__main__":
    # run the main function
    main()
    # close sim app
    simulation_app.close()
