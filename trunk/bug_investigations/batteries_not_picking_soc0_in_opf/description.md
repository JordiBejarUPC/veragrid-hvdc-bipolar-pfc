Hi all,

I'm running a battery in the linear OPF time series and I got a first-step result I can't quite explain, so I'd rather ask than assume I found a bug (I am using VerGrid 6.3.0).

I set the battery's initial state of charge to the minimum (soc_0 = min_soc = 0.3, Enom = 50 MWh, so E_init = 15 MWh, η_d = 0.9). My expectation was that a battery starting empty cannot discharge in the first hour — it should charge first, or stay idle. But this is what I get:

1
2
3
4
5
6
7
8
soc_0 = min_soc = 0.3  ->  E_init = 15.0 MWh

  battery_power[0]  = +5.00 MW   (discharge)
  battery_energy[0] = 15.00 MWh  (stays at the floor)

  t :   0     1     2     3     4     5
  P :  5.0   0.0  -5.0 -10.0  -8.8  -3.8    (P>0 discharge, P<0 charge)
  E : 15.0  15.0  19.5  28.5  36.4  39.9
The battery injects 5 MW in the first hour even though it starts at its minimum SoC. Delivering 5 MW for one hour would need 5/0.9 ≈ 5.56 MWh, which would leave the pack at ~9.4 MWh, below the 15 MWh floor — yet battery_energy[0] stays at 15 MWh. From t=1 onward everything looks consistent: E[t] = E[t-1] + Δ(P[t]) holds exactly, and the battery charges as I'd expect.

The nodal power balance at t=0 is satisfied (the surplus is absorbed by the grid slack), so nothing looks wrong in the power results; it only stood out when I cross-checked battery_power against battery_energy.

So I'm not sure whether there's something I'm not taking into account (some convention about how the initial SoC is applied in the first interval), or whether there's something off with the first simulation step for batteries. Any pointers welcome.

Attached: the .veragrid model, a small script that reproduces the table above, and a plot of power and energy. Thanks!