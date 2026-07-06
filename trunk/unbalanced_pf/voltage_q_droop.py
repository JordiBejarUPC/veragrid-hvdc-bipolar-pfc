def voltage_q_droop(u,
                    u_setpoint_max,
                    u_setpoint_min,
                    u_setpoint,
                    du_setpoint,
                    Q_setpoint,
                    S_r,
                    droop,
                    Q_min,
                    Q_max
                    ):
    """
    Find the actual reactive power output for generators controlled with a voltage droop.
    :param u: Actual voltage value at the terminal [pu]
    :param u_setpoint_max: Maximum voltage setpoint [pu]
    :param u_setpoint_min: Minimum voltage setpoint [pu]
    :param u_setpoint: Specified voltage setpoint [pu]
    :param du_setpoint: Voltage signal coming from the station controller [pu]
    :param Q_setpoint: Specified dispatch reactive power [MVAr]
    :param S_r: Rated apparent power [MVA]
    :param droop: Voltage droop value [%]
    """

    # Voltage limits
    if u > u_setpoint_max:
        u = u_setpoint_max
    elif u < u_setpoint_min:
        u = u_setpoint_min
    else:
        u = u

    du_droop = u_setpoint + du_setpoint - u  # Voltage deviation [pu]

    Q_droop = S_r * 100 / droop  # Additional reactive power for the specified voltage droop [MVAr]

    Q = Q_setpoint + Q_droop * du_droop # Actual reactive power output [MVAr]

    # Reactive power limits
    if Q > Q_max:
        Q = Q_max
    elif Q < Q_min:
        Q = Q_min
    else:
        Q = Q

    return Q

# 1.01456 -> 1.01
# 1.005954 -> 1.0
# 1.001481 -> 0.99
Q = voltage_q_droop(u=1.005954,
                    u_setpoint_max=1.05,
                    u_setpoint_min=0.95,
                    u_setpoint=1.0,
                    du_setpoint=0.0,
                    Q_setpoint=0.0,
                    S_r=33.33333,
                    droop=3.0,
                    Q_min=-7.41,
                    Q_max=12.0
                    )

print('Q =', round(Q, 2), 'MVAr')