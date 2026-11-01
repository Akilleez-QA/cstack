import json
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "data"
DEFAULTS = json.loads((_DATA / "defaults.json").read_text(encoding="utf-8"))
CALIBRATION = json.loads((_DATA / "calibration.json").read_text(encoding="utf-8"))

SOURCES = {
    "alexander_1976": "Alexander, R. McN. (1976). Estimates of speeds of dinosaurs. Nature 261, 129-130 "
                      "(relative stride = 2.3 x Froude^0.3, fitted across walking and running animals).",
    "alexander_jayes_1983": "Alexander, R. McN. and Jayes, A. S. (1983). A dynamic similarity hypothesis for the gaits "
                            "of quadrupedal mammals. Journal of Zoology 201, 135-152.",
    "alexander_1989": "Alexander, R. McN. (1989). Optimization and gaits in the locomotion of vertebrates. "
                      "Physiological Reviews 69(4), 1199-1227 (walk-run transition near Froude 0.5; duty factor).",
    "kram_1997": "Kram, R., Domingo, A. and Ferris, D. P. (1997). Effect of reduced gravity on the preferred walk-run "
                 "transition speed. Journal of Experimental Biology 200, 821-826.",
    "winter": "Winter, D. A. (2009). Biomechanics and Motor Control of Human Movement, 4th ed., Wiley, ch. 4 "
              "(segment lengths as fractions of height: greater trochanter 0.530 H).",
    "perry": "Perry, J. and Burnfield, J. M. (2010). Gait Analysis: Normal and Pathological Function, 2nd ed., SLACK "
             "(stance about 60 % and swing about 40 % of the cycle at a free walk).",
    "kovar_2002": "Kovar, L., Schreiner, J. and Gleicher, M. (2002). Footskate cleanup for motion capture editing. "
                  "ACM SIGGRAPH/Eurographics Symposium on Computer Animation, 97-104.",
    "zmp": "Vukobratovic, M. and Borovac, B. (2004). Zero-moment point: thirty five years of its life. International "
           "Journal of Humanoid Robotics 1(1), 157-173; Kajita, S. et al. (2003). Biped walking pattern generation by "
           "using preview control of zero-moment point. IEEE ICRA, 1620-1626 (cart-table model).",
    "capture_point": "Pratt, J., Carff, J., Drakunov, S. and Goswami, A. (2006). Capture point: a step toward humanoid "
                     "push recovery. IEEE-RAS Humanoids, 200-207; Hof, A. L., Gazendam, M. G. J. and Sinke, W. E. "
                     "(2005). The condition for dynamic stability. Journal of Biomechanics 38(1), 1-8.",
    "savitzky_golay": "Savitzky, A. and Golay, M. J. E. (1964). Smoothing and differentiation of data by simplified "
                      "least squares procedures. Analytical Chemistry 36(8), 1627-1639.",
    "newton": "Newton's second law: a body with no support accelerates downward at g (any mechanics text, e.g. "
              "Meriam, J. L. and Kraige, L. G., Engineering Mechanics: Dynamics).",
    "lynch_park": "Lynch, K. M. and Park, F. C. (2017). Modern Robotics: Mechanics, Planning, and Control. Cambridge "
                  "University Press, ch. 4 (product of exponentials) and ch. 5 (Jacobian, singularities, "
                  "manipulability).",
    "yoshikawa": "Yoshikawa, T. (1985). Manipulability of robotic mechanisms. International Journal of Robotics "
                 "Research 4(2), 3-9.",
    "norton": "Norton, R. L. (2012). Design of Machinery, 5th ed., McGraw-Hill: ch. 2 (Grashof condition), ch. 4 "
              "(four-bar and slider-crank position analysis) and ch. 9 (gear trains).",
    "stosic": "Stosic, N., Smith, I. K. and Kovacevic, A. (2005). Screw Compressors: Mathematical Modelling and "
              "Performance Calculation. Springer (male and female rotors turn in inverse ratio of their lobe counts).",
    "shannon": "Shannon, C. E. (1949). Communication in the presence of noise. Proceedings of the IRE 37(1), 10-21 "
               "(a motion sampled at the frame rate is unambiguous only below half a period per sample).",
    "thomas_johnston": "Thomas, F. and Johnston, O. (1981). The Illusion of Life: Disney Animation. Abbeville "
                       "(squash and stretch keeps the volume); Lasseter, J. (1987). Principles of traditional "
                       "animation applied to 3D computer animation. SIGGRAPH Computer Graphics 21(4), 35-44.",
    "haldane": "Haldane, J. B. S. (1926). On being the right size; Galileo's square-cube law (strength grows with "
               "area, weight with volume).",
    "pendulum": "Small-oscillation period of a physical pendulum, T = 2 pi sqrt(I / (m g d)); a uniform rod swung "
                "from one end gives T = 2 pi sqrt(2 L / (3 g)) (any mechanics text).",
    "kinematics": "Kinematic identity: speed = stride length / cycle time. A planted foot that does not meet it must "
                  "slide.",
    "calibration": "foundation_robotics/data/calibration.json: the known-good and known-bad motion this threshold was "
                   "tried on (an internal motion trial, the the giant character timeline).",
}


def default(section, key):
    return DEFAULTS[section][key]["value"]


def defaults(section, keys):
    return {key: default(section, key) for key in keys}


def status(section, key):
    return DEFAULTS[section][key]["status"]
