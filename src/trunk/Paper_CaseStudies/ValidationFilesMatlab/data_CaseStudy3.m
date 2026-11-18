%% Parameters for the Simulink validation model of Case Study 3
% Model: CaseStudy3_4TerminalBipolarSystem.slx
% Run this script before simulating the model.

%% Base values
Vb = 525e3;                  % Base (pole-to-ground) DC voltage [V]
Sb = 100e6;                  % Base power [W]

%% DC voltage set-point
VDC = 1*Vb;                  % 1.0 p.u. [V]

%% PFC internal voltage sources, taken from the VeraGrid solution (droop control) [V]
Vr_pfc_pos = -0.297726e3;
Vs_pfc_pos = -0.452647e3;

Vr_pfc_neg = 0.216394e3;
Vs_pfc_neg = 0.528031e3;

%% Cable resistances (copper)
rho_20 = 1.7241e-8;                          % Resistivity at 20 C [Ohm*m]
r_ohm_km_land = rho_20*1e3/(3000e-6);        % Land cable, 3000 mm2 [Ohm/km]
r_ohm_km_sea  = rho_20*1e3/(2500e-6);        % Sea cable, 2500 mm2 [Ohm/km]

% Cable lengths [km]
d0a = 10;
d0c = 10;
d1  = 300;
d2  = 300;
d3  = 400;
d4a = 150;
d4b = 150;
d5  = 300;

% Cable resistances [Ohm]
r0a = r_ohm_km_land*d0a;
r0c = r_ohm_km_land*d0c;
r1  = r_ohm_km_sea*d1;
r2  = r_ohm_km_sea*d2;
r3  = r_ohm_km_sea*d3;
r4a = r_ohm_km_sea*d4a;
r4b = r_ohm_km_sea*d4b;
r5  = r_ohm_km_sea*d5;

%% Droop control of the onshore converters (per pole)
Vdc_star = Vb;               % Droop voltage reference [V]
Pdc_star = 15*Sb;            % Droop power reference, 1500 MW [W]
Sr = 3000e6;                 % Converter rating [VA]
DR_percent = 1.0;            % Droop [%]

Kdroop = Sr*100/(DR_percent*Vb);   % Droop gain [W/V] (571428.5714 W/V for DR = 1 %)
