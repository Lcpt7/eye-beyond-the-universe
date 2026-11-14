"""Original procedural character fields for 瞳界 · 星渊.

No image, video, block glyph, prerecorded frame, or network input is used.
The arrays describe light at character positions, not display pixels.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np

TAU = math.tau
DURATION = 144.0
GLYPHS = np.array(list("  .,:;-=+*oxO%#@"), dtype="<U1")


def smooth(a, b, x):
    u = np.clip((x - a) / (b - a), 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def mix(a, b, t):
    return a + (b - a) * t


def gauss(x, width):
    return np.exp(-np.square(x / width))


def nested_scales(t):
    pull = float(smooth(123, 135, t))
    inner = math.exp(mix(math.log(1.), math.log(.14), pull))
    outer = math.exp(mix(math.log(12.), math.log(1.35), pull))
    return inner, outer


@dataclass
class CharacterFrame:
    glyphs: np.ndarray
    colors: np.ndarray
    heading: str = ""
    caption: str = ""
    heading_alpha: float = 1.0
    caption_alpha: float = 1.0

    @property
    def text(self):
        return "\n".join("".join(row) for row in self.glyphs)


def make_palette():
    shades = []
    for silver in (False, True):
        for level in range(16):
            v = (level + 1) / 16
            if silver:
                rgb = (int(222*v), int(216*v), int(248*v))
            else:
                rgb = (int(180*v), int(124*v), int(239*v))
            shades.append("#%02x%02x%02x" % rgb)
    return tuple(shades)


PALETTE = make_palette()


class Universe:
    """Deterministic fields sampled on a grid of monospaced characters."""

    def __init__(self, columns=208, rows=72, cell_aspect=0.5):
        if columns < 48 or rows < 24:
            raise ValueError("At least 48 columns and 24 rows are needed")
        self.columns, self.rows = int(columns), int(rows)
        self.cell_aspect = float(cell_aspect)
        self.aspect = columns * cell_aspect / rows
        y = (np.arange(rows, dtype=np.float32) + .5) * 2 / rows - 1
        x = (np.arange(columns, dtype=np.float32) + .5 - columns/2) * 2 / rows * cell_aspect
        self.x, self.y = np.meshgrid(x, y)
        self.radius = np.hypot(self.x, self.y)
        self.angle = np.arctan2(self.y, self.x)
        rng = np.random.default_rng(73019)
        self.texture = rng.random((256, 256), dtype=np.float32)
        self.stars = rng.random((2400, 5), dtype=np.float32)
        self.stars[:, :2] = self.stars[:, :2] * 2 - 1
        self.stars[:, 2] = .16 + self.stars[:, 2] * .84
        self.goals = self._eye_constellation(rng, len(self.stars))
        # Static spatial dither avoids the snow/static produced by per-frame randomness.
        self.dither = rng.random((rows, columns), dtype=np.float32)
        self.light = np.zeros((rows, columns, 3), dtype=np.float32)

    def noise(self, x, y):
        ix, iy = np.floor(x).astype(np.int32), np.floor(y).astype(np.int32)
        fx, fy = x-ix, y-iy
        fx, fy = fx*fx*(3-2*fx), fy*fy*(3-2*fy)
        a = mix(self.texture[iy & 255, ix & 255], self.texture[iy & 255, (ix+1) & 255], fx)
        b = mix(self.texture[(iy+1) & 255, ix & 255], self.texture[(iy+1) & 255, (ix+1) & 255], fx)
        return mix(a, b, fy)

    def fbm(self, x, y):
        return (.53*self.noise(x, y) + .27*self.noise(x*2.03+17, y*2.03+31)
                + .13*self.noise(x*4.11+7, y*4.11+19) + .07*self.noise(x*8.21+11, y*8.21+13))

    @staticmethod
    def _eye_constellation(rng, count):
        result = np.zeros((count, 2), np.float32)
        edge = count*3//10
        x = np.linspace(-1.2, 1.2, edge)
        side = np.where(np.arange(edge) % 2, 1, -1)
        result[:edge, 0] = x
        result[:edge, 1] = side*.385*np.maximum(0, 1-(x/1.2)**2)**.80
        a = rng.random(count-edge)*TAU
        r = .145 + .225*rng.random(count-edge)**.8
        result[edge:, 0] = r*np.cos(a)
        result[edge:, 1] = r*np.sin(a)
        return result

    def add(self, light, rgb=(.66, .42, 1.0)):
        self.light += np.asarray(light, np.float32)[..., None] * np.asarray(rgb, np.float32)

    def points(self, x, y, strength, rgb=(.80, .75, 1.0)):
        """Sub-cell splats; the presentation layer still emits text exclusively."""
        x, y, strength = np.broadcast_arrays(x, y, strength)
        sx = x*self.rows/(2*self.cell_aspect) + self.columns/2 - .5
        sy = (y+1)*self.rows/2 - .5
        ix, iy = np.floor(sx).astype(np.int32), np.floor(sy).astype(np.int32)
        fx, fy = sx-ix, sy-iy
        for dx, dy, weight in ((0, 0, (1-fx)*(1-fy)), (1, 0, fx*(1-fy)),
                                (0, 1, (1-fx)*fy), (1, 1, fx*fy)):
            xx, yy = ix+dx, iy+dy
            ok = (xx >= 0) & (xx < self.columns) & (yy >= 0) & (yy < self.rows)
            weights = (strength*weight)[ok]
            for ch, color in enumerate(rgb):
                np.add.at(self.light[..., ch], (yy[ok], xx[ok]), weights*color)

    def polyline(self, x, y, strength=.3, rgb=(.72, .61, 1.0), step=.009):
        # Resampling by segment length avoids dotted or bright-at-corner strokes.
        x, y = np.asarray(x), np.asarray(y)
        lengths = np.hypot(np.diff(x), np.diff(y))
        distance = np.concatenate(([0.], np.cumsum(lengths)))
        if distance[-1] < .00001:
            return
        s = np.arange(0, distance[-1], step)
        self.points(np.interp(s, distance, x), np.interp(s, distance, y), strength, rgb)

    def background(self, t, hole=0.0, scale=1.0):
        x, y = self.x, self.y
        if hole:
            bend = hole*.115*scale*scale/(self.radius**2+.08)
            x, y = x*(1-bend), y*(1-bend)
        drift = t*.022
        warp = self.noise(x*1.4+50+drift, y*1.4+60)
        n = self.fbm(x*2.7+warp*1.7+drift+41, y*3.1+warp+87-drift*.35)
        band = gauss(y+x*.24-.16*np.sin(x*1.5+t*.027), .25+n*.34)
        density = np.clip((n-.30)*2.5, 0, 1)
        filaments = np.clip(1-np.abs(n-.52)*7, 0, 1)**4
        veil = band*(density*.21 + filaments*.045)
        self.light[:] = (.0015, .001, .004)
        self.add(veil, (.61, .20, 1.03))

    def starfield(self, t, hole=0., scale=1., converge=0., eye_scale=1.):
        s = self.stars
        travel = t*.008
        z = .18 + (s[:, 2]-travel) % 1.0
        x, y = s[:, 0]*self.aspect/z, s[:, 1]/z
        if hole:
            r = np.maximum(.0001, np.hypot(x, y))
            apparent = .5*(r+np.sqrt(r*r+4*(.33*scale)**2))
            lens = mix(1., apparent/r, hole)
            x, y = x*lens, y*lens
        # Curved trajectories converge to explicit eye-shaped destinations.
        arc = np.sin(converge*math.pi)*(.08+.13*s[:, 3])
        x = mix(x, self.goals[:, 0]*eye_scale, converge) + arc*np.sin(s[:, 4]*TAU)
        y = mix(y, self.goals[:, 1]*eye_scale, converge) + arc*np.cos(s[:, 4]*TAU)
        visibility = smooth(.18, .23, z)*(1-smooth(1.10, 1.18, z))
        bright = (.19+s[:, 3]**7*2.1)*(.8+.2*np.sin(t*.53+s[:, 4]*TAU))
        bright *= mix(visibility, 1., converge)*mix(.80, .72, converge)
        self.points(x, y, bright)

    def eye(self, t, scale=1., opening=1., center=(0., 0.)):
        """Almond lids, radial iris fibres, collarette and stellar corneal glints."""
        x = (self.x-center[0])/scale
        y = (self.y-center[1])/scale
        height = .385*np.maximum(0, 1-(x/1.2)**2)**.8*opening
        inside = smooth(-.012, .012, height-np.abs(y))*(np.abs(x) < 1.2)
        r, a = np.hypot(x, y), np.arctan2(y, x)
        pupil_r = .137 + .007*math.sin(t*.51)
        pupil = 1-smooth(pupil_r-.009, pupil_r+.008, r)
        iris = (1-smooth(.360, .377, r))*(1-pupil)
        n = self.noise(np.cos(a)*13+60, r*37+np.sin(a)*9+t*.012+50)
        # Band-limit angular detail at character-grid resolution. Very high
        # frequencies looked like salt-and-pepper rather than radial fibres.
        fibres = (.5+.5*np.sin(a*37 + n*2.3 + r*17))**5
        fine = (.5+.5*np.sin(a*61-r*24+n*2))**9
        radial = smooth(.14, .19, r)*(1-smooth(.29, .38, r))
        collarette = gauss(r-(.195+.011*np.sin(a*13)), .012)
        rings = .25+.75*(.5+.5*np.sin(r*63+a*.4))
        texture = (.11+.40*fibres+.15*fine)*(.4+.6*radial)*rings
        intensity = (texture + .21*collarette + gauss(r-.363, .009)*.33)*iris
        light = np.zeros_like(self.light)
        light += intensity[..., None]*np.array((.68, .48, .98))
        sclera = inside*(1-iris)*(1-pupil)
        veins = self.fbm(x*4+80, y*8+70)
        veil = .016+.034*gauss(y, .24)+.024*np.clip(1-np.abs(veins-.52)*9, 0, 1)**3
        light += (sclera*veil)[..., None]*np.array((.64, .40, .91))
        edge = gauss(np.abs(y)-height, .009+1.0/(self.rows*scale))*(np.abs(x) < 1.2)
        upper = np.where(y < 0, 1., .47)
        lid = edge*(.22+gauss(x+.47, .6)*.21)*upper*opening**.65
        light += lid[..., None]*np.array((.79, .69, .99))
        # Small constellations, rather than glossy rectangular highlights.
        for hx, hy, radius, power in ((-.14, -.17, .025, .95), (-.08, -.22, .010, .63), (.17, .11, .013, .48)):
            reflect = gauss(np.hypot(x-hx, y-hy), radius)*inside
            light += reflect[..., None]*np.array((.90, .87, 1.0))*power
        light *= inside[..., None]
        return light, pupil*inside

    def tunnel(self, t, amount):
        r = np.maximum(self.radius, .012)
        a = self.angle
        depth = -np.log(r)*1.8-t*1.3
        helix = (.5+.5*np.sin(a*7+depth*2.4))**19
        rings = (.5+.5*np.sin(depth*8+.6*np.sin(a*3)))**22
        envelope = smooth(.04, .16, r)*(1-smooth(1.0, 1.8, r))
        self.add((helix*.18+rings*.11)*envelope*amount, (.67, .46, 1.0))
        count = 130
        i = np.arange(count)
        phase = i*2.399963
        r = .05+((i*.618034+t*.40) % 1.0)**2*2.1
        self.points(r*np.cos(phase+t*.08), r*np.sin(phase+t*.08), amount*(.09+.3*r))

    def planet(self, t, amount):
        cx = mix(1.8, 1.02, smooth(35, 54, t))
        cy, radius = -.075, .78
        x, y = (self.x-cx)/radius, (self.y-cy)/radius
        rr = x*x+y*y
        inside = 1-smooth(.98, 1.02, rr)
        z = np.sqrt(np.maximum(0., 1-rr))
        day = np.clip(-x*.72-y*.45+z*.38, 0, 1)**1.9
        bands = .65+.23*np.sin(y*21+x*3+t*.07)+.12*self.fbm(x*8+60, y*9+50)
        surface = (day*bands*.15+.002)[..., None]*np.array((.60, .49, .86))
        self.light[:] = mix(self.light, surface, (inside*amount)[..., None])
        r = np.sqrt(rr)
        facing = np.clip(-x*.78-y*.49, 0, 1)
        atmosphere = gauss(r-1., .014)*facing**1.3*.91
        halo = gauss(r-1.01, .045)*facing*.12
        self.add((atmosphere+halo)*amount, (.77, .71, 1.))

        # A tiny companion moon makes the foreground planet's scale legible.
        moon = np.hypot(self.x+.84, self.y+.42)
        self.add(gauss(moon-.058, .007)*amount*.25, (.7, .66, .9))

    def meteors(self, t, amount):
        for j in range(9):
            phase = (t*.29+j*.617) % 3.7
            alpha = smooth(0., .24, phase)*(1-smooth(.8, 1.25, phase))*amount
            if alpha < .002:
                continue
            headx = -1.9+phase*2.2+(j%3)*.63
            heady = -.82+phase*.55+(j%4)*.07
            tail = np.linspace(0., .23, 45)
            strength = alpha*np.exp(-tail*17)*.26
            self.points(headx-tail, heady-tail*.31, strength, (.81, .77, 1.))

    def black_hole(self, t, amount, scale):
        x, y = self.x/scale, self.y/scale
        tilt = -.13+.025*math.sin(t*.08)
        c, s = math.cos(tilt), math.sin(tilt)
        qx, qy = x*c+y*s, -x*s+y*c
        radius = np.hypot(x, y)
        disk_r = np.hypot(qx, qy/.185)
        a = np.arctan2(qy/.185, qx)
        radial = smooth(.37, .47, disk_r)*(1-smooth(.78, 1.43, disk_r))
        streak = .64+.18*np.sin(disk_r*46-t*1.1+np.sin(a*3-t*.3)*1.2)
        streak += .08*np.sin(disk_r*86+a*4+t)
        doppler = .58+.42*np.clip(.5-qx*.6, 0, 1)
        disk = radial*streak*doppler
        ring = gauss(radius-.356, .013)*.48+gauss(radius-.37, .033)*.15
        arcr = np.hypot(qx, (qy+.018)/.91)
        arc = gauss(arcr-.425, .026)*(1-smooth(-.02, .16, qy))*.54
        light = (disk*1.5+ring+arc)*amount
        shadow = (1-smooth(.326, .344, radius))*amount
        self.light *= (1-shadow)[..., None]
        light *= np.where((radius < .335) & (qy < .008), 0., 1.)
        silver = np.clip((light-.35)*.7, 0, 1)
        color = np.stack((mix(.66, 1.03, silver), mix(.29, .92, silver), mix(1.16, 1.13, silver)), axis=2)
        self.light += light[..., None]*color
        flare = gauss(qy, .008)*gauss(qx, 1.7)*.13*amount
        self.add(flare*(np.abs(qx) > .36), (.75, .55, 1.))

    def gate(self, t, amount):
        r, a = self.radius, self.angle
        rotation = t*.031
        stone = (1-smooth(.052, .069, np.abs(r-.70)))*amount
        relief = gauss(r-.645, .010)*.17 + gauss(r-.762, .010)*.22
        shade = .024+.035*(.5-.5*np.sin(a+.7))
        cracks = (1-smooth(.94, .995, ((a-rotation)/TAU*20) % 1))
        opacity = stone*cracks*.88
        body = (shade+relief)[..., None]*np.array((.8, .59, 1.))
        self.light[:] = mix(self.light, body, opacity[..., None])
        glow = gauss(r-.61, .009)*.27 + gauss(r-.785, .007)*.16
        self.add(glow*amount, (.68, .47, 1.))
        portal = gauss(r, .52)*(.5+.5*np.sin(r*18-a*3-t*.9))*.035
        self.add(portal*amount)
        # All broken orbits and invented seals are sampled as light at text cells.
        paths = []
        for j in range(8):
            aa = np.linspace(j*TAU/8-rotation*.6, j*TAU/8-rotation*.6+.39, 38)
            paths.append(np.column_stack((.82*np.cos(aa), .82*np.sin(aa))))
        for j in range(20):
            angle = j*TAU/20+rotation
            c, s = math.cos(angle+math.pi/2), math.sin(angle+math.pi/2)
            center = np.array((.703*math.cos(angle), .703*math.sin(angle)))
            glyph = [[(0, -.033), (0, .033)]]
            for k in range(3):
                yy, side = (k-1)*.021, (-1 if (j>>k)&1 else 1)
                glyph.append([(0, yy), (side*.023, yy-.011), (side*.023, yy+.004)])
            for part in glyph:
                p = np.asarray(part)
                paths.append(center+np.column_stack((p[:, 0]*c-p[:, 1]*s, p[:, 0]*s+p[:, 1]*c)))
        self.paths(paths, amount*.24, (.84, .73, 1.))

    def dragon(self, t, amount):
        u = np.linspace(0., 1., 1500)
        x, y, nx, ny = self.dragon_spine(u, t)
        phase = u*TAU*79+t*.13
        width = .008+.064*u**.6
        transverse = np.sin(phase)*width
        cloud = .5+.5*np.cos(phase)
        luminance = (.12+.36*cloud**3)*amount*(.65+.35*np.sin(u*181+t*.5)**2)
        self.points(x+nx*transverse, y+ny*transverse, luminance, (.81, .73, 1.))
        # Sparse constellation edges outline a coiled body without a filled tube.
        uc = np.linspace(0., 1., 140)
        xx, yy, _, _ = self.dragon_spine(uc, t)
        self.polyline(xx, yy, amount*.15)
        paths = []
        for u0 in np.arange(.12, .96, .044):
            xx, yy, nx0, ny0 = self.dragon_spine(np.array([u0]), t)
            p = np.array((xx[0], yy[0]))
            n = np.array((nx0[0], ny0[0]))
            radius = .008+.064*u0**.6
            paths.append(np.array((p+n*radius*.8, p+n*(radius+.04+u0*.025))))
        for j in range(4):
            uu = .36+(j//2)*.39+(j%2)*.045
            xx, yy, _, _ = self.dragon_spine(np.array([uu]), t)
            side = 1 if j % 2 else -1
            p = np.array((xx[0], yy[0]))
            elbow = p+(.055, side*.14)
            wrist = elbow+(.11, side*.04)
            paths.append(np.array((p, elbow, wrist)))
            for claw in range(3):
                tip = wrist+(.07, (claw-1)*.032)
                paths.append(np.array((wrist, tip, tip+(.028, side*.025))))
        hx, hy, _, _ = self.dragon_spine(np.array([1.]), t)
        px, py, _, _ = self.dragon_spine(np.array([.995]), t)
        head = np.array((hx[0], hy[0]))
        direction = head-np.array((px[0], py[0]))
        direction /= np.linalg.norm(direction)
        up = np.array((direction[1], -direction[0]))

        def local(coords):
            p = np.asarray(coords)
            return head+p[:, 0, None]*direction+p[:, 1, None]*up

        paths.append(local([(-.09,.02), (-.04,.08), (.06,.077), (.10,.043), (.21,.025),
                            (.23,-.018), (.18,-.054), (.06,-.062), (-.08,-.025)]))
        for side in (0, 1):
            ox = -.03-side*.045
            paths.append(local([(ox,.06), (ox-.08,.18+side*.02), (ox-.06,.28+side*.02)]))
            paths.append(local([(ox-.08,.18), (ox-.15,.22), (ox-.16,.275)]))
            paths.append(local([(ox-.04,.12), (ox+.015,.17)]))
        for side in (-1, 1):
            s = np.linspace(0, 1, 38)
            whisker = np.column_stack((.18+.25*s-.10*s*s, -.015+side*.10*np.sin(s*3.2)-s*.10+.01*np.sin(s*7+t*.9)))
            paths.append(local(whisker))
        self.paths(paths, amount*.31, (.85, .77, 1.))
        eye = local([(.065, .032)])[0]
        self.points(eye[0], eye[1], amount*2.3, (1., .88, 1.))
        # A few bright vertebrae make this read as a creature made of constellations.
        uu = np.linspace(.08, .97, 33)
        xx, yy, _, _ = self.dragon_spine(uu, t)
        self.points(xx, yy, (.3+.4*np.sin(uu*53)**2)*amount)

    def paths(self, paths, strength, rgb=(.8, .7, 1.)):
        xx, yy = [], []
        for path in paths:
            path = np.asarray(path)
            lengths = np.hypot(np.diff(path[:, 0]), np.diff(path[:, 1]))
            distance = np.concatenate(([0.], np.cumsum(lengths)))
            if distance[-1] < .0001:
                continue
            s = np.arange(0, distance[-1], .009)
            xx.append(np.interp(s, distance, path[:, 0]))
            yy.append(np.interp(s, distance, path[:, 1]))
        if xx:
            self.points(np.concatenate(xx), np.concatenate(yy), strength, rgb)

    @staticmethod
    def dragon_spine(u, t):
        breath = .32*math.sin(t*.21)
        env = np.sin(math.pi*u)
        phase = u*TAU*2
        x = -1.13+1.95*u+.43*np.sin(phase+.2+breath*.6)*env
        y = .41*np.sin(phase+breath)*env+.16-.42*u
        dx = 1.95+.43*(TAU*2*np.cos(phase+.2+breath*.6)*env+math.pi*np.sin(phase+.2+breath*.6)*np.cos(math.pi*u))
        dy = .41*(TAU*2*np.cos(phase+breath)*env+math.pi*np.sin(phase+breath)*np.cos(math.pi*u))-.42
        length = np.maximum(.00001, np.hypot(dx, dy))
        return x, y, dy/length, -dx/length

    def sample(self, t):
        t = float(np.clip(t, 0., DURATION))
        hole = smooth(52, 60, t)*(1-smooth(69, 78, t))
        gate = smooth(69, 78, t)*(1-smooth(96, 106, t))
        dragon = smooth(83, 93, t)*(1-smooth(102, 112, t))
        scale = mix(.69, 1.08, smooth(53, 72, t))
        converge = smooth(103, 122, t)
        pull = smooth(123, 135, t)
        inner_scale, outer_scale = nested_scales(t)
        self.background(t, hole, scale)
        self.light *= (1-.92*converge)
        self.starfield(t, hole, scale, converge, inner_scale)
        if 35 < t < 61:
            self.planet(t, smooth(35, 43, t)*(1-smooth(53, 61, t)))
        if 39 < t < 58:
            self.meteors(t, smooth(39, 43, t)*(1-smooth(54, 58, t)))
        if hole > .001:
            self.black_hole(t, hole, scale)
        if gate > .001:
            self.gate(t, gate)
        if dragon > .001:
            self.dragon(t, dragon)
        if t < 38:
            opening = smooth(1.2, 7.5, t)
            blink = smooth(16.5, 17.1, t)*(1-smooth(17.2, 18.3, t))
            opening *= 1-.987*blink
            zoom = 1+25*smooth(22, 36, t)**3
            eye, pupil = self.eye(t, zoom, opening)
            leave = smooth(31, 38, t)
            through = pupil*smooth(23, 33, t)
            self.light *= mix(through, 1., leave)[..., None]
            self.light += eye*(1-leave)
        if 26 < t < 40:
            self.tunnel(t, smooth(26, 30, t)*(1-smooth(35, 40, t)))
        if t > 117:
            inner_eye, _ = self.eye(t, inner_scale, 1.)
            form = smooth(117, 125, t)
            self.light += inner_eye*form*.64
            self.light *= 1-smooth(136, 141, t)
            opening = 1-smooth(135, 143.4, t)
            outer, aperture = self.eye(t*.45, outer_scale, opening)
            self.light *= aperture[..., None]
            self.light += outer*pull
        fade = smooth(0, 1.5, t)*(1-smooth(142, 144, t))
        # Clear cinematic margins are also generated as spaces, never filled rectangles.
        fade *= (1-smooth(.86, .96, np.abs(self.y)))
        self.light *= np.asarray(fade)[..., None]
        return self.characters(t)

    def characters(self, t):
        tone = 1-np.exp(-np.maximum(0, self.light)*1.5)
        brightness = np.max(tone, axis=2)
        index = np.clip((brightness**.70*(len(GLYPHS)-1) + self.dither*.65).astype(np.int32), 0, len(GLYPHS)-1)
        index[brightness < .018] = 0
        levels = np.clip((brightness**.55*15).astype(np.int32), 0, 15)
        silver = (tone[..., 1] > tone[..., 2]*.65) | (brightness > .72)
        colors = (levels+silver*16).astype(np.uint8)
        heading, caption, heading_alpha, caption_alpha = self.titles(t)
        return CharacterFrame(GLYPHS[index], colors, heading, caption, heading_alpha, caption_alpha)

    @staticmethod
    def titles(t):
        heading, caption, ha, ca = "", "", 0., 0.
        if 8 < t < 16:
            heading = "瞳 界  ·  星 渊"
            caption = "E Y E   →   B E Y O N D   T H E   U N I V E R S E"
            ha = ca = float(smooth(8, 9.5, t)*(1-smooth(14.5, 16, t)))
        for start, end, text in ((39, 47, "一瞬凝眸，万象初生。"), (61, 68, "光也有无法抵达的地方。"),
                                 (78, 85, "古老的门，仍记得星辰之名。"), (96, 103, "它曾以星海为鳞。"),
                                 (113, 120, "群星归位，凝成一眼。"), (129, 136, "你所见的宇宙，正被谁凝望？")):
            if start < t < end:
                caption = text
                ca = float(smooth(start, start+1.4, t)*(1-smooth(end-1.4, end, t)))
        return heading, caption, ha, ca
