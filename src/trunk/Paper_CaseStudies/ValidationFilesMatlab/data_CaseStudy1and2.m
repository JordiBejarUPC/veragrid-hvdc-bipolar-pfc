%% Parameters for the Simulink validation models of Case Studies 1 and 2
% Models: CaseStudy1_Bipolar.slx and CaseStudy2_Bipolar_WithPFC.slx
% Run this script before simulating either model.

%% Base values
Vb = 525e3;                  % Base (pole-to-ground) DC voltage [V]

%% DC voltage set-point of the slack converters
VDC = 1.1*Vb;                % 1.1 p.u. [V]

%% DC cable resistance (copper, 2500 mm2, 100 km)
rho_20 = 1.7241e-8;          % Resistivity at 20 C [Ohm*m]
A_cable = 2500e-6;           % Cross-section [m2]
L_cable = 100e3;             % Length [m]

Rbi = rho_20*L_cable/A_cable;    % Case 1: resistance of each conductor [Ohm]
R   = 2*Rbi;                     % Case 2: resistance of each conductor [Ohm]

%% PFC internal voltage sources (Case 2), taken from the VeraGrid solution [V]
Vr_pfc_pos = -1.200348e3;
Vs_pfc_pos = -0.280080e3;

Vr_pfc_neg = -1.200348e3;
Vs_pfc_neg = -0.280080e3;
