import glob
import os
import py_compile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BlenderCodeCompilesTest(unittest.TestCase):
    """The Blender-side code cannot be imported here (no bpy), so a syntax error in it only showed up inside a
    render. Compiling it catches that in the test suite."""

    def test_director_and_character_code_compiles(self):
        files = glob.glob(os.path.join(ROOT, "engine", "director", "*.py")) + [
            os.path.join(ROOT, "engine", "character.py"), os.path.join(ROOT, "engine", "mocap.py"),
            os.path.join(ROOT, "engine", "props.py"), os.path.join(ROOT, "engine", "studio.py"),
            os.path.join(ROOT, "engine", "qa.py"), os.path.join(ROOT, "engine", "water_still.py"),
            os.path.join(ROOT, "engine", "mocap_still.py"), os.path.join(ROOT, "engine", "films", "cutaway_film.py"),
            os.path.join(ROOT, "tools", "chatterbox", "speak.py")]
        for path in files:
            with self.subTest(path=os.path.basename(path)):
                py_compile.compile(path, doraise=True)


if __name__ == "__main__":
    unittest.main()
