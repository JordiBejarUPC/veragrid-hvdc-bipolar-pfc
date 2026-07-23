# u = 1.01456 # Actual voltage value at the terminal [pu]
# u = 1.005954 # Actual voltage value at the terminal [pu]
# u = 1.001481 # Actual voltage value at the terminal [pu]
u = 0.940645795547452
u_setpoint_max = 1.1 # Maximum voltage setpoint [pu]
u_setpoint_min = 0.9 # Minimum voltage setpoint [pu]
if u > u_setpoint_max:
    u = u_setpoint_max
elif u < u_setpoint_min:
    u = u_setpoint_min
else:
    u = u
u_setpoint = 1.0 # Specified voltage setpoint [pu]
du_setpoint = 0.0 # Voltage signal coming from the station controller
du_droop = u_setpoint + du_setpoint - u # Voltage deviation [pu]

Q_setpoint = 0.0 # Specified dispatch reactive power [MVAr]
S_r = 10 # Rated apparent power [MVA]
ddroop = 5 # Voltage droop value [%]
Q_droop = S_r * 100 / ddroop # Additional reactive power for the specified voltage droop [MVAr]

# Actual reactive power output
Q = Q_setpoint + Q_droop * du_droop
print('Q =', round(Q, 2), 'MVAr')