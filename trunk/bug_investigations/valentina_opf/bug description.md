Describe the bug
I want to run optimal power flow having the constraint of ramp up and ramp down for 
certain generators. However, when running the OPF the changes are higher than the 
ramp selected, additionally I set minimum time up and down for this generators to 
see if with this would work, but it also doesn't work. I am selecting this values through "object".

If I select unit commitment in the options, I cannot select the ramps because 
it won't compile, so for unit commitment, I had to put a very high ramp (the one that comes by default) 
and leave the minimum hours for time up and down. In this the minimum hours work but there is no 
possibility to have the ramp.

My system is also doing load shedding but I would like to disable this feature so I set a very 
high cost for the load, but it is still doing load shedding.

To Reproduce
Steps to reproduce the behavior:

    Click time series
    In database select generator, time series and add the cost of each generator in "cost", for example for gen 4 is 40, for gen 5 is 80 (All the time).
    Go to object and set a minimum time up and down for gen 4 as 24h and gen 5 as 2h.
    In object change the ramp up and ramp down, gen 4: 18 MW/h, gen 5: 200 MW/h
    Run OPF

gen 5 shuts down and restarts for just 1h.

** when unit commitment is ticked, I cannot do step 4. So I run the OPF omitting step 4, 
the minimum hours of operation are fine but is not possible to have the ramp.

    Change the cost of the load: go to database, load, time series. For all the loads I put a cost of 12000.

I want to disable load shedding by adding a high cost to the load. But the system is doing that for certain hours.

Desktop:

    OS: Windows 11, last update 4 June 2025
    Gridcal Version 5.3.14
