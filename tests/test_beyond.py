import ast
from pathlib import Path
import unittest
import numpy as np
from beyond_field import DURATION, GLYPHS, PALETTE, Universe, nested_scales
from beyond import colored_lines


class CharacterFilmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scene = Universe(168, 60)

    def test_no_block_or_image_drawing(self):
        self.assertTrue(all(32 <= ord(c) < 127 for c in GLYPHS))
        tree = ast.parse((Path(__file__).parents[1]/"beyond.py").read_text(encoding="utf-8"))
        drawing = {node.func.attr for node in ast.walk(tree)
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr.startswith("create_")}
        self.assertEqual(drawing, {"create_text"})

    def test_deterministic_finite_fields(self):
        for t in (0, 10, 17.15, 30, 46, 63, 80, 96, 118, 126, 133, 139, 144):
            with self.subTest(t=t):
                a = self.scene.sample(t)
                old = a.text
                b = self.scene.sample(t)
                self.assertEqual(old, b.text)
                np.testing.assert_array_equal(a.colors, b.colors)
                self.assertTrue(np.isfinite(self.scene.light).all())
                self.assertGreaterEqual(float(self.scene.light.min()), 0)
                self.assertTrue((b.colors < len(PALETTE)).all())

    def test_black_loop_endpoints(self):
        first, last = self.scene.sample(0).text, self.scene.sample(DURATION).text
        self.assertEqual(first, last)
        self.assertEqual(set(first), {" ", "\n"})

    def test_blink_closes_iris(self):
        self.scene.sample(10)
        open_light = self.scene.light.sum()
        self.scene.sample(17.15)
        self.assertLess(self.scene.light.sum(), open_light*.12)

    def test_closing_hides_the_inner_universe(self):
        self.scene.sample(135)
        before = float(self.scene.light.sum())
        self.scene.sample(142.9)
        self.assertLess(float(self.scene.light.sum()), before*.08)

    def test_iris_is_distinct_from_black_pupil(self):
        self.scene.sample(10)
        light = self.scene.light.sum(axis=2)
        iris = light[(self.scene.radius > .17) & (self.scene.radius < .34)]
        pupil = light[self.scene.radius < .11]
        self.assertGreater(float(iris.mean()), float(pupil.mean())*20)
        self.assertGreater(float(iris.std()), .02)

    def test_no_hard_cuts_at_scene_boundaries(self):
        for t in (22, 26, 31, 35, 38, 52, 53, 60, 69, 70, 74, 78, 83, 93, 96, 102, 103, 106, 112, 117, 123, 135, 136, 142):
            with self.subTest(t=t):
                self.scene.sample(t-.002)
                a = self.scene.light.copy()
                self.scene.sample(t+.002)
                self.assertLess(float(np.abs(a-self.scene.light).mean()), .003)

    def test_every_major_scene_moves(self):
        for t in (10, 29, 45, 64, 81, 96, 116, 129, 138):
            with self.subTest(t=t):
                a = self.scene.sample(t).text
                b = self.scene.sample(t+.6).text
                self.assertNotEqual(a, b)

    def test_text_grid_has_consistent_line_lengths(self):
        for columns, rows in ((64, 28), (168, 60), (240, 80)):
            frame = Universe(columns, rows).sample(96)
            self.assertEqual(len(frame.text.splitlines()), rows)
            self.assertTrue(all(len(line) == columns for line in frame.text.splitlines()))

    def test_color_layers_reconstruct_every_character(self):
        for t in (10, 30, 46, 63, 80, 96, 121, 132, 139):
            with self.subTest(t=t):
                frame = self.scene.sample(t)
                layers = colored_lines(frame)
                restored = np.full(frame.glyphs.shape, " ", dtype="<U1")
                for row in range(frame.glyphs.shape[0]):
                    for layer in range(8):
                        text = layers[row*8+layer].ljust(frame.glyphs.shape[1])
                        for col, char in enumerate(text):
                            if char != " ":
                                self.assertEqual(int(frame.colors[row, col])//4, layer)
                                restored[row, col] = char
                np.testing.assert_array_equal(restored, frame.glyphs)

    def test_whole_inner_eye_fits_inside_outer_pupil(self):
        for t in np.linspace(123, 135, 61):
            inner, outer = nested_scales(t)
            # 1.2 is the inner eye's half-width. 0.130 is the smallest
            # pupil radius including its breathing motion.
            self.assertLess(inner*1.2, outer*.130)

    def test_seeking_does_not_change_later_render_results(self):
        reference = self.scene.sample(10).text
        self.scene.sample(46)
        self.scene.sample(80)
        self.scene.sample(135)
        self.assertEqual(self.scene.light.dtype, np.float32)
        self.assertEqual(self.scene.sample(10).text, reference)


if __name__ == "__main__":
    unittest.main(verbosity=2)
