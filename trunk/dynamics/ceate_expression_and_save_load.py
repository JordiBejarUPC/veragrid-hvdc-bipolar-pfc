import math
from VeraGridEngine.Utils.Symbolic.block import Block, Expr, Var, Const
from VeraGridEngine.Utils.Symbolic.symbolic import sin, cos
from VeraGridEngine.Utils.Symbolic.symbolic_io import BlockSaver, BlockParser

delta = Var("delta")
omega = Var("omega")
psid = Var("psid")
psiq = Var("psiq")
i_d = Var("i_d")
i_q = Var("i_q")
v_d = Var("v_d")
v_q = Var("v_q")
t_e = Var("t_e")
p_g = Var("P_e")
Q_g = Var("Q_e")
Vg = Var("Vg")
dg = Var("dg")
tm = Var("tm")
et = Var("et")

pi = Const(math.pi)
fn = Const(50)
# tm = Const(0.1)
M = Const(1.0)
D = Const(100)
ra = Const(0.3)
xd = Const(0.86138701)
vf = Const(1.081099313)

Kp = Const(1.0)
Ki = Const(10.0)
Kw = Const(10.0)

block = Block(
    state_eqs=[
        # delta - (2 * pi * fn) * (omega - 1),
        # omega - (-tm / M + t_e / M - D / M * (omega - 1))
        (2 * pi * fn) * (omega - 1),  # dδ/dt
        (tm - t_e - D * (omega - 1)) / M,  # dω/dt
        -Kp * et - Ki * et - Kw * (omega - 1)  # det/dt
    ],
    state_vars=[delta, omega, et],
    algebraic_eqs=[
        et - (tm - t_e),
        psid - (-ra * i_q + v_q),
        psiq - (-ra * i_d + v_d),
        i_d - (psid + xd * i_d - vf),
        i_q - (psiq + xd * i_q),
        v_d - (Vg * sin(delta - dg)),
        v_q - (Vg * cos(delta - dg)),
        t_e - (psid * i_q - psiq * i_d),
        (v_d * i_d + v_q * i_q) - p_g,
        (v_q * i_d - v_d * i_q) - Q_g
    ],
    algebraic_vars=[tm, psid, psiq, i_d, i_q, v_d, v_q, t_e, p_g, Q_g],
)


saver = BlockSaver()
d = saver.save_block(block)
const_save = saver.get_const_to_save()
vars_save = saver.get_vars_to_save()
diff_vars_save = saver.get_diff_vars_to_save()

parser = BlockParser()
parser.parse_consts(data=const_save)
parser.parse_vars(data=vars_save)
parser.parse_diff_vars(data=diff_vars_save)
block2 = parser.parse_block(data=d)


print()
